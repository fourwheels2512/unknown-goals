# Unknown Goals: demonstration build

A run-only build of **robot_mind**, the evidence-based reasoning engine
evaluated in the working paper *Evidence-Based Robot Cognition: An Auditable,
LLM-Free Reasoning Engine That Verifies Before It Trusts* (Nayudu, 2026;
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

## What is coming

The benchmark kit described in the paper (scenario generator, the scripted
and exact belief-space baselines, the LLM comparison harness, the independent
proof checker, the ROS 2 message definitions, and every engine trace and
artifact the paper reports) is released here at the paper's deposit, under
Apache-2.0 with data under CC BY 4.0.

## License

The demonstration binary is free to run for evaluation, research, teaching
and review under the terms in [`LICENSE`](LICENSE). It may not be
redistributed, modified or reverse engineered. The paper is CC BY 4.0.

## Citation

See [`CITATION.cff`](CITATION.cff).

```
Nayudu, K. (2026). Evidence-Based Robot Cognition: An Auditable, LLM-Free
Reasoning Engine That Verifies Before It Trusts. Working paper v0.5.
```

## Contact

Open an issue in this repository.
