cmake_minimum_required(VERSION 3.0.2)
project(emotion)

find_package(catkin REQUIRED COMPONENTS
  rospy
  std_msgs
  sensor_msgs
  geometry_msgs
  cv_bridge
  tf
  tf2_ros
  tf2_geometry_msgs
  pal_interaction_msgs
)

catkin_package()

catkin_install_python(PROGRAMS
  src/emotion.py
  DESTINATION ${CATKIN_PACKAGE_BIN_DESTINATION}
)
