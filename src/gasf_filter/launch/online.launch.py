from launch import LaunchDescription
from launch_ros.actions import Node
from ament_index_python.packages import get_package_share_directory
import os


def generate_launch_description():
    config = os.path.join(get_package_share_directory('gasf_filter'), 'config', 'online.yaml')
    return LaunchDescription([
        Node(package='gasf_filter', executable='gasf_filter_node', name='gasf_filter_node',
             output='screen', parameters=[config]),
    ])
