# Planetary and underwater search: feasibility, install, protocol

Status, 2026-09-02 (branch `space-marine`): **designed, staged, unit-tested, and — after
robot-mind-49 cleared the machine at 02:30 — MEASURED at stage A on both tracks: two
smokes and two four-seed batteries, 26 of 26 episodes correct across engine, sweep and
random arms, read strictly as completeness and commitment (§6.2–6.4).** Stages B and C
(driving, real sonar) and the planted-tip variant (§6.5) are designed, not run. Facts about the third-party
software (versions, dependencies, rendering paths) were checked tonight against the
sources listed in §8 and against this machine.

The question Kiran asked on 2026-09-02 was whether the engine applies to underwater,
Moon and Mars search. The answer in principle (offline, one core, two clocks for delayed
evidence, sub-exhaustive budgets, a small adapter contract) was given then; this document
is the plan to answer it in measurement, on the same terms as the THOR, SubT, hospital and
Nav2 campaigns: engine untouched, no LLM in any evaluation path, hidden-truth protocol,
one seed first and then a four-seed battery (Kiran, 2026-09-02: "4 is good"), wins reported
with the weight they earn and caveats after.

## 0. Summary

| Candidate | Stack | Rendering it needs | On WSL2 here | Verdict | Staged tonight |
|---|---|---|---|---|---|
| Space ROS Curiosity demo (`space-ros/demos`) | ROS 2 Jazzy + Gazebo Harmonic, ros2_control | gpu_lidar + camera on ogre2 (stage B/C only) | ogre2 via Mesa EGL/llvmpipe: works (measured on our Nav2 world) | **GO** — stage A needs no rendering at all | clone, apt deps, colcon workspace built (install-only), terrain mesh parsed, 169 stations |
| `spaceros_gz_demos` (Perseverance/Ingenuity, Moon, Enceladus) | ROS 2 + Harmonic, diff-drive | ogre2 sensors | same | alternate world, lower ceremony; PR #33 to space-ros is still open | cloned and in the workspace |
| Project DAVE, `ros2` branch (IOES-Lab) | ROS 2 Jazzy + Harmonic; multibeam sonar = ogre2 + CUDA | ogre2 (llvmpipe) + CUDA | EGL llvmpipe works; CUDA driver API sees 1 device from Ubuntu-24.04 | **PICK for underwater** — stage A needs no DAVE build | clone, deps, every Fuel model of the ocean-objects world prefetched (24 models), CUDA 12.8 toolkit installed, patched world validated with the SDF parser |
| Stonefish 1.5 + `stonefish_ros2` | own engine, OpenGL 4.3 core | GL 4.3 (FLS/MSIS/SSS are GPU depth-map sensors) | llvmpipe offers GL 4.5 core: runs in software, slowly | viable fallback, second choice (C++ build deferred) | apt deps only |
| HoloOcean 2.3.0 | Unreal Engine 5 (Vulkan on Linux) | a GPU Vulkan device | Vulkan ICDs here: lavapipe only, no NVIDIA ICD in WSL2 | **BLOCKED on WSL2** (same class as Habitat's EGL) — native Windows is the escape hatch | nothing |

Rendering paths measured tonight on WSL2 Ubuntu-24.04 (WSLg, `DISPLAY=:0`, `WAYLAND_DISPLAY=wayland-0`):

| Path | Result |
|---|---|
| GLX / EGL (X11 and Wayland platforms) | Mesa 25.2.8, **llvmpipe**, OpenGL 4.5 core, `Accelerated: no` |
| EGL GBM platform | `eglInitialize failed` (no DRI3 device) |
| Mesa d3d12 (GPU-backed GL through `/dev/dxg`) | driver file and `/dev/dxg` present, but `MESA_LOADER_DRIVER_OVERRIDE=d3d12` still yields llvmpipe |
| Vulkan (`vulkaninfo --summary`) | one device: `llvmpipe`, `PHYSICAL_DEVICE_TYPE_CPU`, API 1.4.318; ICDs present: lvp, intel, radeon, nouveau, virtio, gfxstream, asahi — none for NVIDIA |
| CUDA driver API from Ubuntu-24.04 | `cuInit` 0, one device (RTX 3070 Laptop, driver 572.83) |

The precedent stands: Gazebo's ogre2 sensors render headless on llvmpipe here (the Nav2
world's 2D lidar did), Habitat's CUDA-EGL requirement did not. Everything chosen below
sits on the side that works.

## 1. Space ROS

### 1.1 What Space ROS is now

- Current release **`jazzy-2026.07.0`** (published 2026-08-01). The line is quarterly:
  jazzy-2026.04.0, 2026.01.0, 2025.10.0, 2025.07.0, 2025.04.0, 2025.01.0; the Humble line
  ended at humble-2024.10.0. Base distribution: **ROS 2 Jazzy**, which is what WSL
  Ubuntu-24.04 already runs (ros-base 0.11.0, ros_gz 1.0.22, Nav2 1.3.12, SLAM Toolbox 2.8.5).
- Distribution: Docker images `osrf/space-ros:<tag>` built with Earthly (`earthly
  +main-image`), or the same Earthly build locally. **There are no apt binaries.** Space ROS
  is a from-source rebuild of the ROS 2 core with space-grade tooling (static analysis,
  the IKOS analyzer, a curated package list); it is used as an *underlay*
  (`${SPACEROS_DIR}/setup.bash`) beneath ordinary ROS 2 workspaces.
- The demos repository (`space-ros/demos`, HEAD b0b010e committed 2026-09-01) is required by its own
  README to build on `osrf/space-ros:latest` with a `Dockerfile`, `build.sh`, `run.sh`.
  The Curiosity demo's Dockerfile is `FROM osrf/space-ros:jazzy-2026.07.0` and adds
  only `ros-jazzy-control-msgs` and `ros-jazzy-rmw-cyclonedds-cpp` before `colcon build`.

### 1.2 The Gazebo Mars rover demo, exactly

`space-ros/demos/curiosity_rover/` holds three plain ROS 2 packages:

| Package | Contents |
|---|---|
| `curiosity_description` | xacro URDF of the MSL rover (chassis, six wheels, rocker-bogie "wheel tree", four steer joints, arm, mast, meshes); `models/config/mars_rover_control.yaml` |
| `curiosity_gazebo` | `worlds/mars_curiosity.world`; `models/curiosity_path` (terrain, static, `curiosity_path.stl` 20 MB = 400,000 triangles, `mars_path_simple1.dae` 34 MB); `launch/curiosity_gazebo.launch.py`; node `odom_tf_publisher` |
| `curiosity_rover_demo` | `launch/mars_rover.launch.py`; nodes `move_wheel`, `move_arm`, `move_mast`, `run_demo` |

World (`mars_curiosity.world`, world name `default`): gravity `0 0 -3.711`, world systems
Physics, UserCommands, SceneBroadcaster, a directional sun, and one include:
`model://curiosity_path` at the origin. Measured from the STL tonight: the terrain spans
**x, y ∈ [−152, 152] m, z ∈ [−28.1, 28.1] m** — a 304 m square with 28 m of relief, not
a narrow path. It contains no rocks, landmarks or science targets.

Rover (spawned by `ros_gz_sim create` from `/robot_description` at z = −7.5):

- `gz_ros2_control::GazeboSimROS2ControlPlugin` with `mars_rover_control.yaml`:
  controller manager at 100 Hz; `wheel_velocity_controller`
  (`velocity_controllers/JointGroupVelocityController`, six wheel joints);
  `steer_position_controller` (`joint_trajectory_controller`, four steer joints);
  `wheel_tree_position_controller` (`effort_controllers/JointGroupPositionController`);
  arm and mast `JointTrajectoryController`s; `joint_state_broadcaster`.
- `gz::sim::systems::OdometryPublisher` → gz `/model/curiosity_mars_rover/odometry`,
  bridged to `nav_msgs/Odometry`; `odom_tf_publisher` republishes it as TF.
- Sensors system with a `gpu_lidar` on topic `scan` (bridged to `sensor_msgs/LaserScan`)
  and a `camera` on `image_raw` (bridged with `ros_gz_image`).
- `move_wheel` subscribes **`/cmd_vel` (`geometry_msgs/Twist`)** and maps it to wheel
  velocities `[v, 1.5v, v, −v, −1.5v, −v]` plus Ackermann steering (wheelbase 2.08157 m,
  track 1.53774 m, ±0.6 rad). This is the seam that matters for us: the packaged
  cognition stack already emits Nav2 goals and Nav2 already emits `/cmd_vel`.
- `run_demo` exposes `std_srvs/Empty` services `/move_forward`, `/move_stop`,
  `/turn_left`, `/turn_right`, `/open_arm`, `/close_arm`, `/mast_open`, `/mast_close`,
  `/mast_rotate`.
- `nav2_demo/` in the same repository ships `nav2_params.yaml` (AMCL with
  `base_frame_id: base_footprint`, `scan_topic: scan`, `odom_topic: /odom`; DWB with
  `max_vel_x 2.0`; NavFn; voxel and obstacle layers from `/scan`) and a pre-built
  `mars_map.yaml` (0.05 m/px, origin (−28.2, −22.1)). So Nav2 has been run on this rover
  by its authors, with the same sensor set our Nav2 certification used (2D lidar +
  odometry). Its README still references `/opt/ros/humble`; the params carry over.

Alternate world, staged as well: **`david-dorf/spaceros_gz_demos`** (Apache-2.0, submitted
to space-ros/demos as PR #33 by katie-hughes — still open, not merged, last updated
2026-07-08; this repository's last push 2025-01-23). One package, `exec_depend` on
`rclcpp`, `launch`, `launch_ros`, `ros_gz_sim`, `std_msgs`, four worlds: `mars.sdf` (gravity −3.71; Physics, Imu,
Sensors[ogre2], UserCommands, SceneBroadcaster; `martian_surface` 24.8 MB glb;
`nasa_perseverance` as a **diff-drive on `/perseverance/cmd_vel`** with `/perseverance/odometry`,
camera, depth camera, five arm joints, camera yaw; `nasa_ingenuity` with battery and
thrust), `moon.sdf` (X1/X2 rovers, SCS coordinates), `enceladus.sdf` (a submarine with a
buoyancy engine, two thrusters, odometry and a gpu_lidar published as `/submarine/sonar`),
`orbit.sdf` (ISS + capsule). The Perseverance path needs no ros2_control and is the
quickest way to put a *real drive loop* under the engine; the Enceladus world is a
ready-made planetary-ocean fallback for the marine protocol (§2.8).

### 1.3 Jazzy compatibility and the non-Docker path

The demo packages depend on `ros_gz`, `gz_ros2_control`, `ros2_control`,
`ros2_controllers` (joint_trajectory, velocity, effort, imu_sensor_broadcaster,
joint_state_broadcaster, diff_drive), `control_msgs`, `xacro`, `robot_state_publisher`,
`ros2controlcli` — all of which exist as Jazzy apt packages on Ubuntu 24.04 (candidates
verified with `apt-cache policy`, installed tonight, see §1.4). Nothing in the three
packages needs the Space ROS underlay: **they build and install on vanilla ROS 2 Jazzy +
Gazebo Harmonic without Docker** — verified tonight: `colcon build --symlink-install
--parallel-workers 1` of `curiosity_description`, `curiosity_gazebo`,
`curiosity_rover_demo`, `spaceros_gz_demos` finished in 4 min 39 s under load 23 (they
are install-only packages: xacro, meshes, launch files, Python nodes; no compiled targets),
workspace `~/space_ws` on Ubuntu-24.04.

What this does and does not mean, for the paper:

- After a clean stage A we can say: *the engine searches the Space ROS Mars rover demo's
  terrain on Gazebo Harmonic.* Only after stage B is measured can we say the rover, its
  controllers and its topics were driven — those are not touched by stage A.
- We cannot say we ran *on Space ROS* unless the hardened core underlay is present. That
  underlay is Docker/Earthly-distributed; building it from source natively is a multi-hour
  all-core job (excluded tonight by rule, and unnecessary for the search evidence). If it
  is ever wanted, the path is Earthly on a native Linux box, then `SPACEROS_DIR` as the
  underlay beneath `~/space_ws`; the engine-facing stack is unchanged either way.

### 1.4 Install (done tonight on WSL Ubuntu-24.04; repeatable)

```bash
# apt (all Jazzy binaries; no builds)
sudo apt install -y --no-install-recommends \
  ros-jazzy-gz-ros2-control ros-jazzy-ros2-control ros-jazzy-ros2-controllers \
  ros-jazzy-joint-trajectory-controller ros-jazzy-velocity-controllers \
  ros-jazzy-effort-controllers ros-jazzy-imu-sensor-broadcaster \
  ros-jazzy-ros2controlcli ros-jazzy-rmw-cyclonedds-cpp ros-jazzy-control-msgs \
  ros-jazzy-xacro ros-jazzy-robot-state-publisher ros-jazzy-ros-gz-image \
  python3-vcstool python3-colcon-common-extensions python3-numpy

# sources (shallow)
git clone --depth 1 https://github.com/space-ros/demos.git ~/space_ros_demos          # b0b010e, 2026-09-01
git clone --depth 1 https://github.com/david-dorf/spaceros_gz_demos.git ~/spaceros_gz_demos  # 0810f4d

# workspace: symlink the three Curiosity packages + the sprint package, install-only build
mkdir -p ~/space_ws/src && cd ~/space_ws
for p in curiosity_description curiosity_gazebo curiosity_rover_demo; do
  ln -sfn ~/space_ros_demos/curiosity_rover/$p src/$p; done
ln -sfn ~/spaceros_gz_demos/spaceros_gz_demos src/spaceros_gz_demos
source /opt/ros/jazzy/setup.bash
colcon build --symlink-install --parallel-workers 1
```

Launch commands for the stages (**do not run until robot-mind-49 clears the machine**):

```bash
# stage A: engine search on the Mars terrain, headless, no ROS (gz transport bridge)
cd /mnt/c/dev/robot_mind-space && python3 experiments/embodied/space_find.py --seeds 7 \
  2>&1 | tee /root/space_find_s7.log

# stage B (designed, not built): the demo's full rover on real Nav2 under the packaged stack
source ~/space_ws/install/setup.bash && source ~/rmws/install/setup.bash
ros2 launch curiosity_gazebo curiosity_gazebo.launch.py          # gz + rover + controllers
ros2 run curiosity_rover_demo move_wheel                          # /cmd_vel -> wheels/steer
# then find_nav2.launch.py with world/robot parameters (§1.6)
```

### 1.5 Rendering path for the Mars world

Stage A runs a headless copy of the world (`field_sense.static_world_copy`: `<gui>` out;
only the three infrastructure systems kept — Physics, UserCommands, SceneBroadcaster —
content untouched) and spawns no rendering sensor, so it needs no GL. Physics must stay:
in gz-sim a `set_pose` request only writes a `WorldPoseCmd` component and the Physics
system is what applies it (the SubT launcher injects exactly these three systems; the
hospital world loads the defaults). A first draft of the copy dropped Physics and would
have failed every motion check — the reviewer's source read of gz-sim8 caught it before
any launch. Consequence: the 400k-triangle terrain collider is loaded (a DART mesh load,
one-off); every body in stage A is `<static>`, so nothing moves except by command. Stages B and C spawn the rover, whose
`gpu_lidar` and `camera` are ogre2 sensors: they render on Mesa EGL + llvmpipe, the path
that already renders the Nav2 world's lidar here. Expect the camera at low frame rates on
software GL; the lidar was fine.

### 1.6 Hidden-truth protocol for the Mars world (`experiments/embodied/space_find.py`)

The protocol is the hospital's, transplanted:

- **Map (the engine's LOCATION entities).** A station grid over the terrain: 6 m pitch,
  clipped to a 72 m square around the rover's spawn (`SEARCH_AREA = (−36, 36, −36, 36)`),
  cells whose height differs from a grid neighbour by more than 0.35 × pitch dropped.
  Measured tonight from the STL: **169 stations, z ∈ [−12.45, −1.23] m** (no cell was
  steep). The full terrain would give 2,597 stations — far beyond a 250-visit budget, so
  the clip is a declared config, disclosed with the result. Station heights come from a
  2 m raster of the mesh (max vertex z per cell). Contents are never in the map.
- **World setup (evaluator only).** Four unique-instance science targets (`sample_tube_1`,
  `heat_probe_1`, `radio_beacon_1`, `drill_bit_1`; static 0.3 m boxes) spawned at a depot
  600 m away, plus 12 `rock_k` distractors (0.6 m boxes) scattered 2 m from stations chosen
  by the fixed world seed `space_world`. Unique-instance classes make the class-level task
  and the instance grading coincide (the hospital lesson: a resident sibling satisfies a
  class find while grading demands the relocated one).
- **Per episode (seed s).** `random.Random(f"space_{s}")` picks the target instance, a
  station and a bearing; the target is placed 1.0 m off that station at terrain z + 0.3.
  **Truth = the station nearest the placed pose** (the same association rule the adapter
  uses, so a faithful nearest-station localization is never graded wrong). The scout
  (static box, motion verified once through the ECM) starts at the first station.
- **Sensing (adapter, stage A).** `LogicalSense`: every registered instance within 8 m of
  the commanded scout pose is a contact at 0.95 (the fidelity of Gazebo's logical camera —
  physics-state read, no rendering, no occlusion). The sought class's instances are read
  live from the ECM; everything else from the start snapshot. Claims through
  `field_sense.contacts_to_claims` (§4): LOCATED_AT the nearest station at the sensor's
  confidence; ABSENT_FROM every station whose 1.5 m association region lies inside the 8 m
  read (the hospital seed-5 fix); nothing for a station with sub-gate target evidence (the
  THOR YOLO fix); an instance-named target ignores same-class siblings (the decoy fix).
- **Grading.** `found_at == truth`, where truth is the station nearest the moved target's
  pose **as read back from the simulator's ECM after the placement settled** (the intended
  pose and its station are recorded beside it; an unconfirmed placement skips the
  episode). Restore: the target returns to the depot after every episode, ECM-verified, so
  no episode inherits a relocation. Budget 250 visits; the engine's ledger is fresh per
  episode by construction.
- **Seeds.** Smoke: seed 7, all the way through the fix loop of
  `benchmark-iteration-protocol` (probe each defect, fix adapter-side, commit). Battery:
  seeds **7, 11, 23, 42** on the committed build. Artifact:
  `data/artifacts/embodied/space_find.json` (per-seed rows: target, truth, found, visits,
  wall time; grid and sensor parameters).
- **Baselines.** `--policies engine,sweep,random`: the hospital campaign's scripted arms
  over the SAME executor pathway (same sensor read, same budget, same commitment rule —
  commit to the station nearest the first claim-grade sighting of the class). `sweep`
  walks the grid row-major from the first station; `random` shuffles it with a seeded RNG.
  They run on the committed build after the engine smoke is clean; rows carry a `policy`
  field and the artifact a per-policy summary.
- **Stage B — the rover drives.** The demo's rover under the packaged cognition stack:
  `cognition_node` (FindObject action) → Nav2 `NavigateToPose` goals → Nav2 with the
  session-nav2 configuration (DWB, SLAM Toolbox or the demo's `mars_map.yaml` + AMCL) on
  the rover's `/scan` and `/odom` → `/cmd_vel` → the demo's own `move_wheel` → the six
  wheel velocities and four steer angles. Sensing through `frustum_sensor_node` over the
  `/world_poses` shim, as certified 21/21 on the arena world. Certification script:
  `ros2_stack_cert.py --nav2` with a world parameter. Only changes needed are launch
  parameters (world file, robot name, frames, DWB limits for a 900 kg rover on Mars
  gravity) — no cognition changes. Not built tonight.
- **Stage C — real perception.** `yolo_sense_node` on the rover's `/image_raw` with
  YOLO-World prompted with the target classes; the targets then need meshes, not boxes.

### 1.7 Risks and unknowns (to be measured on the smoke seed)

1. `set_pose` and `create` answer true on ENQUEUE, not on execution (gz-sim's
   UserCommands service handler). The bridge therefore never trusts the answer: the scout
   is motion-verified through the ECM before any episode (`verify_motion`), every target
   placement and every restore is waited on through the ECM (`field_sense.wait_for_pose`,
   20 s, 0.25 m), an unconfirmed placement skips the episode with a message, and **truth is
   the station nearest the ECM readback**, with the intended truth recorded beside it.
2. `EntityFactory.name` / `.pose` are documented overrides (the pose is applied after
   creation); the post-spawn scene snapshot check catches a silent no-op.
3. Silent spawn no-ops (the THOR twin lesson): the script refuses to run if any spawned
   model is missing from the post-spawn scene snapshot.
4. World load time: the 20 MB collision mesh loads in seconds under the hospital-world
   precedent; the 600 s readiness loop is generous.
5. Station z from a 2 m raster of max vertex height can sit slightly above the surface
   under the scout; irrelevant for sensing (3D distance), relevant only in stage B.

## 2. Underwater

### 2.1 HoloOcean 2.3.0 — blocked on WSL2

- Built on Unreal Engine 5 and the Holodeck framework (BYU FRoStLab). Sensors: DVL, IMU,
  optical camera, imaging / profiling / sidescan / echosounder sonars, depth, raycast and
  semantic-raycast lidar; "3+ rich worlds"; documented as able to "run headless".
- Install: `pip install .` from `holoocean/client`, then `holoocean.install("Ocean")`
  downloads the packaged Unreal world; Python ≥ 3.7; "64-bit Linux or Windows"; docs ask
  for "a dedicated GPU" and, for Docker, an NVIDIA GPU with X11 forwarding; the engine
  source needs a GitHub account linked to Epic (EULA), and runtime Docker images are not
  distributed for the same reason. Docs pushed 2026-09-01; `holoocean-ros` pushed
  2026-05-21; the main repository is not visible to the GitHub search API (EULA-gated).
- Why it is blocked here: UE5 on Linux renders through Vulkan (Unreal's Linux RHI; not
  stated in HoloOcean's own docs, which say "OpenGL 3+" — inferred from the engine). The
  only Vulkan device WSL2
  exposes to this distro is `llvmpipe` (CPU); NVIDIA ships no Vulkan ICD for WSL2. UE5's
  packaged Linux builds will not run on a CPU Vulkan device at any usable rate, and
  "headless" in HoloOcean means no window, not no GPU. This is the same wall Habitat hit
  (no CUDA-EGL device), reported the same way: **needs native Linux with an NVIDIA driver,
  or native Windows.** HoloOcean does support Windows natively; the RTX 3070 on the host is
  a plausible path later (not staged tonight: GPU rule, and multi-GB downloads outside WSL).

### 2.2 Stonefish 1.5 — viable in software, second choice

- Last tagged release v1.5 (2025-06-10); `master` is at 2026-07-14 with CMake
  `VERSION 1.6.0`; GPL-3.0; C++ library (Bullet physics + own renderer). `stonefish_ros2`
  (`master` 2025-12-04, package version 1.6.0) provides the standard simulator node from an
  XML scenario and requires **the same library version** — so build both from `master`,
  not v1.5 + ros2 master. Jazzy support is not stated by the author; it is a ROS 2
  ament package with no distro pin.
- Requirement: **OpenGL 4.3** for the graphical simulator; the console simulator
  runs without graphics but then has no cameras, lights, depth-map sensors or waves.
  Sonars: **FLS, MSIS and SSS are GPU depth-map sensors (graphical mode only)**, with
  multiplicative + additive noise models and parameters `beams`, `bins`,
  `horizontal_fov`, `vertical_fov`, `range_min`, `range_max`; **Multibeam and Profiler are
  analytic ray-casts** and work in console mode.
- On WSL2 here: llvmpipe offers OpenGL 4.5 core, above the 4.3 minimum, so the graphical
  simulator *can* run in software, at low frame rates; the FLS would render on llvmpipe at
  small `beams × bins`. The build is C++ (`cmake .. && make -jX && sudo make install`) —
  deferred, since it pegs cores. Dependencies installed tonight: `libglm-dev`, `libsdl2-dev`,
  `libfreetype-dev` (24.04's name for `libfreetype6-dev`).
- Why second: a second engine, a second transport (`stonefish_ros2` only), a GPL licence,
  and a software-GL render path where DAVE gives us the gz stack we have already certified
  three times and a sonar with CUDA compute.

### 2.3 Project DAVE (`ros2` branch) — the pick

- IOES-Lab `dave`, branch `ros2` (HEAD cc98a53, 2026-05-20), Apache-2.0: the GSoC 2024/2025
  port of DAVE to **ROS 2 Jazzy + Gazebo Harmonic on Ubuntu 24.04**. Repositories
  (`extras/repos/dave.jazzy.repos`): `dave`, `dockwater`, `rocker`. The Docker image is
  `osrf/ros:jazzy-desktop-full` + an install script + ArduSub/MAVROS/QGroundControl — none
  of which the search protocol needs.
- Worlds (`models/dave_worlds/worlds/`): `dave_ocean_models.world`, `dave_graded_seabed`,
  `dave_ocean_waves{,_mossy_ground,_sonar,_sonar_integrated,_transient_current}`,
  `dave_Santorini`, `dave_multibeam_sonar`, `dave_integrated`, `dave_bimanual_example`,
  `dave_electrical_mating`, `dave_plug_and_socket`, `dvl_world`, `new_dvl`,
  `usbl_tutorial`, `camera_tutorial`, `ocean_current_plugin`.
- **`dave_ocean_models.world` is the search world.** It contains a `Sand Heightmap`
  seabed at z = −95, `Coast Water`, and DAVE's own catalogue of **named, single-instance
  seabed objects**: `torpedo_mk46`, `torpedo_mk48`, `sonobuoy`, `flight_data_recorder`,
  `uxo_b`, `uxo_c`, `hardhat_standard`, `hardhat_ribbed`, `hardhat_superribbed`,
  `hardhat_octagonal`, `mbari_mars` (all at x = 13, y ∈ [−6, 6], z = −94), plus unnamed
  clutter (two sunken vases, a Niskin bottle, four kelp, two corals, a lionfish, a sunken
  ship at (35, −10)). Eleven unique-instance target classes, exactly what the protocol
  demands, authored by the simulator's own maintainers.
- Sensors in the port: **multibeam forward-looking sonar** (`blueview_p900` model: 512
  beams, ±1.13447 rad = 130° horizontal, ±0.10472 rad = 12° vertical, range 0.1–10 m,
  900 kHz, 29.9 kHz bandwidth, `sensorGain 0.02`, topics `sonar_image_raw`/`sonar_image`),
  implemented as a custom gz rendering sensor (`multibeam_sonar_system`) with CUDA
  processing (GSoC 2025: 12.6× speed-up, cuBLAS); DVL (`gz-sim-dvl-system`, in Harmonic
  itself), USBL, underwater camera; vehicles `rexrov`, `bluerov2`, `bluerov2_heavy`,
  `bluerov2_heavy_multibeam_sonar`, `glider_slocum`.
- CMake facts for the sonar: `find_package(CUDAToolkit QUIET)` — **without a CUDA
  toolkit the package builds nothing** (it prints one STATUS line, "CUDA Toolkit not found
  or disabled: Skipping CUDA-specific targets", and installs an empty package); with it, `enable_language(CUDA)`,
  `CUDA_ARCHITECTURE` cache variable (default `60`; set `86` for the RTX 3070), and it
  needs `gz-sim8`, `gz-sensors8`, `gz-rendering8` (ogre or ogre2), OpenCV, `cv_bridge`,
  `marine_acoustic_msgs`.
- On WSL2 here: the sonar renders through ogre2 (llvmpipe EGL, the path that works) and
  computes through CUDA (`cuInit` succeeds from this distro). Plausible, **unverified**:
  the build has not been attempted (all-core C++ + nvcc, excluded tonight). Stage A of the
  protocol needs none of it: the world and its models load in the same static
  transport-only configuration the SubT adapter uses.

### 2.4 Install (done tonight unless marked)

```bash
sudo apt install -y --no-install-recommends libeigen3-dev protobuf-compiler \
  ros-jazzy-cv-bridge ros-jazzy-marine-acoustic-msgs python3-numpy
git clone --depth 1 -b ros2 https://github.com/IOES-Lab/dave.git ~/dave      # cc98a53

# Fuel models of the ocean-objects world (24 unique URIs), prefetched into ~/.gz/fuel:
#   hmoyen: sand heightmap, torpedo mk46/mk48, sonobuoy, flight data recorder,
#   unexploded ordnance b/c, hardhat standard/ribbed/superribbed/octagonal, mbari mars,
#   sunken vase with inertia, niskin with inertia, north east down frame (39 MB)
#   cole: kelp 01-04, coral01/02, lionfish, sunken vase 02, sunken ship
#   openrobotics: coast water
gz fuel download -u "https://fuel.gazebosim.org/1.0/hmoyen/models/Sand Heightmap"  # etc.
# (the world names the retired host fuel.ignitionrobotics.org for half of them; the
#  adapter's patched copy rewrites it to fuel.gazebosim.org, which is how the cache is keyed)

# CUDA toolkit for the stage-B sonar build (WSL repo; toolkit only, never a driver) —
# installed tonight: /usr/local/cuda/bin/nvcc = CUDA 12.8
wget https://developer.download.nvidia.com/compute/cuda/repos/wsl-ubuntu/x86_64/cuda-keyring_1.1-1_all.deb
sudo dpkg -i cuda-keyring_1.1-1_all.deb && sudo apt update && sudo apt install -y cuda-toolkit-12-8

# stage B build (NOT tonight; after clearance; two workers so the machine stays usable)
mkdir -p ~/dave_ws/src && ln -sfn ~/dave ~/dave_ws/src/dave && cd ~/dave_ws
source /opt/ros/jazzy/setup.bash
colcon build --symlink-install --parallel-workers 2 \
  --packages-up-to multibeam_sonar multibeam_sonar_system dave_sensor_models dave_worlds \
  --cmake-args -DCUDA_ARCHITECTURE=86 -DCMAKE_CUDA_COMPILER=/usr/local/cuda/bin/nvcc
```

Launch for stage A (**do not run until cleared**):

```bash
cd /mnt/c/dev/robot_mind-space && python3 experiments/embodied/marine_find.py --seeds 7 \
  2>&1 | tee /root/marine_find_s7.log
```

### 2.5 The sonar sense model (`experiments/embodied/field_sense.py`)

Contract. A sense model answers "what do you sense from this pose and heading" with
`Contact`s: instance name (or empty for a bare echo), class, position, range, bearing,
**`strength` = the sensor's own confidence in [0, 1]**, and a source tag. The adapter
never sees anything else; the evaluator's placement enters only through the sensor's
read of the world, as it would for a real sonar.

Stage A (`LogicalSonar`): the BlueView P900 footprint (10 m, 130°) over physics-state
poses, three fans per station (headings 0°, 120°, 240° — the AUV yaws the fan through
390°) from one ECM read, and a **declared echo curve**
`strength = 0.95 · 0.5^((r / 10)²)`: 0.95 at 0 m, 0.475 at the rated range, half-power
at 10 m. With the claim gate at 0.5 the effective detection radius is 9.6 m; a contact
between 9.6 and 10 m is real but weak and records nothing for its station (rule 4 below).
This is a stand-in with its shape written down, not a measurement of anything; the artifact
carries the curve's parameters. The P900's 12° vertical fan is not modelled in stage A
(the footprint is a horizontal sector): at 2 m altitude a seabed object at the rated range
sits 8.5° below horizontal, inside the fan once the head is pitched down, which is how an
AUV surveys; the real geometry arrives with the real sensor in stage B.

Stage B (designed): the real `multibeam_sonar` image on the scout (blueview_p900 attached
to a static body). Identity by association — the known instances' poses projected into
(range, bearing) bins, the same principle as THOR's instance boxes and the Nav2+YOLO plan —
and **`strength` = the normalized echo statistic of the object's bin footprint against
background**. As in the paper's detector paragraph: precision comes from the association,
so recall is the number; disclosed the same way.

Claim rules (`contacts_to_claims`, each pinned by a test):

1. Contact ≥ gate → LOCATED_AT the nearest station at the contact's strength (the
   engine's anchor path is status-gated, not confidence-gated).
2. Class-level target satisfied by any instance; instance-named target only by that
   instance; a same-class sibling in the swath is not the target.
3. No target contact → ABSENT_FROM every station whose 1.5 m association region lies
   wholly inside the swath (range ≤ range_max − 1.5; for a directional fan also inside the
   cone with an angular margin of 1.5 / range), at 0.95. For the three-fan sweep the union
   footprint is omnidirectional at the rated range. The test is on the 3D distance to the
   station centre; an object 1 m off a cleared station plus the terrain raster's height
   difference could in principle sit outside the read (Mars: only if the 2 m raster differs
   by more than ~3.8 m within a cell — not the case on this terrain; seabed: worst case
   8.2 m, still a 0.60 echo above the gate).
4. A sub-gate contact of the target class in the swath records nothing for its station —
   no sighting, no absence.
5. Confidence clamped to [0, 1], three decimals.

### 2.6 Hidden-truth protocol for the DAVE world (`experiments/embodied/marine_find.py`)

- **Map.** Survey stations on a 5 m grid over x ∈ [−5, 40], y ∈ [−20, 12] at 2 m altitude
  above the nominal seabed (z = −93): **70 stations** (`sv_<row>_<col>`). Pitch below the
  rated range, so neighbouring swaths overlap; the object catalogue and the sunken ship are
  inside the grid. Contents never in the map.
- **World.** A patched copy of `dave_ocean_models.world`: GUI block removed; Buoyancy,
  DVL and Sensors systems removed; Physics, UserCommands and SceneBroadcaster kept (the
  three the SubT launcher injects — Physics applies `set_pose`); **gravity set to 0 0 0**
  because the eleven objects, the vases and the lionfish are not `<static>` and were meant
  to sink under the stripped Buoyancy system — with zero gravity they stay where authored
  or commanded; **every include pinned `<static>true</static>`** (sdformat's include-level
  override) so an object authored into the heightmap is not pushed out by contact
  resolution (a static model still moves on `set_pose`, as the SubT scout does); Fuel host
  names rewritten. Includes' poses and lights untouched.
- **Targets.** The eleven named objects, filtered at launch to those the loaded scene
  actually contains with exactly one instance of their class (the script refuses to run if
  none is present — a Fuel fetch failure is not a result).
- **Per episode (seed s).** `random.Random(f"marine_{s}")` picks the target, a station and
  a bearing; the object is placed 1.0 m off the station on the seabed (z = −94.5). Truth =
  nearest station to the placed pose. The scout starts at the first station. Restore: the
  object returns to its start-of-world pose (the scene snapshot) after the episode.
- **Grading, budget, seeds, artifact, baselines.** As for Mars: truth from the ECM
  readback of the moved object after the placement settled (intended pose recorded), ECM-
  verified restore, 250 visits, smoke seed 7 then 7/11/23/42, `--policies engine,sweep,random` on the
  committed build (the scripted arms commit only on a claim-grade echo, as the engine's
  anchor path does), `data/artifacts/embodied/marine_find.json` with the sonar parameters
  and the declared curve recorded.
- **Stage C.** DAVE's `bluerov2_heavy` under the packaged stack. DAVE drives its BlueROV2s
  through **ArduSub SITL + MAVROS** (per-vehicle `ardusub.parm`; the Docker image installs
  ArduSub, MAVROS and QGroundControl); `dave_ros_gz_plugins` on the `ros2` branch holds
  only a DVL bridge, an ocean-current plugin and spherical coordinates — no thruster
  allocation or altitude hold. So stage C means the NavigateToPose client targeting a
  MAVROS guided-mode setpoint (or a small thruster-allocation node written for the
  purpose), `/odometry` from the DVL bridge. Nav2 does not apply underwater. Designed
  only, and the drive loop is the larger part of the work.

### 2.7 What the marine result would and would not show

If the engine finds the object at the truth station in 4/4 seeds within budget: the search
policy transfers to a sonar-shaped sensor with range-dependent confidence and a
directional swath — the first hidden-truth seabed object search we know of in an open
simulator. It would not show sonar perception (stage A's echoes are physics-state reads
with a declared curve and a horizontal-only footprint — the 12° vertical fan is not
modelled), hydrodynamics, navigation error, or currents. Those are what
stages B and C add, one at a time, each measured before it is claimed.

### 2.8 Fallback already in hand

`spaceros_gz_demos/worlds/enceladus.sdf` (staged, builds, Harmonic-native): a submarine with
a gpu_lidar published as sonar in a liquid ocean on Enceladus. The same `marine_find.py`
protocol runs there with the lidar-as-sonar footprint if the DAVE world's Fuel assets fail
to load — a planetary-ocean search rather than a seabed-object search. And the SubT cave
worlds already measured 12/12 are the planetary-cave analogue (JPL CoSTAR's motivation).

## 3. Lunar note

The Moon was part of the question. Options seen tonight, none staged: `space-ros/demos/
lunar_pole_exploration_rover` and `lunar_terrain` (a DEM-based lunar world with a sun
plugin from JPL Horizons ephemerides — Docker-first like the rest), `spaceros_gz_demos/
moon.sdf` (X1/X2 rovers; **staged in `~/space_ws`**, same drive loop as Mars), OmniLRS and
the NASA Lunar Autonomy Challenge simulator (Isaac Sim — GPU, excluded tonight). The Mars
protocol runs unchanged on `moon.sdf` with a `--world` flag once Mars is measured.

## 4. Adapter skeletons and tests

| File | Role |
|---|---|
| `experiments/embodied/field_sense.py` | `Contact`, `SenseModel`, `station_grid`, `nearest_station`, `contacts_to_claims`, `sonar_strength`, `LogicalSense`, `LogicalSonar`. No simulator import. |
| `experiments/embodied/space_find.py` | `SpaceExecutor` / `SpaceSession` (the engine's executor contract: `execute(action, target, now)` → report with result, new claims, time spent, robot location), `SpaceEvaluator` (spawns, placements, grading, restore), `SpaceBridge` (SubtBridge + spawn + sense channel; gz imported lazily), STL bounds/raster, `main`. |
| `experiments/embodied/marine_find.py` | `MarineExecutor` / `MarineSession`, `MarineEvaluator`, `MarineBridge` (one ECM read per station, three fans), `patch_world`, `main`. |
| `tests/test_space_marine_adapters.py` | 25 tests: grid naming/order/slope rule; nearest-station tie-break; class parsing; every claim rule (sighting at sensor confidence, sibling ignored, swath-only absence, sub-gate suppression, cone for sightings and absence, clamp/out-of-range, purity); the sonar curve and both sense models; the evaluators' seeded placements, restore and reproducibility; **the executor holds no reference to the evaluator**; a visit reads the world only through the sense channel; the world patch keeps only the three infrastructure systems, zeroes gravity for the seabed copy and rewrites Fuel hosts; the scripted arms commit on first claim-grade sight and the random arm is seeded; the ECM poll trusts only the readback. |

`uv run pytest`: **212 passed** (187 before + 25) on the Windows venv, 2026-09-02.
`uv run ruff check` clean on the four files.

Not tested, by construction: anything that needs Gazebo (spawn, set_pose, ECM readback,
world load). Those are exercised by the smoke seed under the fix loop.

## 5. Staged state on WSL Ubuntu-24.04 (verified from the logs)

- apt: the ros2_control set, cyclonedds, xacro, robot_state_publisher, ros_gz_image,
  vcstool, colcon, numpy, Stonefish deps, Eigen, protobuf, cv_bridge, marine_acoustic_msgs
  — exit 0. `mesa-utils`, `vulkan-tools` (for the measurements in §0).
- `~/space_ros_demos` (166 MB), `~/spaceros_gz_demos` (413 MB), `~/dave` (97 MB).
- `~/space_ws/install`: `curiosity_description`, `curiosity_gazebo`, `curiosity_rover_demo`,
  `spaceros_gz_demos` (colcon exit 0).
- `~/.gz/fuel`: all 24 models of the DAVE ocean-objects world. Inspected: the object
  models carry no plugins and no `<static>` flag (they were meant to sink under Physics —
  inert in the static copy); `sand heightmap`, kelp, corals and the ship are static meshes;
  `coast water` carries one model-level plugin, `gz-sim-shader-param-system` (a visual
  shader; nothing renders in stage A). Model names as the models declare them — the ones
  the scene service will report: `sand_heightmap`, `coast_waves`, `world_ned`,
  `Kelp01`..`Kelp04`, `coral01`, `coral02`, `Lionfish`, `Pot01`, `Pot02`, `niskin`,
  `sunkenship`; the eleven targets take the world's `<name>` overrides. The adapter's
  non-contact filter uses exactly these.
- `cuda-toolkit-12-8`: **installed** (`/usr/local/cuda/bin/nvcc`, CUDA 12.8.r12.8), stage
  script finished 01:08 EDT.
- SDF-parser validation (`gz sdf -p` / `-k`, no simulator) of the patched copies written by
  the adapters' own functions: both parse; the only errors are include resolution, which
  the bare parser cannot do (no find callback) — expected. It exposed one real defect: the
  DAVE world's name is **`dave_ocean_model`**, not `default`; the bridge would have waited
  forever on `/world/default/...`. Both adapters now read the name from the SDF
  (`field_sense.world_name_of`) instead of assuming it.
- Nothing launched: no `gz sim`, no ROS graph, no GPU job, nothing on the `Ubuntu` distro.
  Load average stayed the THOR/decoy batteries' own (21–24 on 16 cores).

Logs: `/root/space_marine_stage.log`, `/root/space_marine_fuel.log`.

## 6. Morning run order (after robot-mind-49 says the machine is free)

robot-mind-49's window (02:00 message): after the THOR seeds, the integrator's three
certifications and the relaunched decoy-30 run — roughly 03:00–04:00 — the two seed-7
smokes may run alongside the decoy run; batteries after the fix loop; keep the load average
under about 8 and never more than one `gz sim` of this track at a time.

Launcher: `bash scripts/space_marine_smoke.sh space|marine <seeds>` from Ubuntu-24.04 —
it refuses to start while another `gz sim` of this track (a `mars_rm`/`dave_rm` copy) is
alive or the load average is above 8 (`LOAD_CEIL`; other sessions' batteries are not
counted, the supervising session decides the window), exports `GZ_PARTITION=space_marine`
so the server, the Python transport node and the `gz model` readbacks live in their own gz
transport partition and never share the default one with another session's world (a
`gz model` readback discovers worlds through the partition, so sharing it with a second
server is a wrong-world risk), streams to `~/<track>_find_s<seeds>.log`, writes the artifact to
`data/artifacts/embodied/<track>_find_s<seeds>.json`, and prints the build SHA it ran on.

1. Mars smoke: `bash scripts/space_marine_smoke.sh space 7` (equivalently
   `python3 experiments/embodied/space_find.py --seeds 7 2>&1 | tee /root/space_find_s7.log`). Expect the world-up line, `169 stations`, the spawn check, then
   the seed line. On any defect: probe the exact failing case, fix adapter-side, rerun seed
   7, commit — never touch `src/`.
2. Marine smoke: `python3 experiments/embodied/marine_find.py --seeds 7 2>&1 | tee
   /root/marine_find_s7.log`. Expect `70 stations`, a model count ≥ 25, `11 unique-instance
   targets`. First load may be slow (Fuel cache validation); the readiness loop is 900 s.
3. Batteries on the committed build: `--seeds 7,11,23,42` for each, logs
   `/root/space_find_battery.log`, `/root/marine_find_battery.log`; artifacts land in
   `data/artifacts/embodied/`.
4. Scripted baselines on the same stations: `bash scripts/space_marine_smoke.sh space
   7,11,23,42 engine,sweep,random` (and `marine`), then the numbers go to this document
   first; the integrator folds them into the paper.
5. Stage B only after A is clean: Nav2 on the Curiosity rover (`find_nav2.launch.py` with
   world/robot parameters), and the DAVE sonar build with `--parallel-workers 2`.

### 6.1 Pre-registered placements (computed before any run, build 0bf6038)

The seeds are strings into `random.Random`, so the placements are fixed by the code; this
table was produced by a WSL dry-run of the evaluators (no simulator) so that the truth of
each episode is on record before the first launch. The simulator's own pose of the moved
object remains the grading signal; this table is what it must agree with.

| Track | Seed | Target | Truth station | Placed (x, y, z) |
|---|---|---|---|---|
| Mars | 7 | heat_probe | st_0_11 | (30.7, −36.7, −12.19) |
| Mars | 11 | drill_bit | st_4_7 | (5.8, −13.0, −9.37) |
| Mars | 23 | radio_beacon | st_6_2 | (−23.3, −0.7, −6.54) |
| Mars | 42 | drill_bit | st_5_2 | (−24.8, −5.4, −6.97) |
| Seabed | 7 | flight_data_recorder | sv_2_3 | (10.9, −9.6, −94.50) |
| Seabed | 11 | uxo_c | sv_2_2 | (4.5, −10.9, −94.50) |
| Seabed | 23 | uxo_b | sv_5_7 | (29.0, 5.2, −94.50) |
| Seabed | 42 | hardhat_ribbed | sv_3_2 | (5.3, −4.0, −94.50) |

Also from the dry-run: the WSL system Python imports the engine and both adapters
(7.9 s cold), `gz.msgs10` `EntityFactory` exposes `name` and `pose` (the spawn path), the
world names resolve to `default` and `dave_ocean_model`, and a clean sonar read at the
first survey station clears exactly its four-station neighbourhood (`sv_0_0`, `sv_0_1`,
`sv_1_0`, `sv_1_1`) under the 10 m − 1.5 m rule.

### 6.2 Measured so far (updated as runs complete)

| Track | Seed | Policy | Target | Truth (ECM readback) | Found | Visits / stations | Wall | Build | Verdict |
|---|---|---|---|---|---|---|---|---|---|
| Mars | 7 | engine | heat_probe | st_0_11 (= intended; readback (30.677, −36.736, −12.188) equals the placement) | st_0_11 | 59 / 169 | 234 s | 1f99838 | **CORRECT**, zero wrong commitments |
| Seabed | 7 | engine | flight_data_recorder | sv_2_3 (= intended; readback (10.91, −9.585, −94.5) equals the placement) | sv_2_3 | 11 / 70 | 11.5 s | ad60ee1 | **CORRECT**, zero wrong commitments |

Mars smoke notes: world up with Physics present (the 400k-triangle collider loaded within
the readiness window); scout motion verified through the ECM; spawns all present in the
scene snapshot; gz server log has zero errors or warnings; the run used the default gz
transport partition (the partition isolation was added afterwards at robot-mind-49's
request). Seabed smoke notes: world up with 26 models and all 11 unique-instance targets; Physics
present with zero gravity and every include pinned static; run on `GZ_PARTITION=
space_marine`; gz server log clean (informational lines only). Neither smoke exposed an
adapter defect (no skipped placements, no readback drift, no absence claims at sighted
stations), so per the iteration protocol the committed build proceeds to the scripted
arms and the four-seed batteries unchanged.

### 6.3 Mars four-seed battery (measured 03:08–03:14, build ad60ee1, `GZ_PARTITION=space_marine`)

Artifact `data/artifacts/embodied/space_find_s7_11_23_42.json`; every ECM readback equals
its placement; 12 of 12 episodes correct, zero wrong commitments in every arm.

| Seed | Target | Truth | engine visits | sweep visits | random visits |
|---|---|---|---|---|---|
| 7 | heat_probe | st_0_11 | 58 | 11 | 34 |
| 11 | drill_bit | st_4_7 | 24 | 46 | 3 |
| 23 | radio_beacon | st_6_2 | 21 | 68 | 37 |
| 42 | drill_bit | st_5_2 | 21 | 55 | 30 |
| **correct** | | | **4/4** | **4/4** | **4/4** |
| mean visits (of 169 stations) | | | 31.0 | 45.0 | 26.0 |

Wilson 95% interval for 4/4 is [0.51, 1.00] per arm ([0.76, 1.00] for the 12 pooled
episodes). **How to read this, exactly as the paper reads the plain SubT and hospital
protocols (limitation 10):** with uniform priors, an always-present target and no evidence
before the first contact, this protocol grades search completeness and correct commitment
only. The engine's order until evidence arrives is a nearest-first sweep, so a random order
can beat it by luck at n = 4, and the three visit means are inside noise (per-seed spreads
of 3 to 68 visits). No efficiency claim is made from these numbers; the same finding on
the same protocol is what the hospital campaign reported before its planted-tip variant
separated the policies. Seed 7's engine arm took 58 visits here against 59 in the smoke on
the same placement (readback identical to three decimals): run-to-run variance of one
visit in a physics world, the same class the integrator is chasing on the hospital seed 3
(settle timing at placement). The ECM settle guard stays, and from the commit that records this battery on, both
adapters log the settle time of every placement in the artifact (`settle_s`).

### 6.4 Seabed four-seed battery (measured 03:20–03:29, build c3220b9 minus the settle logging, `GZ_PARTITION=space_marine`)

Artifact `data/artifacts/embodied/marine_find_s7_11_23_42.json`; world up with 26 models and
all 11 unique-instance targets; every ECM readback equals its placement; 12 of 12 episodes
correct, zero wrong commitments in every arm; gz server log clean.

| Seed | Target | Truth | engine visits | sweep visits | random visits |
|---|---|---|---|---|---|
| 7 | flight_data_recorder | sv_2_3 | 11 | 13 | 5 |
| 11 | uxo_c | sv_2_2 | 12 | 3 | 6 |
| 23 | uxo_b | sv_5_7 | 6 | 47 | 2 |
| 42 | hardhat_ribbed | sv_3_2 | 2 | 22 | 4 |
| **correct** | | | **4/4** | **4/4** | **4/4** |
| mean visits (of 70 stations) | | | 7.75 | 21.25 | 4.25 |

Wilson 95% interval for 4/4 is [0.51, 1.00] per arm. Same reading as Mars, word for word:
uniform priors, an always-present target and no evidence before the first echo, so the
protocol grades completeness and correct commitment only; the engine's order until
evidence arrives is a nearest-first sweep, a random order can beat it by luck at n = 4,
and the visit means are inside noise. No efficiency claim. Seed 7's engine arm took 11
visits in the battery and 11 in the smoke (same placement, readback identical), so the
one-visit variance seen on Mars did not recur here. This battery ran before the settle-time
logging was added, so its rows carry `settle_s: null`.

What the two batteries do establish, with the weight they earn: on two new field
geometries (a 169-station Mars terrain with an 8 m logical mast sensor; a 70-station
seabed survey with a sonar-shaped sensor whose confidence falls with range and whose
absence bookkeeping follows a fan), the engine's search completes and commits correctly in
8 of 8 seeded episodes, with the same adapter rules and the same untouched engine as the
warehouse, THOR, SubT and hospital campaigns. That is transfer of the search machinery to
planetary and underwater station maps, measured, and nothing more.

### 6.5 The discriminating variant: planted tips and staged decoys (DESIGNED, pre-registered, not run)

The `hospital_tips.py` pattern, transplanted to both worlds and to be run only after the
batteries above are recorded:

- **Tip.** Before the search, the evaluator ingests one REPORTED claim
  `unknown:<class> LOCATED_AT <tip station>` at the hospital's tip confidence through the
  front door (the same path the warehouse uses for witness reports). The engine decides what
  the report is worth; the scripted arms are `sweep` (ignores it) and `tipfollow` (visits
  the tip station first, then sweeps).
- **Tip coin, pre-registered now.** `random.Random(f"{track}_tip_{seed}").random() < 0.5`
  is TRUE; a TRUE tip names the truth station, a FALSE tip names a different station drawn
  uniformly from the rest with `random.Random(f"{track}_tipspot_{seed}")`. Coins for the
  four seeds, computed before any tip episode: **Mars 7 TRUE, 11 TRUE, 23 FALSE, 42 FALSE;
  seabed 7 FALSE, 11 FALSE, 23 TRUE, 42 TRUE.** Both cells hold two seeds, so no addendum
  seeds are needed; if more power is wanted later, the addendum rule is the hospital's:
  the first integer seeds, in order, whose coin fills the thinner cell.
- **Decoy staging (the `hospital_tips_twin.py` trick, embodied).** For every FALSE-tip
  seed the evaluator stages a same-class look-alike beside the lied-about station — on
  Mars a second static box of the target class named `<class>_9` at the tip station plus
  1.0 m on a bearing from `random.Random(f"space_decoy_{seed}")`; on the seabed a second
  instance of the same Fuel model (`<name><class>_9</name>`, e.g. a second `uxo_b` at the
  tip station on the seabed) — and the briefing names the asset id, so a class-matching
  commit rule can now be fooled. TRUE-tip seeds carry no decoy and reduce to the plain
  protocol. The decoy is spawned after the world snapshot and removed (moved to the depot,
  ECM-verified) after the episode, so no later episode inherits it.
- **The four deciders, as in `hospital_tips_twin.py`:** `engine` (unchanged engine; the tip
  enters as a REPORTED claim about the asset id); `sweep` (row-major sweep, commits on
  CLASS match — naive); `tipfollow` (tip station first, then sweep, commits on CLASS match
  — naive, fast and wrong when fooled); `tipfollow_id` (tip station first, then sweep,
  commits only on the NAMED instance — the scripted arm that cannot be fooled but pays the
  sweep). All four share the executor pathway, budget and sensor.
- **Grading.** Correctness against the ECM readback of the real target, as above; visits
  split by TRUE and FALSE cells; the numbers that matter are wrong commitments under FALSE
  tips with a decoy present (the engine must verify, not obey — the hospital measured
  engine 6/6 correct, `sweep` fooled 4/6, `tipfollow` fooled 5/6) and the TRUE-cell visit
  count against `tipfollow`. n = 4 per world gives two seeds per cell; the decoy cell is
  therefore directional at best (Wilson for 2/2 is [0.34, 1.00]) — a power run needs the
  addendum rule. Files: `space_tips.py`, `marine_tips.py` (not written), artifacts
  `space_tips.json`, `marine_tips.json`.

## 7. Claims

Both four-seed batteries are measured (§6.3, §6.4); the sentences the numbers support are:
"On the Space ROS Curiosity Mars terrain (169 stations, logical 8 m mast sensor), the engine
localized the relocated cache in 4/4 seeded episodes (Wilson [0.51, 1.00]) at 21–58 visits,
zero wrong commitments; scripted sweep and random arms also 4/4, visit means inside noise
(limitation 10)"; "On Project DAVE's ocean-objects world (70 survey stations, a BlueView
P900 footprint with a declared echo curve), 4/4 at 2–12 visits, zero wrong commitments;
sweep and random 4/4, means inside noise." Each with the stage-A disclosure (physics-state
sensing, teleport-abstracted motion, declared curve, horizontal-only fan) in the same
paragraph, and no efficiency claim until the planted-tip variant (§6.5) is run. Every
negative stays in. Not claimed: driving the rover or the AUV, sonar perception, Space ROS
itself (the demo packages on vanilla Jazzy), lunar worlds.

## 7.1 Reviewer pass (2026-09-02, before any launch)

A separate reviewer agent red-teamed this document and the three adapter files against
the gz-sim8 sources and the third-party repositories (read-only; no simulator, no WSL).
What it found and what changed:

- **Blocker, fixed.** The headless world copy dropped the Physics system; in gz-sim8
  `set_pose` only writes a `WorldPoseCmd` and Physics is the only system that applies
  it, so every motion check would have failed. The SubT launcher's own `INFRA_PLUGINS`
  injects Physics (its docstring says otherwise — the misquoted precedent). The copy now
  keeps Physics, UserCommands and SceneBroadcaster; the seabed copy also zeroes gravity
  because DAVE's objects are not `<static>` and were meant to sink under Buoyancy.
- **Likely bug, fixed.** gz's `set_pose` / `create` services answer true on enqueue, so
  the placement guard was dead and truth came from the intended pose. Placements and
  restores are now waited on through the ECM (`wait_for_pose`), an unconfirmed placement
  skips the episode, and truth is the station nearest the readback (intended recorded).
- **Doc errors, fixed.** Stage-C drive loop for DAVE (ArduSub SITL + MAVROS, not a
  thruster plugin); Stonefish version/compatibility (build both from `master` 1.6.0);
  `spaceros_gz_demos` dependencies and PR #33 author/date; demos commit date; the CUDA
  CMake message; test counts; the §1.3 sentence that claimed rover/controllers/topics for
  stage A; "measured SubT pattern" wording; the HoloOcean Vulkan statement marked as an
  engine-level inference; the 3D absence test and the vertical sonar fan disclosed.
- **Verified correct, no change:** the Space ROS release facts, the Curiosity demo's
  packages/controllers/topics/services, nav2_demo, the DAVE world catalogue and P900
  parameters, the STL parser layout (file is exactly 84 + 400,000 × 50 bytes), the grid,
  the plugin regex, the paths, the world names, and the absence of any hidden-truth leak.

## 8. Sources checked tonight

- Space ROS releases: github.com/space-ros/space-ros (releases API: jazzy-2026.07.0,
  2026-08-01); space.ros.org; Getting Started (Docker Hub `osrf/space-ros`).
- Demos: github.com/space-ros/demos (README, `curiosity_rover/` README, Dockerfile,
  package manifests, `curiosity_gazebo.launch.py`, `mars_curiosity.world`,
  `mars_rover_control.yaml`, `sensor_mast.xacro`, `curiosity_mars_rover.gazebo`,
  `move_wheel`, `nav2_demo/` README, `nav2_params.yaml`, `mars_map.yaml`); Mars-Rover.rst in
  space-ros/docs.
- github.com/david-dorf/spaceros_gz_demos (README topic tables, `mars.launch.xml`,
  `load_world.launch.py`, `worlds/mars.sdf`, manifest); PR space-ros/demos#33 (open).
- DAVE: github.com/IOES-Lab/dave branch `ros2` (README, `.docker/jazzy.amd64.dockerfile`,
  `extras/repos/dave.jazzy.repos`, `gazebo/dave_gz_multibeam_sonar/multibeam_sonar/
  CMakeLists.txt`, `models/dave_worlds/worlds/*.world`, `blueview_p900/model.sdf`);
  Open Robotics Discourse GSoC 2024/2025 posts; field-robotics-lab.github.io/dave.doc.
- Stonefish: github.com/patrykcieslak/stonefish (README, releases), stonefish.readthedocs.io
  (building, install, sensors), github.com/patrykcieslak/stonefish_ros2.
- HoloOcean: byu-holoocean.github.io/holoocean-docs (v2.3.0 index and installation),
  github.com/byu-holoocean/holoocean-ros.
- This machine: `glxinfo -B`, `eglinfo -B`, `vulkaninfo --summary`, `libcuda` `cuInit`,
  `apt-cache policy`, the staging logs.
