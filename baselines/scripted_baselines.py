"""Scripted baselines on the warehouse benchmark, under the exact LLM
episode contract (same generator, same executor, same 8-action budget,
same success rule, same hidden-truth grading).

The ALFWorld ablation (PAPER 5.9b) showed scripted baselines are the
only honest way to know what a benchmark measures. This applies the
same discipline to our own flagship benchmark:

  sweep   evidence-ignoring: inspect every location in sorted order,
          then scan every cart in sorted order
  random  the same action set in a seeded random order (per-episode)
  lastseen inspect the target's most recent sighting location first,
          then fall back to the sweep order (minimal evidence use)
  filter  the mid-tier baseline a reviewer asks for: a plain Bayesian
          filter over holders (locations, carts, persons) with
          argmax-posterior action selection -- the belief updating any
          POMDP-lite tracker provides, with NONE of the engine's
          machinery: no ledger, no epistemic statuses, no
          supersede/contradiction bookkeeping, no proof paths, no
          multi-anchor hypotheses, no transport handoff, no rule
          induction. If the engine beats this, the machinery earned it.

  uv run python experiments/scripted_baselines.py --seeds 12 --levels 2,3,4,5,6
"""

from __future__ import annotations

import argparse
import json
import random
import sys
from pathlib import Path

from unknown_goals.core.config import DEFAULT_CONFIG, EngineConfig  # noqa: E402
from unknown_goals.core.enums import (  # noqa: E402
    ActionResult,
    ActionType,
    EntityType,
    Predicate,
)
from unknown_goals.execution.executor import Executor  # noqa: E402
from unknown_goals.models.records import ActionSpec, Claim  # noqa: E402
from unknown_goals.simulation.generator import generate  # noqa: E402
from unknown_goals.simulation.world import World, WorldSpec  # noqa: E402
from unknown_goals.storage.ledger import Ledger  # noqa: E402


def action_menu(spec: WorldSpec) -> list[ActionSpec]:
    locations = sorted(e.entity_id for e in spec.entities
                       if e.entity_type == EntityType.LOCATION)
    containers = sorted(e.entity_id for e in spec.entities
                        if e.entity_type == EntityType.CONTAINER)
    return ([ActionSpec(action_type=ActionType.INSPECT_LOCATION, target=t)
             for t in locations]
            + [ActionSpec(action_type=ActionType.SCAN_CONTAINER, target=t)
               for t in containers])


def order_for(policy: str, spec: WorldSpec, evidence: list[Claim],
              seed: int) -> list[ActionSpec]:
    menu = action_menu(spec)
    if policy == "sweep":
        return menu
    if policy == "random":
        rng = random.Random(f"baseline_{seed}")
        menu = list(menu)
        rng.shuffle(menu)
        return menu
    if policy == "lastseen":
        sightings = [c for c in evidence
                     if c.subject == spec.target
                     and c.predicate == Predicate.LOCATED_AT]
        first: list[ActionSpec] = []
        if sightings:
            latest = max(sightings, key=lambda c: (c.event_time_end,
                                                   c.ingested_at))
            first = [a for a in menu if a.target == latest.obj]
        rest = [a for a in menu if a not in first]
        return first + rest
    raise ValueError(policy)


class FilterBelief:
    """The plain Bayesian belief the `filter` baseline maintains: a
    distribution over holders (locations, carts, persons) plus the latest
    known position of every person and cart. Shared with the belief-space
    planner (experiments/belief_planner.py) so both start from the same
    reading of the briefing evidence; the only thing the planner adds is
    lookahead. Kept as a class so run_filter_episode's behaviour is
    byte-identical to the closure version it replaced."""

    def __init__(self, spec: WorldSpec) -> None:
        self.target = spec.target
        self.locations = sorted(e.entity_id for e in spec.entities
                                if e.entity_type == EntityType.LOCATION)
        self.carts = sorted(e.entity_id for e in spec.entities
                            if e.entity_type == EntityType.CONTAINER)
        self.persons = sorted(e.entity_id for e in spec.entities
                              if e.entity_type == EntityType.PERSON)
        holders = self.locations + self.carts + self.persons
        self.belief: dict[str, float] = dict.fromkeys(
            holders, 1.0 / max(len(holders), 1))
        self.person_at: dict[str, str] = {}
        self.cart_at: dict[str, str] = {}

    def normalize(self) -> None:
        z = sum(self.belief.values()) or 1.0
        for s in self.belief:
            self.belief[s] /= z

    def toward(self, state: str, c: float) -> None:
        others = max(len(self.belief) - 1, 1)
        for s in self.belief:
            self.belief[s] *= c if s == state else (1 - c) / others
        self.normalize()

    def against(self, state: str, c: float) -> None:
        self.belief[state] *= (1 - c)
        self.normalize()

    def absorb(self, claim: Claim) -> None:
        belief = self.belief
        if claim.subject == self.target:
            if claim.predicate == Predicate.LOCATED_AT \
                    and claim.obj in belief:
                self.toward(claim.obj, claim.confidence)
            elif claim.predicate in (Predicate.NEAR, Predicate.CARRIED_BY,
                                     Predicate.LAST_SEEN_WITH,
                                     Predicate.INSIDE) \
                    and claim.obj in belief:
                self.toward(claim.obj, claim.confidence)
            elif claim.predicate == Predicate.ABSENT_FROM \
                    and claim.obj in belief:
                self.against(claim.obj, claim.confidence)
        elif claim.predicate == Predicate.ENTERED \
                and claim.subject in self.persons:
            self.person_at[claim.subject] = claim.obj
        elif claim.predicate == Predicate.MOVED_TO \
                and claim.subject in self.carts:
            self.cart_at[claim.subject] = claim.obj

    def absorb_briefing(self, evidence: list[Claim]) -> None:
        for claim in sorted(evidence, key=lambda c: (c.event_time_end,
                                                     c.ingested_at)):
            self.absorb(claim)

    def find_set(self, action: ActionSpec) -> list[str]:
        """Holders an action would reveal: a location plus every person
        last seen standing there; a cart only itself."""
        if action.action_type == ActionType.INSPECT_LOCATION:
            return [action.target] + [p for p in self.persons
                                      if self.person_at.get(p) == action.target]
        return [action.target]

    def score(self, action: ActionSpec) -> float:
        return sum(self.belief.get(h, 0.0) for h in self.find_set(action))


def run_filter_episode(spec: WorldSpec, evidence: list[Claim],
                       seed: int,
                       config: EngineConfig = DEFAULT_CONFIG) -> dict:
    """Sequential belief filter under the identical episode contract.

    Update rule (textbook independent noisy observations): a claim
    placing the target with holder H multiplies belief[H] by its
    confidence c and every other holder by (1-c)/(n-1); an absence
    claim multiplies belief[H] by (1-c); person ENTERED / cart MOVED_TO
    claims maintain a latest-position map so person-held mass scores
    the person's last known location. Actions: argmax posterior over
    the same non-repeating menu, ties in menu order; a miss Bayes-downs
    the checked holder (sensor hit rate 0.9) and any person mass
    standing there (0.5, hands not fully visible), then renormalizes.
    """
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
    for _ in range(config.budget.max_actions):
        if not menu:
            break
        action = max(menu, key=lambda a: (fb.score(a), -menu.index(a)))
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
            else:
                fb.absorb(c)
        if success:
            break
        if action.action_type == ActionType.INSPECT_LOCATION:
            fb.against(action.target, 0.9)
            for p in fb.persons:
                if fb.person_at.get(p) == action.target:
                    fb.against(p, 0.5)
        else:
            fb.against(action.target, 0.9)
    return {"seed": seed, "truth": spec.truth_note,
            "ground_truth": truth, "success": success,
            "found_at": found_at,
            "correct": bool(success and found_at == truth),
            "steps": steps}


def run_scripted_episode(spec: WorldSpec, evidence: list[Claim],
                         policy: str, seed: int,
                         config: EngineConfig = DEFAULT_CONFIG) -> dict:
    """Mirrors run_llm_episode's environment setup, action execution,
    success rule, and budget exactly — only the decision-maker differs."""
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

    success, found_at, steps = False, None, 0
    for action in order_for(policy, spec, evidence, seed)[
            :config.budget.max_actions]:
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
        if success:
            break
    return {"seed": seed, "truth": spec.truth_note,
            "ground_truth": truth, "success": success,
            "found_at": found_at,
            "correct": bool(success and found_at == truth),
            "steps": steps}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--seeds", type=int, default=12, help="seeds per level")
    ap.add_argument("--seed-base", type=int, default=20_000)
    ap.add_argument("--levels", default="2,3,4,5,6")
    ap.add_argument("--policies", default="sweep,random,lastseen,filter")
    args = ap.parse_args()
    levels = [int(x) for x in args.levels.split(",")]
    seeds = [args.seed_base + i for i in range(args.seeds)]
    policies = args.policies.split(",")

    out: dict[str, list] = {p: [] for p in policies}
    for policy in policies:
        for level in levels:
            for seed in seeds:
                spec, evidence = generate(seed, level)
                if policy == "filter":
                    row = run_filter_episode(spec, evidence, seed)
                else:
                    row = run_scripted_episode(spec, evidence, policy, seed)
                row["level"] = level
                out[policy].append(row)

    print(f"{'policy':<10}{'overall':>12}{'steps*':>8}", end="")
    for lv in levels:
        print(f"{'L' + str(lv):>8}", end="")
    print("   (*avg steps on correct episodes)")
    for policy in policies:
        rows = out[policy]
        n = len(rows)
        wins = sum(r["correct"] for r in rows)
        win_steps = [r["steps"] for r in rows if r["correct"]]
        avg = sum(win_steps) / len(win_steps) if win_steps else float("nan")
        print(f"{policy:<10}{f'{wins}/{n}':>12}{avg:>8.2f}", end="")
        for lv in levels:
            lr = [r for r in rows if r["level"] == lv]
            print(f"{f'{sum(r['correct'] for r in lr)}/{len(lr)}':>8}",
                  end="")
        print()

    path = Path("data/artifacts/scripted_baselines_warehouse.json")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(out, indent=2))
    print(f"\nper-episode results -> {path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
