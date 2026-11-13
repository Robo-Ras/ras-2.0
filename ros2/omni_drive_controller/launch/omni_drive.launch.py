"""Sobe a base omni: cinemática + ponte serial com o Arduino + odometria simulada (loopback).

    ros2 launch omni_drive_controller omni_drive.launch.py
    ros2 launch omni_drive_controller omni_drive.launch.py port:=/dev/ttyUSB0
    ros2 launch omni_drive_controller omni_drive.launch.py port:=/tmp/ttyFakeArduino   # sem robô
    ros2 launch omni_drive_controller omni_drive.launch.py use_loopback:=false

Tópicos:
    /cmd_vel           (entrada, geometry_msgs/Twist)  <- Nav2, teleop, etc.
    /wheel_pwm         (omni_drive_controller_msgs/WheelPwm)
    /applied_cmd_vel   (velocidade que realmente foi para os motores; alimenta a odometria)
    /odom, TF map->odom->base_link   (nav2_loopback_sim)
    /arduino/connected (std_msgs/Bool)
"""
import os

from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument
from launch.conditions import IfCondition
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node


def generate_launch_description():
    default_params = os.path.join(
        get_package_share_directory('omni_drive_controller'), 'config', 'omni_drive.yaml')

    params_file = LaunchConfiguration('params_file')
    port = LaunchConfiguration('port')
    use_loopback = LaunchConfiguration('use_loopback')

    return LaunchDescription([
        DeclareLaunchArgument('params_file', default_value=default_params),
        DeclareLaunchArgument('port', default_value='/dev/ttyACM0',
                              description='Porta serial do Arduino'),
        DeclareLaunchArgument('use_loopback', default_value='true',
                              description='Odometria simulada via nav2_loopback_sim'),

        Node(
            package='omni_drive_controller',
            executable='omni_kinematics_node',
            name='omni_kinematics',
            output='screen',
            parameters=[params_file],
        ),
        Node(
            package='omni_drive_controller',
            executable='arduino_bridge_node',
            name='arduino_bridge',
            output='screen',
            parameters=[params_file, {'port': port}],
        ),

        # Odometria: integra a velocidade APLICADA (pós saturação/rampa/watchdog),
        # não o /cmd_vel cru, para não "andar" na simulação o que o motor não andou.
        Node(
            package='nav2_loopback_sim',
            executable='loopback_simulator',
            name='loopback_simulator',
            output='screen',
            parameters=[params_file],
            remappings=[
                ('cmd_vel', 'applied_cmd_vel'),
                # o scan do loopback é falso (vem do mapa); não colide com um LiDAR real em /scan
                ('scan', 'loopback/scan'),
            ],
            condition=IfCondition(use_loopback),
        ),
        # Frame do "laser" do loopback. Ajuste a posição quando montar o LiDAR no URDF.
        Node(
            package='tf2_ros',
            executable='static_transform_publisher',
            name='base_to_scan_tf',
            arguments=['--frame-id', 'base_link', '--child-frame-id', 'base_scan'],
            condition=IfCondition(use_loopback),
        ),
    ])
