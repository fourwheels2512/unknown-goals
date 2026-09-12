# Edge profile: the whole engine, one laptop core, a third of a millisecond

The engine's entire cognition stack — append-only evidence ledger, incremental
belief graph, multi-hop hypothesis generation with machine-checkable proofs,
contradiction bookkeeping, belief scoring, planner and learned policy — makes
one decision in **0.33 ms (median) on a single pinned laptop core**, with a
**p99 under 1.1 ms**, inside **60 MiB of resident memory**, from a **170 KiB
wheel** whose complete runtime dependency closure is **14 MiB** (pure Python
apart from pydantic-core, the one compiled extension).
No GPU, no server, no network, no language model. A second core buys nothing
because nothing here needs one. For an edge robot that is the difference
between cognition that fits inside the control loop and cognition that has
to be scheduled around it: at these numbers a 10 Hz decision cycle uses
under 1% of one core, and the p99 leaves more than 9× headroom inside a
10 ms tick.

**Scope, stated plainly:** these are laptop-CPU numbers (Intel Core
i9-11900H, one or two of its cores pinned by affinity), measured on
Windows 11 and inside WSL 2 Ubuntu 24.04. No Jetson, Raspberry Pi, or
other ARM/embedded board was measured and no claim is made about them. The
workload is fresh-ledger episodes (about 40 claims); per-decision cost grows
with lifetime memory, which is the soak's separate subject
(`data/artifacts/stress/s4_soak*.json`, PAPER §5.12).

## What was measured

Workload: the warehouse benchmark, levels 1–6, 60 held-out seeds
(10000–10059, disjoint from the 0–249 training range) = **360 graded
episodes, 1,025 decisions**. Every episode is graded against hidden ground
truth exactly as the benchmark grades it, so the cost below is the cost of
the engine's shipped behaviour — the run re-reports success 1.000, correct
1.000, proof validity 1.000 and 1.847 actions per episode, identical to the
benchmark harness on the same seeds.

A **decision** is one engine cycle: contradiction detection over the ledger,
incremental belief-graph refresh, hypothesis generation and belief scoring
(with derived claims appended to the ledger), plus planner candidate
generation and policy choice when an action follows. Timing wraps the
runner's own calls; no engine code was modified for measurement
(`experiments/edge_profile.py`).

Process pinned with `psutil.Process().cpu_affinity` to CPU 0 (1 core) or CPUs
0–1 (2 cores). Six warm-up episodes excluded. Wall clock via
`perf_counter_ns`; CPU time via `process_time`; peak RSS from the peak
working set (Windows) or `ru_maxrss` (Linux). System-wide CPU utilisation
across the measured pass is recorded per run so the conditions are on the
record.

## Results

Config/rules v0.2.0, Python 3.12, all runs 2026-09-01 on the same machine
(i9-11900H, 8 cores / 16 threads, 2.5 GHz base; WSL 2 sees 16 vCPUs).

| run | decision median | p95 | p99 | max | episode median | peak RSS | CPU s / wall s | success | correct | proofs |
|---|---|---|---|---|---|---|---|---|---|---|
| Windows, 1 core  | **0.34 ms** | 0.77 ms | 1.05 ms | 7.89 ms† | 3.11 ms | 59.1 MiB | 1.27 / 1.33 | 1.000 | 1.000 | 1.000 |
| Windows, 2 cores | **0.34 ms** | 0.73 ms | 1.03 ms | 1.52 ms  | 3.10 ms | 59.5 MiB | 1.27 / 1.29 | 1.000 | 1.000 | 1.000 |
| WSL 2 Ubuntu 24.04, 1 core  | **0.33 ms** | 0.70 ms | 0.93 ms | 1.30 ms | 3.02 ms | 53.6 MiB | 1.27 / 1.27 | 1.000 | 1.000 | 1.000 |
| WSL 2 Ubuntu 24.04, 2 cores | **0.31 ms** | 0.71 ms | 0.98 ms | 1.79 ms | 2.82 ms | 53.4 MiB | 1.20 / 1.20 | 1.000 | 1.000 | 1.000 |

† one decision of 1,025; the next-slowest was 1.1 ms. During that pass CPU 0
(the pinned core, which also services Windows interrupts) was shared with
two finishing detector probes from another session (all-CPU utilisation
23.8%). Every other run's max is under 2 ms.

CPU s / wall s ≈ 1.0 everywhere: the engine is single-threaded and compute
bound; the 2-core runs are within noise of the 1-core runs, as expected.

**Per level** (decision median / p95, ms; 1-core runs):

| level | 1 (direct) | 2 (carrier) | 3 (transport) | 4 (stash) | 5 (noise) | 6 (gaslight) |
|---|---|---|---|---|---|---|
| Windows | 0.09 / 0.13 | 0.30 / 0.43 | 0.41 / 0.55 | 0.43 / 0.79 | 0.44 / 0.85 | 0.47 / 0.84 |
| WSL 2   | 0.08 / 0.13 | 0.27 / 0.47 | 0.38 / 0.63 | 0.37 / 0.72 | 0.42 / 0.78 | 0.41 / 0.76 |

Level 6 — the adversarial one, with planted false tips and the
verify-then-redirect behaviour — costs 0.47 ms per decision.

**Memory.** Resident set at import (before any episode): 49.5 MiB on
Windows, 44.9 MiB on Linux. Peak across 360 episodes: 59.5 MiB / 53.6 MiB —
about 10 MiB of growth for the whole run, since each episode's in-memory
SQLite ledger is released with its runner.

**Start-up.** Median of 7 cold subprocess launches:

| | Windows | WSL 2 |
|---|---|---|
| interpreter start (`python -c pass`) | 78–97 ms | 34–35 ms |
| `import robot_mind.evaluation.benchmark` (pulls pydantic, networkx, sqlite3) | 733–887 ms | 758–856 ms |
| start + import | 0.84–1.03 s | 0.82–0.92 s |

Import time is dominated by networkx and pydantic module initialisation,
not by the engine's own 74 source files.

**Install size** (runtime closure from installed distribution metadata,
`__pycache__` excluded):

| distribution | version | size |
|---|---|---|
| networkx | 3.6.1 | 6.71 MiB |
| pydantic-core | 2.46.5 | 5.25 MiB (Windows) / 4.80 MiB (Linux) |
| pydantic | 2.13.5 | 1.81 MiB |
| **robot-mind** (engine source, 74 files) | 0.1.0 | **0.44 MiB** |
| typing-extensions, typing-inspection, annotated-types | | 0.25 MiB |
| **total** | | **14.5 MiB (Windows) / 14.1 MiB (Linux)** |

Built wheel: `robot_mind-0.1.0-py3-none-any.whl`, **170 KiB**. The only
compiled component is pydantic-core; everything else, including the engine,
is pure Python over the standard library's SQLite. `psutil` is a profiling
(dev) dependency only and is not part of the runtime closure.

## Conditions and honest limits

- **Laptop CPU only.** i9-11900H at 2.5 GHz base (turbo enabled, laptop
  power plan). An embedded ARM core will be slower; by how much is not
  measured here and is not claimed.
- **WSL 2 is a VM.** Its vCPUs are scheduled by the hypervisor; the numbers
  matched native Windows to within a few percent, which says the engine is
  not sensitive to the environment, not that WSL is representative of a
  robot's Linux.
- **Load disclosure.** The runs were taken in a window when the machine was
  near idle: all-CPU utilisation during the pass was 6.2% for both WSL runs
  and 23.8% / 24.9% for the Windows runs (another session's detector probes
  finishing). The Windows 1-core max is the visible consequence. Earlier
  smoke passes under 98% system load produced 0.9 ms medians and 9 ms p95s
  — those are not reported as results, but they say what to expect when
  cognition shares a core with a saturated perception stack.
- **Fresh ledgers.** ~40 claims per episode. The soak measures growth with
  lifetime memory; this document does not.
- **Python 3.12, CPython.** No PyPy, no compiled extension of the engine.

## Reproduce

```
uv run python experiments/edge_profile.py --cores 1          # Windows, source checkout
uv run python experiments/edge_profile.py --cores 2
# inside WSL: install the wheel + deps into a clean target, then
uv build --wheel
pip3 install --target /root/edge_site pydantic networkx psutil dist/robot_mind-0.1.0-py3-none-any.whl
PYTHONPATH=/root/edge_site python3 experiments/edge_profile.py --cores 1 --tag wsl_1c
```

Artifacts: `data/artifacts/edge/edge_profile_{win_1c,win_2c,wsl_1c,wsl_2c}.json`
(full distributions, per-level tables, per-CPU load, machine facts).
