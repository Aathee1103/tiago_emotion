#!/usr/bin/env python3

import os
import wave
import time
import rclpy
from rclpy.node import Node
from rclpy.action import ActionClient

from audio_common_msgs.msg import AudioData
from tts_msgs.action import TTS

import webrtcvad
import requests
import random

from trajectory_msgs.msg import JointTrajectory, JointTrajectoryPoint


AUDIO_RATE = 16000
AUDIO_CHANNELS = 1
AUDIO_WIDTH = 2

FRAME_DUR = 30
FRAME_SIZE = int(AUDIO_RATE * FRAME_DUR / 1000) * AUDIO_WIDTH

SILENCE_TIMEOUT = 2.0


class VoiceToSpeech(Node):

    def __init__(self):
        super().__init__('voice_to_speech')

        # ---------------- FLAGS ----------------
        self.recording = False
        self.is_speaking = False

        self.buffer = bytearray()
        self.frames = []
        self.last_voice_time = 0

        # ---------------- VAD ----------------
        self.vad = webrtcvad.Vad(2)

        # ---------------- TTS ----------------
        self.tts_client = ActionClient(self, TTS, '/tts_engine/tts')

        # ---------------- AUDIO INPUT ----------------
        self.create_subscription(
            AudioData,
            '/audio_in/raw',
            self.audio_callback,
            10
        )

        # ---------------- MOTION ----------------
        self.arm_pub = self.create_publisher(
            JointTrajectory,
            '/arm_controller/joint_trajectory',
            10
        )

        self.head_pub = self.create_publisher(
            JointTrajectory,
            '/head_controller/joint_trajectory',
            10
        )

        self.motion_timer = self.create_timer(1.2, self.motion_loop)

        self.get_logger().info("🚀 Voice-to-Speech + Motion system ready")

    # ==================================================
    # AUDIO CALLBACK
    # ==================================================
    def audio_callback(self, msg):

        if self.is_speaking:
            return

        self.buffer.extend(msg.data)

        while len(self.buffer) >= FRAME_SIZE:
            frame = self.buffer[:FRAME_SIZE]
            self.buffer = self.buffer[FRAME_SIZE:]

            try:
                is_speech = self.vad.is_speech(frame, AUDIO_RATE)
            except:
                return

            if is_speech:
                if not self.recording:
                    self.start_recording()

                self.frames.append(frame)
                self.last_voice_time = time.time()

            else:
                if self.recording:
                    if time.time() - self.last_voice_time > SILENCE_TIMEOUT:
                        self.stop_and_process()

    # ==================================================
    # START RECORDING
    # ==================================================
    def start_recording(self):

        self.recording = True
        self.frames = []

        os.makedirs("/ros2_ws/audio_logs", exist_ok=True)

        filename = f"audio_{int(time.time())}.wav"
        self.file_path = f"/ros2_ws/audio_logs/{filename}"

        self.wf = wave.open(self.file_path, 'wb')
        self.wf.setnchannels(AUDIO_CHANNELS)
        self.wf.setsampwidth(AUDIO_WIDTH)
        self.wf.setframerate(AUDIO_RATE)

        self.get_logger().info(f"🎤 Recording started")

    # ==================================================
    # STOP + PROCESS
    # ==================================================
    def stop_and_process(self):

        for f in self.frames:
            self.wf.writeframes(f)

        self.wf.close()
        self.recording = False

        text = self.send_to_flask(self.file_path)

        if text:
            self.speak(text)

        self.frames = []

    # ==================================================
    # FLASK STT
    # ==================================================


    def send_to_flask(self, file_path):

        url = "http://10.68.0.128:5000/upload_audio"

        try:
            with open(file_path, "rb") as f:
                files = {"file": (os.path.basename(file_path), f, "audio/wav")}
                r = requests.post(url, files=files)

            self.get_logger().info(f"📤 Flask raw response: {r.text}")

            # ---------------- FIX HERE ----------------
            try:
                data = r.json()
                text = data.get("response", "")
            except Exception:
                text = r.text

            return text.strip()

        except Exception as e:
            self.get_logger().error(f"Flask error: {e}")
            return None

    # ==================================================
    # SPEAK
    # ==================================================
    def speak(self, text):

        if not text:
            return

        self.is_speaking = True

        goal = TTS.Goal()
        goal.input = text
        goal.locale = "en_US"

        self.get_logger().info(f"🗣 Speaking: {text}")

        self.tts_client.wait_for_server()
        future = self.tts_client.send_goal_async(goal)
        future.add_done_callback(self.goal_response)

    # ==================================================
    # TTS RESPONSE
    # ==================================================
    def goal_response(self, future):

        goal_handle = future.result()

        if not goal_handle.accepted:
            self.is_speaking = False
            return

        result_future = goal_handle.get_result_async()
        result_future.add_done_callback(self.result_callback)

    # ==================================================
    # SPEECH DONE
    # ==================================================
    def result_callback(self, future):

        self.get_logger().info("✅ Speech finished")

        self.is_speaking = False

    # ==================================================
    # MOTION LOOP (ONLY WHILE SPEAKING)
    # ==================================================
    def motion_loop(self):

        if not self.is_speaking:
            return

        # ---------------- HEAD ----------------
        head = JointTrajectory()
        head.joint_names = ["head_1_joint", "head_2_joint"]

        h = JointTrajectoryPoint()
        h.positions = [
            random.uniform(0.0, 0.2),
            random.uniform(-0.7, -0.4)
        ]
        h.time_from_start.sec = 1

        head.points.append(h)
        self.head_pub.publish(head)

        # ---------------- ARM ----------------
        arm = JointTrajectory()
        arm.joint_names = [
            "arm_1_joint","arm_2_joint","arm_3_joint",
            "arm_4_joint","arm_5_joint","arm_6_joint","arm_7_joint"
        ]

        a = JointTrajectoryPoint()

        a.positions = [
            0.32,
            random.uniform(-0.33, -0.1),
            random.uniform(-0.3, -1.3),
            1.9,
            -1.45,
            1.43,
            -0.001
        ]

        a.time_from_start.sec = 2

        arm.points.append(a)
        self.arm_pub.publish(arm)


# ==================================================
# MAIN
# ==================================================
def main():
    rclpy.init()
    node = VoiceToSpeech()

    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass

    node.destroy_node()
    rclpy.shutdown()


if __name__ == "__main__":
    main()
