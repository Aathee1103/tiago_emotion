#include <memory>
#include <thread>
#include <chrono>
#include <cmath>

#include "rclcpp/rclcpp.hpp"
#include "rclcpp_action/rclcpp_action.hpp"

#include "moveit/move_group_interface/move_group_interface.h"

#include "geometry_msgs/msg/pose.hpp"
#include "tf2_geometry_msgs/tf2_geometry_msgs.hpp"
#include "tf2/LinearMath/Quaternion.h"

#include "control_msgs/action/follow_joint_trajectory.hpp"
#include "trajectory_msgs/msg/joint_trajectory_point.hpp"

using FollowJointTrajectory = control_msgs::action::FollowJointTrajectory;
using GoalHandleFJT = rclcpp_action::ClientGoalHandle<FollowJointTrajectory>;


// -----------------------------
// ADD isClose HERE
// -----------------------------
bool isClose(const geometry_msgs::msg::Pose &a,
             const geometry_msgs::msg::Pose &b)
{
  return (std::abs(a.position.x - b.position.x) < 0.01 &&
          std::abs(a.position.y - b.position.y) < 0.01 &&
          std::abs(a.position.z - b.position.z) < 0.01);
}


// -----------------------------
// GRIPPER CLIENT
// -----------------------------
class GripperClient
{
public:
  explicit GripperClient(const rclcpp::Node::SharedPtr & node)
  : node_(node)
  {
    client_ = rclcpp_action::create_client<FollowJointTrajectory>(
      node_,
      "/gripper_controller/follow_joint_trajectory");
  }

  void send_position(double right, double left)
  {
    if (!client_->wait_for_action_server(std::chrono::seconds(5))) {
      RCLCPP_ERROR(node_->get_logger(), "Gripper action server not available");
      return;
    }

    FollowJointTrajectory::Goal goal_msg;

    goal_msg.trajectory.joint_names = {
      "gripper_right_finger_joint",
      "gripper_left_finger_joint"
    };

    trajectory_msgs::msg::JointTrajectoryPoint point;
    point.positions = {right, left};
    point.time_from_start = rclcpp::Duration::from_seconds(1.0);

    goal_msg.trajectory.points.push_back(point);

    auto options =
      rclcpp_action::Client<FollowJointTrajectory>::SendGoalOptions();

    options.result_callback =
      [this](const GoalHandleFJT::WrappedResult & result) {
        if (result.code == rclcpp_action::ResultCode::SUCCEEDED) {
          RCLCPP_INFO(node_->get_logger(), "Gripper motion succeeded");
        } else {
          RCLCPP_ERROR(node_->get_logger(), "Gripper motion failed");
        }
      };

    client_->async_send_goal(goal_msg, options);
  }

private:
  rclcpp::Node::SharedPtr node_;
  rclcpp_action::Client<FollowJointTrajectory>::SharedPtr client_;
};


// -----------------------------
// MAIN
// -----------------------------
int main(int argc, char **argv)
{
  rclcpp::init(argc, argv);

  auto node = std::make_shared<rclcpp::Node>(
    "moveit_arm_cartesian",
    rclcpp::NodeOptions().automatically_declare_parameters_from_overrides(true)
  );

  rclcpp::executors::MultiThreadedExecutor executor;
  executor.add_node(node);
  std::thread spinner([&executor]() { executor.spin(); });

  std::this_thread::sleep_for(std::chrono::seconds(2));

  moveit::planning_interface::MoveGroupInterface move_group(node, "arm_torso");

  move_group.setPoseReferenceFrame("base_footprint");
  move_group.setPlanningTime(10.0);
  move_group.setNumPlanningAttempts(10);
  move_group.setMaxVelocityScalingFactor(0.3);
  move_group.setMaxAccelerationScalingFactor(0.3);

  GripperClient gripper(node);

  // -----------------------------
  // HOME
  // -----------------------------
  geometry_msgs::msg::Pose home = move_group.getCurrentPose().pose;

  RCLCPP_INFO(node->get_logger(),
    "HOME: x=%.3f y=%.3f z=%.3f",
    home.position.x,
    home.position.y,
    home.position.z);

  // -----------------------------
  // TARGET
  // -----------------------------
  geometry_msgs::msg::Pose target1 = home;

  target1.position.x = 0.790;
  target1.position.y = 0.040;
  target1.position.z = 0.940;//0.930

  tf2::Quaternion q;
  q.setRPY(0.0, M_PI / 2, 0.0);
  target1.orientation = tf2::toMsg(q);

  RCLCPP_INFO(node->get_logger(), "MOVING TO TARGET...");

  move_group.setStartStateToCurrentState();
  move_group.setPoseTarget(target1);
  move_group.move();

  // -----------------------------
  // YOUR LOOP (UNCHANGED)
  // -----------------------------
  RCLCPP_INFO(node->get_logger(), "Waiting for target...");

  rclcpp::Rate rate(10);

  while (rclcpp::ok())
  {
    auto current = move_group.getCurrentPose().pose;

    if (isClose(current, target1))
    {
      RCLCPP_INFO(node->get_logger(), "Target reached!");
      break;
    }

    rate.sleep();
  }


  geometry_msgs::msg::Pose target2 = target1;

  target2.position.x = target1.position.x;
  target2.position.y = target1.position.y;
  target2.position.z = target1.position.z -0.05;//0.930

  target2.orientation = target1.orientation;

  RCLCPP_INFO(node->get_logger(), "MOVING TO TARGET2...");

  move_group.setStartStateToCurrentState();
  move_group.setPoseTarget(target2);
  move_group.move();

  // -----------------------------
  // YOUR LOOP (UNCHANGED)
  // -----------------------------
  RCLCPP_INFO(node->get_logger(), "Waiting for target2...");


  while (rclcpp::ok())
  {
    auto current = move_group.getCurrentPose().pose;

    if (isClose(current, target2))
    {
      RCLCPP_INFO(node->get_logger(), "Target2 reached!");
      break;
    }

    rate.sleep();
  }

  // -----------------------------
  // CLOSE GRIPPER
  // -----------------------------
  RCLCPP_INFO(node->get_logger(), "Closing gripper...");
  gripper.send_position(0.02, 0.02);
  std::this_thread::sleep_for(std::chrono::seconds(2));

  // -----------------------------
  // RETURN HOME
  // -----------------------------
  RCLCPP_INFO(node->get_logger(), "Returning home...");

  move_group.setStartStateToCurrentState();
  move_group.setPoseTarget(home);
  move_group.move();

  RCLCPP_INFO(node->get_logger(), "Waiting for home...");


  while (rclcpp::ok())
  {
    auto current = move_group.getCurrentPose().pose;

    if (isClose(current, home))
    {
      RCLCPP_INFO(node->get_logger(), "Home reached!");
      break;
    }

    rate.sleep();
  }

  // -----------------------------
  // OPEN GRIPPER (ONLY AFTER HOME)
  // -----------------------------
  RCLCPP_INFO(node->get_logger(), "Opening gripper...");
  gripper.send_position(0.04, 0.04);
  std::this_thread::sleep_for(std::chrono::seconds(2));

  RCLCPP_INFO(node->get_logger(), "DONE");

  rclcpp::shutdown();
  spinner.join();
  return 0;
}