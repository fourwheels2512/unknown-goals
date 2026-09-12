"""Belief-space planner baseline: the principled competitor the paper names.

The belief filter (scripted_baselines.py) picks the argmax-posterior check.
A belief-space (POMDP) planner instead maximizes the probability of finding
the target within the remaining action budget, looking ahead over what each
check could reveal. On this benchmark that planner can be solved EXACTLY:

  * the world is static during a search (every ground event precedes it);
  * a check is a Bernoulli sensor with a known hit rate (inspect 0.97,
    scan 0.98, the executor's own config) over the holders it can reveal
    (a location plus any person last seen standing there; a cart only
    itself), and a hit ends the episode;
  * so a miss is the only continuing observation, its Bayes update
    multiplies the revealed holders by (1 - hit rate) and renormalizes, and
    those updates COMMUTE - the belief after a set of misses does not depend
    on their order.

Hence the finite-horizon value over the belief MDP is
    V(S, k) = max_{a not in S} [ P(hit | a, b_S) + (1 - P(hit | a, b_S)) V(S + a, k - 1) ],
    V(., 0) = 0,
over subsets S of the 8-action menu (256 states), which is exact dynamic
programming, not a Monte-Carlo approximation: this is the optimal policy for
the POMDP defined by the filter's reading of the briefing evidence and the
true sensor model. The planner starts from the same FilterBelief the filter
baseline uses (identical evidence interpretation: no ledger, no epistemic
statuses, no contradiction bookkeeping, no multi-anchor hypotheses, no
transport handoff), so the only thing it adds over the filter is lookahead.
If it closes the gap to the engine, the engine's edge was planning; if it
does not, the edge is evidence interpretation.

  uv run python experiments/belief_planner.py                 # budgets 2..8, 100 seeds/level
  uv run python experiments/belief_planner.py --seeds 12      # the baselines-table seeds

Same episode contract as every other baseline: same generator, executor,
budget, success rule (a >= 0.9 LOCATED_AT claim about the target), hidden-
truth grading. Engine untouched. Copyright (c) 2026 Kiran Nayudu."""
from __future__ import annotations

import argparse
import json
import math
from functools import lru_cache
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent

from unknown_goals.core.config import DEFAULT_CONFIG, EngineConfig  # noqa: E402
from unknown_goals.core.enums import ActionResult, ActionType, Predicate  # noqa: E402
from unknown_goals.execution.executor import Executor  # noqa: E402
from unknown_goals.models.records import ActionSpec, Claim  # noqa: E402
from unknown_goals.simulation.generator import generate  # noqa: E402
from unknown_goals.simulation.world import World, WorldSpec  # noqa: E402
from unknown_goals.storage.ledger import Ledger  # noqa: E402

from baselines.scripted_baselines import (  # noqa: E402
    FilterBelief,
    action_menu,
)


def hit_rate(action: ActionSpec, config: EngineConfig) -> float:
    if action.action_type == ActionType.INSPECT_LOCATION:
        return config.planner.inspect_tp_rate
    return config.planner.scan_tp_rate


class ExactBeliefPlanner:
    """Finite-horizon exact DP over subsets of the action menu."""

    def __init__(self, fb: FilterBelief, menu: list[ActionSpec],
                 config: EngineConfig) -> None:
        self.fb = fb
        self.menu = menu
        self.config = config
        self.holders = list(fb.belief.keys())
        self.idx = {h: i for i, h in enumerate(self.holders)}
        # per action: the holder indexes it reveals and its hit rate
        self.reveal = [[self.idx[h] for h in fb.find_set(a) if h in self.idx]
                       for a in menu]
        self.rate = [hit_rate(a, config) for a in menu]

    def _belief_after(self, taken: int) -> list[float]:
        b = [self.fb.belief[h] for h in self.holders]
        for j, mask in enumerate(1 << i for i in range(len(self.menu))):
            if taken & mask:
                for h in self.reveal[j]:
                    b[h] *= (1.0 - self.rate[j])
        z = sum(b) or 1.0
        return [x / z for x in b]

    def plan(self, horizon: int) -> ActionSpec | None:
        """Exact DP: V(taken, k) = max_a [p_a + (1 - p_a) V(taken + a, k - 1)].
        Ties broken by fewer expected steps, then menu order (deterministic)."""
        n = len(self.menu)

        @lru_cache(maxsize=None)
        def value(taken: int, k: int) -> tuple[float, float]:
            if k == 0:
                return 0.0, 0.0
            b = self._belief_after(taken)
            best_key, best = None, (0.0, 0.0)
            for j in range(n):
                if taken & (1 << j):
                    continue
                p = self.rate[j] * sum(b[h] for h in self.reveal[j])
                v_next, s_next = value(taken | (1 << j), k - 1)
                v = p + (1.0 - p) * v_next
                steps = 1.0 + (1.0 - p) * s_next
                key = (round(v, 12), -round(steps, 12), -j)
                if best_key is None or key > best_key:
                    best_key, best = key, (v, steps)
            return best

        if horizon <= 0 or n == 0:
            return None
        b = self._belief_after(0)
        best_key, best_action = None, None
        for j in range(n):
            p = self.rate[j] * sum(b[h] for h in self.reveal[j])
            v_next, s_next = value(1 << j, horizon - 1)
            v = p + (1.0 - p) * v_next
            steps = 1.0 + (1.0 - p) * s_next
            key = (round(v, 12), -round(steps, 12), -j)
            if best_key is None or key > best_key:
                best_key, best_action = key, self.menu[j]
        return best_action


def run_planner_episode(spec: WorldSpec, evidence: list[Claim], seed: int,
                        config: EngineConfig = DEFAULT_CONFIG) -> dict:
    ledger = Ledger()
    for entity in spec.entities:
        ledger.add_entity(entity)
    world = World(spec)
    start = max((e.t for e in spec.events), default=0) + 1
    world.advance_to(start)
    now = max([start] + [c.ingested_at for c in evidence])
    for claim in evidence:
        ledger.append_claim(claim)
    executor = Executor(world, ledger, config)
    truth = world.true_location(spec.target)

    fb = FilterBelief(spec)
    fb.absorb_briefing(evidence)
    menu = action_menu(spec)
    success, found_at, steps = False, None, 0
    budget = config.budget.max_actions
    while steps < budget and menu:
        planner = ExactBeliefPlanner(fb, menu, config)
        action = planner.plan(budget - steps)
        if action is None:
            break
        menu.remove(action)
        report = executor.execute(action, spec.target, now)
        now += report.time_spent
        steps += 1
        if report.result == ActionResult.INVALID:
            continue
        for c in report.new_claims:
            if (c.subject == spec.target
                    and c.predicate == Predicate.LOCATED_AT
                    and c.confidence >= 0.9):
                success, found_at = True, c.obj
            elif c.predicate in (Predicate.ENTERED, Predicate.MOVED_TO):
                fb.absorb(c)
        if success:
            break
        # a miss: the true sensor model's Bayes update on the revealed holders
        r = hit_rate(action, config)
        for h in fb.find_set(action):
            if h in fb.belief:
                fb.belief[h] *= (1.0 - r)
        fb.normalize()
    return {"seed": seed, "truth": spec.truth_note, "ground_truth": truth,
            "success": success, "found_at": found_at,
            "correct": bool(success and found_at == truth), "steps": steps}


def wilson(k: int, n: int, z: float = 1.96) -> tuple[float, float]:
    p = k / n
    c = (p + z * z / (2 * n)) / (1 + z * z / n)
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / (1 + z * z / n)
    return round(c - h, 4), round(c + h, 4)


def summarise(rows: list[dict]) -> dict:
    n = len(rows)
    k = sum(r["correct"] for r in rows)
    return {"n": n, "success": round(sum(r["success"] for r in rows) / n, 4),
            "correct": round(k / n, 4), "correct_wilson95": wilson(k, n),
            "wrong": sum(1 for r in rows if r["success"] and not r["correct"]),
            "mean_steps": round(sum(r["steps"] for r in rows) / n, 3)}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--budgets", default="2,3,4,5,6,8")
    ap.add_argument("--seeds", type=int, default=100)
    ap.add_argument("--seed-base", type=int, default=20_000)
    ap.add_argument("--levels", default="2,3,4,5,6")
    ap.add_argument("--out", default=None)
    args = ap.parse_args()
    budgets = [int(b) for b in args.budgets.split(",")]
    levels = [int(x) for x in args.levels.split(",")]
    seeds = [args.seed_base + i for i in range(args.seeds)]
    out_path = Path(args.out) if args.out else (
        REPO / "data" / "artifacts" /
        ("belief_planner_sweep.json" if args.seeds != 12 else "belief_planner_sweep_12.json"))
    out = {"policy": "exact belief-space planner (finite-horizon DP over the "
                     "filter's belief with the true sensor model)",
           "config_version": DEFAULT_CONFIG.config_version,
           "seeds": seeds, "levels": levels, "budgets": budgets, "results": {}}
    for b in budgets:
        cfg = DEFAULT_CONFIG.model_copy(deep=True)
        cfg.budget.max_actions = b
        rows = []
        for level in levels:
            for seed in seeds:
                spec, evidence = generate(seed, level)
                r = run_planner_episode(spec, evidence, seed, config=cfg)
                r["level"] = level
                rows.append(r)
        summ = summarise(rows)
        summ["per_level"] = {str(lv): summarise([r for r in rows if r["level"] == lv])
                             for lv in levels}
        summ["episodes"] = rows
        out["results"][str(b)] = summ
        print(f"budget {b} planner success {summ['success']:.3f} correct "
              f"{summ['correct']:.3f} {summ['correct_wilson95']} wrong "
              f"{summ['wrong']} steps {summ['mean_steps']:.2f}  per-level "
              f"{ {lv: v['correct'] for lv, v in summ['per_level'].items()} }",
              flush=True)
    out_path.write_text(json.dumps(out, indent=1))
    print(f"-> {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
