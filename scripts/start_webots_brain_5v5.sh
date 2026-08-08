#!/usr/bin/env bash
set -eo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"

if [[ ! -f /opt/ros/humble/setup.bash ]]; then
  echo "[ERROR] ROS 2 Humble setup not found: /opt/ros/humble/setup.bash"
  exit 1
fi
if [[ ! -f "$ROOT/install/setup.bash" ]]; then
  echo "[ERROR] Workspace has not been built yet: $ROOT/install/setup.bash"
  echo "Build it first, then source the install space."
  exit 1
fi

# Refuse to start over an older process that does not hold this release's
# dual-Brain lock file.
if pgrep -f "[b]rain_node" >/dev/null 2>&1 \
  || pgrep -f "[w]ebots_ros2_bridge.*[b]ridge_node" >/dev/null 2>&1 \
  || pgrep -f "[s]im_game_controller_node" >/dev/null 2>&1; then
  echo "[ERROR] Existing Brain or Webots Bridge processes were found."
  echo "Run: $ROOT/scripts/stop_webots_brain_5v5.sh"
  exit 1
fi

# Hold an exclusive lock for the lifetime of ros2 launch. This prevents the
# same 5v5 stack from being started twice and publishing duplicate commands.
LOCK_FILE="/tmp/webots_5v5_brain_simulator.lock"
exec 9>"$LOCK_FILE"
if ! flock -n 9; then
  echo "[ERROR] Another Webots 5v5 Brain Simulator stack is already running."
  echo "Run: $ROOT/scripts/stop_webots_brain_5v5.sh"
  exit 1
fi

source /opt/ros/humble/setup.bash
source "$ROOT/install/setup.bash"

if [[ -n "${WEBOTS_GATEWAY_HOST:-}" ]]; then
  GATEWAY_HOST="$WEBOTS_GATEWAY_HOST"
elif grep -qi microsoft /proc/version 2>/dev/null; then
  GATEWAY_HOST="$(ip route show default | awk '/default/ {print $3; exit}')"
else
  GATEWAY_HOST="127.0.0.1"
fi

if [[ -z "$GATEWAY_HOST" ]]; then
  echo "[ERROR] Could not determine the Windows host IP."
  echo "Set it manually: WEBOTS_GATEWAY_HOST=<Windows-IP> $0"
  exit 1
fi

WSL_IP="$(hostname -I 2>/dev/null | awk '{print $1}')"

echo "[VERSION] Webots 5v5 Brain Simulator 1.0.2"
echo "[NETWORK] WSL/ROS2 state listener: ${WSL_IP:-unknown}:10081"
echo "[NETWORK] Webots command target:  ${GATEWAY_HOST}:10082"
echo "[NETWORK] Webots must be launched with WEBOTS_ROS_HOST=${WSL_IP:-<WSL-IP>}"
echo "[TEAMS] RED=brain_red_v3 | BLUE=brain_blue_wangyifei_v1 | kickoff=RED"
echo "[LOCK] Duplicate launch protection enabled: $LOCK_FILE"

exec ros2 launch webots_ros2_bridge brain_5v5.launch.py \
  gateway_host:="$GATEWAY_HOST"
