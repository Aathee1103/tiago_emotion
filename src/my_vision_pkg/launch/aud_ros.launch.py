from launch import LaunchDescription
from launch_ros.actions import Node

def generate_launch_description():

    image_node = Node(
        package='my_vision_pkg',
        executable='image_emotion',
        name='image_emotion_node',
        output='screen'
    )

    audio_node = Node(
        package='my_vision_pkg',
        executable='audio_rec',
        name='audio_recorder',
        output='screen'
    )
    moveit_node = Node(
        package='my_vision_pkg',
        executable='moveit_node',
        name='list_moveit_groups',
        output='screen'
    )

    return LaunchDescription([
        image_node,
        audio_node,
        moveit_node
    ])