#!/usr/bin/env python3

import rclpy
from rclpy.node import Node
import numpy as np
import cv2
import open3d as o3d

from sensor_msgs.msg import PointCloud2, CameraInfo
import sensor_msgs_py.point_cloud2 as pc2

from visualization_msgs.msg import Marker
from moveit_msgs.msg import CollisionObject
from shape_msgs.msg import SolidPrimitive
from geometry_msgs.msg import Pose

from tf2_ros import Buffer, TransformListener
from tf_transformations import quaternion_matrix


class TableDetector(Node):

    def __init__(self):
        super().__init__("table_detector")

        self.tf_buffer = Buffer()
        self.tf_listener = TransformListener(self.tf_buffer, self)

        self.fx = self.fy = self.cx = self.cy = None

        # ---------------- STABILITY CONTROL ----------------
        self.table_buffer = []
        self.required_frames = 5
        self.table_published = False

        # ---------------- ROS ----------------
        self.create_subscription(
            CameraInfo,
            "/head_front_camera/depth/camera_info",
            self.info_cb,
            1
        )

        self.create_subscription(
            PointCloud2,
            "/head_front_camera/depth/points",
            self.cb,
            10
        )

        self.marker_pub = self.create_publisher(Marker, "/table_marker", 10)
        self.collision_pub = self.create_publisher(CollisionObject, "/collision_object", 10)

        cv2.namedWindow("table_view", cv2.WINDOW_NORMAL)

        self.get_logger().info("🚀 TABLE DETECTOR (5-frame stable MoveIt version)")

    # ---------------- CAMERA ----------------
    def info_cb(self, msg):
        if self.fx is None:
            self.fx, self.fy = msg.k[0], msg.k[4]
            self.cx, self.cy = msg.k[2], msg.k[5]

    # ---------------- MAIN CALLBACK ----------------
    def cb(self, msg):

        if self.fx is None or self.table_published:
            return

        # ---------------- TF ----------------
        try:
            t = self.tf_buffer.lookup_transform(
                "base_link",
                msg.header.frame_id,
                rclpy.time.Time()
            )

            mat = quaternion_matrix([
                t.transform.rotation.x,
                t.transform.rotation.y,
                t.transform.rotation.z,
                t.transform.rotation.w
            ])

            mat[:3, 3] = [
                t.transform.translation.x,
                t.transform.translation.y,
                t.transform.translation.z
            ]

        except Exception:
            return

        # ---------------- POINT CLOUD ----------------
        pts = np.array([
            [p[0], p[1], p[2]]
            for p in pc2.read_points(msg, field_names=("x", "y", "z"), skip_nans=True)
        ])

        if len(pts) < 1500:
            return

        pts_tf = (mat @ np.c_[pts, np.ones(len(pts))].T).T[:, :3]

        pcd = o3d.geometry.PointCloud()
        pcd.points = o3d.utility.Vector3dVector(pts_tf)
        pcd = pcd.voxel_down_sample(0.02)

        # ---------------- PLANE EXTRACTION ----------------
        temp = pcd
        candidates = []

        for _ in range(6):

            if len(temp.points) < 800:
                break

            model, inliers = temp.segment_plane(
                distance_threshold=0.02,
                ransac_n=3,
                num_iterations=1200
            )

            a, b, c, d = model
            normal = np.array([a, b, c])
            normal = normal / (np.linalg.norm(normal) + 1e-6)

            plane_pts = np.asarray(temp.select_by_index(inliers).points)
            temp = temp.select_by_index(inliers, invert=True)

            if len(plane_pts) < 400:
                continue

            z_mean = np.mean(plane_pts[:, 2])
            size = len(plane_pts)
            flatness = abs(normal[2])

            # floor / ceiling rejection
            if z_mean < 0.20 or z_mean > 2.0:
                continue

            if flatness < 0.80:
                continue

            if size > 50000:
                continue

            score = flatness * np.log(size + 1) / (np.std(plane_pts[:, 2]) + 1e-6)

            candidates.append((score, plane_pts, z_mean))

        # ---------------- NO TABLE ----------------
        if len(candidates) == 0:
            self.table_buffer.clear()
            self.clear_rviz()
            return

        candidates.sort(key=lambda x: x[0], reverse=True)
        score, table_pts, z = candidates[0]

        # confidence check
        if score < 8.0:
            self.table_buffer.clear()
            self.clear_rviz()
            return

        # ---------------- BUFFERING ----------------
        self.table_buffer.append(table_pts)

        self.get_logger().info(
            f"🟡 buffering: {len(self.table_buffer)}/{self.required_frames}"
        )

        if len(self.table_buffer) < self.required_frames:
            return

        # ---------------- FINAL STABLE TABLE ----------------
        all_pts = np.concatenate(self.table_buffer, axis=0)

        # optional noise cleanup
        z_mean = np.mean(all_pts[:, 2])
        z_std = np.std(all_pts[:, 2])
        all_pts = all_pts[np.abs(all_pts[:, 2] - z_mean) < 2 * z_std]

        self.get_logger().info("🟢 FINAL TABLE CONFIRMED (published once)")

        self.publish_marker(all_pts)
        self.publish_collision(all_pts)

        self.table_published = True
        self.table_buffer.clear()

        # ---------------- VISUAL ----------------
        img = np.zeros((480, 640, 3), dtype=np.uint8)

        for x, y, z in pts_tf:
            if z <= 0:
                continue
            u = int(self.cx + (x * self.fx) / z)
            v = int(self.cy + (y * self.fy) / z)
            if 0 <= u < 640 and 0 <= v < 480:
                img[v, u] = (0, 0, 255)

        for x, y, z in all_pts:
            if z <= 0:
                continue
            u = int(self.cx + (x * self.fx) / z)
            v = int(self.cy + (y * self.fy) / z)
            if 0 <= u < 640 and 0 <= v < 480:
                img[v, u] = (0, 255, 0)

        cv2.imshow("table_view", img)
        cv2.waitKey(1)

    # ---------------- MARKER ----------------
    def publish_marker(self, pts):
        marker = Marker()
        marker.header.frame_id = "base_link"
        marker.header.stamp = self.get_clock().now().to_msg()

        marker.ns = "table"
        marker.id = 0
        marker.type = Marker.CUBE
        marker.action = Marker.ADD

        center = np.mean(pts, axis=0)

        marker.pose.position.x = float(center[0])
        marker.pose.position.y = float(center[1])
        marker.pose.position.z = float(center[2])
        marker.pose.orientation.w = 1.0

        marker.scale.x = 0.5
        marker.scale.y = 0.5
        marker.scale.z = 0.03

        marker.color.r = 0.0
        marker.color.g = 1.0
        marker.color.b = 0.0
        marker.color.a = 0.6

        self.marker_pub.publish(marker)

    # ---------------- MOVEIT COLLISION ----------------
    def publish_collision(self, pts):

        cloud = o3d.geometry.PointCloud()
        cloud.points = o3d.utility.Vector3dVector(pts)

        obb = cloud.get_oriented_bounding_box()
        center = obb.center

        L = float(obb.extent[0])
        W = float(obb.extent[1])

        obj = CollisionObject()
        obj.header.frame_id = "base_link"
        obj.header.stamp = self.get_clock().now().to_msg()
        obj.id = "table"
        obj.operation = CollisionObject.ADD

        tabletop = SolidPrimitive()
        tabletop.type = SolidPrimitive.BOX
        tabletop.dimensions = [L, W, 0.03]

        pose_top = Pose()
        pose_top.position.x = float(center[0])
        pose_top.position.y = float(center[1])
        pose_top.position.z = float(center[2])
        pose_top.orientation.w = 1.0

        obj.primitives = [tabletop]
        obj.primitive_poses = [pose_top]

        self.collision_pub.publish(obj)

        self.get_logger().info(f"🦾 MoveIt table published | L={L:.2f}, W={W:.2f}")

    # ---------------- CLEAR ----------------
    def clear_rviz(self):
        marker = Marker()
        marker.header.frame_id = "base_link"
        marker.ns = "table"
        marker.id = 0
        marker.action = Marker.DELETE
        self.marker_pub.publish(marker)


def main():
    rclpy.init()
    node = TableDetector()
    rclpy.spin(node)
    node.destroy_node()
    rclpy.shutdown()


if __name__ == "__main__":
    main()