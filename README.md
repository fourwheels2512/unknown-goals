# Unknown Goals: benchmark kit and demonstration build

A run-only build of **robot_mind**, the evidence-based reasoning engine
evaluated in the working paper *A Decision Layer for Robot Object Search
Under Unreliable Evidence, With a Checkable Provenance Record for Every
Commitment* (Nayudu, 2026;
public rendering in [`paper/`](paper/)). The engine keeps an append-only
evidence ledger, holds competing explanations at once, picks the physical
check that teaches it the most, verifies tips before trusting them, and
commits only after it has looked. Every decision carries a proof path that
an independent checker can re-validate.

This repository lets you **run** that engine on seeded scenarios and read
every decision it makes. It does not contain the engine's source code, and
the binary withholds the computations the paper withholds (see
[What you can and cannot see](#what-you-can-and-cannot-see)).

No language model, no network access, no training data, no telemetry. Every
run is a deterministic function of the seed.

## Download

Binaries are on the [Releases](../../releases) page.

| File | Platform | Notes |
|---|---|---|
| `unknown-goals-demo-windows-x86_64.exe` | Windows 10/11, x86-64 | single file, no install |
| `unknown-goals-demo-linux-x86_64` | Linux, x86-64 | single file; needs glibc 2.38 or newer (`ldd --version`) |

macOS is not built yet. The Linux binary runs under Docker or WSL on other
systems.

Verify the download against `SHA256SUMS` in this repository:

```
sha256sum -c SHA256SUMS            # Linux
certutil -hashfile unknown-goals-demo-windows-x86_64.exe SHA256   # Windows, compare by eye
```

The Windows binary is unsigned. SmartScreen may ask you to confirm the first
run; the checksum is the way to know you have the file this repository
describes.

## Quick start

```
unknown-goals-demo demo                       # the canonical wrench episode, fully traced
unknown-goals-demo demo --seed 42 --level 6   # a generated GASLIGHT scenario: planted false evidence
unknown-goals-demo demo --seed 42 --level 6 --explain   # ... plus a plain-English narrative
unknown-goals-demo replay --seed 7 --level 3  # run the same scenario twice: records byte-identical
unknown-goals-demo whatif --seed 11 --level 6 --without-source anonymous_tip   # counterfactual
unknown-goals-demo benchmark                  # train a rule on 1,000 seeded episodes, test on 300 held out
unknown-goals-demo coffee --rung 3            # the Coffee Ladder: find, gather and brew in an unfamiliar house
unknown-goals-demo ask "where is wrench_12"   # a natural-language request against the canonical world
unknown-goals-demo --help
```

The commands below call the file `unknown-goals-demo`; rename your download to that (on Linux also `chmod +x` it), or type the full file name.

### Difficulty levels

| Level | What the evidence looks like |
|---|---|
| 1 | direct observation, one hop |
| 2 | a person carried the object, two hops |
| 3 | person plus cart chain, three to four hops |
| 4 | plus distractors, decoys and stale claims |
| 5 | plus contradictions, occlusion, wrong-branch recovery |
| 6 | **GASLIGHT**: an adversary plants confident false sightings, staged twin-object decoys and contradictory reports while the true chain hides in normal noise |

Any integer seed is a new scenario. The scenarios in the paper's tables are
seeds of this same generator.

### What to look for

A `demo` run prints, for each step: the map with the robot's position and
its belief per location, the competing hypotheses with their belief and
status, the action chosen and why, the outcome, and the new evidence that
outcome put on the ledger. Then the result against hidden ground truth, the
proof path of the top derived conclusion, a proof audit, and the final
hypothesis states.

On level 6 with seed 42, watch the first step: the engine goes to verify the planted tip,
finds nothing, marks the report contradicted, and redirects. It never commits
to a location it has not looked at.

`replay` shows determinism: two runs of the same seed produce the same record.
The files in [`samples/`](samples/) are what the build in this release prints
for the commands above; your output should match them exactly on the same
platform.

`benchmark` takes about ten seconds on a laptop core. It trains a
rule on 1,000 seeded episodes, validates it on 300 held-out seeds, and, if the
rule validates, saves it to `data/artifacts/learned_rules.json` in the current
directory; later `demo` runs in that directory use it and say so.

## What you can and cannot see

**Shown:** every claim on the ledger with its status, confidence, time and
source; every hypothesis with its belief and status; every action with its
rationale; every proof path (input claims, rules, assumptions, time
constraints); the proof audit; counterfactual belief shifts.

**Withheld, as in the public paper:** how support, contradiction, age and
rule reliability combine into a belief and the constants they combine under;
the trigger that widens a refuted search; and how the three load-bearing
mechanisms (multi-anchor hypotheses, transport hand-off, repetition decay with
the policy gate) are computed. Concretely, this build does not print the
per-hypothesis belief breakdown, the planner's per-action numbers, or the
numeric window constants inside proof time constraints (they appear as
`window`).

**Not distributed:** the engine's source. The binary is compiled machine
code with docstrings and assertions stripped. It is a demonstration, not a
library: it has no importable API and no configuration surface.

## The benchmark kit

The kit in this repository is the other half of the claim the paper makes.
The demonstration build above lets you watch the engine decide. The kit
lets you check what it decided, on the episodes the paper counts, without
taking the engine's word for anything and without the engine being present.

```
pip install -e .          # Python 3.12+, pydantic and networkx
```

### What ships

| directory | what is in it |
|---|---|
| `unknown_goals/` | the scenario generator, the world and executor, the episode contract, the evidence ledger and belief graph, the proof checker, the decision replayer, the verifier |
| `baselines/` | every policy the engine is measured against: sweep, random, last-seen, a Bayesian filter, the exact finite-horizon belief-space planner, and the LLM comparison harness |
| `data/artifacts/` | the per-episode results of the suites the paper reports, less the five artifacts that serialise tuned configuration, one superseded rerun, and one partner's survey data that is not the author's to publish; `docs/ARTIFACTS.md` names each with its reason |
| `data/exports/` | the ledger export of every engine episode whose commitment the paper counts: its entities, every claim with status, confidence, times and provenance, the rules in force, every decision with its rationale and outcome, and the proof path of every derived claim |
| `docs/`, `paper/` | the paper's public rendering and the protocol documents |
| `ros2/robot_mind_msgs/` | the typed ROS 2 interfaces the engine speaks on a robot |

### Where each number comes from

| ledger export | artifact | episodes | compressed | artifact vs. this build |
|---|---|---:|---:|---|
| `absent_target.jsonl.gz` | `data/artifacts/absent_target.json` | 2400 | 5.57 MB | identical |
| `audit_unseen_repro.jsonl.gz` | `data/artifacts/audit_unseen_repro.json` | 71 | 0.14 MB | identical |
| `battery_final.jsonl.gz` | `data/artifacts/battery_final.json` | 1059 | 1.38 MB | identical |
| `budget_sweep.jsonl.gz` | `data/artifacts/budget_sweep.json` | 360 | 0.42 MB | identical |
| `budget_sweep_100.jsonl.gz` | `data/artifacts/budget_sweep_100.json` | 3000 | 3.45 MB | identical |
| `calibration.jsonl.gz` | `data/artifacts/calibration.json` | 150 | 0.15 MB | identical |
| `head_to_head.jsonl.gz` | `data/artifacts/head_to_head.json` | 48 | 0.05 MB | **differs** -- accuracy is identical; `engine_steps` differs in a minority of episodes because the artifact predates the shipped build |
| `head_to_head_deepseek-chat_strong.jsonl.gz` | `data/artifacts/head_to_head_deepseek-chat_strong.json` | 48 | 0.05 MB | **differs** -- accuracy is identical; `engine_steps` differs in a minority of episodes because the artifact predates the shipped build |
| `head_to_head_gemini-3.7-flash_strong.jsonl.gz` | `data/artifacts/head_to_head_gemini-3.7-flash_strong.json` | 12 | 0.02 MB | **differs** -- accuracy is identical; `engine_steps` differs in a minority of episodes because the artifact predates the shipped build |
| `head_to_head_gemini-3.7-flash_strong_l2345.jsonl.gz` | `data/artifacts/head_to_head_gemini-3.7-flash_strong_l2345.json` | 48 | 0.05 MB | identical |
| `head_to_head_qwen2.5_7b-instruct_strong_l2345.jsonl.gz` | `data/artifacts/head_to_head_qwen2.5_7b-instruct_strong_l2345.json` | 48 | 0.05 MB | identical |
| `head_to_head_strong.jsonl.gz` | `data/artifacts/head_to_head_strong.json` | 48 | 0.05 MB | **differs** -- accuracy is identical; `engine_steps` differs in a minority of episodes because the artifact predates the shipped build |
| `woz_dynamic.jsonl.gz` | `data/artifacts/woz_dynamic.json` | 758 | 3.57 MB | **differs** -- the artifact is from an earlier build and is kept as the development record; the export is the shipped build's rerun of the same command |
| `woz_dynamic_night480.jsonl.gz` | `data/artifacts/woz_dynamic_night480.json` | 756 | 3.04 MB | **differs** -- every key and value in the artifact is reproduced exactly; the current script writes two keys the artifact predates |
| `woz_selfimprove.jsonl.gz` | `data/artifacts/woz_selfimprove.json` | 767 | 2.69 MB | **differs** -- the artifact is from an earlier build and is kept as the development record; the export is the shipped build's rerun of the same command |
| `woz_test.jsonl.gz` | `data/artifacts/woz_test.json` | 435 | 0.15 MB | **differs** -- the artifact is from an earlier build and is kept as the development record; the export is the shipped build's rerun of the same command |

#### Artifacts not in the kit

| file | why it is not in the kit |
|---|---|
| `data/artifacts/vk/` (the whole directory) | a partner's survey data (an AUV eelgrass survey run for a client, with the site's coordinates, the vehicle's logs and the team's own labels): not part of the paper and not the author's to publish; the engine's results on it are reported to the partner, not here |
| `data/artifacts/evolved_config.json` | a full serialisation of the engine's tuned configuration |
| `data/artifacts/self_repair_exam.json` | names configuration fields and the values repaired to |
| `data/artifacts/self_repair_exam2.json` | names configuration fields and the values repaired to |
| `data/artifacts/stress/s8_selfrepair_redteam.json` | records a configuration field and the value it was sabotaged to |
| `data/artifacts/staleness_ordering.json` | carries engine constants: the study is of the withheld belief arithmetic and publishes its constants as numbers |
| `data/artifacts/audit_unseen_repro_two.json` | superseded, uncited: the committed file is from an earlier build (12/17) and the paper does not cite it |
| `data/exports/audit_unseen_repro_two.jsonl.gz` | superseded, uncited: the artifact it belongs to does not ship |

Artifacts that ship without a ledger export:

| artifact | why there is no export |
|---|---|
| `data/artifacts/audit_unseen_sweep.json` | the scripted-sweep ablation runs no engine episode at all (policy=sweep replaces every FIND decision; the artifact's own `seeks` column is 0 in all 30 rows), so there is nothing to export. |
| `data/artifacts/audit_unseen_sweep_two.json` | same: 0 engine seeks in all 17 rows. |
| `data/artifacts/woz_dynamic_*.json (12 ablation variants)` | deferred: no recorded invocation. The variants (clock_decay, clock_nodecay, decay, nodecay, full_decay, full_nodecay, meta, night480_meta, night480_reflect, reflect, w3_decay, w3_nodecay) carry no metadata, and no script, document or docstring records the flags each was run with; guessing the mapping would fabricate provenance. woz_dynamic.json (defaults) and woz_dynamic_night480.json (--night-minutes 480, the command printed in the paper's reproduction block) are exported. |

The full version of both tables, with what each export covers, is in
[`docs/ARTIFACTS.md`](docs/ARTIFACTS.md).

### What the kit lets you check

```
python -m unknown_goals.verify --quick
```

Regenerates every baseline from its integer seed and compares the result
with the artifact committed here, field by field. A baseline that does not
come back identical is a failure of the kit, not of the artifact. Then it
re-validates every proof in `data/exports/` and, where a summary artifact
records a proof-validity fraction of its own, requires the checker's
fraction to equal it exactly. Drop `--quick` to include the 100-seed
suites.

```
python -m unknown_goals.checker data/exports/battery_final.jsonl.gz
```

The independent checker. For every claim the engine derived, it confirms
the proof exists, names an operator the engine emits, cites only claims
that were on that episode's ledger and reached it no later than the claim
they support, applies only rules that episode knew, and asserts only time
constraints the cited claims satisfy. For every episode that ends FOUND it
requires the ledger to witness the commitment: an observation of the
object at the committed place, at the resolve bar or above, made by
something other than the reasoner. For every episode that ends NOT-FOUND
it re-derives the coverage certificate from the export's own entities and
claims rather than reading it back: one empty-handed look of the robot's
own per place, none older than the last claim that placed the object; a
certificate that declares the object static in its own text is read under
the same rule place by place, with every refuted sighting named. Exit
status is non-zero if any proof, commitment or certificate fails. No
engine code runs.

An episode may be flown on a ledger that outlived an earlier one — two
dives of one survey are one record — and its export then names, in
`history_claim_ids`, the claims that were already there when it began.
Their proofs are replayed like any other and this episode may cite them
(that is what the shared record is for), but the episode is not held to
them: a certificate an earlier dive derived is that dive's, not this one's
verdict. What an export cannot do is rewrite its own history — a named id
that is not on the ledger, a claim one of this episode's own decisions
wrote, a count larger than the ledger its first decision saw, or a history
claim whose proof leans on a claim this episode wrote — and each of those
fails the episode. An export with no such key, which is every export
shipped here, is read exactly as before.

```
python -m unknown_goals.replay data/exports/battery_final.jsonl.gz --list
python -m unknown_goals.replay data/exports/battery_final.jsonl.gz --episode test=T2 seed=10007 level=6
```

The replayer walks one episode decision by decision: what was on the ledger
when the engine chose, the hypotheses it held with their belief and status,
the action and the rationale it gave, the outcome, the evidence that
outcome produced — then the result against hidden ground truth and the
proof path of the last claim it derived, with the checker's verdict.

```
python -m baselines.belief_planner --seeds 12 --out /tmp/planner.json
```

Any baseline can also be run on its own, on any seeds, at any budget.

### What the checker certifies, and what it does not

The checker **replays provenance and tests the two kinds of commitment.
It does not re-derive belief values.** It establishes that every
conclusion the engine committed to is traceable to evidence that was on
the ledger at the time, under rules that episode declared, in an order
time allows — and that nothing in the chain is missing, dangling or
anachronistic; that a FOUND was witnessed by an observed sighting at the
bar; and that a NOT-FOUND rests on a complete, current sweep of the places
the episode knew. `tests/test_checker_forgery.py` holds the mutations it
has to reject, among them certificates whose provenance replays cleanly.
That is what makes a commitment auditable after the fact.

It does not recompute the belief arithmetic, and it cannot: how support,
contradiction, age and rule reliability combine into a belief, and the
constants they combine under, are withheld from this release, as they are
from the public paper. Nor does the checker grade correctness — whether a
commitment was *right* is the hidden-truth grading in the artifacts, not
the checker's verdict.

The engine arm of a comparison is likewise **read, not recomputed**: those
rows in `data/artifacts/` are the engine's measured output, committed with
the paper. What the kit gives you instead of trust is the ledger export
behind them, which the checker and the replayer take apart episode by
episode.

**What changed since v0.5.0-kit.2.** The checker reads an episode whose
ledger carried claims from an earlier one: an export may name those claims
in `history_claim_ids`, and the commitment and certificate checks then
judge what this episode derived rather than what it inherited, while every
proof, this episode's and its history's, is replayed as before. Four ways
of rewriting history are rejected, each with its own message, and
`tests/test_checker_forgery.py` holds them. No export in this release
carries the key, and none of the counts below moves: the release is the
same artifacts under a checker that can also read a two-dive record.
`ros2/robot_mind_msgs/` also gains the three message types a seabed search
node speaks — one message per camera frame from whatever detector runs on
the vehicle, and the per-cell coverage read-out it publishes back.

**What changed since v0.5.0-kit.1.** The checker in that release (commit
`191eea3`) validated proof paths alone: it did not test the order in which
cited claims reached the ledger, and it had no commitment or certificate
check, so every "proof steps valid" total quoted against it is that check
and no more. This release adds the three. The digest file
`unknown_goals/data/leak_hashes.json` and the self-test that read it are
gone: the digests were reversible from the kit's own vocabulary, so they
withheld nothing. The gate that keeps the withheld computation out of the
kit runs in the engine repository when the kit is built and is not part of
the kit.

### Licensing

Code Apache-2.0 (`LICENSE`). Data, documents and the paper CC BY 4.0
(`LICENSE-DATA`). The demonstration binaries keep their evaluation license
(`LICENSE-DEMO`).

## License

The benchmark kit -- the code in `unknown_goals/`, `baselines/` and `tests/`
-- is Apache-2.0 ([`LICENSE`](LICENSE)). The artifacts, ledger exports,
documents and paper under `data/`, `docs/`, `paper/` and `samples/` are
CC BY 4.0 ([`LICENSE-DATA`](LICENSE-DATA)).

The demonstration binary is free to run for evaluation, research, teaching
and review under the terms in [`LICENSE-DEMO`](LICENSE-DEMO). It may not be
redistributed, modified or reverse engineered.

## Citation

See [`CITATION.cff`](CITATION.cff).

```
Nayudu, K. (2026). A Decision Layer for Robot Object Search Under Unreliable Evidence, With a Checkable Provenance Record for Every Commitment. Working paper v0.5.
```

## Contact

Open an issue in this repository.
