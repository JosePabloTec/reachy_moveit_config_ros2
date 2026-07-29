import os
import yaml

from launch import LaunchDescription
from launch_ros.actions import Node
from launch_ros.descriptions import ParameterValue
from launch.substitutions import (
    Command,
    FindExecutable,
    PathJoinSubstitution,
)
from launch_ros.substitutions import FindPackageShare
from ament_index_python.packages import get_package_share_directory


def load_file(package_name, file_path):
    """
    Load a text file from a ROS 2 package.
    """
    package_path = get_package_share_directory(package_name)
    absolute_file_path = os.path.join(package_path, file_path)

    try:
        with open(absolute_file_path, "r") as file:
            return file.read()
    except EnvironmentError as e:
        raise RuntimeError(
            f"Could not load file: {absolute_file_path}"
        ) from e


def load_yaml(package_name, file_path):
    """
    Load a YAML file from a ROS 2 package.
    """
    package_path = get_package_share_directory(package_name)
    absolute_file_path = os.path.join(package_path, file_path)

    try:
        with open(absolute_file_path, "r") as file:
            return yaml.safe_load(file)
    except EnvironmentError as e:
        raise RuntimeError(
            f"Could not load YAML file: {absolute_file_path}"
        ) from e


def generate_launch_description():

    # ============================================================
    # Package name
    # ============================================================

    moveit_config_package = "reachy_moveit_config_ros2"

    # ============================================================
    # Robot description
    #
    # IMPORTANT:
    # This launch file only starts move_group.
    #
    # The rest of the Reachy system is expected to already provide:
    #   - /robot_description
    #   - /joint_states
    #   - /tf
    #   - /tf_static
    #
    # We still provide robot_description directly to move_group
    # because move_group requires the robot model.
    # ============================================================

    robot_description = {
        "robot_description": ParameterValue(
            Command(
                [
                    FindExecutable(name="xacro"),
                    " ",
                    PathJoinSubstitution(
                        [
                            FindPackageShare("reachy_description"),
                            "urdf",
                            "reachy.urdf.xacro",
                        ]
                    ),

                    # Match the working launch file's simulation setup
                    " use_fake_hardware:=true",
                    " use_gazebo:=true",
                    " depth_camera:=true",
                ]
            ),
            value_type=str,
        )
    }

    # ============================================================
    # Robot semantic description (SRDF)
    # ============================================================

    robot_description_semantic_config = load_file(
        moveit_config_package,
        "config/reachy2.srdf",
    )

    robot_description_semantic = {
        "robot_description_semantic": robot_description_semantic_config
    }

    # ============================================================
    # Kinematics
    # ============================================================

    kinematics_yaml = load_yaml(
        moveit_config_package,
        "config/kinematics.yaml",
    )

    # ============================================================
    # OMPL Planning Pipeline
    #
    # This structure matches the configuration used by the
    # working Reachy launch file.
    # ============================================================

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

            "start_state_max_bounds_error": 0.1,
        }
    }

    ompl_planning_yaml = load_yaml(
        moveit_config_package,
        "config/ompl_planning.yaml",
    )

    if ompl_planning_yaml:
        ompl_planning_pipeline_config["move_group"].update(
            ompl_planning_yaml
        )

    # ============================================================
    # MoveIt controller configuration
    #
    # This is required by MoveIt for trajectory execution.
    #
    # It does NOT launch the controllers.
    # The actual controllers must already be running.
    # ============================================================

    moveit_simple_controllers_yaml = load_yaml(
        moveit_config_package,
        "config/reachy_controllers.yaml",
    )

    moveit_controllers = {
        "moveit_simple_controller_manager": (
            moveit_simple_controllers_yaml
        ),
        "moveit_controller_manager": (
            "moveit_simple_controller_manager/"
            "MoveItSimpleControllerManager"
        ),
    }

    # ============================================================
    # Trajectory execution
    # ============================================================

    trajectory_execution = {
        "moveit_manage_controllers": True,
        "trajectory_execution.allowed_execution_duration_scaling": 1.2,
        "trajectory_execution.allowed_goal_duration_margin": 0.5,
        "trajectory_execution.allowed_start_tolerance": 0.01,
    }

    # ============================================================
    # Planning Scene Monitor
    # ============================================================

    planning_scene_monitor_parameters = {
        "planning_scene_monitor": {
            "publish_planning_scene": True,
            "publish_geometry_updates": True,
            "publish_state_updates": True,
            "publish_transforms_updates": True,
        }
    }

    # ============================================================
    # 3D Sensors / OctoMap
    # ============================================================

    sensors_3d_yaml = load_yaml(
        moveit_config_package,
        "config/sensors_3d.yaml",
    )

    sensors_3d_parameters = sensors_3d_yaml or {}

    # ============================================================
    # Move Group
    #
    # This is the ONLY node launched by this file.
    # ============================================================

    move_group_node = Node(
        package="moveit_ros_move_group",
        executable="move_group",
        name="move_group",
        output="screen",

        parameters=[
            # ----------------------------------------------------
            # Robot model
            # ----------------------------------------------------
            robot_description,

            # ----------------------------------------------------
            # Semantic robot model
            # ----------------------------------------------------
            robot_description_semantic,

            # ----------------------------------------------------
            # Kinematics
            # ----------------------------------------------------
            kinematics_yaml,

            # ----------------------------------------------------
            # OMPL planning pipeline
            # ----------------------------------------------------
            ompl_planning_pipeline_config,

            # ----------------------------------------------------
            # Trajectory execution
            # ----------------------------------------------------
            trajectory_execution,

            # ----------------------------------------------------
            # MoveIt controller manager
            # ----------------------------------------------------
            moveit_controllers,

            # ----------------------------------------------------
            # Simulation time
            #
            # Must match the rest of the running Reachy stack.
            # Your working launch file uses True for the MoveIt node.
            # ----------------------------------------------------
            {
                "use_sim_time": True,
            },

            # ----------------------------------------------------
            # Planning Scene Monitor
            # ----------------------------------------------------
            planning_scene_monitor_parameters,

            # ----------------------------------------------------
            # 3D sensor configuration
            # ----------------------------------------------------
            sensors_3d_parameters,

            # ----------------------------------------------------
            # OctoMap configuration
            # ----------------------------------------------------
            {
                "octomap_frame": "base_link",
                "octomap_resolution": 0.05,

                "occupancy_map_monitor": {
                    "enabled": True,
                },
            },
        ],
    )

    # ============================================================
    # Launch description
    # ============================================================

    return LaunchDescription(
        [
            move_group_node,
        ]
    )
