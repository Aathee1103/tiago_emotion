from setuptools import setup
import os
from glob import glob

package_name = 'my_vision_pkg'

setup(
    name=package_name,
    version='0.0.0',

    packages=[package_name],

    data_files=[
        # required for ament index
        ('share/ament_index/resource_index/packages',
            ['resource/' + package_name]),

        # package.xml install
        ('share/' + package_name, ['package.xml']),

        # ✅ launch files install
        (os.path.join('share', package_name, 'launch'),
            glob('launch/*.launch.py')),
    ],

    install_requires=['setuptools'],

    zip_safe=True,

    maintainer='user',
    maintainer_email='user@todo.todo',
    description='Vision + Audio ROS2 package',
    license='TODO',

    entry_points={
        'console_scripts': [
            'image_emotion = my_vision_pkg.image_emotion:main',
            'audio_rec = my_vision_pkg.audio_rec:main',
            'moveit_node = my_vision_pkg.moveit_node:main',
            'moveit_service = my_vision_pkg.moveit_service:main',
            'table_detect = my_vision_pkg.table_detect:main',
            'arm_motion_speak = my_vision_pkg.arm_motion_speak:main',
            
        ],
    },
)

