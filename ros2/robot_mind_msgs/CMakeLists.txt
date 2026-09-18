cmake_minimum_required(VERSION 3.8)
project(robot_mind_msgs)

find_package(ament_cmake REQUIRED)
find_package(geometry_msgs REQUIRED)
find_package(std_msgs REQUIRED)
find_package(rosidl_default_generators REQUIRED)

rosidl_generate_interfaces(${PROJECT_NAME}
  "action/FindObject.action"
  "srv/IngestClaim.srv"
  "srv/QueryBelief.srv"
  "srv/Sense.srv"
  "msg/SeabedContact.msg"
  "msg/CellStatus.msg"
  "msg/CellStatusArray.msg"
  DEPENDENCIES geometry_msgs std_msgs
)

ament_package()
