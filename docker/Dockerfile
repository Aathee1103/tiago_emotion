FROM ros:humble

ENV DEBIAN_FRONTEND=noninteractive
ENV RMW_IMPLEMENTATION=rmw_cyclonedds_cpp
ENV ROS_DOMAIN_ID=0
ENV PYTHONUNBUFFERED=1

SHELL ["/bin/bash", "-c"]
WORKDIR /ros2_ws

# -----------------------------
# Base tools
# -----------------------------
RUN apt-get update && apt-get install -y \
    git \
    build-essential \
    python3-pip \
    python3-rosdep \
    python3-colcon-common-extensions \
    python3-argcomplete \
    software-properties-common \
    pkg-config \
    libgl1 \
    libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

# -----------------------------
# Enable Ubuntu repos (IMPORTANT FIX)
# -----------------------------
RUN add-apt-repository universe && \
    add-apt-repository multiverse && \
    apt-get update

# -----------------------------
# System multimedia deps (FIX rosdep GStreamer failure)
# -----------------------------
RUN apt-get install -y \
    libgstreamer1.0-0 \
    libgstreamer1.0-dev \
    gstreamer1.0-tools \
    gstreamer1.0-plugins-base \
    gstreamer1.0-plugins-good \
    gstreamer1.0-plugins-bad \
    gstreamer1.0-plugins-ugly \
    gstreamer1.0-libav \
    libgstrtspserver-1.0-dev \
    gir1.2-gstreamer-1.0 \
    gir1.2-gst-plugins-base-1.0 \
    gstreamer1.0-alsa \
    && rm -rf /var/lib/apt/lists/*

# -----------------------------
# ROS2 + MoveIt + TIAGo
# -----------------------------
RUN apt-get update && apt-get install -y \
    ros-humble-rmw-cyclonedds-cpp \
    ros-humble-navigation2 \
    ros-humble-nav2-bringup \
    ros-humble-slam-toolbox \
    ros-humble-rviz2 \
    ros-humble-cv-bridge \
    ros-humble-vision-opencv \
    ros-humble-image-transport \
    ros-humble-pcl-ros \
    ros-humble-pointcloud-to-laserscan \
    ros-humble-moveit \
    ros-humble-moveit-ros-planning \
    ros-humble-moveit-ros-move-group \
    ros-humble-moveit-ros-visualization \
    ros-humble-moveit-ros-perception \
    ros-humble-moveit-simple-controller-manager \
    ros-humble-ros2-control \
    ros-humble-ros2-controllers \
    ros-humble-tiago-moveit-config \
    && rm -rf /var/lib/apt/lists/*

# -----------------------------
# rosdep setup
# -----------------------------
RUN rosdep init || true && rosdep update

# -----------------------------
# Python deps
# -----------------------------
RUN pip3 install --no-cache-dir \
    flask \
    flask-cors \
    scipy \
    transforms3d \
    requests \
    numpy==1.26.4 \
    webrtcvad

# -----------------------------
# Workspace
# -----------------------------
COPY ./src /ros2_ws/src

# IMPORTANT CLEAN (prevents fake package.xml errors)
RUN find /ros2_ws/src -type d \( -name build -o -name install -o -name log \) -exec rm -rf {} +

# -----------------------------
# rosdep install (SAFE MODE)
# -----------------------------
RUN source /opt/ros/humble/setup.bash && \
    rosdep install --from-paths src --ignore-src -r -y \
    --rosdistro humble \
    --skip-keys="festival festvox-kallpc16k pymoveit2 gstreamer1.0-tools gstreamer1.0-plugins-good gstreamer1.0-plugins-base"

# -----------------------------
# Build workspace
# -----------------------------
RUN source /opt/ros/humble/setup.bash && \
    colcon build --symlink-install

# -----------------------------
# Default shell
# -----------------------------
CMD ["bash"]