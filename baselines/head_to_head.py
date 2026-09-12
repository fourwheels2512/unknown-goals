"""Head-to-head: the engine against an LLM agent on identical generated
scenarios, graded against identical hidden ground truth.

The LLM arm runs here. The engine arm is READ from the artifact committed
with the paper (--engine-rows): the engine is not part of this kit. The
ledger export behind every engine row is in data/exports/ and the kit's
checker re-validates its proof paths. --no-engine runs the LLM alone.

  python -m baselines.head_to_head --seeds 12 --levels 2,3,4,5 \
      --engine-rows data/artifacts/head_to_head_strong.json
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

from unknown_goals.core.enums import RuleStatus  # noqa: E402
from unknown_goals.llm.agent_runner import run_llm_episode  # noqa: E402
from unknown_goals.llm.ollama_client import OllamaClient  # noqa: E402
from unknown_goals.models.records import Rule  # noqa: E402
from unknown_goals.simulation.generator import generate  # noqa: E402


def load_learned_rules() -> list[Rule]:
    path = Path("data/artifacts/learned_rules.json")
    if not path.exists():
        return []
    rules = [Rule.model_validate(r) for r in json.loads(path.read_text())]
    return [r for r in rules if r.status == RuleStatus.VALIDATED]


def load_engine_rows(path: Path | None) -> list[dict]:
    """The engine's measured rows for these scenarios, read from the
    artifact committed with the paper. The engine is not in this kit; the
    ledger export behind each row is in data/exports/ and
    `python -m unknown_goals.checker` re-validates its proof paths."""
    if path is None or not path.exists():
        raise SystemExit(
            "the engine arm is read from a shipped artifact. Pass "
            "--engine-rows data/artifacts/head_to_head_<model>_<scaffold>"
            "_l<levels>.json, or --no-engine to run the LLM arm alone.")
    return json.loads(path.read_text(encoding="utf-8"))


def engine_row(rows: list[dict], level: int, seed: int) -> dict:
    for r in rows:
        if r["level"] == level and r["seed"] == seed:
            return r
    raise SystemExit(f"the shipped artifact has no engine row for level "
                     f"{level}, seed {seed}")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--seeds", type=int, default=12, help="seeds per level")
    ap.add_argument("--seed-base", type=int, default=20_000)
    ap.add_argument("--levels", default="2,3,4,5")
    ap.add_argument("--model", default="qwen2.5:7b-instruct")
    ap.add_argument("--provider", default="ollama", choices=["ollama", "gemini", "deepseek"])
    ap.add_argument("--scaffold", default="basic", choices=["basic", "strong"])
    ap.add_argument("--engine-rows", default=None,
                    help="shipped artifact whose engine arm is reported")
    ap.add_argument("--no-engine", action="store_true",
                    help="run the LLM arm alone, with no engine column")
    args = ap.parse_args()
    levels = [int(x) for x in args.levels.split(",")]
    seeds = [args.seed_base + i for i in range(args.seeds)]
    if args.provider == "gemini":
        from unknown_goals.llm.gemini_client import GeminiClient
        client = GeminiClient(model=args.model)
    elif args.provider == "deepseek":
        from unknown_goals.llm.openai_compat_client import OpenAICompatClient
        client = OpenAICompatClient(model=args.model)
    else:
        client = OllamaClient(model=args.model)
    learned = load_learned_rules() or None
    engine_rows = ([] if args.no_engine else
                   load_engine_rows(Path(args.engine_rows)
                                    if args.engine_rows else None))

    rows = []
    t0 = time.time()
    for level in levels:
        for seed in seeds:
            spec, evidence = generate(seed, level)
            eng = ({"engine_correct": False, "engine_steps": 0}
                   if args.no_engine
                   else engine_row(engine_rows, level, seed))
            spec2, evidence2 = generate(seed, level)
            t1 = time.time()
            llm = run_llm_episode(spec2, evidence2, client, scaffold=args.scaffold)
            llm_secs = time.time() - t1
            rows.append({
                "level": level, "seed": seed,
                "truth": spec.truth_note,
                "engine_correct": bool(eng["engine_correct"]),
                "engine_steps": eng["engine_steps"],
                "llm_correct": llm.correct,
                "llm_success_any": llm.success,
                "llm_steps": llm.steps_used,
                "llm_invalid": llm.invalid_actions,
                "llm_parse_failures": llm.parse_failures,
                "llm_secs": round(llm_secs, 1),
                "llm_actions": llm.actions,
            })
            r = rows[-1]
            print(f"L{level} seed={seed} [{r['truth']:<12}] "
                  f"engine: {'WIN ' if r['engine_correct'] else 'fail'} {r['engine_steps']} steps | "
                  f"llm: {'WIN ' if r['llm_correct'] else 'fail'} {r['llm_steps']} steps "
                  f"({r['llm_invalid']} invalid, {r['llm_secs']}s)", flush=True)

    n = len(rows)
    eng_wins = sum(r["engine_correct"] for r in rows)
    llm_wins = sum(r["llm_correct"] for r in rows)
    eng_steps = [r["engine_steps"] for r in rows if r["engine_correct"]]
    llm_steps = [r["llm_steps"] for r in rows if r["llm_correct"]]
    print("\n" + "=" * 60)
    print(f"episodes: {n}   total time: {time.time() - t0:.0f}s   model: {args.model}")
    print(f"{'':>24}{'engine':>10}{'llm':>10}")
    print(f"{'found (correct)':>24}{eng_wins:>7}/{n}{llm_wins:>7}/{n}")
    print(f"{'success rate':>24}{eng_wins / n:>10.2f}{llm_wins / n:>10.2f}")
    if eng_steps:
        print(f"{'avg steps when correct':>24}{sum(eng_steps) / len(eng_steps):>10.2f}", end="")
        print(f"{sum(llm_steps) / len(llm_steps):>10.2f}" if llm_steps else f"{'n/a':>10}")
    print(f"{'invalid actions':>24}{0:>10}{sum(r['llm_invalid'] for r in rows):>10}")
    per_level: dict[int, list] = {}
    for r in rows:
        per_level.setdefault(r["level"], []).append(r)
    for lvl, rs in sorted(per_level.items()):
        print(f"  L{lvl}: engine {sum(x['engine_correct'] for x in rs)}/{len(rs)}"
              f"  llm {sum(x['llm_correct'] for x in rs)}/{len(rs)}")

    safe_model = args.model.replace(":", "_").replace("/", "_")
    lv = args.levels.replace(",", "")
    out = Path(f"data/artifacts/head_to_head_{safe_model}_{args.scaffold}_l{lv}.json")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(rows, indent=2))
    print(f"\nper-episode results -> {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
