"""Action-budget sweep on the warehouse benchmark: where does brute force stop
working, and does the engine keep working there?

The shipped 8-action budget covers the world's 6 locations + 2 carts, so any
exhaustive policy reaches 100% success (scripted_baselines.py). Three outside
reviews of the paper asked the obvious follow-up: shrink the budget below the
number of places to look and see who survives. This runs the four scripted
policies (sweep / random / last-seen / Bayesian filter) under the identical
episode contract at budgets 2..8, on the same 12 seeds x levels 2-6 the
baselines artifact uses. The budget is the config field the benchmark
already reads (BudgetConfig.max_actions).

The engine's own rows are READ from the artifact committed with the paper,
not recomputed: the engine is not part of this kit. The ledger export behind
every engine row is in data/exports/, and the kit's checker re-validates its
proof paths with no engine code (python -m unknown_goals.checker).

  python -m baselines.budget_sweep                  # budgets 2,3,4,5,6,8
  python -m baselines.budget_sweep --budgets 3,4

Correct = success AND found_at == ground truth (hidden-truth grading).
Copyright (c) 2026 Kiran Nayudu."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent

from unknown_goals.core.config import DEFAULT_CONFIG  # noqa: E402
from unknown_goals.simulation.generator import generate  # noqa: E402

from baselines.scripted_baselines import (  # noqa: E402
    run_filter_episode,
    run_scripted_episode,
)

POLICIES = ["engine", "filter", "random", "lastseen", "sweep"]


def load_engine_rows(path: Path) -> dict:
    """The engine's measured rows, read from the artifact committed with
    the paper. Nothing in this kit recomputes them; what it offers instead
    is the ledger export behind every row (data/exports/) and a checker
    that re-validates their proof paths with no engine code."""
    if not path.exists():
        raise SystemExit(
            f"engine rows not found: {path}\n"
            "Pass --engine-rows to name the shipped artifact whose engine "
            "arm this run should report.")
    return json.loads(path.read_text(encoding="utf-8"))


def engine_episode(shipped: dict, budget: int, seed: int,
                   level: int) -> dict:
    rows = shipped["results"][str(budget)]["engine"]["episodes"]
    for r in rows:
        if r["seed"] == seed and r["level"] == level:
            return {"seed": seed, "level": level,
                    "success": bool(r["success"]),
                    "correct": bool(r["correct"]),
                    "steps": int(r["steps"])}
    raise SystemExit(f"the shipped artifact has no engine row for budget "
                     f"{budget}, seed {seed}, level {level}")


def scripted_episode(policy: str, seed: int, level: int, config) -> dict:
    spec, evidence = generate(seed, level)
    if policy == "filter":
        r = run_filter_episode(spec, evidence, seed, config=config)
    else:
        r = run_scripted_episode(spec, evidence, policy, seed, config=config)
    return {"seed": seed, "level": level, "success": bool(r["success"]),
            "correct": bool(r["correct"]), "steps": int(r["steps"])}


def summarise(rows: list[dict]) -> dict:
    n = len(rows)
    return {"n": n,
            "success": round(sum(r["success"] for r in rows) / n, 4),
            "correct": round(sum(r["correct"] for r in rows) / n, 4),
            "wrong": sum(1 for r in rows if r["success"] and not r["correct"]),
            "mean_steps": round(sum(r["steps"] for r in rows) / n, 3)}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--budgets", default="2,3,4,5,6,8")
    ap.add_argument("--seeds", type=int, default=12)
    ap.add_argument("--seed-base", type=int, default=20_000)
    ap.add_argument("--levels", default="2,3,4,5,6")
    ap.add_argument("--out", default=str(REPO / "data" / "artifacts"
                                         / "budget_sweep.json"))
    ap.add_argument("--engine-rows", default=None,
                    help="the shipped artifact whose engine arm is "
                         "reported (default: data/artifacts/<name of --out>)")
    args = ap.parse_args()
    budgets = [int(b) for b in args.budgets.split(",")]
    levels = [int(x) for x in args.levels.split(",")]
    seeds = [args.seed_base + i for i in range(args.seeds)]
    engine_rows_path = (Path(args.engine_rows) if args.engine_rows
                        else REPO / "data" / "artifacts"
                        / Path(args.out).name)
    shipped = load_engine_rows(engine_rows_path)
    print(f"engine arm read from {engine_rows_path} (not recomputed)")

    out = {"config_version": DEFAULT_CONFIG.config_version,
           "seeds": seeds, "levels": levels, "budgets": budgets,
           "engine_learned_rules": shipped["engine_learned_rules"],
           "shipped_budget": DEFAULT_CONFIG.budget.max_actions,
           "results": {}}
    for b in budgets:
        cfg = DEFAULT_CONFIG.model_copy(deep=True)
        cfg.budget.max_actions = b
        out["results"][str(b)] = {}
        for policy in POLICIES:
            rows = []
            for level in levels:
                for seed in seeds:
                    if policy == "engine":
                        rows.append(engine_episode(shipped, b, seed, level))
                    else:
                        rows.append(scripted_episode(policy, seed, level, cfg))
            summ = summarise(rows)
            summ["per_level"] = {
                str(lv): summarise([r for r in rows if r["level"] == lv])
                for lv in levels}
            summ["episodes"] = rows
            out["results"][str(b)][policy] = summ
            print(f"budget {b} {policy:9s} success {summ['success']:.3f} "
                  f"correct {summ['correct']:.3f} wrong {summ['wrong']} "
                  f"steps {summ['mean_steps']:.2f}", flush=True)
    Path(args.out).write_text(json.dumps(out, indent=1))

    print("\n| budget | " + " | ".join(POLICIES) + " |")
    print("|---|" + "---|" * len(POLICIES))
    for b in budgets:
        cells = []
        for p in POLICIES:
            s = out["results"][str(b)][p]
            cells.append(f"{s['correct']*100:.0f}% ({s['mean_steps']:.2f})")
        print(f"| {b} | " + " | ".join(cells) + " |")
    print(f"\n-> {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
