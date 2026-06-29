#!/bin/bash
source /opt/ros/noetic/setup.bash
cd /workspace/catkin_ws
catkin_make
source devel/setup.bash
rosrun emotion emotion.py
