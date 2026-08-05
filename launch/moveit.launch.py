import os
import yaml


from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument
from launch_ros.actions import Node
from launch.substitutions import (
   Command,
   FindExecutable,
   PathJoinSubstitution,
   LaunchConfiguration,
)
from launch_ros.substitutions import FindPackageShare
from launch_ros.descriptions import ParameterValue
from ament_index_python.packages import get_package_share_directory


from reachy_config import (
   BETA,
   DVT,
   ReachyConfig,
)




def load_file(package_name, file_path):
   package_path = get_package_share_directory(package_name)
   absolute_file_path = os.path.join(package_path, file_path)


   try:
       with open(absolute_file_path, "r") as file:
           return file.read()
   except EnvironmentError:
       return None




def load_yaml(package_name, file_path):
   package_path = get_package_share_directory(package_name)
   absolute_file_path = os.path.join(package_path, file_path)


   try:
       with open(absolute_file_path, "r") as file:
           return yaml.safe_load(file)
   except EnvironmentError:
       return None




def generate_launch_description():


   use_sim_time = LaunchConfiguration("use_sim_time")


   # Package name
   moveit_config_package = "reachy_moveit_config_ros2"


   reachy_config = ReachyConfig()


   # Robot description


   reachy_urdf_config = (
       " depth_camera:=true",
       f" robot_config:={reachy_config.model}",
       f' neck_config:="{reachy_config.part_conf("neck_config", fake=False)}"',
       f' right_shoulder_config:="{reachy_config.part_conf("right_shoulder_config", fake=False)}"',
       f' right_elbow_config:="{reachy_config.part_conf("right_elbow_config", fake=False)}"',
       f' right_wrist_config:="{reachy_config.part_conf("right_wrist_config", fake=False)}"',
       f' left_shoulder_config:="{reachy_config.part_conf("left_shoulder_config", fake=False)}"',
       f' left_elbow_config:="{reachy_config.part_conf("left_elbow_config", fake=False)}"',
       f' left_wrist_config:="{reachy_config.part_conf("left_wrist_config", fake=False)}"',
       f' antenna_config:="{reachy_config.part_conf("antenna_config", fake=False)}"',
       f' grippers_config:="{reachy_config.part_conf("grippers_config", fake=False)}"',
       f' robot_model:="{BETA if reachy_config.beta else DVT}"',
   )


   # Robot semantic description


   robot_description_semantic_config = load_file(
       moveit_config_package,
       "config/reachy2.srdf",
   )


   robot_description_semantic = {
       "robot_description_semantic": robot_description_semantic_config
   }


   # Kinematics



   kinematics_yaml = load_yaml(
       moveit_config_package,
       "config/kinematics.yaml",
   )


   # OMPL planning pipeline config




   ompl_planning_pipeline_config = {
       "move_group": {
           "planning_plugin": "ompl_interface/OMPLPlanner",


           "request_adapters": (
               "default_planner_request_adapters/"
               "AddTimeOptimalParameterization "
               "default_planner_request_adapters/"
               "ResolveConstraintFrames "
               "default_planner_request_adapters/"
               "FixWorkspaceBounds "
               "default_planner_request_adapters/"
               "FixStartStateBounds "
               "default_planner_request_adapters/"
               "FixStartStateCollision "
               "default_planner_request_adapters/"
               "FixStartStatePathConstraints"
           ),


           "start_state_max_bounds_error": 0.3,  # necessary for the ERL Robot shoulder roll
       }
   }


   ompl_planning_yaml = load_yaml(
       moveit_config_package,
       "config/ompl_planning.yaml",
   )


   ompl_planning_pipeline_config["move_group"].update(
       ompl_planning_yaml
   )


   # MoveIt controller configuration




   moveit_simple_controllers_yaml = load_yaml(
       moveit_config_package,
       "config/reachy_controllers.yaml",
   )


   moveit_controllers = {
       "moveit_simple_controller_manager":
           moveit_simple_controllers_yaml,


       "moveit_controller_manager":
           "moveit_simple_controller_manager/"
           "MoveItSimpleControllerManager",
   }


   # Trajectory execution


   trajectory_execution = {
       "moveit_manage_controllers": True,
       "trajectory_execution.allowed_execution_duration_scaling": 1.2,
       "trajectory_execution.allowed_goal_duration_margin": 0.5,
       "trajectory_execution.allowed_start_tolerance": 0.01,
   }


   # Planning Scene Monitor


   planning_scene_monitor_parameters = {
       "planning_scene_monitor": {
           "publish_planning_scene": True,
           "publish_geometry_updates": True,
           "publish_state_updates": True,
           "publish_transforms_updates": True,
       }
   }


   # 3D Sensors / OctoMap


   sensors_3d_yaml = load_yaml(
       moveit_config_package,
       "config/sensors_3d_hardware.yaml",
   )


   sensors_3d_parameters = sensors_3d_yaml or {}


   occupancy_map_yaml = load_yaml(
       moveit_config_package,
       "config/occupancy_map.yaml",
   )


   occupancy_map_parameters = occupancy_map_yaml or {}


   # Depth image to PointCloud2


   head_depth_to_pointcloud = Node(
       package="depth_image_proc",
       executable="point_cloud_xyz_node",
       name="head_depth_to_pointcloud",
       output="screen",
       remappings=[
           ("image_rect", "/camera/depth/image_raw"),
           ("camera_info", "/camera/depth/camera_info"),
           ("points", "/camera/depth/points2"),
       ],
       parameters=[
           {
               "use_sim_time": use_sim_time,
           }
       ],
   )


   torso_depth_to_pointcloud = Node(
       package="depth_image_proc",
       executable="point_cloud_xyz_node",
       name="torso_depth_to_pointcloud",
       output="screen",
       remappings=[
           (
               "image_rect",
               "/teleop_camera/depth/image_raw",
           ),
           (
               "camera_info",
               "/teleop_camera/depth/camera_info",
           ),
           (
               "points",
               "/torso_camera/depth/points2",
           ),
       ],
       parameters=[
           {
               "use_sim_time": use_sim_time,
           }
       ],
   )


   # Move Group


   move_group_node = Node(
       package="moveit_ros_move_group",
       executable="move_group",
       name="move_group",
       output="screen",


       parameters=[
           robot_description_semantic,
           kinematics_yaml,
           ompl_planning_pipeline_config,
           trajectory_execution,
           moveit_controllers,
           planning_scene_monitor_parameters,
           sensors_3d_parameters,
           occupancy_map_parameters,


           {
               "use_sim_time": use_sim_time,
           },
       ],
   )


   # RViz
   # COntains the same configuration as reachy.launch.py


   rviz_config_file = PathJoinSubstitution(
       [
           FindPackageShare("reachy_description"),
           "config",
           "moveit.rviz",
       ]
   )


   rviz_node = Node(
       package="rviz2",
       executable="rviz2",
       name="rviz2",
       output="log",


       arguments=[
           "-d",
           rviz_config_file,
       ],


       parameters=[
           robot_description_semantic,
           ompl_planning_pipeline_config,
           kinematics_yaml,
       ],
   )




   # Launch


   return LaunchDescription(
       [
           DeclareLaunchArgument(
               "use_sim_time",
               default_value="false",
               description="Use simulation time if true",
           ),


           # Convert depth images to PointCloud2
           head_depth_to_pointcloud,
           torso_depth_to_pointcloud,


           # MoveIt
           move_group_node,


           # RViz
           rviz_node,
       ]
   )
