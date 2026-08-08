#!/usr/bin/env bash
set -eo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
source /opt/ros/humble/setup.bash
colcon build --symlink-install --packages-up-to \
  brain_red_v3 brain_blue_wangyifei_v1 webots_ros2_bridge game_controller
echo "[OK] Built RED brain_v3, BLUE wangyifei_v1, GameController, and Webots bridge."
