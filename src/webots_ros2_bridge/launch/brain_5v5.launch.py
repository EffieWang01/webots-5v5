"""Launch independent RED and BLUE Brain packages."""
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node
from ament_index_python.packages import get_package_share_directory
import os

TEAM_IDS = {"red": 29, "blue": 30}
TEAM_PACKAGES = {
    "red": "brain_red_v3",
    "blue": "brain_blue_wangyifei_v1",
}
ROLES = {
    1: "goal_keeper",
    2: "defender",
    3: "striker",
    4: "striker",
    5: "striker",
}


def brain_paths(package_name):
    share = get_package_share_directory(package_name)
    return {
        "config": os.path.join(share, "config", "config_sim_truth.yaml"),
        "vision": os.path.join(share, "config", "vision_sim_truth.yaml"),
        "tree": os.path.join(share, "behavior_trees", "game.xml"),
    }


def generate_launch_description():
    gateway_host = LaunchConfiguration("gateway_host")
    nodes = [
        Node(
            package="game_controller",
            executable="sim_game_controller_node",
            name="sim_game_controller",
            output="screen",
            parameters=[{
                "world_state_topic": "/webots/world_state",
                "ball_move_threshold": 0.35,
                "set_play_timeout": 12.0,
                "timeout_fallback_enabled": True,
                "use_sim_time": True,
            }],
        ),
        Node(
            package="webots_ros2_bridge",
            executable="bridge_node",
            name="webots_ros2_bridge",
            output="screen",
            parameters=[{"gateway_host": gateway_host}],
        )
    ]

    for team in ("red", "blue"):
        package_name = TEAM_PACKAGES[team]
        paths = brain_paths(package_name)
        for player_id in range(1, 6):
            robot_name = f"{team}_{player_id}"
            nodes.append(
                Node(
                    package=package_name,
                    executable="brain_node",
                    name=f"brain_{robot_name}",
                    output="screen",
                    parameters=[
                        paths["config"],
                        {
                            "tree_file_path": paths["tree"],
                            "vision_config_path": paths["vision"],
                            "vision_config_local_path": "",
                            "game.team_id": TEAM_IDS[team],
                            "game.player_id": player_id,
                            "game.player_role": ROLES[player_id],
                            "game.number_of_players": 5,
                            "game.sim_ground_truth": True,
                            "sim.flip_field": team == "blue",
                            "robot.robot_name": robot_name,
                            "use_sim_time": True,
                            "enable_com": True,
                            "game_control_ip": "127.0.0.1",
                        },
                    ],
                )
            )

    return LaunchDescription(
        [
            DeclareLaunchArgument("gateway_host", default_value="127.0.0.1"),
            *nodes,
        ]
    )
