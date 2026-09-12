# Embodied demos: the engine driving real-world simulators

Date: 2026-08-31. Machine: Windows 11 laptop, RTX 3070 Laptop GPU (8 GB),
WSL2 (Ubuntu 26.04 + Ubuntu 24.04), WSLg display, software OpenGL (llvmpipe —
the WSL NVIDIA driver exposes CUDA but no GL/EGL acceleration). Everything
below was run on THIS machine; where a simulator could not run here, that is
stated plainly and no result is claimed.

| sim | ran here? | task result | blocker / next step |
|---|---|---|---|
| AI2-THOR 5.0.0 | **YES** (WSL2 + WSLg, llvmpipe) | find-and-fetch, 12 unseen scenes × 8 seeds, occlusion-tested next-best-view planner: **95/96 fetched (99.0%), 95/95 committed localizations correct** (both the commitment and the truth are read from the simulator's `parentReceptacles` field, so this line confirms consistency, not localization from pixels; the 95/96 fetch is graded by the simulator's pickup); seven seeds 12/12 incl. verification seed 137; the one miss fell on the other verification seed (314) | one residual miss (a plate on a side table, budget exhausted, no wrong commitment) |
| AI2-THOR + **real perception** (YOLO-World on 1080² rendered frames, `--perception yolo`) | **YES** (GPU detector, cu128) | same 12 scenes × 8 seeds (3 development, 5 declared before they ran): **83/96 fetched (86.5%), 83/83 commitments correct, 0 wrong**; held-out five alone 52/60 (86.7%), 52/52; median 19 actions per fetch | every miss probed to the detector (8 thin/small-object recall floors, 4 mislabels, 1 sealed in a box; no synonym added, each mislabel a single spawn); the association step is the disclosed tracker stand-in |
| AI2-THOR **lifelong mind** (opt-in, default off) | **YES** | 30-episode habit-world curve, one mind vs a fresh mind per episode on identical placements: **95 → 10 actions** on habit episodes once the habit validated (episode 20, held-out precision 0.73); 30/30 both arms, 0 wrong commitments; a wrong habit costs +1…+7 actions, never a commitment | single scene, oracle perception; cross-house transfer of habits not yet measured |
| Gazebo (gz-sim Harmonic 8.15) | **YES** (WSL2, headless server, CPU-only) | 4-bay logical-camera hunt: **4/4 episodes, target bay correct every time** (1–4 engine actions) | none for the physics-only demo |
| ROS 2 Jazzy + gz-sim (diff-drive over `/cmd_vel`, `ros_gz` bridge) | **YES** (WSL2 Ubuntu-24.04, headless) | topic-level demo **4/4**; packaged stack (`ros2/`: LifecycleNode + `FindObject` action + `IngestClaim`/`QueryBelief`/`Sense` services, Nav2-compatible `NavigateToPose` client) certified **20/20 checks**: 4/4 staged finds, lifecycle gates, false tip verified-then-abandoned over ROS | Nav2/MoveIt 2 themselves not run here (interface-level compatibility, demo driver serves the same action) |
| **ROS 2 + real Nav2 + YOLO-World** (the seams crossed together) | **YES** (Ubuntu-24.04, headless gz, detector on the laptop GPU) | RGB camera on the scout, YOLO-World in the `Sense` slot, detections bound to entities by projecting physics poses through the camera intrinsics; target and three distractors one mesh and one texture, target staged beside a look-alike in 4 of 5 episodes: **26/26 checks**, the four finds with the same inspection sequences as the logical-sensor lanes, the tip verified twice and abandoned after one navigation timeout reordered its inspections, 0 wrong-instance sightings, 0 wrong commitments | association knows the entities' poses (tracker stand-in, disclosed); adapter-side confirmation gate on the engine's verdict, identical in kind to the AI2-THOR adapter's |
| DARPA SubT Virtual (osrf/subt worlds in gz-sim Harmonic) | **YES** (headless, CPU-only) | engine-driven artifact search on DARPA's own circuit practice worlds, 4 worlds (tunnel×2, urban, cave) × 3 seeds: **12/12 reports scored under SubT's rule** (right class, within 5 m) | the competition's ROS Melodic/Ign Dome cloudsim stack is EOL — worlds + scoring rule run, not the full stack; sensing is section-granular logical-camera-grade (disclosed) |
| AWS RoboMaker hospital world (gz-sim Harmonic) | **YES** (headless, CPU-only) | hospital-logistics fetch (first such benchmark to our knowledge): a relocated cart/stand localized among 102 real hospital furniture spots, 8 seeds: **8/8 correct**, search depth 1–21 visits; planted-tip variant (12 seeds × 3 policies): **12/12 every policy**, true tips → 1.0 visits for the engine (6× fewer than sweep), zero wrong commitments; staged-decoy round (6 seeds × 4 policies): engine **6/6, 0 fooled** at its no-decoy cost while class-match policies are fooled 4–5/6 | repo is archived upstream (Apache-2.0, still usable); two world-file fixes + local models needed (recorded below) |
| Space ROS Mars rover demo (Curiosity terrain on ROS 2 Jazzy + gz-sim Harmonic; `space_find.py`) | **YES** (headless, CPU-only, `GZ_PARTITION=space_marine`) | 169-station survey grid, logical 8 m mast sensor, pre-registered placements with ECM readback; 4 seeds × 3 arms: **engine 4/4** (21–58 visits, mean 31.0), sweep 4/4 (45.0), random 4/4 (26.0); 0 wrong commitments | uniform-prior protocol: completeness + commitment only, no efficiency claim; planted-tip/decoy variant pre-registered, not run; not "on Space ROS" (demo packages on vanilla Jazzy) — `docs/SPACE_MARINE.md` |
| Project DAVE seabed survey (`dave_ocean_models` world; `marine_find.py`) | **YES** (headless, CPU-only, gravity zeroed, includes pinned static) | 70 stations, 11 unique-instance seabed targets, BlueView P900 footprint with declared echo curve; 4 seeds × 3 arms: **engine 4/4** (2–12 visits, mean 7.75), sweep 4/4 (21.25), random 4/4 (4.25); 0 wrong | same reading; no sonar perception, no driving; HoloOcean blocked on WSL2 (Vulkan), Stonefish viable fallback |
| Habitat (habitat-sim 0.3.3) | NO (installs, cannot render) | — | every published build variant creates its windowless GL context via EGL and rejects WSLg's software-only stack (`unable to find CUDA device 0 among 1 EGL devices`; only device is `GL_MESA_device_software`); verified on both the headless and windowed conda builds; next: native Linux boot or a cloud GPU box — the env then works unchanged |
| iGibson / OmniGibson | NO (partial install) | — | iGibson is superseded upstream by OmniGibson; OmniGibson 1.x + Isaac Sim has a native-Windows path and this RTX 3070 8 GB matches NVIDIA's minimum spec — `pip install omnigibson` succeeded into `C:\dev\og-env` (Python 3.10), but the remaining Isaac Sim + torch + assets download (~15–20 GB plus shader compilation) exceeded this session's timebox; next commands recorded below |

## AI2-THOR: the engine fetches objects in 3D houses

`adapters/thor_embodied.py` + `experiments/embodied/thor_find.py` — the same
division of labor as the ALFWorld 134/134 adapter (docstring discloses it in
full): the ENGINE decides every step of the search (belief scores, expected
information gain, absence bookkeeping, refuted-fallback); the ADAPTER only
translates simulator visibility metadata into typed OBSERVED claims and engine
actions into Teleport/OpenObject/PickupObject calls. No LLM anywhere. Success
is the simulator's own `PickupObject lastActionSuccess` signal.

Protocol: object placement shuffled per-episode (`InitialRandomSpawn`,
seeded); target class chosen evaluator-side among placeable pickupables; the
engine receives the receptacle list as bare LOCATION entities (the analogue of
ALFWorld's opening room listing) and nothing about contents. FloorPlan1 was
the development scene; the 12 evaluation scenes (kitchens 2–5, living rooms
201–203, bedrooms 301–303, bathrooms 401–402) were run untouched.

Results (seed 7, `data/artifacts/embodied/thor_find_eval.json`):

| scene | target | outcome | engine seeks→acts | sim actions | found at | ground truth |
|---|---|---|---|---|---|---|
| FloorPlan2 (kitchen) | plate | **fetched** | 7 | 51 | drawer_11 | drawer_11 |
| FloorPlan3 (kitchen) | spatula | **fetched** | 2 | 15 | microwave_1 | microwave_1 |
| FloorPlan4 (kitchen) | cup | **fetched** | 1 | 4 | diningtable_1 | diningtable_1 |
| FloorPlan5 (kitchen) | butterknife | **fetched** | 6 | 21 | fridge_1 | fridge_1 |
| FloorPlan201 (living) | laptop | **fetched** | 6 | 28 | armchair_1 | armchair_1 |
| FloorPlan202 (living) | statue | **fetched** | 7 | 9 | coffeetable_1 | coffeetable_1 |
| FloorPlan203 (living) | remotecontrol | **fetched** | 1 | 13 | coffeetable_1 | coffeetable_1 |
| FloorPlan301 (bedroom) | keychain | failed | — | 60 (budget) | — | bed_1 |
| FloorPlan302 (bedroom) | book | **fetched** | 1 | 4 | bed_1 | bed_1 |
| FloorPlan303 (bedroom) | cloth | **fetched** | 1 | 5 | bed_1 | bed_1 |
| FloorPlan401 (bathroom) | toiletpaper | **fetched** | 8 | 12 | shelf_4 | bathtub_1 or shelf_4 |
| FloorPlan402 (bathroom) | tissuebox | failed | — | 60 (budget) | — | shelf_1 |

**10/12 fetched. Every localization the engine committed to matched ground
truth.** The searches are visibly non-trivial: the plate hunt opened and ruled
out ten receptacles before drawer_11; the butterknife required opening the
fridge; the toiletpaper hunt worked through eight candidate spots.

**The perception campaign (five diagnose→fix→re-test iterations, same
session):** the first honest multi-seed sample scored 64% (23/36) — the
engine's search was already sound (100% localization precision), but the
adapter's single-pose camera missed small or occluded targets. Each iteration
diagnosed the exact failing episodes with targeted probes, fixed the physical
root cause adapter-side (never the engine, never target-aware), and re-ran
the full battery: 64% → 75% → 88% → **93.75%**. Probe-verified fixes, each
mapped to a measured failure: walk-along sweeps of large surfaces with
coverage cycling across revisits; door-reopen before grasping;
approach-then-grasp with a crouched retry and interactable-pose fallback;
interior-bottom aiming and a rim steep-glance for bins; bounding-box-center
(not pivot) aiming plus a vertical look-at spread for tall furniture; a
dispersed near-spot arc for large openables (a fridge's top shelf is visible
past its open door from exactly one lateral spot); an elevated-bottom
discriminator so counter fixtures get one look but floor-standing stools keep
full treatment; a crouched under-overhang glance for tucked seats; and an
action budget re-based 60 → 250 to preserve search depth as a "check" grew
from one teleport to a full sensing pass (per-episode counts still reported).

**The next-best-view planner (second campaign, same session):** the
heuristic pose synthesis above had a measured ceiling of 93.75% (90/96) —
one failure class, small items on/behind non-convex or cluttered surfaces
(an L-counter's notch, the floor behind a garbage can, a cluttered sink
basin). Its designed successor replaced it: classic occlusion-tested
next-best-view. Per receptacle, the sim's own valid-placement surface
coordinates (`GetSpawnCoordinatesAboveReceptacle` — surface topology a
bounding box cannot express) are gridded into sample points, with interior
twins clamped inside the box for door-less cavities; every reachable
position × {stand, crouch} (camera heights measured from the sim) is
ray-cast against them with fixed-furniture AABBs as occluders; greedy
set-cover picks the pose set, yaw/pitch fitted inside FOV margins. The
enclosed-furniture arc branch (fridges, cabinets) and the measured
tucked-seat glance were kept; the legacy geometry remains only as a
fallback when the ray-cast finds no sight line.

Probe-measured model facts the planner encodes (each fixed a diagnosed
failing episode, none target-aware): THOR's visibility radius gates on
the BODY (horizontal), not the 3D eye-to-point distance; looking into an
open-top container needs the eye ≥ 0.45 m above the rim (a crouched
camera 0.4 m over a can's rim is blind where a standing one sees in);
cavity contents are direction-dependently visible behind unmodelable
mesh (a basin's contents visible only from the west while a steep look
from the south stayed blind) — so interior samples demand coverage from
three distinct 45° approach sectors; a host's box never occludes its own
nested receptacle (the counter has a cutout there); and the floor pose
budget scales with floor area (a 189-sample living-room floor capped at
12 poses left a box in its east half unfindable). Two adapter
bookkeeping fixes surfaced the same way: a sighting with multiple THOR
parents (bottle in a garbage can lists the can AND the floor) is now
credited to the smallest-footprint parent, and a seek that learns
absences about a KNOWN instance no longer counts as having learned
nothing and gives up.

Final battery — 8 seeds × 12 scenes on the committed build (1ba0dec),
per-seed artifacts in `thor_find_eval_s{7,11,23,42,99,137,256,314}.json`:

| seed | 7 | 11 | 23 | 42 | 99 | 137* | 256 | 314* | total |
|---|---|---|---|---|---|---|---|---|---|
| fetched | 12 | 12 | 12 | 12 | 12 | 12 | 12 | 11 | **95/96 (99.0%)** |

*never used for diagnosis — pure verification seeds. Localization
precision 95/95 — not one wrong commitment across the whole campaign;
found == fetched everywhere. Mean sim actions per episode 18–43 by seed.

The one residual miss (honest): seed 314, FloorPlan3, a plate on a side
table — 250-action budget exhausted with no sighting and no wrong
commitment. Accepted as-is rather than iterated on (placements are not
bit-stable across process launches — measured 2026-09-01: bit-stable across
`reset()` calls WITHIN one controller process, 0/30 pickupables differ over
three seeds, but a new launch redraws — so each battery run redraws its
episode configurations; chasing the last placement is whack-a-mole the
detector front-end is designed to end). Two measured negatives remain recorded so
they are not retried: `GetInteractablePoses` as search vantages (4/12 vs
10/12 — those poses optimise touching furniture, not seeing its
contents; it is still used for grasping) and naive look-at sampling from
`GetSpawnCoordinatesAboveReceptacle` WITHOUT visibility ray-casting
(regressed seed 7 from 12/12 to 9/12; the ray-cast + set-cover above is
precisely what it lacked).

One reproducibility caveat: AI2-THOR's `InitialRandomSpawn` produced
different placements across runs despite a fixed `randomSeed`, so episode
placements are not bit-stable the way the engine's own benchmarks are; the
table above is the committed run's data, and the JSON artifact carries every
per-episode detail.

Honest scope notes:
- Locomotion is abstracted to "go to receptacle X" (Teleport to a vantage pose
  from the sim's own GetInteractablePoses/reachable-positions API), exactly as
  ALFWorld's `go to` command abstracts walking. The engine's contribution is
  *which* receptacle to check and *when to stop* — not footstep control.
- Perception in the battery above is the simulator's per-frame `visible`
  flag (1.5 m visibility distance), not a learned detector. The real-detector
  variant (YOLO-World on rendered frames through the
  `ingestion/vision_adapter.py` seam) is the next section, with its own
  numbers.
- Setup queries (receptacle registry + vantage poses) are not counted against
  the episode's 60-action budget; every in-episode Teleport/Open/Close/Pass/
  Pickup is.

## AI2-THOR with real perception: YOLO-World on rendered frames

`--perception yolo` replaces THOR's metadata `visible` flags with an actual
detector on the rendered RGB frame (`src/robot_mind/adapters/thor_yolo.py`;
YOLO-World `yolov8x-worldv2`, ultralytics, GPU ~42 ms/frame). Division of
labor, and what it does and does not prove:

| module | what it does | honesty note |
|---|---|---|
| detector | open-vocabulary YOLO-World prompted once with a FIXED list of the 62 iTHOR pickupable types (a trained detector's class list: never scene-derived, never told the target) | its confidence is what enters the ledger |
| associator | binds each detection to a rendered instance by IoU ≥ 0.35 against the simulator's instance-segmentation 2D boxes, same class or a fixed visual-synonym group | the stand-in for a tracker/data-association module; it can only ACCEPT detector output — a hallucinated box with no instance under it is dropped, an instance the detector missed stays unseen. It uses the sim's instance identity, so **wrong-instance commitments are impossible by construction**; detector recall is the honest bottleneck |
| seam | every accepted sighting is a `DetectionEvent` → OBSERVED claim through `ingestion/vision_adapter.py`, carrying the detector's own number | the engine's anchor/resolve path is status-gated, not confidence-gated: a fresh claim-grade sighting resolves, its confidence is weighed in belief and shown in the proof |

Consequences, measured rather than assumed: an object THOR flags visible but
the detector misses is not seen (recall cost); an object beyond THOR's 1.5 m
cliff that the detector finds in-frame is seen; the failure mode the
front-end adds is missed sightings, never false ones. The oracle path is
byte-identical to before.

**Fix campaign at 480² render (imgsz 640), seed-7 smoke 5/12 → 10/12
(commits 6e303fa → 2cf2835).** Every fix adapter-side, target-blind, probed
against its diagnosed failing case first: (1) synonym groups — the detector
localizes perfectly but names sibling classes (WineBottle→"Bottle" 0.83 at
IoU 0.88, Statue→"TableTopDecor" 0.90 at 0.95, Cloth→"Towel", later
DishSponge↔"Book"), so association accepts a fixed group while localization
still gates on the instance's own box; (2) claim-backed registration — a
sub-gate detection never mints an entity (a claimless ghost once became the
seek target); (3) absence honesty under weak evidence + one step-back vantage
for small receptacles — detection is view-asymmetric (a pot 0.67 from a
lateral vantage, ~0.15 from its burner's own close crop) and a strong
sighting/weak absence pair oscillated for 29 seeks; (4) proven-view memory —
a vantage that produced a claim-grade detection leads the next visit to that
parent (toilet paper: 9 cross-room sightings vs 10 blind own-pose visits);
(5) two-sector coverage of large open surfaces — pickupable clutter is
invisible to the target-blind planner (a cup was a 28 px sliver from both
same-side table poses); (6) claim gate 0.15 → 0.05 — association supplies
the precision, so a matched weak detection is a real object seen badly.
Measured dead ends, not to retry: `ChangeFOV` is a silent no-op on the render
(boxes pixel-identical at 30° and 90°, re-measured at 1080²); upscaling
imgsz to 1280 from a 480² render hurts as often as it helps. Three seeds at
480² on that build scored 27/36 (s7 11/12, s11 8/12, s23 8/12; every miss a
small object the detector never associated — the 480² artifacts were
superseded by the decision below and ship under
`data/artifacts/embodied/superseded_480/`).

**Decision: render at 1080² (imgsz 1088), the proof battery = seeds 7, 11,
23, one seed at a time to 12/12 with a probe-first fix loop.** Cost: ~4–5×
the wall time per episode (llvmpipe software rendering), nothing else.

- **Seed 7, first pass at 1080²: 12/12** (mean 21.7 env actions). The 480²
  miss — a dish sponge deep in a fridge, a sub-300 px sliver at 480² — is
  detected and fetched in 46 actions.
- **Seed 11, first pass: 10/12.** Two misses, both probed
  (`scripts/thor_detector_probe.py` renders every planned and approach
  vantage of the target's receptacle and prints the detections overlapping
  its instance box): a **fork inside a garbage can** is never associated in
  250 actions (76 receptacle visits, no Fork match; open-vocabulary detector
  floor for a tined sliver seen over a rim — residual, disclosed); a **soap
  bar in a bathtub** is a different story. The detector saw it at 0.57–0.74
  from the bathtub's own vantage on five consecutive looks, the reasoner
  RESOLVED it at the bathtub, and the engine still reported not-found: the
  runner's episode-level confirmation needs ≥ 0.9, and the session's
  "learned nothing, give up" test ran before its "does the engine resolve the
  target where I am standing" check. The fix is ordering only
  (`ThorSession.find`: ask the engine's verdict before giving up); oracle
  sightings are 0.97 and confirm inside the runner, so the shipped oracle
  battery is untouched by it. Verified on the failing case: FloorPlan401
  seed 11 fetches the soap bar in 61 actions (the trace shows the verdict
  `resolved=bathtub_1 robot=bathtub_1` firing right where the old code gave
  up). The fork probe, for the record: from the garbage can's planned
  vantages the fork is a 9×63 or 26×58 px box and the only overlapping
  detections are SoapBar 0.03 at IoU 0.20, TissueBox 0.18 at IoU 0.19 and
  ButterKnife 0.12 at IoU 0.12 — nothing reaches the 0.35 association gate.
- **Proof battery on the fixed build (commit 1a850b1; artifacts
  `thor_find_yolo1080_s{7,11,23}.json`): 31/36 fetched (86.1%), 31/31
  committed localizations correct, zero wrong commitments.** Median 17 env
  actions per fetched episode (mean 31.1); every miss ran its full 250-action
  budget and reported not-found. (The held-out seeds follow below.)

| seed | fetched | mean env actions (all / fetched) | misses, each probed |
|---|---|---|---|
| 7 | **12/12** | 21.7 / 21.7 | — |
| 11 | **11/12** | 69.7 / 53.3 | fork inside a garbage can (detector floor) |
| 23 | 8/12 | 93.1 / 14.6 | credit card ×2 (flat on a coffee table, on a dining table), keychain inside a garbage can, candle on a toilet tank — all thin/tiny-object detector floors, see below |

  Read against the same three seeds at 480² (27/36 with the same object
  classes missing plus several the higher render rescued), the resolution
  decision bought three episodes and the confirmation fix one; what remains
  is the detector, not the search: with a real detector in the loop the
  engine still never commits to anything it has not seen, and 31 of 31
  commitments were right.

- **Held-out seeds (42, 99, 137, 256, 314; declared on commit 8b4a83f
  before any ran, launched on the frozen build, touched by no fix;
  artifacts `thor_find_yolo1080_s{42,99,137,256,314}.json`): 52/60
  fetched (86.7%), 52/52 committed localizations correct, zero wrong
  commitments — the development seeds' rate reproduced.** Over all eight
  seeds: **83/96 (86.5%), 83/83 correct, 0 wrong**; median 19 env actions
  per fetched episode (mean 30.3). Wilson 95%: all eight [0.78, 0.92],
  held-out five [0.76, 0.93], development three [0.71, 0.94].

| seed | fetched | median env actions (fetched) | misses, each probed |
|---|---|---|---|
| 42 | **11/12** | 20 | fork inside a garbage can (FloorPlan2): 9×63 to 26×58 px from the can's vantages, nothing above IoU 0.20 overlapping (SoapBar 0.03, TissueBox 0.18, ButterKnife 0.12), the same numbers as seed 11's fork (the can's default pose) — recall floor |
| 99 | **12/12** | 25 | — |
| 137 | **11/12** | 19 | butter knife inside a garbage can (FloorPlan2): 3×78 to 26×73 px from the can's vantages; TissueBox 0.15 and HandTowel 0.04 at IoU 0.24, SoapBar 0.03 at IoU 0.39 from an approach pose (below the 0.05 gate and not a Knife synonym) — recall floor |
| 256 | 8/12 | 17 | butter knife on a dining table (FloorPlan4): 4×3 px from the table's planned vantages; from an approach pose at 0.7 m, 51×98 px, localized at IoU 0.93 but read as "Pen" 0.25 / "Pencil" 0.19 — mislabel. CD (FloorPlan301): inside a box on the bed, never rendered in any frame (visibility flag true, no pixels) — sealed in a container the adapter does not open. Alarm clock on a shelf (FloorPlan303): localized at IoU 0.92–0.97 from planned and approach poses but never named above 0.10 (Plate 0.10, Book 0.08; Box 0.27 only at IoU 0.05) — recall floor. Plunger on a shelf (FloorPlan401): 173×493 px, read as "BaseballBat" 0.09 / "Spatula" 0.15 at IoU 0.84–0.98 — mislabel |
| 314 | 10/12 | 19.5 | pepper shaker on a dining table (FloorPlan4): out of frame from the table's planned vantages; from an approach pose at 0.7 m, 31×71 px, localized at IoU 0.92 and read as "SoapBottle" at 0.92 — a confident mislabel. Credit card on a chair (FloorPlan301): 13×39 px, nothing above the gate overlapping (CellPhone 0.22 at IoU 0.05, Book 0.04) — recall floor |
| **held-out** | **52/60** | 19.5 | |
| **all eight** | **83/96** | 19 | |

  Run record: the five seeds were launched together at 22:25 on
  2026-09-01; five concurrent 1080² detector processes saturated the
  8 GB GPU and completed no episode in 56 minutes, so seeds 256 and 314
  were stopped before their first episode and re-queued behind the other
  three (at most three concurrent). Two episodes — FloorPlan203 on seeds
  42 and 137 — crashed at simulator start-up (a Unity `Initialize`
  timeout under that contention, before a target had been chosen) and
  were rerun alone with the same seed as **fresh draws** (AI2-THOR's
  `InitialRandomSpawn` redraws per launch, so a rerun is a new placement,
  not a reproduction; `scripts/thor_merge_rerun.py`): remote control
  fetched in 13 actions, cellphone in 13. The crash records stay in the
  artifacts marked `superseded_by_rerun`; `scripts/thor_yolo_table.py`
  counts live episodes only and lists the crashes. Wall time is not a
  graded quantity: the detector is deterministic per frame and the
  budget is in actions, so contention changes only the clock.

  Read together, the thirteen misses of the eight-seed battery fall into
  three classes. **Recall floor (8):** thin or small objects the detector
  never names above the gate from any reachable vantage — two forks and a
  butter knife inside FloorPlan2's garbage can (seeds 11, 42, 137), a
  keychain inside a can (23), three credit cards lying flat (23 ×2, 314),
  and seed 256's alarm clock, localized at IoU 0.97 but never named above
  0.10. **Mislabel (4):** the detector localizes the object (IoU
  0.84–0.93) and calls it something outside the instance's synonym group
  — a jar candle "Cup" at 0.54 (23), a pepper shaker "SoapBottle" at 0.92
  (314), a butter knife on a dining table "Pen" at 0.27 (256), a plunger
  "Spatula"/"BaseballBat" at 0.15 (256). Each is a single spawn, so under
  the campaign's two-independent-spawns rule none enters the synonym
  table; a Candle/Cup, PepperShaker/SoapBottle, ButterKnife/Pen or
  Plunger/Spatula group would each rescue one episode and each waits for
  a second measurement. **Sealed in a container (1):** seed 256's CD sat
  inside a box on a bed and appeared in no frame at all; the adapter opens
  openable receptacles (fridges, cabinets), not a box, and the oracle
  battery's visibility flag would have "seen" it. Two adapter-side
  observations, not fixes: FloorPlan4's dining table is framed only at
  its near end by the table's planned vantages (both dining-table misses
  rendered only from the probe's 0.7 m approach poses), and the two
  garbage-can misses on FloorPlan2 share one physical configuration. In
  every one of the thirteen the engine reported not-found after its
  budget and committed to nothing.

Residual class at 1080², honestly stated: thin or tiny objects — a fork seen
over a can's rim, a keychain inside a can (seed 23: a 6×4 to 16×6 px smudge
from every planned and approach vantage, no detection overlapping it at
all), two credit cards lying flat (seed 23: 45×10 px from the coffee
table's planned vantage and "Book" at 0.08 even from 0.36 m crouched; on
the dining table "Pen" at 0.02 from 0.58 m) — sit below open-vocabulary
recall from every reachable vantage; the engine reports not-found and never
commits to anything else. One miss is a mislabel rather than a floor: the
candle on the toilet tank (seed 23) is localized at IoU 0.91 but named "Cup"
at 0.54 (a jar candle does look like a cup). A Candle↔Cup synonym would
rescue it, but the campaign's rule is two independent spawns before a
synonym is added, and this is one; it stays a miss until a second
measurement says otherwise. The association step is the disclosed oracle stand-in for a
tracker; with a real tracker, a low-confidence label could bind to the wrong
instance, and the engine's verify-before-trust loop (re-inspection,
absence bookkeeping) is what would catch it — that is the seam this
front-end was built to exercise.

Repro (WSL Ubuntu, `~/alfworld-env`; weights in `/root/yolo/`; torch must be
the cu128 wheel — the default PyPI torch refuses the 12.8 driver):

```
~/alfworld-env/bin/python experiments/embodied/thor_find.py \
    --scenes FloorPlan2,FloorPlan3,FloorPlan4,FloorPlan5,FloorPlan201,FloorPlan202,FloorPlan203,FloorPlan301,FloorPlan302,FloorPlan303,FloorPlan401,FloorPlan402 \
    --seed 7 --width 1080 --height 1080 --perception yolo \
    --weights /root/yolo/yolov8x-worldv2.pt \
    --out data/artifacts/embodied/thor_find_yolo1080_s7.json
```

## Real pixels: a phone camera in a house (the detector's word alone)

The one sensing abstraction every battery above kept, an association step
that knows which entity a detection belongs to (AI2-THOR's instance boxes,
the Nav2 arena's projected poses), is removed here, and so is the
simulator. The owner films six zones of a lived-in house with a hand-held
phone; the engine searches the footage. Full protocol, every sitting's
verdict written before its detector ran, the recording sheets, and the
per-episode analysis: `docs/PHONE_PROTOCOL.md`. Harnesses
`experiments/embodied/phone_find.py` and `phone_tips.py`; sense models in
`src/robot_mind/adapters/phone_vocab.py`.

| item | protocol |
|---|---|
| zones | 1 green sofa, 2 black desk, 3 kitchen island, 4 marble table, 5 blue bin, 6 navy bench |
| classes | Mug, Book, Bowl, RemoteControl, Bottle (a STANLEY tumbler), CellPhone |
| a sitting | six rounds; each round's six placements drawn from a seed and committed as a manifest before filming; one 3–5 s 1080p pan per zone per round; 36 clips |
| sensing | the clip is decoded, YOLO-World (`yolov8x-worldv2`, input 1088) runs on every tenth frame with a fixed household vocabulary, and the per-zone maximum enters the ledger as an OBSERVED `LOCATED_AT` claim at the detector's number; claim gate 0.05; no instance id, no IoU gate, no association |
| engine | briefed with the target class and the six zone names only; the phone adapter sets `sighting_resolves_at` to the loop's confirmation confidence (0.9): a weaker sighting is a hypothesis, unsearched zones stay in the beam, an exhausted search commits to its uniquely best-supported zone. Engine default unchanged (0.0); every native suite byte-identical |
| arms | engine; sweep (zones 1..6, commit on the first accepted sighting); random (seeded order, same rule); tips: one zone reported at 0.75 per episode, 18 true and 18 false per sitting, plus a tip-follower |
| grading | commitment == the manifest's zone; a miss and a wrong commitment are counted apart |

**The sittings, in order (each graded footage is checked by eye against
its manifest before any detector runs; the verdicts are in the protocol
doc).**

| sitting | pre-registered | find | tips true / false | note |
|---|---|---|---|---|
| first (pilot, 30 ep.) | engine as then shipped | 8/30 → 26/30 after the fixes | — | filmed off its manifest (placements rotated); disclosed pilot, never a paper number |
| second, 36 ep. | engine as then shipped, THOR vocabulary | **12/36** = sweep 12, random 13 | 16/18 / 3/18 | raw detector output found the resolve-on-sighting rule's blind spot; three fixes below; re-run on the same clips 29/36 (7 wrong, all perception) |
| third, 36 ep. | fixed engine, sense model v2 | **33/36** (sweep 13, random 20) | 15/18 / 18/18 | 3 wrong, all perception: remote read as phone above a phone without its placemat (×2), tumbler read as soap bottle |
| fourth, 36 ep. | fixed engine, sense model v3 | **36/36** (sweep 24, random 27) | **18/18 / 18/18** | tip-follower 18/18 / 13/18; 0 of 18 commitments at a false tip's zone; every class 6/6; 5.03 mean visits |

**The three fixes after the second sitting (docs/PHONE_PROTOCOL.md, "What
the run measured").** (1) Engine: `Reasoner.locate` resolved any fresh
uncontradicted sighting regardless of confidence, right wherever an
inspection can confirm a sighting (warehouse, IoU-gated simulators), wrong
on raw detector output where the same clip returns the same detection;
`BeliefConfig.sighting_resolves_at`, set by the phone adapter to 0.9, default
0.0 (measured on the native suites: T1 actions 1.74 → 2.48 at the bar, so the
default stays). (2) Harness bookkeeping: absence was recorded under the class
name only and a demoted weak sighting made its zone "unsearched" again,
spending the budget on re-visits. (3) Sense model v2: aliases (tumbler,
water bottle → Bottle; smartphone, iphone → CellPhone), distractor prompts as
their own classes (power bank, stone dish, ...), one label per object where
a distractor box overlaps.

**Sense model v3, chosen on graded footage, then tested once.** One label
per object across every class (the strongest overlapping box keeps its
label) and synonym folding (each graded class's THOR synonym group folded
into its per-clip maximum), same weights and prompt list. Replayed offline
from raw detection dumps: second sitting 29/36 → 29/36, third 33/36 → 35/36
(tips 15/18 → 17/18). YOLOE backends (25/36 on the second sitting) and
visual exemplars were measured and not picked. Pre-registered for the
fourth sitting in commit `673e3fd` before any of its footage existed.

**The fourth sitting's one close call.** Round 19: the phone on the blue bin
read "cellphone" 0.750 (under the bar), the tumbler on the sofa read
"cellphone" 0.752 (and "bottle" 0.84). After all six zones the belief was
0.51 for the bin against 0.49 for the sofa (the later sighting weighs
slightly more), the verdict named the bin, the robot returned and committed
(seven visits). An argmax over the detector would have picked the sofa. In
the tips run the false tip pointed at that sofa; the engine still committed
to the bin, the sweep and the tip-follower did not. Two other readings sat
under the bar and cost nothing: the remote on the bench placemat read
"cellphone" 0.896 (the engine had resolved at the island, 0.957, before
reaching it) and the tumbler read "remote" 0.892 against the remote's 0.980.
Seventeen of the 36 true sightings were under the bar (the tumbler in every
round, 0.83–0.89): those hunts ended by exhaustion at seven visits, none
wrongly. Replay any engine episode from its recorded detections with
`scripts/phone_replay_trace.py data/artifacts/embodied/phone_find_s4.json 19 CellPhone`.

**Footage facts recorded before the run.** All 36 clips per manifest by
eye; phone on the light placemat on the bin (round 19) and the bench
(round 31) as the sheet requires; the remote also on the placemat in five
of its six clips (not asked for; disclosed); every round filmed in the
order 1, 2, 3, 4, 6, 5, identical across rounds (no placement leaks; the
harness reads clips by zone name). Footage is not in the repository
(`data/phone*/`, gitignored); it is available on the same request basis as
the artifact bundle.

**Scope.** No robot (the camera was carried by hand), no map (the zones
were declared), one house, one camera, one sitting of 36 (Wilson lower
bound 0.90). The detector confusions of the earlier sittings (remote as
phone, tumbler as something else) are still present at 0.75–0.90; this
sitting's rules kept them below the phone's own readings.

## Lifelong mind: the engine keeps what it learned (opt-in, default off)

Every battery above runs a FRESH mind per episode, so every number measures
cognition from a cold start. `EngineConfig.lifelong` (default OFF, so all of
those numbers byte-reproduce) turns on the alternative a deployed robot
actually wants: a persistent store of its OWN confirmed fetches, from which
two learned artifacts return on the next episode —

- **habits**: class-level habitual locations ("mugs live on countertops"),
  mined with the engine's standard rule lifecycle (candidate on support,
  provisional on training precision, VALIDATED only on held-out fetches the
  miner never saw), instantiated for the current house (every countertop
  in it) and handed to the reasoner as an **advisory** blind-search prior.
  Advisory by construction: an observed absence removes a room from that
  prior entirely (engine invariant, unchanged), so a habit can steer the
  first look and never outvote what the robot then sees;
- **bandit statistics** (optional): the contextual bandit's context/action
  estimates, serialized between episodes.

Learning is from outcomes the robot verified itself (a pickup the simulator
confirmed), never from an evaluator's ground truth. `learning/lifelong.py`,
`tests/test_lifelong.py`.

**Learning-curve protocol (`experiments/embodied/thor_lifelong.py`),
evaluator-side and disclosed.** One scene (FloorPlan1), one target class
(mug), 30 episodes with seeds 1–30. Each episode shuffles the house
(`InitialRandomSpawn`), then with probability 0.75 (seeded) the evaluator
moves the mug onto its HABITUAL receptacle — the "things have usual places,
with noise" regularity of a real household, which iTHOR's uniform spawn lacks
— otherwise the shuffled placement stands. The habitual receptacle was chosen
by a measured sweep (`scripts/thor_lifelong_select.sh`,
`lifelong_sel_*.json`): countertop_2 is the only candidate the cold-start
search reaches late (95 actions, 4 seeks) yet resolves with one direct look
(2 engine actions); stools, shelves and burners cost 8–29 from cold, leaving
nothing for a habit to save. Two arms run the identical placement (the spawn
is bit-stable within one controller process across resets; the staging is
deterministic): **fresh** = a new mind per episode (the protocol of every
shipped battery), **lifelong** = one mind across the 30. Oracle perception at
480²: the question is whether cognition carries knowledge forward, not
whether the detector sees.

| | fresh mind | lifelong mind |
|---|---|---|
| fetched | 30/30 | 30/30 |
| wrong commitments | 0 | 0 |
| mean env actions, all 30 | 79.7 | **51.4** |
| first third (episodes 1–10) | 59.4 | 59.4 (identical: nothing validated yet) |
| last third (episodes 21–30) | 95.0 | **10.0** |
| habit episodes after validation (10/10) | 95 each | **10 each** |
| habit validated at | — | episode 20: support 15, precision 0.80, held-out 0.73, reliability 0.73 |

The curve is a step, not a slope: the mind is indistinguishable from a
cold start until the lifecycle lets the habit through, then every visit to
the habitual counter costs one look instead of a four-seek sweep of 37
receptacles. That is the lifecycle discipline working as intended — 20 own
fetches, with mixed placements diluting the class, before a rule is trusted
— and it is the same machinery that promoted the warehouse cart-transport
rule (`docs/PAPER.md`). Artifact: `thor_lifelong.json`.

Two things measured on the way, kept for the record. The first curve
(`thor_lifelong_run1_countertop2.json`) validated the same habit and gained
NOTHING (95 vs 96): a class habit was being instantiated on the lexically
first countertop while the mug lived on countertop_2 — a rule now carries
every instance of its class (`scope["rooms"]`; a rule without it behaves
exactly as before, test-covered). And in this run the seeded coin drew
habit episodes for all ten post-validation episodes, so the cost of a
habit that turns out WRONG was measured separately: the same learned mind
continued into four episodes where the mug was staged off the habitual
countertop — three off any countertop; in episode 31 it sat on the coffee
machine, whose parent receptacle is countertop_3, so the class-level habit
still covered that one (`--keep-store --seed-start 31 --p-habit 0.0`,
`thor_lifelong_wronghabit.json`) against a cold start on the same
placements — fresh 11 / 25 / 78 / 22 actions, lifelong 12 / 12 / 85 / 7,
4/4 fetched and zero wrong commitments in both. A habit that is wrong costs
the one or a few looks its rooms take (+1, +7) and, because it reorders
the whole sweep, occasionally lands earlier by luck (−13, −15); it never
costs a commitment. That is the advisory property, measured.

Repro:

```
~/alfworld-env/bin/python experiments/embodied/thor_lifelong.py \
    --scene FloorPlan1 --target mug --habit-recep countertop_2 \
    --episodes 30 --p-habit 0.75
```

## DARPA SubT Virtual: the engine searches DARPA's own worlds

`experiments/embodied/subt_find.py` — the engine hunts competition
artifacts (backpack, phone, drill, extinguisher, survivor, gas, vent,
helmet, rope) in the SubT Virtual Testbed's circuit practice worlds,
loaded content-unmodified in gz-sim Harmonic, headless CPU-only. The
DARPA cloudsim stack (ROS Melodic + Ignition Dome, competition ended
Sept 2021) is EOL and does not run here; what runs is DARPA's worlds and
DARPA's scoring rule — a report scores iff the artifact class is right
and the reported position is within 5 m of truth.

The engine's map is the world's tile list (bare LOCATION entities with
tile coordinates, parsed from the same SDF the sim runs); contents are
never given. A visit teleports a spawned scout to the tile and senses at
the world's own section granularity: the artifacts NEAREST the visited
tile (urban/cave "tiles" are 25–50 m multi-storey sections — measured:
16 of urban_01's 20 artifacts sit beyond 10 m of every tile-center
vantage, so a fixed-radius bubble cannot represent surveying a section).
Sensing reads the sim's physics state exactly (the fidelity of Gazebo's
logical camera — no rendering, no occlusion test), so the position half
of the scoring rule is inherited from the sensor; what is genuinely
graded is the SEARCH: whether the engine's tile-by-tile hunt, on its
belief/EIG/absence machinery alone, reaches sensor contact and commits
to the right place and class. Locomotion is teleport-abstracted, as in
every adapter here.

Results — 4 worlds × 3 seeds on one build, one target class per episode
(seeded, evaluator-side), budget 250 tile-visits
(`data/artifacts/embodied/subt_find.json` + `subt_urban01.json`):

| world | tiles | seed 7 | seed 11 | seed 23 |
|---|---|---|---|---|
| tunnel_circuit_practice_01 | 438 | rescue_randy, 87 visits | backpack, 26 | rescue_randy, 87 |
| tunnel_circuit_practice_02 | 192 | extinguisher, 12 | extinguisher, 12 | backpack, 75 |
| urban_circuit_practice_01 | 34 | phone, 6 | backpack, 2 | vent, 7 |
| cave_circuit_practice_01 | 57 | backpack, 12 | rescue_randy, 22 | rescue_randy, 22 |

**12/12 reports scored (SubT rule).** Two presentation caveats from an
independent audit of these rows, stated here so the table cannot
oversell: `dist_m` is 0.0 *by construction* (the sensor and the
evaluator read the same scene snapshot — the 5 m criterion grades the
abstraction, not a localization estimate; the genuinely graded quantity
is the search, as disclosed above), and episodes whose seeds draw the
same target class are byte-identical deterministic replays, so the 12
episodes comprise 9 distinct searches (the audit re-derived every visit
count from world geometry alone: under uniform priors the engine's
planner sweeps nearest-unvisited-first, and each reported instance is
the first of its class along that sweep). Targets are always present —
there are no absent-target episodes in this protocol.

Three integration lessons are recorded in the code: SubT's world plugins suppress gz-sim's default
systems, so the launcher injects only the standard
Physics/UserCommands/SceneBroadcaster infrastructure into a patched copy
(world content byte-identical); gz's `scene/info` service serves the
LOAD-TIME scene graph and never live poses, so scout motion is verified
once per world through the ECM state (`gz model -p`) before any episode
is trusted; and the cave tile models' legacy Ogre material-script
fallbacks fail Harmonic's strict URI resolution hard enough to abort the
whole world load — `scripts/sanitize_fuel_material_scripts.py` strips
them from the local Fuel cache (visual fallbacks only; the PBR material
stays; the headless server renders nothing).

## Hospital logistics: a first-of-its-kind fetch benchmark

`experiments/embodied/hospital_find.py` — per episode the evaluator
relocates one logistics item (a mop cart, a patient wheelchair, a
surgical trolley...) beside a seeded furniture spot on the AWS RoboMaker
hospital floor (aws-robomaker-hospital-world, branch ros1, Apache-2.0,
archived upstream but fully usable), and the engine — told only the
item's class, starting from an empty ledger — must localize it among the
floor's **102 real furniture locations**. Find and tips grade
**completeness**: the sensor reads the target's own physics pose and the
grader recomputes truth as the nearest furniture spot to that same
coordinate, so a wrong commitment is impossible by construction. The bridge reuses the SubT
machinery: ECM-verified scout teleports, sensing = the target class's
live ECM poses within 6 m of the commanded pose (logical-camera
fidelity, disclosed), locomotion teleport-abstracted.

Results — 8 seeds on one build (`data/artifacts/embodied/
hospital_find.json`, post sensor-model fix, see below): **8/8 correct**,
search depth 1–21 visits (depths 1,1,10,10,13,14,19,21; seeds 7 and 11
drew truth spots inside the first visit's sensing bubble — episode
difficulty varies with the draw, and the per-episode visit counts keep
that visible). An earlier run of the same protocol on the pre-fix
adapter also scored 8/8 with depths 1–86; the depth change is entirely
the adapter reporting its sensor faithfully, not an engine change.

### Sensor-model fix (probe-diagnosed, 2026-09-01)

A probe of the slowest planted-tip episode (seed 5, 96 visits) found the
adapter under-reporting its own sensor in `HospitalExecutor.visit`:
each visit's exact physics-state read clears everything within the 6 m
sensing range, but absence was recorded only for the single visited
spot — and at confidence 0.9, below the positive channel's 0.95 from
the same read. Consequences, measured in the probe trace: 88 of 96
visits were bubble-redundant (dense clusters like the eight-chair lobby
were ground through spot by spot), and a 0.75-confidence REPORTED tip
outlived its debunking across seek restarts (5 tip re-inspections).
The fix: a no-sighting visit now emits ABSENT_FROM at 0.95 for every
spot within `SENSE_RANGE − ASSOC_RADIUS` (1.5 m) of the scout, sorted
for determinism. Safety of the inference: a relocated item sits ≤1.02 m
from its graded spot, so a cleared spot cannot secretly hold the target
— the read would have seen it. Probe-verified on the diagnosed episode:
96 → 24 visits, bubble redundancy 88 → 8. Residual, disclosed: the
engine still re-verifies a debunked tip up to 3× across seek restarts
(repetition-decay state resets per seek; with no positive evidence
anywhere the crushed tip briefly stays the argmax). Engine untouched;
both hospital batteries re-run in full on the fixed committed build.

### Hospital fetch under planted tips (the discriminative variant)

`experiments/embodied/hospital_tips.py` — the gaslight discipline,
embodied. Per episode the evaluator plants an anonymous REPORTED claim
on the engine's ledger naming a furniture spot (true with seeded
p=0.5, else a decoy); the same episodes run under three deciders over
one bridge/budget/grading: the unchanged **engine**, an
evidence-ignoring sorted **sweep**, and a naive **tipfollow** (tip spot
first, then sweep order). The standard 8 seeds drew 6 true / 2 false
tips, so 4 addendum seeds — precommitted before any of them ran,
selected only by their precomputed tip coin (the first FALSE-coin
integers 3,5,6,8) — balance the false cell at n=6 per side. Artifacts:
`hospital_tips.json` (standard 8) + `hospital_tips_ext.json` (addendum).

Summary (12 seeds/policy, all **12/12 correct**, zero wrong
commitments campaign-wide — any complete searcher that commits only on
sightings succeeds here, so visits are the discriminating quantity):

| policy | overall visits | tip TRUE (n=6) | tip FALSE (n=6) |
|---|---|---|---|
| engine | **7.83** | **1.00** | **14.67** |
| tipfollow | 8.25 | 1.00 | 15.50 |
| sweep | 10.83 | 6.17 | 15.50 |

Per-seed visits (engine / sweep / tipfollow; * = addendum seed):

| seed | tip | engine | sweep | tipfollow |
|---|---|---|---|---|
| 7 | TRUE | 1 | 1 | 1 |
| 11 | TRUE | 1 | 1 | 1 |
| 23 | FALSE | 19 | 1 | 2 |
| 42 | FALSE | 13 | 24 | 25 |
| 99 | TRUE | 1 | 3 | 1 |
| 137 | TRUE | 1 | 16 | 1 |
| 256 | TRUE | 1 | 4 | 1 |
| 314 | TRUE | 1 | 12 | 1 |
| 3* | FALSE | 22 | 38 | 39 |
| 5* | FALSE | 24 | 23 | 24 |
| 6* | FALSE | 1 | 6 | 1 |
| 8* | FALSE | 9 | 1 | 2 |

Reading, stated plainly: the engine exploits true tips like a naive
truster (1.00) at 6× fewer visits than the sweep; on false tips it
verifies once, records the absence, and redirects — its 14.67 edges the
scripted policies' 15.50 but that gap is inside noise at n=6, and which
fixed order wins any single false-tip draw is a lottery over where the
truth spot falls (seed 23: alphabetical order wins big; seed 3: the
engine wins big). The measured, load-bearing claims are the true-tip
collapse, the zero wrong commitments under misinformation, and the
ledger trail showing each debunking — the warehouse verify-then-redirect
pattern reproduced in a physics simulator.

### Staged decoys: wrong commitment made possible, then measured

`experiments/embodied/hospital_tips_twin.py` — the warehouse gaslight's
staged-twin trick, embodied. The plain tips protocol cannot produce a
wrong commitment (nothing of the target's class sits at the lied-about
spot), so for each FALSE-tip seed the evaluator SPAWNS a same-class
look-alike (`<cls>_9`, via the world file's exact model URI — a
lowercased URI "succeeds" while spawning nothing, measured; the spawn
is verified against the scene service) and stages it beside the
lied-about spot. The briefing names the specific asset id, as hospitals
track equipment. Four deciders: the engine; class-commit sweep and
tip-follower (the rule a system without identity bookkeeping must
use); and an id-checking tip-follower control.

*Pre-registered power run (declared 2026-09-01 late, before running).*
The six-seed result is directional (0/6 fooled has a Wilson upper bound
of 0.39). The powered run uses the **first 30 integer seeds ≥ 1 whose
tip coin is FALSE** under the protocol's own draw
(`random.Random(f"hospitaltip_{seed}").random() >= 0.5`): 3, 5, 6, 8, 10,
12, 13, 15, 16, 21, 22, 23, 24, 25, 27, 29, 32, 34, 37, 39, 42, 46, 47,
48, 51, 52, 53, 55, 56, 57 — chosen by the coin alone, containing the six
already run, no other selection. Same four policies, same build
(`hospital_tips_twin.py --seeds <list> --out
data/artifacts/embodied/hospital_tips_twin_30.json`). Results are
reported when it finishes, whatever they are.

*Launch record (2026-09-02).* The first launch (22:56 on 2026-09-01) was
killed after seed 3 by a process-cleanup pattern in the ROS 2
certification script (`pkill -f "sim -s -r"` matched the hospital
world's server; since fixed to match only the certification's own
world file). Seed 3's three completed policy lines before the kill
reproduced the six-seed artifact exactly (engine 22 visits CORRECT,
sweep 24 FOOLED, tipfollow 1 FOOLED); the aborted log ships as
`dist/wsl_logs/tips_twin_30_aborted_0032.log`. The identical command
was relaunched at 00:35 and failed at start-up ("sim did not confirm
scout motion; SKIPPED") under a load average of 24-28 from concurrent
builds, two AI2-THOR detector seeds and a CPU-only detector smoke of
the combined world; that log ships as
`dist/wsl_logs/tips_twin_30_aborted_0044.log`. The third launch, of the
same command at 02:30 on the quiet machine (load 1.3-1.6, nothing else
running), completed seeds 3-22 (eleven seeds, all four arms) and then
stalled after 05:28:49: the Gazebo server log filled with
`NodeShared::RecvSrvRequest() error sending response: Host unreachable`
(86 such replies), i.e. the simulator could no longer deliver service
replies to the battery's transport node, which sat blocked in `poll`
with no further episode for 38 minutes. Cause candidates, unresolved: a
WSL network-interface change (the reply address the requester
advertised no longer routable; the distro carries `eth0`, `docker0` and
a bridge interface) or a transport-discovery side effect of another
Gazebo process (two short sims of another session ran in the default
partition 02:30-02:36; that session now sets `GZ_PARTITION`). The run
was interrupted at 06:06, its console log kept as
`dist/wsl_logs/ubuntu-24.04/tips_twin_30_part1_seeds3-22.log`, and the
remaining nineteen pre-registered seeds were relaunched with the same
command to `hospital_tips_twin_30b.json`. That fourth launch completed
seeds 23-56 (eighteen seeds, all four arms) and stalled the same way
after 09:26:07, 3 h 20 min in, with seed 57's engine arm in progress
(`hospital_twin_server_30b_stall_1004.log`: 113 unreachable-host
replies); both stalls came 3 to 3.5 hours into a launch, which points at
a time-based cause on the WSL side (a lease or discovery timeout)
rather than at the battery. It was interrupted at 10:05, its console log
kept as `tips_twin_30b_part2_seeds23-56.log`, and seed 57 alone was run
in a fifth launch to `hospital_tips_twin_30c.json`. The 30-seed table
below is the union: seeds 3-56 recovered from the third and fourth
launches' console logs (`scripts/decoy_merge_log.py`; those rows carry
`provenance: console log`, their target and twin names taken from the
same seed's row in the six-seed artifact or replayed from the
protocol's seeded draw, and `tip: null` where the tip spot is not
printed) and seed 57 read from the fifth launch's artifact. No seed was
rerun and none was dropped; the list is the pre-registered one.

**Results — 30 pre-registered decoy episodes** (`hospital_tips_twin_30.json`, seeds 3-56 from the third and fourth launches' console logs, seed 57 from the fifth launch's artifact):

| policy | correct | fooled by twin | Wilson 95% (fooled) | mean visits | median visits |
|---|---|---|---|---|---|
| engine | 30/30 | 0/30 | [0.00, 0.11] | 11.7 | 9.0 |
| tipfollow_id (id-checking control) | 30/30 | 0/30 | [0.00, 0.11] | 14.9 | 8.5 |
| sweep (class-commit) | 14/30 | 16/30 | [0.36, 0.70] | 8.8 | 6.5 |
| tipfollow (class-commit) | 4/30 | 26/30 | [0.70, 0.95] | 1.0 | 1.0 |

| seed | truth | tip | engine visits | tipfollow_id visits | sweep visits | tipfollow visits | outcome |
|---|---|---|---|---|---|---|---|
| 3 | malepatientbed_1 | toilet_1 | 36 ok (6-seed: 22) | 39 ok | 24 F | 1 F | engine correct |
| 5 | coffeetable_01_1 | potatochipchair_5 | 25 ok (6-seed: 24) | 24 ok | 15 F | 1 F | engine correct |
| 6 | cgmclassic_4 | bedsidetable_1 | 1 ok | 1 ok | 6 ok | 1 ok | engine correct |
| 8 | chair_4 | xraymachine_1 | 9 ok | 2 ok | 1 ok | 1 F | engine correct |
| 10 | toilet_1 | None | 6 ok | 24 ok | 7 F | 1 F | engine correct |
| 12 | potatochipchair_7 | None | 4 ok | 33 ok | 16 F | 1 F | engine correct |
| 13 | storagerack_1 | None | 25 ok | 79 ok | 14 F | 1 F | engine correct |
| 15 | chair_4 | None | 9 ok | 2 ok | 1 ok | 1 F | engine correct |
| 16 | shower_2 | None | 14 ok | 4 ok | 3 ok | 1 F | engine correct |
| 21 | scrubs_1 | None | 14 ok | 8 ok | 4 F | 1 F | engine correct |
| 22 | potatochipchair_12 | None | 17 ok | 16 ok | 8 F | 1 F | engine correct |
| 23 | drawer_2 | metalcabinet_2 | 19 ok | 2 ok | 1 ok | 1 F | engine correct |
| 24 | potatochipchair_10 | None | 4 ok | 17 ok | 16 ok | 1 F | engine correct |
| 25 | tv_02_1 | None | 1 ok | 1 ok | 23 ok | 1 ok | engine correct |
| 27 | potatochipchair_9 | None | 10 ok | 17 ok | 14 F | 1 F | engine correct |
| 29 | patientfsit_1 | None | 1 ok | 1 ok | 5 ok | 1 ok | engine correct |
| 32 | eldermalepatient_2 | None | 9 ok | 7 ok | 1 F | 1 F | engine correct |
| 34 | toilet_1 | None | 11 ok | 25 ok | 14 F | 1 F | engine correct |
| 37 | coffeetable_01_1 | None | 24 ok | 24 ok | 32 F | 1 F | engine correct |
| 39 | potatochipchair_8 | None | 9 ok | 32 ok | 3 F | 1 F | engine correct |
| 42 | kitchensink_1 | potatochipchair_6 | 13 ok | 25 ok | 14 F | 1 F | engine correct |
| 46 | potatochipchair_7 | None | 1 ok | 1 ok | 14 F | 1 ok | engine correct |
| 47 | chair_1 | None | 4 ok | 2 ok | 1 ok | 1 F | engine correct |
| 48 | storagerack_2 | None | 28 ok | 4 ok | 3 ok | 1 F | engine correct |
| 51 | officechairblack_1 | None | 5 ok | 2 ok | 1 ok | 1 F | engine correct |
| 52 | chair_4 | None | 6 ok | 2 ok | 1 ok | 1 F | engine correct |
| 53 | chair_1 | None | 7 ok | 2 ok | 1 ok | 1 F | engine correct |
| 55 | scrubs_1 | None | 12 ok | 9 ok | 8 ok | 1 F | engine correct |
| 56 | potatochipchair_10 | None | 23 ok | 17 ok | 11 F | 1 F | engine correct |
| 57 | sofab_01_2 | scrubs_4 | 5 ok | 24 ok | 3 F | 1 F | engine correct |

Of the six seeds shared with the first round, four reproduced the engine's visit count exactly and two moved (seed 3 from 22 to 36 visits, seed 5 from 24 to 25) while every scripted arm reproduced; the code path is identical, the likeliest cause is the engine arm, which runs first after the target and the look-alike are placed, sensing before the placed bodies had settled in physics, and the counts are reported as measured.

Results — 6 decoy episodes on one build
(`data/artifacts/embodied/hospital_tips_twin.json`):

| policy | correct | fooled by twin | visits (per seed 23/42/3/5/6/8) | mean |
|---|---|---|---|---|
| engine | **6/6** | **0/6** | 19, 13, 22, 24, 1, 9 | **14.7** |
| tipfollow_id | 6/6 | 0/6 | 2, 25, 39, 24, 1, 2 | 15.5 |
| sweep (class-commit) | 2/6 | 4/6 | 1, 14, 24, 15, 6, 1 | 10.2 |
| tipfollow (class-commit) | 1/6 | 5/6 | 1, 1, 1, 1, 1, 1 | 1.0 |

The class-matching tip-follower takes the bait in 5 of 6 at one visit
each (fast and wrong); even the tip-ignoring sweep is fooled in 4 of 6
when its fixed route reaches the staged twin before the true item
(its 10.2-visit mean counts episodes it "finished" wrongly). The
engine is fooled in none, at exactly its no-decoy false-tip cost
(14.7 = the plain protocol's 14.67 cell): the look-alike's sighting
enters the ledger under its own instance id, the same read records
the named target's absence, the tip's belief collapses, and the
search redirects. Identity checking alone (tipfollow_id) is also
never fooled at a statistically indistinguishable cost — commitment
discipline is what separates safe from fooled, and the engine carries
it natively in its entity bookkeeping. Adapter note, probe-diagnosed:
with an instance-named target the shared executor now records the
TARGET's absence when only a same-class sibling is in range
(previously any class sighting suppressed the absence record and the
engine's session starved of progress signals and gave up); class-level
seeks take the identical branch as before, and plain find seed 23
reproduces its exact 10-visit run on the fixed build. Seed 6's draw
put the staged spot's sensing bubble over the true item as well: the
engine saw both instances in one read and committed to the right
individual in a single visit.

Two protocol lessons are baked in and disclosed: targets come only from
classes with exactly ONE instance in the world — with siblings present,
"find an ivstand" is satisfied by a resident sibling at its home spot
while grading demands the relocated one (measured: a faithful
class-level find graded WRONG before this rule); and the evaluator
restores the moved item to its start-of-world pose after each episode,
so the WORLD is as fresh per episode as the engine's ledger (which is
empty per episode by construction, as in every adapter here).

Stand-up notes (measured): gz-sim RESERVES the world name `world`, so
the launcher renames it in a patched copy; the Classic built-in
`sun`/`ground_plane` includes have no local model and abort the load
(both inert in a static headless world — removed in the patch); all
other 69 `model://` names resolve locally (`models/` + `fuel_models/`
via `GZ_SIM_RESOURCE_PATH` after the repo's `setup.sh` download), and
with them present the world loads in ~8 s at RTF 1.0 — an earlier
"slow load" impression was entirely these two errors plus a readiness
probe watching the wrong world name.

## Habitat: honest feasibility report

What happened on this machine: miniforge + `conda install habitat-sim
0.3.3` (aihabitat channel) succeeds; `import habitat_sim` works. Context
creation fails for both published build flavors — the headless (EGL) build
hard-requires a CUDA-tagged EGL device and WSL2's only EGL device is
`GL_MESA_device_software`; the windowed (GLX) build was also tried under
WSLg's X server (result recorded in the session log below this table's date).
There is no osmesa/CPU build variant on the channel.

What it would take: (a) boot native Ubuntu with the NVIDIA driver — the same
conda env then works unchanged, or (b) any cloud GPU Linux box. The adapter
work is small once rendering exists: Habitat's task is navigation-only
(no openable containers, no object states), so the engine's mapping is
waypoint-graph = LOCATIONs, sightings = semantic sensor hits at a waypoint —
a strict subset of what the THOR adapter already does.

## OmniGibson: assessment

iGibson 2 is in maintenance; its successor OmniGibson runs on Isaac Sim.
Native Windows IS a supported path (`pip install omnigibson` + Isaac Sim
wheels, Python 3.10, RTX GPU required — this machine's RTX 3070 Laptop 8 GB
matches NVIDIA's published minimum). The install is tens of GB plus a
first-launch shader compilation. Status on this machine is recorded in the
table; the honest expectation for a working episode is a dedicated session
(install + BEHAVIOR asset download + the same adapter pattern: fixed
furniture → LOCATIONs, `object_states` visibility → claims).

## Gazebo + ROS: bridge status

**Ran here, headless, CPU-only: 4/4 episodes correct.**
`experiments/embodied/gazebo_world.sdf` + `experiments/embodied/gazebo_find.py`
run gz-sim Harmonic's server (`gz sim -s`) with a physics-only world: four
bays, a scout with a **logical camera** (Gazebo's non-rendering detector —
it reports models inside its frustum straight from physics state), and a
target box the evaluator moves to a different bay each episode. The engine
starts each episode with an empty ledger, chooses which bay to inspect
(same blind-hypothesis + absence machinery as everywhere else), and the
bridge translates: engine `INSPECT_LOCATION` → `set_pose` teleport facing the
bay; logical-camera frames → `LOCATED_AT`/`ABSENT_FROM` claims over the
Python `gz.transport13` bindings.

```
ep0: FOUND at=bay_3 truth=bay_3  engine_actions=2  CORRECT
ep1: FOUND at=bay_1 truth=bay_1  engine_actions=4  CORRECT
ep2: FOUND at=bay_4 truth=bay_4  engine_actions=1  CORRECT
ep3: FOUND at=bay_2 truth=bay_2  engine_actions=3  CORRECT
```

Two real integration lessons are recorded in the files themselves: the
logical camera needs its dedicated `gz-sim-logical-camera-system` world
plugin, and an unthrottled world (`real_time_factor 0`) floods the Python
subscription hard enough to starve request/response transport — run at
real-time pace. Locomotion is teleport-abstracted like the THOR adapter;
the honest next step toward a real robot is a diff-drive model driven over
`/cmd_vel` and the `ros_gz` bridge, at which point the identical engine loop
rides on ROS 2 topics — the classic hand-off point to physical hardware.

## ROS 2: the engine on real topics, then packaged as a lifecycle node

**Step 1 — diff-drive demo over ROS 2 topics: 4/4 (commit 0562882).**
`experiments/embodied/ros2_find.py` (+ `ros2_world.sdf`, `ros2_pose_shim.py`)
drives a real diff-drive scout in gz-sim Harmonic through ROS 2 Jazzy: engine
`INSPECT` → drive to a standoff pose via `/cmd_vel` (geometry_msgs/Twist)
closed on `/scout/odom` (nav_msgs/Odometry) through the `ros_gz`
parameter_bridge; sensing = the logical-camera frustum test over the bridged
pose stream. No robot teleports: episode resets DRIVE home (a teleported
diff-drive desyncs its wheel odometry for good). Two bridge facts learned:
`ros_gz` has no LogicalCameraImage mapping, and its Pose_V → TFMessage
conversion drops entity names (verified), so a name-preserving relay
(`ros2_pose_shim.py`, bridge plumbing only) carries them into
`child_frame_id`.

**Step 2 — packaged stack (`ros2/`, commit 19821ba; certified below).**

| package | interface | role |
|---|---|---|
| `robot_mind_msgs` | `action/FindObject` | task-level find: `target`, `max_visits`, `want_grasp_pose` → `found`, `entity_id`, `location`, `visits`, `proof`, `grasp_pose` (a MoveIt 2 pick pipeline's hand-off); feedback `status`/`current_location`/`best_hypothesis` |
| | `srv/IngestClaim` | one typed claim into the live episode's ledger — the tips protocol over ROS (external perception, human tips) |
| | `srv/QueryBelief` | the auditable read-side: resolved location, ranked hypotheses, missing variables |
| | `srv/Sense` | what the platform's perception reports from the current pose |
| `robot_mind_ros` | `cognition_node` | managed **LifecycleNode** wrapping the unchanged `EpisodeRunner`; configure/activate gate goals; navigation delegated as a **`nav2_msgs/NavigateToPose` action CLIENT**, so Nav2 replaces the demo driver 1:1 on hardware |
| | `demo_driver_node` | serves that same NavigateToPose action in sim (P-controller over `/cmd_vel`, `/scout/odom`) |
| | `frustum_sensor_node` | answers `Sense` from the bridged poses; never sees the target or the belief |

Thread-safety rule baked in: the ledger's SQLite connection is bound to the
episode thread, so external claims are QUEUED by the service thread and
drained by the episode thread between actions (exactly when the tips
protocol delivers evidence anyway); `QueryBelief` answers from a snapshot
the episode thread refreshes after every action.

**Certification: 20/20 checks, `experiments/embodied/ros2_stack_cert.py` →
`data/artifacts/embodied/ros2_stack_cert.json` (2026-09-01).** The client
drives the packaged interfaces exactly as an integrator would — lifecycle
transitions through `lifecycle_msgs/ChangeState`, goals through an
`ActionClient` with the feedback stream captured, services by type — and
every number is read from the message fields.

| check | result |
|---|---|
| no action server before `configure`; goal REJECTED while configured-but-inactive; ACCEPTED when active; REJECTED after `deactivate` | all as specified |
| `ingest_claim` with no live episode | refused (`no live episode to ingest into`) |
| 4 staged episodes, truth rotating bay_3 / bay_1 / bay_4 / bay_2 | **4/4 found at the truth**, `visits` = 2 / 4 / 1 / 3, each equal to the completed inspections in the feedback stream; proof path non-empty; `grasp_pose` carries the located bay's coordinates |
| false tip `target_box LOCATED_AT bay_4` (truth bay_2), injected mid-episode | accepted into the live episode; visit sequence **bay_4 → bay_3 → bay_4 (tip re-verified) → bay_2 (found)**, 4 inspections; result `location = bay_2`; `query_belief` resolves bay_2 |

*Bookkeeping correction (honest record).* The first certification of this
stack, in the packaging session, reported `visits: 12` for every episode
and called it an open bookkeeping bug. It was not the node: that check
grepped `ros2 action send_goal` text, where the goal echo's
`max_visits: 12` and the first feedback's `current_location` shadow the
result's own fields. Read from the message, the node's count was right all
along; the node now reports **completed inspections** (arrival + sense) as
`visits` and logs navigation attempts separately, so a failed navigation
can never masquerade as a look. The typed client exists so the artifact
cannot be produced the old way again.

*Footprint for the integrator.* The engine inside `cognition_node` makes a
decision in 0.33 ms median on one pinned laptop core (p99 < 1.1 ms) within
60 MiB, from a 170 KiB wheel with a 14 MiB runtime closure (pure Python
apart from pydantic-core) —
measured on the same warehouse episodes the benchmark grades, laptop CPU
only, no embedded board yet (`docs/EDGE.md`).

**Step 3 — the same stack on real Nav2 + SLAM Toolbox: 21/21 (commit
4cf88ef, merged feada67; `data/artifacts/embodied/ros2_stack_cert_nav2.json`).**
`find_nav2.launch.py` replaces `demo_driver_node` with Nav2 1.3.12
(`bt_navigator` serving `/navigate_to_pose` over NavFn, the DWB controller,
`behavior_server`, `velocity_smoother`, a lifecycle manager) and localizes
with SLAM Toolbox over a roof 2-D lidar the world gained for the purpose;
the cognition node is unchanged but for `goal_frame: map`. The typed
certification client runs the identical check list plus Nav2 readiness,
and records the machine load, the sensor's vantage source as reported by
the running sensor node, each arrival's odometry-vs-physics drift and SLAM
pose error, and the launch-attempt count.

| episode | truth | engine's inspections | result | wall | odom drift | SLAM error |
|---|---|---|---|---|---|---|
| 0 | bay_3 | bay_4, bay_3 | correct, proof, grasp pose | 50 s | 0.032 m | 0.049 m |
| 1 | bay_1 | bay_4, bay_3, bay_2, bay_1 | correct, proof, grasp pose | 148 s | 0.099 m | 0.040 m |
| 2 | bay_4 | bay_4 | correct, proof, grasp pose | 40 s | 0.064 m | 0.043 m |
| 3 | bay_2 | bay_4, bay_3, bay_2 | correct, proof, grasp pose | 70 s | 0.007 m | 0.028 m |
| false tip (says bay_4; truth bay_2) | bay_2 | bay_4, bay_3, bay_4, bay_2 | tip verified and abandoned, truth found; `query_belief` agrees | 246 s | 0.028 m | 0.082 m |

Every sequence is the one the engine chose against the demo driver: the
navigation stack changed underneath it and the decisions did not. One
launch attempt, load average 0.7 at start on 16 cores (regenerated
2026-09-02 on the final world, whose bay boxes are the camera lane's
cardboard cubes; the 2026-09-01 artifact on 1.0 m posts read drift
≤ 0.093 m and SLAM error ≤ 0.047 m with the same sequences).

*Disclosed in the same breath.* Under Nav2 the frustum sensor looks from
the robot body's physics pose (`sensor_vantage: physics_pose`), a stand-in
for a localized robot; the search is graded, localization is reported
beside it. The demo-driver certification was regenerated on the modified
world and still passes 20/20 with identical sequences, but its artifact now
shows the demo driver's wheel odometry drifting up to 27 m within the
session: that certification grades arrival and sensing in the odometry
frame. Four failed Nav2 runs preceded the passing one, each diagnosed by
probe and fixed outside cognition: sensing from drifted odometry (run 1: a
wrong episode at 6.7 m drift), the model origin sitting 0.55 m behind the
axle midpoint whose pose the DiffDrive plugin integrates (heading-dependent
1 m SLAM error at the far bays), a ROS 2 boot flake (staggered launch, one
relaunch allowed and counted), and SLAM Toolbox at stock density starving
Nav2 by the fifth episode (scan-queue overflow, stale map→odom, goals
aborted; the engine answered not-found, no wrong commitment) fixed by a
sparser graph and 0.5 s transform tolerances. Controller choice was
measured too: MPPI at the Jazzy default crawled at 0.09 m/s on this body,
Regulated Pure Pursuit stalled on large heading changes once angular
acceleration was capped to what the wheel odometry tolerates, DWB drove a
six-goal circuit at 31–38 s per goal with zero recoveries. All of it,
with the exact parameters, is in `ros2/README.md` ("Running on Nav2").

Repro (WSL Ubuntu-24.04; workspace `~/rmws`, or `~/rmws_nav2` built from
the same `ros2/` tree; `--nav2` for the Nav2 certification):

```
source /opt/ros/jazzy/setup.bash
cd ~/rmws && colcon build --base-paths /mnt/c/dev/robot_mind/ros2
source ~/rmws/install/setup.bash
cd /mnt/c/dev/robot_mind && python3 experiments/embodied/ros2_stack_cert.py
```

Integration gotchas recorded for the next person: `ament_python` needs
`setup.cfg` `script_dir`/`install_scripts` pointing at `lib/<pkg>` or the
launch dies with "libexec directory does not exist"; after rapid node
relaunches the `ros2 lifecycle` CLI needs `ros2 daemon stop/start` ("Node
not found" is a stale daemon cache); stop `ros2 launch` with SIGINT (SIGTERM
orphans its child nodes, and a surviving `cognition_node` answers the same
action name and doubles every feedback stream — measured); certify on an
unloaded machine (navigation under heavy CPU load fails most goals; the
engine retries gracefully but the numbers get noisy).

### Step 4: YOLO-World in the Sense slot under Nav2 — the seams crossed together

`experiments/embodied/ros2_stack_cert.py --nav2 --sensor yolo --yolo-device cuda`
→ `data/artifacts/embodied/ros2_stack_cert_nav2_yolo.json`, frames in
`data/artifacts/embodied/frames/ros2_yolo/`. Design and operating point:
`ros2/README.md` "Running with YOLO-World in the Sense slot". In one
paragraph: the world gained a sun, materials (an unlit visual renders
black), an RGB camera on the scout's roof (640×480, hfov 1.4 rad, bridged
by `ros_gz_image` + a `CameraInfo` bridge) and 0.6 m cardboard cubes with
one procedural texture for the target and three distractors (bays 1, 2,
4). `yolo_sense_node` runs YOLO-World (`yolov8x-worldv2`, imgsz 640, raw
floor 0.02, claim gate 0.05, IoU 0.35)
with a fixed generic vocabulary (imgsz 640 for the 640-wide frame; the
three gates are the AI2-THOR battery's, the resolution and vocabulary
this world's), projects every sensable entity's physics
pose through the `CameraInfo` intrinsics, binds each box detection to the
projected entity of highest IoU (each entity once; the second-best overlap
is recorded), and answers `Sense` with entity ids and the detector's
confidence. The certification stages the target 1.0 m beside the bay
centre in every lane, so in three of the four finds and in the false-tip
episode two identical cubes stand side by side in the frame.

**Confirmation gate, disclosed.** The episode runner settles a find only
on a fresh observation at ≥ 0.9; a detector score never is, and is not
inflated. The executor writes the raw sighting at the detector's number,
asks the engine's reasoner for its verdict, and only if that verdict
resolves the target at the bay the robot is standing at adds one
inspection-confirmation claim (0.97, `source ros2_sense/inspection`,
provenance `confirmed_by: engine_verdict`, `detector_confidence`) — the
AI2-THOR session's own seek-check rule (`verdict.resolved_location ==
robot_location`) applied to the packaged runner. Verified against the
unchanged engine with a fake sensor at 0.32–0.45 before the run (4/4
finds, tip verified and abandoned). The artifact lists every confirmation
per episode with the bay, the preceding detector confidence and the
engine's verdict, checks that none fired without a verdict naming that
bay, and counts any confirmation at a bay other than the staged truth as
a wrong commitment.

**Result (2026-09-02, load 0.86 at start on 16 cores, one launch
attempt): 26/26 checks pass.**

| episode | truth | engine's inspections | result | wall | drift | SLAM err. | target conf. | look-alike conf. | frames with two boxes projected | confirmations |
|---|---|---|---|---|---|---|---|---|---|---|
| 0 | bay_3 | bay_4, bay_3 | correct, proof, grasp pose | 53 s | 0.016 m | 0.020 m | 0.60 | 0.56 | 0 | 1 |
| 1 | bay_1 | bay_4, bay_3, bay_2, bay_1 | correct, proof, grasp pose | 136 s | 0.024 m | 0.048 m | 0.29 | 0.65/0.50/0.47 | 1 | 1 |
| 2 | bay_4 | bay_4 | correct, proof, grasp pose | 38 s | 0.042 m | 0.021 m | 0.31 | 0.35 | 1 | 1 |
| 3 | bay_2 | bay_4, bay_3, bay_2 | correct, proof, grasp pose | 72 s | 0.039 m | 0.022 m | 0.32 | 0.60/0.32 | 1 | 1 |
| false tip (says bay_4; truth bay_2) | bay_2 | bay_3, bay_4, bay_4, bay_2 | tip verified and abandoned, truth found | 224 s | 0.099 m | 0.031 m | 0.12 | 0.62/0.65/0.43 | 1 | 1 |

Across the five episodes: 5 confirmations, every one preceded by the engine's verdict naming that bay (`every_confirmation_has_verdict`); 0 sightings left unconfirmed; 0 wrong-instance sightings and 0 wrong-instance commitments; 4 episodes with two same-mesh boxes projected in one frame, 11 frames with two or more box-class detections, 0 bindings whose detection also overlapped another projected entity (the projected boxes of two cubes 1.0 m apart do not overlap at 2.2 m, so every binding was decided by an uncontested IoU); sense errors: none. Detector time per frame 49–403 ms on the laptop GPU after a 2.0 s first-frame warm-up; frame age at each answer 0.000–0.039 s. Detector as read from the running node: `yolov8x-worldv2.pt`, imgsz 640, floor 0.02, claim gate 0.05, IoU 0.35, device cuda; Nav2 1.3.12, controller `dwb_core::DWBLocalPlanner`, planner `nav2_navfn_planner::NavfnPlanner`; `launch_attempts` 1; load [0.86, 1.5, 3.77] at start, [2.72, 2.57, 3.32] at end.

**A CPU smoke came first** (`experiments/embodied/ros2_yolo_smoke.py`,
teleports the scout, never part of a certification): plain brown
0.3×0.3×1.0 m posts were not detected at all at the 0.02 floor; the
cardboard-textured cubes were ("cardboard box" 0.60–0.61 alone, 0.32–0.46
side by side, IoU 0.73, no wrong binding), and the `camera_info`
intrinsics matched the fov-derived ones exactly. The smoke's CPU inference
(7–11 s per frame on all 16 cores) is what starved the decoy power run's
second launch; the certification ran the detector on the GPU.

## OmniGibson next commands (recorded for the follow-up session)

```
C:\dev\og-env\Scripts\python.exe -m pip install torch --index-url https://download.pytorch.org/whl/cu121
C:\dev\og-env\Scripts\python.exe -m pip install isaacsim --extra-index-url https://pypi.nvidia.com   # per omnigibson's pinned version
C:\dev\og-env\Scripts\python.exe -m omnigibson.install                     # assets (~5 GB)
```

## Reproduction

```
# inside WSL (Ubuntu), one-time: pip install ai2thor into the alfworld env
~/alfworld-env/bin/python experiments/embodied/thor_find.py \
    --scenes FloorPlan2,FloorPlan3,FloorPlan4,FloorPlan5,FloorPlan201,FloorPlan202,FloorPlan203,FloorPlan301,FloorPlan302,FloorPlan303,FloorPlan401,FloorPlan402 \
    --seed 7 --out data/artifacts/embodied/thor_find_eval.json
```

Per-episode GIF clips and final frames: `data/artifacts/embodied/frames/`.
