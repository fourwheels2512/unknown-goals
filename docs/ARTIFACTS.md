# Artifacts, ledger exports and what is not here

Every number the paper reports for the engine comes from an artifact in
`data/artifacts/`. For the batteries whose commitments the paper counts,
the engine's own ledger for every episode is in `data/exports/`, one
gzipped JSON-lines file per artifact, one line per episode, in the
artifact's own row order.

## What each export covers, and how the artifact compares

The last column compares the **committed artifact** with what the
**shipped build** produces from the same recorded command, as parsed JSON
after dropping timing and machine fields.

A row marked **differs** is not a failure of the export. The export is a
faithful record of the shipped build re-running the recorded command. The
artifact is the historical record of what was measured when the paper's
table was written, and it is kept unchanged rather than quietly
regenerated. Where they differ, the export is the current build and the
artifact is the older one; the reason is in the row.

| ledger export | artifact | episodes | compressed | artifact vs. this build |
|---|---|---:|---:|---|
| `absent_target.jsonl.gz` | `data/artifacts/absent_target.json` | 2400 | 5.54 MB | identical |
| `audit_unseen_repro.jsonl.gz` | `data/artifacts/audit_unseen_repro.json` | 71 | 0.14 MB | identical |
| `battery_final.jsonl.gz` | `data/artifacts/battery_final.json` | 1059 | 1.37 MB | identical |
| `budget_sweep.jsonl.gz` | `data/artifacts/budget_sweep.json` | 360 | 0.42 MB | identical |
| `budget_sweep_100.jsonl.gz` | `data/artifacts/budget_sweep_100.json` | 3000 | 3.42 MB | identical |
| `calibration.jsonl.gz` | `data/artifacts/calibration.json` | 150 | 0.15 MB | identical |
| `head_to_head.jsonl.gz` | `data/artifacts/head_to_head.json` | 48 | 0.05 MB | **differs** -- accuracy is identical; `engine_steps` differs in a minority of episodes because the artifact predates the shipped build |
| `head_to_head_deepseek-chat_strong.jsonl.gz` | `data/artifacts/head_to_head_deepseek-chat_strong.json` | 48 | 0.05 MB | **differs** -- accuracy is identical; `engine_steps` differs in a minority of episodes because the artifact predates the shipped build |
| `head_to_head_gemini-3.7-flash_strong.jsonl.gz` | `data/artifacts/head_to_head_gemini-3.7-flash_strong.json` | 12 | 0.02 MB | **differs** -- accuracy is identical; `engine_steps` differs in a minority of episodes because the artifact predates the shipped build |
| `head_to_head_gemini-3.7-flash_strong_l2345.jsonl.gz` | `data/artifacts/head_to_head_gemini-3.7-flash_strong_l2345.json` | 48 | 0.05 MB | identical |
| `head_to_head_qwen2.5_7b-instruct_strong_l2345.jsonl.gz` | `data/artifacts/head_to_head_qwen2.5_7b-instruct_strong_l2345.json` | 48 | 0.05 MB | identical |
| `head_to_head_strong.jsonl.gz` | `data/artifacts/head_to_head_strong.json` | 48 | 0.05 MB | **differs** -- accuracy is identical; `engine_steps` differs in a minority of episodes because the artifact predates the shipped build |
| `woz_dynamic.jsonl.gz` | `data/artifacts/woz_dynamic.json` | 758 | 3.56 MB | **differs** -- the artifact is from an earlier build and is kept as the development record; the export is the shipped build's rerun of the same command |
| `woz_dynamic_night480.jsonl.gz` | `data/artifacts/woz_dynamic_night480.json` | 756 | 3.03 MB | **differs** -- every key and value in the artifact is reproduced exactly; the current script writes two keys the artifact predates |
| `woz_selfimprove.jsonl.gz` | `data/artifacts/woz_selfimprove.json` | 767 | 2.68 MB | **differs** -- the artifact is from an earlier build and is kept as the development record; the export is the shipped build's rerun of the same command |
| `woz_test.jsonl.gz` | `data/artifacts/woz_test.json` | 435 | 0.15 MB | **differs** -- the artifact is from an earlier build and is kept as the development record; the export is the shipped build's rerun of the same command |

## What each export records

Recorded by the run that produced it, not written afterwards.

**`audit_unseen_repro.jsonl.gz`** — ALFWorld valid_unseen games 1-30 of the sorted split, 30/30 won, 71 engine seeks; the artifact regenerates exactly

**`battery_final.jsonl.gz`** — compared as battery_repro.json against the committed battery_final.json with the volatile key `tag` stripped; T1-T5 all identical

**`head_to_head.jsonl.gz`** — engine_correct 48/48 reproduces exactly; engine_steps differ in 9 of 48 episodes (mean 1.833 vs committed 1.750). The same difference appears with the export hook absent, so it is a property of the committed artifact (2026-08-31 build), not of the export.

**`head_to_head_deepseek-chat_strong.jsonl.gz`** — engine_correct 48/48 reproduces; engine_steps differ in 9 of 48; hook-independent.

**`head_to_head_gemini-3.7-flash_strong.jsonl.gz`** — engine_correct 12/12 reproduces; engine_steps differ in 5 of 12 (mean 3.167 vs committed 3.250); hook-independent.

**`head_to_head_gemini-3.7-flash_strong_l2345.jsonl.gz`** — engine columns identical episode by episode

**`head_to_head_qwen2.5_7b-instruct_strong_l2345.jsonl.gz`** — engine columns identical episode by episode

**`head_to_head_strong.jsonl.gz`** — engine_correct 48/48 reproduces; engine_steps differ in 9 of 48; hook-independent (control run without --export-dir is identical to the run with it).

**`woz_dynamic.jsonl.gz`** — the committed artifact has no `claims_superseded` or `meta_rationale` key, so it predates nightly consolidation and the meta-controller. Daily brews regenerate as 12/12 on every day in both conditions against the committed 12,4,1,0,2,0 (drives off) and 12,6,5,4,2,3 (drives on).

**`woz_dynamic_night480.jsonl.gz`** — every key and value committed in the artifact is reproduced exactly (0 mismatches over the whole file); the current script writes two keys the artifact predates (claims_superseded, meta_rationale).

**`woz_selfimprove.jsonl.gz`** — the committed artifact has no `patrol` key at all, so it predates the current script; its attempt-1 rows report brewed=false where every current run brews. Hook-independent (control run identical).

**`woz_test.jsonl.gz`** — the run with the hook and the run without it are byte-equal, so the difference is the committed artifact's: it names different item instances (mug_blue vs mug_red) and different room-discovery counts. The battery's own T4 aggregates over the same houses reproduce exactly (w1 1.00 / coverage 0.524, w2 1.00 / 1.0, w3 0.96 / 1.0).


## Artifacts not in the kit

Two reasons. Either the file carries constants of the belief arithmetic
that this release withholds -- a serialised configuration, or a study whose
arms are named for the constants they move -- or it is superseded and the
paper does not cite it.

| file | why it is not in the kit |
|---|---|
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

The build refuses to finish if any of these reaches the kit, and it refuses
on any artifact key that looks like a tuned constant, so the list above is
enforced rather than merely stated.

Copyright (c) 2026 Kiran Nayudu. Data CC BY 4.0.
