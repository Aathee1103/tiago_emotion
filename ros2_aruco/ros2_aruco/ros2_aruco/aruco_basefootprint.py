import rclpy
import rclpy.node

from rclpy.qos import qos_profile_sensor_data

from cv_bridge import CvBridge
import cv2
import numpy as np
import tf_transformations

from sensor_msgs.msg import CameraInfo, Image
from geometry_msgs.msg import PoseArray, Pose, PoseStamped
from ros2_aruco_interfaces.msg import ArucoMarkers

from tf2_ros import Buffer, TransformListener
from tf2_ros import LookupException
from tf2_ros import ConnectivityException
from tf2_ros import ExtrapolationException

from tf2_geometry_msgs import do_transform_pose


class ArucoNode(rclpy.node.Node):

    def __init__(self):
        super().__init__("aruco_node")

        # ---------------- PARAMETERS ----------------
        self.declare_parameter("marker_size", 0.0625)
        self.declare_parameter("aruco_dictionary_id", "DICT_5X5_250")
        self.declare_parameter("image_topic", "/camera/image_raw")
        self.declare_parameter("camera_info_topic", "/camera/camera_info")
        self.declare_parameter("camera_frame", "")

        self.marker_size = self.get_parameter("marker_size").value
        dictionary_id_name = self.get_parameter("aruco_dictionary_id").value
        image_topic = self.get_parameter("image_topic").value
        info_topic = self.get_parameter("camera_info_topic").value
        self.camera_frame = self.get_parameter("camera_frame").value

        self.get_logger().info(f"Marker size: {self.marker_size}")
        self.get_logger().info(f"Marker type: {dictionary_id_name}")

        # ---------------- CAMERA STATE ----------------
        self.camera_ready = False
        self.info_msg = None
        self.intrinsic_mat = None
        self.distortion = None

        # ---------------- TF ----------------
        self.tf_buffer = Buffer()
        self.tf_listener = TransformListener(self.tf_buffer, self)

        self.target_frame = "base_footprint"

        # ---------------- SUBSCRIBERS ----------------
        self.info_sub = self.create_subscription(
            CameraInfo,
            info_topic,
            self.info_callback,
            qos_profile_sensor_data
        )

        self.create_subscription(
            Image,
            image_topic,
            self.image_callback,
            qos_profile_sensor_data
        )

        # ---------------- PUBLISHERS ----------------
        self.poses_pub = self.create_publisher(
            PoseArray,
            "aruco_poses",
            10
        )

        self.markers_pub = self.create_publisher(
            ArucoMarkers,
            "aruco_markers",
            10
        )

        # ---------------- CV BRIDGE ----------------
        self.bridge = CvBridge()

        # ---------------- ARUCO ----------------
        try:
            dictionary_id = cv2.aruco.__getattribute__(
                dictionary_id_name
            )

            if type(dictionary_id) != type(
                cv2.aruco.DICT_5X5_100
            ):
                raise AttributeError

        except AttributeError:

            self.get_logger().error(
                f"bad aruco_dictionary_id: {dictionary_id_name}"
            )

            options = "\n".join(
                [
                    s for s in dir(cv2.aruco)
                    if s.startswith("DICT")
                ]
            )

            self.get_logger().error(
                f"valid options:\n{options}"
            )

            raise

        self.aruco_dictionary = cv2.aruco.Dictionary_get(
            dictionary_id
        )

        self.aruco_parameters = (
            cv2.aruco.DetectorParameters_create()
        )

    # ------------------------------------------------
    # CAMERA INFO CALLBACK
    # ------------------------------------------------
    def info_callback(self, msg):

        self.info_msg = msg

        self.intrinsic_mat = np.array(
            msg.k
        ).reshape(3, 3)

        self.distortion = np.array(msg.d)

        self.camera_ready = True

    # ------------------------------------------------
    # IMAGE CALLBACK
    # ------------------------------------------------
    def image_callback(self, msg):

        if not self.camera_ready:
            self.get_logger().warn(
                "Waiting for camera info..."
            )
            return

        cv_image = self.bridge.imgmsg_to_cv2(
            msg,
            desired_encoding="mono8"
        )

        corners, ids, _ = cv2.aruco.detectMarkers(
            cv_image,
            self.aruco_dictionary,
            parameters=self.aruco_parameters
        )

        pose_array = PoseArray()
        markers_msg = ArucoMarkers()

        frame = (
            self.camera_frame
            if self.camera_frame
            else self.info_msg.header.frame_id
        )

        pose_array.header.stamp = msg.header.stamp
        pose_array.header.frame_id = frame

        markers_msg.header.stamp = msg.header.stamp
        markers_msg.header.frame_id = frame

        if ids is None:

            self.poses_pub.publish(pose_array)
            self.markers_pub.publish(markers_msg)

            return

        rvecs, tvecs, _ = cv2.aruco.estimatePoseSingleMarkers(
            corners,
            self.marker_size,
            self.intrinsic_mat,
            self.distortion
        )

        for i, marker_id in enumerate(ids):

            pose = Pose()

            # ---------------- CAMERA FRAME ----------------

            x = float(tvecs[i][0][0])
            y = float(tvecs[i][0][1])
            z = float(tvecs[i][0][2])

            camera_distance = np.sqrt(
                x * x +
                y * y +
                z * z
            )

            self.get_logger().info(
                f"[CAMERA] Marker {int(marker_id[0])} "
                f"x={x:.3f} "
                f"y={y:.3f} "
                f"z={z:.3f} "
                f"distance={camera_distance:.3f} m"
            )

            pose.position.x = x
            pose.position.y = y
            pose.position.z = z

            rot_mat = np.eye(4)

            rot_mat[0:3, 0:3] = cv2.Rodrigues(
                rvecs[i][0]
            )[0]

            quat = tf_transformations.quaternion_from_matrix(
                rot_mat
            )

            pose.orientation.x = quat[0]
            pose.orientation.y = quat[1]
            pose.orientation.z = quat[2]
            pose.orientation.w = quat[3]

            # ---------------- BASE_FOOTPRINT ----------------

            try:

                pose_stamped = PoseStamped()

                pose_stamped.header.stamp = msg.header.stamp
                pose_stamped.header.frame_id = frame
                pose_stamped.pose = pose

                transform = self.tf_buffer.lookup_transform(
                    self.target_frame,
                    frame,
                    rclpy.time.Time()
                )

                pose_base = do_transform_pose(
                    pose_stamped,
                    transform
                )

                bx = pose_base.pose.position.x
                by = pose_base.pose.position.y
                bz = pose_base.pose.position.z

                base_distance = np.sqrt(
                    bx * bx +
                    by * by +
                    bz * bz
                )

                self.get_logger().info(
                    f"[BASE_FOOTPRINT] Marker {int(marker_id[0])} "
                    f"x={bx:.3f} "
                    f"y={by:.3f} "
                    f"z={bz:.3f} "
                    f"distance={base_distance:.3f} m"
                )

            except (
                LookupException,
                ConnectivityException,
                ExtrapolationException
            ) as e:

                self.get_logger().warn(
                    f"TF transform failed: {str(e)}"
                )

            pose_array.poses.append(pose)
            markers_msg.poses.append(pose)
            markers_msg.marker_ids.append(
                int(marker_id[0])
            )

        self.poses_pub.publish(pose_array)
        self.markers_pub.publish(markers_msg)


def main():

    rclpy.init()

    node = ArucoNode()

    rclpy.spin(node)

    node.destroy_node()

    rclpy.shutdown()


if __name__ == "__main__":
    main()


#aruco normal

import rclpy
import rclpy.node
from rclpy.qos import qos_profile_sensor_data

from cv_bridge import CvBridge
import numpy as np
import cv2
import tf_transformations

from sensor_msgs.msg import CameraInfo, Image
from geometry_msgs.msg import PoseArray, Pose
from ros2_aruco_interfaces.msg import ArucoMarkers
from rcl_interfaces.msg import ParameterDescriptor, ParameterType


class ArucoNode(rclpy.node.Node):

    def __init__(self):
        super().__init__("aruco_node")

        # ---------------- PARAMETERS ----------------
        self.declare_parameter("marker_size", 0.0625)
        self.declare_parameter("aruco_dictionary_id", "DICT_5X5_250")
        self.declare_parameter("image_topic", "/camera/image_raw")
        self.declare_parameter("camera_info_topic", "/camera/camera_info")
        self.declare_parameter("camera_frame", "")

        self.marker_size = self.get_parameter("marker_size").value
        dictionary_id_name = self.get_parameter("aruco_dictionary_id").value
        image_topic = self.get_parameter("image_topic").value
        info_topic = self.get_parameter("camera_info_topic").value
        self.camera_frame = self.get_parameter("camera_frame").value

        self.get_logger().info(f"Marker size: {self.marker_size}")
        self.get_logger().info(f"Marker type: {dictionary_id_name}")

        # ---------------- STATE ----------------
        self.camera_ready = False
        self.info_msg = None
        self.intrinsic_mat = None
        self.distortion = None

        # ---------------- SUBSCRIPTIONS ----------------
        self.info_sub = self.create_subscription(
            CameraInfo,
            info_topic,
            self.info_callback,
            qos_profile_sensor_data
        )

        self.create_subscription(
            Image,
            image_topic,
            self.image_callback,
            qos_profile_sensor_data
        )

        # ---------------- PUBLISHERS ----------------
        self.poses_pub = self.create_publisher(PoseArray, "aruco_poses", 10)
        self.markers_pub = self.create_publisher(ArucoMarkers, "aruco_markers", 10)

        # ---------------- CV BRIDGE ----------------
        self.bridge = CvBridge()

        # ---------------- ARUCO (UNCHANGED AS REQUESTED) ----------------
        try:
            dictionary_id = cv2.aruco.__getattribute__(dictionary_id_name)
            if type(dictionary_id) != type(cv2.aruco.DICT_5X5_100):
                raise AttributeError
        except AttributeError:
            self.get_logger().error(f"bad aruco_dictionary_id: {dictionary_id_name}")
            options = "\n".join([s for s in dir(cv2.aruco) if s.startswith("DICT")])
            self.get_logger().error(f"valid options: {options}")

        self.aruco_dictionary = cv2.aruco.Dictionary_get(dictionary_id)
        self.aruco_parameters = cv2.aruco.DetectorParameters_create()

    # ---------------- CAMERA INFO CALLBACK ----------------
    def info_callback(self, msg: CameraInfo):
        self.info_msg = msg
        self.intrinsic_mat = np.array(msg.k).reshape(3, 3)
        self.distortion = np.array(msg.d)
        self.camera_ready = True

        #self.get_logger().info("Camera info received ✔")

    # ---------------- IMAGE CALLBACK ----------------
    def image_callback(self, msg: Image):

        if not self.camera_ready:
            self.get_logger().warn("Waiting for camera info...")
            return

        cv_image = self.bridge.imgmsg_to_cv2(msg, desired_encoding="mono8")

        corners, ids, _ = cv2.aruco.detectMarkers(
            cv_image,
            self.aruco_dictionary,
            parameters=self.aruco_parameters
        )

        pose_array = PoseArray()
        markers_msg = ArucoMarkers()

        frame = self.camera_frame if self.camera_frame else self.info_msg.header.frame_id

        pose_array.header.stamp = msg.header.stamp
        markers_msg.header.stamp = msg.header.stamp
        pose_array.header.frame_id = frame
        markers_msg.header.frame_id = frame

        if ids is None:
            self.poses_pub.publish(pose_array)
            self.markers_pub.publish(markers_msg)
            return

        rvecs, tvecs, _ = cv2.aruco.estimatePoseSingleMarkers(
            corners,
            self.marker_size,
            self.intrinsic_mat,
            self.distortion
        )
        for i, marker_id in enumerate(ids):

            pose = Pose()

            x = tvecs[i][0][0]
            y = tvecs[i][0][1]
            z = tvecs[i][0][2]

            # 👉 PRINT marker position
            self.get_logger().info(
                f"Marker ID {int(marker_id[0])} -> x: {x:.3f}, y: {y:.3f}, z: {z:.3f}"
            )

            pose.position.x = x
            pose.position.y = y
            pose.position.z = z

            rot_mat = np.eye(4)
            rot_mat[0:3, 0:3] = cv2.Rodrigues(rvecs[i][0])[0]

            quat = tf_transformations.quaternion_from_matrix(rot_mat)

            pose.orientation.x = quat[0]
            pose.orientation.y = quat[1]
            pose.orientation.z = quat[2]
            pose.orientation.w = quat[3]

            pose_array.poses.append(pose)
            markers_msg.poses.append(pose)
            markers_msg.marker_ids.append(int(marker_id[0]))
        """
        for i, marker_id in enumerate(ids):

            pose = Pose()

            pose.position.x = tvecs[i][0][0]
            pose.position.y = tvecs[i][0][1]
            pose.position.z = tvecs[i][0][2]
            self.get_logger().info(f"Marker ID {int(marker_id[0])} -> x: {x:.3f}, y: {y:.3f}, z: {z:.3f}")

            rot_mat = np.eye(4)
            rot_mat[0:3, 0:3] = cv2.Rodrigues(rvecs[i][0])[0]

            quat = tf_transformations.quaternion_from_matrix(rot_mat)

            pose.orientation.x = quat[0]
            pose.orientation.y = quat[1]
            pose.orientation.z = quat[2]
            pose.orientation.w = quat[3]

            pose_array.poses.append(pose)
            markers_msg.poses.append(pose)
            markers_msg.marker_ids.append(int(marker_id[0]))
        """

        self.poses_pub.publish(pose_array)
        self.markers_pub.publish(markers_msg)


def main():
    rclpy.init()
    node = ArucoNode()
    rclpy.spin(node)
    node.destroy_node()
    rclpy.shutdown()


if __name__ == "__main__":
    main()