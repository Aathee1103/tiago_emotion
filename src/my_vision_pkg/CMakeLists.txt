cmake_minimum_required(VERSION 3.8)
project(my_vision_pkg)

# =====================
# C++ dependencies
# =====================

find_package(ament_cmake REQUIRED)
find_package(rclcpp REQUIRED)
find_package(rclcpp_action REQUIRED)

find_package(moveit_ros_planning_interface REQUIRED)
find_package(moveit_core REQUIRED)

find_package(control_msgs REQUIRED)
find_package(trajectory_msgs REQUIRED)
find_package(tf2_geometry_msgs REQUIRED)

# =====================
# C++ executable
# =====================

add_executable(moveit_arm
  my_vision_pkg/moveit_arm.cpp
)

ament_target_dependencies(moveit_arm
  rclcpp
  rclcpp_action
  moveit_ros_planning_interface
  moveit_core
  control_msgs
  trajectory_msgs
  tf2_geometry_msgs
)

install(TARGETS
  moveit_arm
  DESTINATION lib/${PROJECT_NAME}
)

# =====================
# Python support (unchanged)
# =====================

find_package(ament_cmake_python REQUIRED)

ament_python_install_package(${PROJECT_NAME})

install(PROGRAMS
  my_vision_pkg/image_emotion.py
  my_vision_pkg/audio_rec.py
  my_vision_pkg/moveit_node.py
  my_vision_pkg/moveit_service.py
  my_vision_pkg/table_detect.py
  my_vision_pkg/arm_motion_speak.py
  DESTINATION lib/${PROJECT_NAME}
)

# =====================
# Export
# =====================

ament_package()