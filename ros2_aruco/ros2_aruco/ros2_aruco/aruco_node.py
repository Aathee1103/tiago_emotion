import rclpy
from rclpy.node import Node

import numpy as np
import cv2
import tf_transformations

from sensor_msgs.msg import CameraInfo, Image
from geometry_msgs.msg import PoseArray, Pose

from cv_bridge import CvBridge

import tf2_ros
from rclpy.qos import QoSProfile, QoSReliabilityPolicy, QoSHistoryPolicy


class ArucoNode(Node):

    def __init__(self):
        super().__init__("aruco_node")

        # ---------------- PARAMETERS ----------------
        self.declare_parameter("marker_size", 0.0625)
        self.declare_parameter("image_topic", "/camera/image_raw")
        self.declare_parameter("camera_info_topic", "/camera/camera_info")
        self.declare_parameter("base_frame", "base_footprint")

        self.marker_size = self.get_parameter("marker_size").value
        image_topic = self.get_parameter("image_topic").value
        info_topic = self.get_parameter("camera_info_topic").value
        self.base_frame = self.get_parameter("base_frame").value

        # ---------------- CAMERA ----------------
        self.K = None
        self.D = None
        self.camera_frame = None
        self.camera_ready = False

        # ---------------- TF ----------------
        self.tf_buffer = tf2_ros.Buffer()
        self.tf_listener = tf2_ros.TransformListener(self.tf_buffer, self)

        # ---------------- QoS FIX (IMPORTANT) ----------------
        qos = QoSProfile(
            reliability=QoSReliabilityPolicy.BEST_EFFORT,
            history=QoSHistoryPolicy.KEEP_LAST,
            depth=10
        )

        # ---------------- SUBSCRIPTIONS ----------------
        self.create_subscription(CameraInfo, info_topic, self.info_cb, qos)
        self.create_subscription(Image, image_topic, self.image_cb, qos)

        # ---------------- PUBLISHERS ----------------
        self.pose_pub = self.create_publisher(PoseArray, "aruco_poses_base", 10)

        # ---------------- CV ----------------
        self.bridge = CvBridge()

        # ---------------- ARUCO (FIXED) ----------------
        self.dictionary = cv2.aruco.getPredefinedDictionary(
            cv2.aruco.DICT_5X5_250
        )

        self.params = cv2.aruco.DetectorParameters_create()

        self.get_logger().info("🚀 ArUco Node Ready")

    # =====================================================
    # CAMERA INFO
    # =====================================================
    def info_cb(self, msg: CameraInfo):
        self.K = np.array(msg.k).reshape(3, 3)
        self.D = np.array(msg.d)
        self.camera_frame = msg.header.frame_id
        self.camera_ready = True

    # =====================================================
    def image_cb(self, msg: Image):

        if not self.camera_ready:
            return

        img = self.bridge.imgmsg_to_cv2(msg, "bgr8")

        corners, ids, _ = cv2.aruco.detectMarkers(
            img,
            self.dictionary,
            parameters=self.params
        )

        pose_array = PoseArray()
        pose_array.header.frame_id = self.base_frame
        pose_array.header.stamp = msg.header.stamp

        if ids is None:
            #cv2.imshow("aruco_view", img)
            #cv2.waitKey(1)
            self.pose_pub.publish(pose_array)
            return

        # draw marker outlines
        #cv2.aruco.drawDetectedMarkers(img, corners, ids)

        rvecs, tvecs, _ = cv2.aruco.estimatePoseSingleMarkers(
            corners,
            self.marker_size,
            self.K,
            self.D
        )

        for i in range(len(ids)):

            # ---------------- VISUALIZATION ----------------
            #cv2.drawFrameAxes(
            #    img,
            #    self.K,
            #    self.D,
            #    rvecs[i],
            #    tvecs[i],
            #    0.05
            #3)

            # center of marker
            c = corners[i][0].mean(axis=0)
            px, py = int(c[0]), int(c[1])

            # ID (shifted left so not overlapping axis)
            #cv2.putText(
            #    img,
            #    f"ID:{int(ids[i][0])}",
            #    (px - 80, py - 20),
            #    cv2.FONT_HERSHEY_SIMPLEX,
            #    0.7,
            #    (0, 255, 0),
            #    2
            #)

            # ---------------- TF + POSE ----------------
            x, y, z = tvecs[i][0]

            p_cam = np.array([x, y, z, 1.0])

            rot = np.eye(4)
            rot[:3, :3] = cv2.Rodrigues(rvecs[i][0])[0]

            q = tf_transformations.quaternion_from_matrix(rot)

            try:
                tf = self.tf_buffer.lookup_transform(
                    self.base_frame,
                    self.camera_frame,
                    rclpy.time.Time()
                )

                tf_rot = tf_transformations.quaternion_matrix([
                    tf.transform.rotation.x,
                    tf.transform.rotation.y,
                    tf.transform.rotation.z,
                    tf.transform.rotation.w
                ])

                t = tf.transform.translation

                p_base = tf_rot @ p_cam
                p_base[0] += t.x
                p_base[1] += t.y
                p_base[2] += t.z

                self.get_logger().info( f"ID {int(ids[i][0])}: x={p_base[0]:.2f}, y={p_base[1]:.2f}, z={p_base[2]:.2f}")

                pose = Pose()
                pose.position.x = float(p_base[0])
                pose.position.y = float(p_base[1])
                pose.position.z = float(p_base[2])

                pose.orientation.x = q[0]
                pose.orientation.y = q[1]
                pose.orientation.z = q[2]
                pose.orientation.w = q[3]

                pose_array.poses.append(pose)

            except Exception as e:
                self.get_logger().warn(f"TF failed: {e}")

        self.pose_pub.publish(pose_array)

        # ---------------- SHOW WINDOW ----------------
        #cv2.imshow("aruco_view", img)
        #cv2.waitKey(1)


# =====================================================
# MAIN
# =====================================================
def main():
    rclpy.init()
    node = ArucoNode()
    rclpy.spin(node)
    node.destroy_node()
    rclpy.shutdown()


if __name__ == "__main__":
    main()