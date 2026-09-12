# Stress battery, latency increments and the edge profile

These notes accompany the paper *A Decision Layer for Robot Object Search
Under Unreliable Evidence, With a Checkable Provenance Record for Every
Commitment*, and they ship with the benchmark kit. They carry the
per-suite detail that the paper's robustness-and-cost and persistent-mind
sections summarise.

## Stress battery: per-episode figures, the defects and the sabotage sweep
This block carries the details of the nine-suite battery of
the paper's robustness-and-cost section that its three paragraphs leave out. The under-32 ms
figure for the 1,860 fuzzed episodes is a worst case per episode. The
~5 ms in the head-to-head table is the typical fresh-ledger
figure on the benchmark distribution, and the edge profile puts the
per-episode cost at 2.8-3.1 ms median and 4.8-5.4 ms p95 on levels
1-6. Of the five defects, the timestamp fields had no upper bound, so a
value outside the database's 64-bit range reached the ledger and crashed
it. The stack-trace defect sat behind an `assert` that Python's
optimised mode strips, and the fix adds real input validation with a
one-line error message. The out-of-range confidence appeared at two
claim-construction sites, one in the reasoner and one in the executor's
sensor model, and both now clamp the computed value into the valid band.
Every fix preserves behaviour on valid input. The sixth reported failure
came from a test that demanded full restoration of health where the loop
promises only never to make things worse. The test was corrected to
assert that contract. The unscreened sabotage sweep applied 120
random-field, random-magnitude edits to the configuration. Of these,
119 were applied and 1 was rejected by validation, 12 helped and 107
were correctly left at rest. The loop never crashed, never adopted a
regression and never adopted its placebo.


## Latency increments: profiling, mechanism and equivalence
Per-decision latency grows with accumulated memory
(the lifelong-cost figure). Caching the append-only ledger and linearising
a contradiction scan cut per-day soak latency about 4x. Three
increments of incremental view maintenance followed, all
byte-identical in their decisions. The first made a 300-day life about 7x faster and day 300 about 8x faster (4.46 s -> 0.54 s), and the second made the life a further 4.0x faster (day 300: 0.548 s -> 0.153 s). The third cut
the claim-rows walked over days 81-120 from 9,000,154 to
1,014,180. Over five interleaved paired repetitions under 33-59%
background load it ran the life a further 2.5-3.4x faster
(median 3.0x), day 300 falling from 0.157-0.248 s to
0.040-0.081 s. The shipped pair (`s4_soak_pre_ivm3.json`
 -> `s4_soak.json`, repetitions in
`s4_soak_ivm3_reps.json`) reads 35.0 s -> 10.0 s and
0.241 -> 0.053 s/day. First-to-last-window growth, the least
stable number here, read 10.5-15.9x before and 4.5-8.7x
after, against 6.6x in claims. The slope has moved and is not yet reliably below the growth of the ledger.

This block records, for each latency increment of the paper's robustness-and-cost section,
what profiling found, what changed and how equivalence was checked.
Every run is byte-identical in its decisions. Before any maintenance,
first-to-last-window growth of the 300-day soak was 33.7x. The
first fix cached the append-only ledger and linearised a contradiction
scan, for about 4x per day. Increment one maintains the belief
graph, filtered claim reads and effective statuses on append, and the
run in its session showed 13.2x growth.

Increment two was profiled first: 68% of a simulated day was the drive
manager's room-visit scan re-parsing entities from SQLite. It caches
entities and keeps every claim index in the ledger's canonical order at
insertion, so filtered reads never sort. It also turns contradiction
detection into an incremental view over the claims appended or
re-trusted since its last check. The view emits the events the full
pass would, in the same order. Tests enforce that equivalence, and the
360-episode held-out record dump keeps the same SHA-256. Measured back
to back on a quiet machine, the whole 300-day life went from 106 s to
27 s with identical claim counts and clocks at every checkpoint.
Growth after increment two was 8.2x first-to-last window, against
8.0x in the paired before-run, and the ratio moves with machine
load. The constant factor fell and the slope did not, because the
drives' visit scan, nightly reflection and the per-subject
contradiction check still walked full claim lists. The artifacts are
`s4_soak_ivm2.json` (that session's after-run) and
`s4_soak_pre_ivm2.json` (its paired before-run).

Increment three builds two of those three views. Profiling the soak
after increment two put 34.6% of profiled time (days 81-120 of the
workload) in the room-visit scan. That scan asked for every claim ever
recorded and took a maximum over them. Only the newest trusted robot
sighting of a room can win that maximum, and every claim index is
already in canonical order. The view therefore walks each room's own
index backwards and stops at the first match. A composite
subject-predicate index answers the reasoner's commonest question
(every hypothesis hop, every absence check) directly. A filtered read
whose index is keyed on the filters asked for skips the per-row
re-test. Nightly reflection collects its subjects from the three
location-family predicate pools, and the patrol loop reads the claim
count instead of copying the ledger. Two differential tests join the
standing equivalence checks. The room-visit view agrees with a verbatim
copy of the previous implementation on every one of 1,680 calls. The
indexed read agrees with a full-scan ground truth, order included, over
3,210 queries. The 360-episode benchmark keeps the same report and
record-dump SHA-256, and 432 tests pass. The count of claim-rows walked
over days 81-120, 9,000,154 -> 1,014,180 (8.9x
fewer), is immune to machine load. The room-visit scan's share of
profiled time fell from 34.6% to 0.3%. In the five interleaved
repetitions, wall and CPU clocks agreed within 2% in every run. The
whole 300-day life ran in 21.8-33.6 s before and 7.8-12.0 s after,
and day 300 sped up 2.2-5.0x (median 3.3x). The growth
ratio is the least stable number in the battery because its denominator
is a 0.01-0.02 s/day first window. Its medians were 12.1x
before and 7.4x after. The withdrawn single-pair reading (0.2819
 -> 0.0917 s/day, 9.4x -> 5.4x) was taken under a
different interpreter. The short-episode benchmark is unchanged within
noise: best-of-9 CPU time over 180 episodes 484 -> 516 ms, median
531 -> 531 ms.

The next increment has a named target. The contradicted-location-claim
search and the per-subject sighting walk become maintained views
through an ordered contradicted-claim index and an event-time-sorted
per-subject index. The per-decision cost is then O(delta * k + R), independent of N except through k. That is an implementation
plan, not a theorem. Whether those two views suffice, or whether a
multi-tier ledger (hot window plus consolidated summaries) or a bounded
temporal horizon is needed to make the slope zero, is left open.


## Edge profile: run details
The fresh-ledger profile of the paper's robustness-and-cost section was taken as follows.
Each of its 1,025 decisions is a full cycle of contradiction
detection, incremental belief-graph refresh, hypothesis generation and
scoring, and planner choice. The 0.33-0.34 ms median is on one laptop
core (Intel i9-11900H) pinned by affinity. Across the four runs with
one or two pinned cores the median is 0.31-0.34 ms, and Windows 11
and WSL 2 Ubuntu 24.04 agree to within a few percent. Of the 14 MiB
runtime dependency closure, pydantic-core, the one compiled extension,
is 5 MiB, and the engine itself is 0.44 MiB of pure Python over the
standard library's SQLite. The profiled run re-reports the benchmark's
own success, correctness, proof validity (1.000) and 1.847 actions per
episode, so the number is the cost of the shipped behaviour. A second
core buys nothing: the engine is single-threaded, with CPU s/wall s
~= 1.0.
