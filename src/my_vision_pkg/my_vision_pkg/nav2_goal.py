#!/usr/bin/env python3

import rclpy
from rclpy.node import Node
from rclpy.action import ActionClient

from rclpy.qos import QoSProfile, ReliabilityPolicy, HistoryPolicy
from std_msgs.msg import Header
from nav2_msgs.action import NavigateToPose
from action_msgs.msg import GoalStatus 
from trajectory_msgs.msg import JointTrajectory, JointTrajectoryPoint
from builtin_interfaces.msg import Duration
from std_srvs.srv import Trigger
import time
from trajectory_msgs.msg import JointTrajectory, JointTrajectoryPoint

import math

from tf2_ros import Buffer
from tf2_ros import TransformListener
from tf2_ros import LookupException
from tf2_ros import ConnectivityException
from tf2_ros import ExtrapolationException
class Nav2ThenMove(Node):

    def __init__(self):
        super().__init__('nav2_then_move')
        self.goal_handle = None
        # ---------------- NAV2 ----------------
        self.client = ActionClient(self, NavigateToPose, 'navigate_to_pose')
        self.dock_client = self.create_client(Trigger, '/start_docking')
        # ---------------- QoS ----------------
        qos = QoSProfile(
            reliability=ReliabilityPolicy.RELIABLE,
            history=HistoryPolicy.KEEP_LAST,
            depth=10
        )

        self.head_pub = self.create_publisher(
            JointTrajectory,
            '/head_controller/joint_trajectory',
            qos
        )
        self.continue_srv = self.create_service(Trigger,'/continue_navigation',self.continue_callback)

        self.torso_pub = self.create_publisher(
            JointTrajectory,
            '/torso_controller/joint_trajectory',
            qos
        )
        self.goal_number = 1
        self.tf_buffer = Buffer()
        self.tf_listener = TransformListener(self.tf_buffer, self)

        self.goal_check_timer = None

        self.voice_client = self.create_client(Trigger,'/start_voice')
        # ---------------- GOAL ----------------
        #self.goal_x = 1.8623, goal position:
        #x = 1.732
        #y = -0.205
        self.goal_x = 1.732
        self.goal_y = -0.2

        self.qx = 0.0
        self.qy = 0.0
        self.qz = -0.137
        self.qw = 0.991


        #-0.113, -0.290, 0.099
        self.goal2_x = -0.113
        self.goal2_y = -0.290

        self.goal2_qx = 0.0
        self.goal2_qy = 0.0
        self.goal2_qz = 0.847
        self.goal2_qw = 0.531

        self.timer = None
        self.goal2_sent = False
        self.get_logger().info("🚀 Node started")

        self.send_goal()

        #self.call_voice_service()

    def get_robot_pose(self):

        try:
            trans = self.tf_buffer.lookup_transform(
                "map",
                "base_link",
                rclpy.time.Time()
            )

            x = trans.transform.translation.x
            y = trans.transform.translation.y

            q = trans.transform.rotation

            # quaternion -> yaw
            yaw = math.atan2(
                2.0 * (q.w * q.z + q.x * q.y),
                1.0 - 2.0 * (q.y * q.y + q.z * q.z)
            )

            return x, y, yaw

        except (
            LookupException,
            ConnectivityException,
            ExtrapolationException,
        ):
            return None

    def goal_yaw(self):
        return math.atan2(
            2.0 * (self.qw * self.qz + self.qx * self.qy),
            1.0 - 2.0 * (self.qy * self.qy + self.qz * self.qz)
        )


    def angle_diff(self, a, b):
        d = a - b
        while d > math.pi:
            d -= 2.0 * math.pi
        while d < -math.pi:
            d += 2.0 * math.pi
        return abs(d)


    def continue_callback(self, request, response):
        self.goal_number = 2

        self.get_logger().info("Docking completed")

        self.goal_x = self.goal2_x
        self.goal_y = self.goal2_y

        self.qx = self.goal2_qx
        self.qy = self.goal2_qy
        self.qz = self.goal2_qz
        self.qw = self.goal2_qw

        self.send_goal()

        response.success = True
        response.message = "Goal 2 started"

        return response


    # =====================================================
    def send_goal(self):

        self.client.wait_for_server()

        goal = NavigateToPose.Goal()
        goal.pose.header.frame_id = "map"
        goal.pose.header.stamp = self.get_clock().now().to_msg()

        goal.pose.pose.position.x = self.goal_x
        goal.pose.pose.position.y = self.goal_y

        goal.pose.pose.orientation.x = self.qx
        goal.pose.pose.orientation.y = self.qy
        goal.pose.pose.orientation.z = self.qz
        goal.pose.pose.orientation.w = self.qw

        self.get_logger().info("🚀 Sending Nav2 goal")

        self.client.send_goal_async(goal).add_done_callback(self.goal_response)

    # =====================================================
    def goal_response(self, future):

        goal_handle = future.result()

        if not goal_handle.accepted:
            self.get_logger().error("❌ Goal rejected")
            return

        self.get_logger().info("✅ Goal accepted")

        self.goal_handle = goal_handle

        # IMPORTANT: must be inside function scope
        goal_handle.get_result_async().add_done_callback(self.result_callback)
    
    def call_docking_service(self):

        self.get_logger().info("🚀 Calling docking service")

        while not self.dock_client.wait_for_service(timeout_sec=1.0):
            self.get_logger().info("Waiting for /start_docking service...")

        req = Trigger.Request()
        self.dock_client.call_async(req)


    def check_goal_reached(self):

        pose = self.get_robot_pose()

        if pose is None:
            return

        x, y, yaw = pose

        distance = math.sqrt(
            (x - self.goal_x) ** 2 +
            (y - self.goal_y) ** 2
        )

        yaw_error = self.angle_diff(
            yaw,
            self.goal_yaw()
        )

        self.get_logger().info(
            f"Distance={distance:.2f}  "
            f"Yaw error={math.degrees(yaw_error):.1f} deg"
        )

        # choose tolerances
        if distance < 0.30 and yaw_error < math.radians(15):

            self.get_logger().info("Goal reached by pose check.")

            if self.goal_check_timer is not None:
                self.goal_check_timer.cancel()
                self.goal_check_timer = None

            self.stop_all_nav2()

            self.goal_completed()

    def stop_all_nav2(self):

        self.get_logger().info("Cancelling Nav2 goal...")

        if self.goal_handle is not None:
            future = self.goal_handle.cancel_goal_async()
            future.add_done_callback(self.cancel_done)


    def cancel_done(self, future):

        self.get_logger().info("Nav2 goal cancelled.")

    def result_callback(self, future):

        status = future.result().status

        if status == GoalStatus.STATUS_SUCCEEDED:

            self.get_logger().info("Navigation succeeded")
            self.goal_completed()
            return

        self.get_logger().warn(
            f"Navigation returned status {status}. "
            "Monitoring robot position..."
        )

        if self.goal_check_timer is None:
            self.goal_check_timer = self.create_timer(
                0.5,
                self.check_goal_reached
            )

    def goal_completed(self):

        self.get_logger().info("🎯 Goal completed confirmed")

        if self.goal_number == 1:

            self.publish_motion()
            time.sleep(5)
            self.call_docking_service()
            #self.goal2_timer = self.create_timer(
            #    5.0,
            #    self._send_goal2_once
            #)

        elif self.goal_number == 2:
            self.call_voice_service()

    def _send_goal2_once(self):
        if self.goal2_sent:
            return

        self.goal2_sent = True

        if self.goal2_timer is not None:
            self.goal2_timer.cancel()
            self.goal2_timer = None

        self.goal_number = 2

        self.goal_x = self.goal2_x
        self.goal_y = self.goal2_y

        self.qx = self.goal2_qx
        self.qy = self.goal2_qy
        self.qz = self.goal2_qz
        self.qw = self.goal2_qw

        self.get_logger().info("🚀 Sending Goal 2")

        self.send_goal()

    def call_voice_service(self):

        while not self.voice_client.wait_for_service(timeout_sec=1.0):
            self.get_logger().info("Waiting for /start_voice")

        req = Trigger.Request()

        self.voice_client.call_async(req)
    # =====================================================
    def build_msgs(self):

        # ---------------- HEAD ----------------
        head = JointTrajectory()

        head.header = Header()
        head.header.frame_id = ""
        head.header.stamp.sec = 0  # will be overwritten later

        head.joint_names = ["head_1_joint", "head_2_joint"]

        hp = JointTrajectoryPoint()
        hp.positions = [0.0, -0.6]
        hp.time_from_start = Duration(sec=1, nanosec=0)

        head.points = [hp]

        # ---------------- TORSO ----------------
        torso = JointTrajectory()

        torso.header = Header()
        torso.header.frame_id = ""
        torso.header.stamp.sec = 0

        torso.joint_names = ["torso_lift_joint"]

        tp = JointTrajectoryPoint()
        tp.positions = [0.2]
        tp.time_from_start = Duration(sec=1, nanosec=0)

        torso.points = [tp]

        return head, torso

    # =====================================================
    def publish_motion(self):

        self.get_logger().info("🎯 publish motion executing")

        head, torso = self.build_msgs()

        now = self.get_clock().now().to_msg()

        head.header.stamp = now
        torso.header.stamp = now

        self.head_pub.publish(head)
        self.torso_pub.publish(torso)


# =====================================================
def main():
    rclpy.init()
    node = Nav2ThenMove()
    rclpy.spin(node)
    node.destroy_node()
    rclpy.shutdown()


if __name__ == '__main__':
    main()
