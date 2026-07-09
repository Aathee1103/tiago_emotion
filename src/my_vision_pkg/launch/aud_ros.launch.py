from launch import LaunchDescription
from launch_ros.actions import Node

def generate_launch_description():

    #image_node = Node(
    #    package='my_vision_pkg',
    #    executable='image_emotion',
    #    name='image_subscriber'',
    #    output='screen'
    #)

    audio_node = Node(
        package='my_vision_pkg',
        executable='audio_rec',
        name='voice_to_speech',
        output='screen'
    )
    moveit_node = Node(
        package='my_vision_pkg',
        executable='moveit_arm',
        name='moveit_arm_cartesian',
        output='screen'
    )
    marker_node = Node(
        package='my_vision_pkg',
        executable='marker_align',
        name='aruco_docking',
        output='screen'
    )
    table_node = Node(
        package='my_vision_pkg',
        executable='table_detect',
        name='table_detector',
        output='screen'
    )


    #return LaunchDescription([
    #    image_node,
    #    audio_node,
    #    moveit_node
    #])
    return LaunchDescription([
        audio_node,
        moveit_node
    ])