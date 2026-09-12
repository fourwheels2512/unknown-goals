# ROS 2 message definitions

`robot_mind_msgs` is the typed interface the engine speaks on a robot. It
is an ordinary ament_cmake interface package with no dependency on the
engine, and it is the part of the ROS 2 integration this kit ships, under
Apache-2.0. The nodes that implement these interfaces are part of the
engine and are not distributed.

| interface | purpose |
|---|---|
| `action/FindObject.action` | ask for an object; feedback per step, result with the commitment and its proof |
| `srv/IngestClaim.srv` | put one typed claim on the evidence ledger |
| `srv/QueryBelief.srv` | ask what is believed about an entity, and why |
| `srv/Sense.srv` | the perception contract: look from here, report what was seen |

The definitions are the contract the paper's certification runs used, so a
third-party perception stack or planner can be written against them
directly: `Sense` is the seam where a detector plugs in, and `FindObject`
is the seam where a task executive does.

## Build

```
mkdir -p ~/ros2_ws/src && cd ~/ros2_ws/src
cp -r <this kit>/ros2/robot_mind_msgs .
cd ~/ros2_ws && colcon build --packages-select robot_mind_msgs
source install/setup.bash
ros2 interface show robot_mind_msgs/action/FindObject
```

Tested on ROS 2 Humble and Jazzy.

## What the interfaces imply

Two properties of the engine show up in the message fields rather than in
prose, and they are worth reading before writing against them.

* **A result carries its proof.** `FindObject` does not return a pose and a
  confidence alone; it returns what the commitment rests on. A caller can
  refuse a result whose provenance it does not accept.
* **Sensing is a service, not a topic.** The engine chooses where to look
  next and then asks. A perception node that answers `Sense` is answering a
  question the engine decided to ask, which is why the same engine runs
  against a simulator, a real camera, or recorded detections without
  changing.

`Sense` carries `bool ok` and `string error` so a perception failure is
reported as a failure rather than as an absence of the object: the
difference matters to everything downstream.

Copyright (c) 2026 Kiran Nayudu. Apache-2.0.
