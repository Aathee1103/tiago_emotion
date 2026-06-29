FROM ubuntu:22.04

ENV DEBIAN_FRONTEND=noninteractive

# =========================
# SYSTEM DEPENDENCIES
# =========================
RUN apt-get update && apt-get install -y --no-install-recommends \
    python3 \
    python3-pip \
    python3-dev \
    git \
    curl \
    wget \
    ffmpeg \
    libsm6 \
    libxext6 \
    libgl1 \
    libglib2.0-0 \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# =========================
# PYTHON SETUP
# =========================
RUN pip3 install --upgrade pip

# IMPORTANT: avoid NumPy 2.x conflicts
RUN pip3 install "numpy<2"

# =========================
# CORE AI STACK
# =========================
RUN pip3 install \
    flask \
    opencv-python \
    tensorflow==2.15.0 \
    tf-keras \
    deepface

# =========================
# UTILITIES
# =========================
RUN pip3 install requests pillow

# =========================
# WORKDIR
# =========================
WORKDIR /app

