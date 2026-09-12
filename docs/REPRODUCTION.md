# Reproduction notes and the artifact bundle

These notes accompany the paper *A Decision Layer for Robot Object Search
Under Unreliable Evidence, With a Checkable Provenance Record for Every
Commitment*, and they ship with the benchmark kit. They carry the
per-suite reproduction commands and the artifact inventory that the
paper's reproducibility statement summarises.

## Engine-side commands

These run in the author's environment, against the engine's own
repository. The kit's own verify command is documented in the kit's
README.

```
uv sync
uv run pytest                                   # all acceptance gates (432 tests)
uv run robot-mind demo --explain                # traced episode + plain-English story
uv run robot-mind demo --seed 11 --level 6 --explain    # survive a gaslighting
uv run robot-mind chat "anyone seen my wrench?" # hybrid: LLM proposes, engine verifies
uv run robot-mind benchmark                     # trains + compares on held-out seeds
uv run robot-mind coffee                        # rung-3 brew, dishwasher rescue included
uv run robot-mind whatif --seed 11 --level 6    # evidence-influence counterfactuals
uv run python experiments/battery.py --tag mine # the 5-test scorecard
uv run python experiments/absent_target.py --json data/artifacts/absent_target.json   # the absent-target battery
uv run python experiments/woz_test.py           # unfamiliar houses, empty ledger
uv run python experiments/woz_dynamic.py --night-minutes 480    # the changing world
uv run python experiments/calibration.py        # ECE / Brier / reliability table
uv run python experiments/make_race.py --seed 20002 --level 5   # side-by-side replay
uv run python experiments/head_to_head.py --scaffold strong     # requires Ollama
uv run python experiments/scripted_baselines.py                 # sweep/random/last-seen baselines
uv run python experiments/learn_live.py         # + streamlit run experiments/dashboard.py
uv run python scripts/reproduce.py              # every native suite in one command, diffed vs artifacts

# embodied (WSL/Linux; see docs/EMBODIED.md for environment stand-up)
python experiments/embodied/thor_find.py --scenes FloorPlan2,...,FloorPlan402 --seed 7
python experiments/embodied/subt_find.py --worlds tunnel_circuit_practice_01 --seeds 7,11,23
python experiments/embodied/hospital_find.py --seeds 7,11,23,42,99,137,256,314
python experiments/embodied/hospital_tips.py --seeds 7,11,23,42,99,137,256,314
python experiments/embodied/hospital_tips.py --seeds 3,5,6,8 --out data/artifacts/embodied/hospital_tips_ext.json
python experiments/embodied/hospital_tips_twin.py --seeds 23,42,3,5,6,8
python experiments/embodied/gazebo_find.py
# real pixels (WSL Ubuntu, the detector env; every sitting's result in docs/PHONE_PROTOCOL.md)
python experiments/embodied/phone_find.py --clips-dir data/phone_s4 --manifest data/artifacts/embodied/phone_manifest_s4.json --arms engine,sweep,random --sense-model v3 --imgsz 1088
python experiments/embodied/phone_tips.py --clips-dir data/phone_s4 --manifest data/artifacts/embodied/phone_manifest_s4.json --arms engine,sweep,tipfollow --sense-model v3 --imgsz 1088
```

## Reproduction commands and artifact inventory

These are the per-suite reproduction commands, the regenerate-to-verify
figures and the artifact bundle contents that the paper's reproducibility statement
summarises.

- Figures regenerate from the shipped artifacts via
  `scripts/make_paper_figs.py`.
- The discriminating table (the budget table) reproduces with
  one command, `uv run python experiments/budget_sweep.py`, in
  under a minute on a laptop. The scripted baselines reproduce with
  `experiments/scripted_baselines.py`. The warehouse benchmark,
  calibration and stress suites reproduce with the engine-side commands
  listed above.
- The absent-target battery of the paper's absent-target section reproduces with
  `uv run python experiments/absent_target.py`, which
  regenerates `data/artifacts/absent_target.json`.
- The real-pixels battery ships its per-episode artifacts
  (`phone_find_s4.json`, `phone_tips_s4.json`, the
  earlier sittings' files beside them) and its protocol with every sitting's result (`docs/PHONE_PROTOCOL.md`).
- The `scripts/reproduce.py` report ends with one gaslight
  episode traced end to end (claims, hypotheses, proof path) and the
  counterfactual that removes its planted tip.
- Regenerate-to-verify rather than artifact-shipped, each from the
  stated command: the 40-episode gaslight run, the learned-layer table,
  the Gazebo bridge log, the pre-incremental-maintenance soak baseline
  curve, and the hospital world's location count (computed from the
  externally downloaded world file).
- The transfer-ladder rates quote the 25-seed battery summary. The
  separately shipped 40-seed `coffee_ladder.json` is a distinct,
  larger run scoring 0.95, 0.80, 0.80 on the same three rungs, within
  Wilson noise of the 25-seed figures.
- The committed `alfworld_valid_unseen.json` carries the v2
  re-run (134/134). The first run's 129/134 is preserved in git history
  (commit `ebb9bb1`) and recomputes to the same numbers.
- The pre-generated bulk artifact bundle is a 393 MB zip, 400 MB
  and 575 files unpacked: every artifact JSON, the kept frames of the
  AI2-THOR and gz-arena runs, and 122 run and certification logs from
  both WSL distributions. A 2.4 GB companion bundle carries the
  real-perception run animations.
  `scripts/stage_artifact_bundle.py --logs-dir dist/wsl_logs`
  rebuilds both with a manifest and SHA-256 sums. Both are available on
  request via a data-access issue on the benchmark-kit repository.
- The SubT and hospital worlds require minor world-file patches
  (reserved world name, legacy material scripts), recorded as scripts in
  the repository.
