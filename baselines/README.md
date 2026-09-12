# Baselines

Four scripted policies, one exact belief-space planner, and an LLM agent
harness. They all run here, from integer seeds, and they all regenerate the
numbers the paper reports for them, byte for byte:

```
python -m unknown_goals.verify --quick
```

| file | what it runs | artifact it regenerates |
|---|---|---|
| `scripted_baselines.py` | sweep, random, last-seen, Bayesian filter | `data/artifacts/scripted_baselines_warehouse.json` |
| `belief_planner.py` | the exact finite-horizon belief-space planner | `data/artifacts/belief_planner_sweep_12.json`, `belief_planner_sweep.json` |
| `budget_sweep.py` | the four scripted arms at budgets 2..8 | the scripted arms of `data/artifacts/budget_sweep.json`, `budget_sweep_100.json` |
| `head_to_head.py` | an LLM agent (Ollama, Gemini or an OpenAI-compatible endpoint) | `data/artifacts/head_to_head*.json` (its LLM arm) |

Every policy uses the same generator, the same executor, the same 8-action
budget, the same success rule and the same hidden-truth grading as the
engine. That is the point of them: a difference in the result is a
difference in the decision-making, not in the contract.

## The engine arm is read, not recomputed

`budget_sweep.py` and `head_to_head.py` report an engine column. The engine
is not in this kit, so those rows are **read from the shipped artifact** in
`data/artifacts/` — they are the engine's measured output, committed with
the paper, and this kit does not recompute them. Both scripts say so when
they run, and `--engine-rows` names the artifact they read.

What the kit lets you do with the engine's rows instead of trusting them:

* `python -m unknown_goals.checker data/exports/<artifact>.jsonl.gz`
  re-validates every proof path behind those rows, with no engine code.
* `python -m unknown_goals.replay data/exports/<artifact>.jsonl.gz --episode ...`
  walks any one of those episodes decision by decision against the evidence
  on the ledger at the time.
* The demonstration build on the releases page reproduces the engine's
  behaviour on any seed, live. It does not write these artifact files.

## Regenerating one by hand

```
python -m baselines.scripted_baselines --seeds 12 --levels 2,3,4,5,6
python -m baselines.belief_planner --seeds 12 --out /tmp/bp12.json
python -m baselines.budget_sweep --out /tmp/budget_sweep.json
python -m baselines.head_to_head --provider ollama --model qwen2.5:7b-instruct --seeds 12
```

`scripted_baselines.py` writes into `data/artifacts/` under the current
working directory, so run it from a scratch directory if you do not want to
overwrite the shipped file. The other three take `--out`.

Copyright (c) 2026 Kiran Nayudu. Apache-2.0.
