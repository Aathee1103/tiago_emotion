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


class Nav2ThenMove(Node):

    def __init__(self):
        super().__init__('nav2_then_move')

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

        self.get_logger().info("🚀 Node started")
        self.send_goal()
        #self.call_voice_service()





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

        goal_handle.get_result_async().add_done_callback(self.result_callback)
    
    def call_docking_service(self):

        self.get_logger().info("🚀 Calling docking service")

        while not self.dock_client.wait_for_service(timeout_sec=1.0):
            self.get_logger().info("Waiting for /start_docking service...")

        req = Trigger.Request()
        self.dock_client.call_async(req)





    def result_callback(self, future):

        result_wrapper = future.result()
        status = result_wrapper.status

        # ❌ NEVER continue if navigation failed
        if status != GoalStatus.STATUS_SUCCEEDED:
            self.get_logger().error("❌ Navigation failed or canceled")

            # optional: retry logic here
            return

        # ✅ ONLY SUCCESS PATH BELOW
        if self.goal_number == 1:

            self.get_logger().info("🎯 Goal 1 reached successfully")

            self.publish_motion()
            #self.call_docking_service()

        elif self.goal_number == 2:

            self.get_logger().info("🎯 Goal 2 reached successfully")

            self.call_voice_service()

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
