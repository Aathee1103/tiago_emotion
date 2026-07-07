#!/usr/bin/env python3

import rclpy
from rclpy.node import Node
from geometry_msgs.msg import Twist, PoseArray
from std_srvs.srv import Trigger


class ArucoDocking(Node):

    def __init__(self):
        super().__init__('aruco_docking')

        # publisher to twist_mux input
        self.pub = self.create_publisher(Twist, '/key_vel', 10)

        # subscribe to marker
        self.sub = self.create_subscription(
            PoseArray,
            '/aruco_poses_base',
            self.cb,
            10
        )
        self.continue_client = self.create_client(Trigger,'/continue_navigation')

        # service to start docking
        self.srv = self.create_service(Trigger, '/start_docking', self.start_cb)

        self.active = False

        # target pose
        self.desired_x = 0.69
        self.desired_y = 0.07

        # gains
        self.kx = 0.45
        self.ky = 1.3

        # limits
        self.max_vx = 0.2
        self.max_wz = 0.6

        self.get_logger().info("🤖 Docking node ready (waiting for service)")

    def continue_navigation(self):

        while not self.continue_client.wait_for_service(timeout_sec=1.0):
            self.get_logger().info("Waiting for continue_navigation service...")

        req = Trigger.Request()

        self.continue_client.call_async(req)

    def start_cb(self, request, response):
        self.active = True
        self.get_logger().info("🚀 Docking activated")
        response.success = True
        response.message = "Docking started"
        return response

    def cb(self, msg: PoseArray):

        if not self.active:
            return

        if len(msg.poses) == 0:
            self.stop()
            return

        p = msg.poses[0]
        x = p.position.x
        y = p.position.y

        ex = x - self.desired_x
        ey = y - self.desired_y

        vx = self.kx * ex
        wz = self.ky * ey

        vx = max(min(vx, self.max_vx), -self.max_vx)
        wz = max(min(wz, self.max_wz), -self.max_wz)

        cmd = Twist()
        cmd.linear.x = vx
        cmd.angular.z = wz

        self.pub.publish(cmd)

        self.get_logger().info(
            f"x={x:.2f}, y={y:.2f}, ex={ex:.2f}, ey={ey:.2f}"
        )

        if abs(ex) < 0.02 and abs(ey) < 0.02:
            self.get_logger().info("🎯 Docking complete")
            self.stop()
            self.active = False

            self.continue_navigation()

    def stop(self):
        self.pub.publish(Twist())


def main():
    rclpy.init()
    node = ArucoDocking()
    rclpy.spin(node)
    node.destroy_node()
    rclpy.shutdown()


if __name__ == '__main__':
    main()