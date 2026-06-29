#!/usr/bin/env python3
import rclpy
from rclpy.node import Node

from sensor_msgs.msg import Image
from cv_bridge import CvBridge

from rclpy.qos import qos_profile_sensor_data

import cv2
import requests

SERVER_URL = "http://192.168.1.175:5000/emotion"

class ImageSubscriber(Node):

    def __init__(self):
        super().__init__('image_subscriber')

        self.bridge = CvBridge()

        self.subscription = self.create_subscription(
            Image,
            '/head_front_camera/rgb/image_raw',
            self.listener_callback,
            qos_profile_sensor_data)

        self.get_logger().info("Subscribed to camera topic")

    def listener_callback(self, msg):

        try:
            cv_image = self.bridge.imgmsg_to_cv2(
                msg,
                desired_encoding='bgr8'
            )

            success, buffer = cv2.imencode(
                '.jpg',
                cv_image,
                [cv2.IMWRITE_JPEG_QUALITY, 80]
            )

            if not success:
                return

            files = {
                'image': (
                    'frame.jpg',
                    buffer.tobytes(),
                    'image/jpeg'
                )
            }

            response = requests.post(
                SERVER_URL,
                files=files,
                timeout=5
            )

            if response.status_code == 200:
                result = response.json()
                self.get_logger().info(
                    f"Faces detected: {result['faces']}"
                )

        except Exception as e:
            self.get_logger().error(str(e))


def main(args=None):

    rclpy.init(args=args)

    node = ImageSubscriber()

    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass

    node.destroy_node()
    rclpy.shutdown()


if __name__ == '__main__':
    main()