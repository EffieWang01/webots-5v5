#!/usr/bin/env bash
set -eo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

if [[ ! -r /etc/os-release ]]; then
  echo "[ERROR] Cannot identify the WSL Linux distribution."
  exit 1
fi
. /etc/os-release
if [[ "${ID:-}" != "ubuntu" || "${VERSION_ID:-}" != "22.04" ]]; then
  echo "[ERROR] Ubuntu 22.04 is required for ROS 2 Humble. Found: ${PRETTY_NAME:-unknown}."
  echo "Install it from Windows with: wsl --install -d Ubuntu-22.04"
  exit 1
fi

echo "[WSL 1/4] Installing base tools and enabling the ROS 2 repository..."
# Older preview packages accidentally stored the ASCII-armored ROS key in
# ros2.list.  APT then tries to parse the key as a repository and refuses to
# run.  Keep a timestamped backup before the first apt-get update.
ROS_LIST=/etc/apt/sources.list.d/ros2.list
if [[ -f "$ROS_LIST" ]] && sudo grep -q "BEGIN PGP PUBLIC KEY BLOCK" "$ROS_LIST"; then
  backup="${ROS_LIST}.broken.$(date +%Y%m%d%H%M%S)"
  echo "[FIX] Backing up malformed ROS source: $backup"
  sudo mv "$ROS_LIST" "$backup"
fi

sudo apt-get update
sudo apt-get install -y curl gnupg2 lsb-release locales software-properties-common
sudo locale-gen en_US en_US.UTF-8 >/dev/null
sudo update-locale LC_ALL=en_US.UTF-8 LANG=en_US.UTF-8
export LANG=en_US.UTF-8
sudo add-apt-repository -y universe

# APT expects a binary (dearmored) keyring here, not the textual PGP key.
curl -fsSL https://raw.githubusercontent.com/ros/rosdistro/master/ros.key \
  | gpg --dearmor \
  | sudo tee /usr/share/keyrings/ros-archive-keyring.gpg >/dev/null
ARCH="$(dpkg --print-architecture)"
echo "deb [arch=${ARCH} signed-by=/usr/share/keyrings/ros-archive-keyring.gpg] http://packages.ros.org/ros2/ubuntu ${VERSION_CODENAME} main" \
  | sudo tee "$ROS_LIST" >/dev/null

echo "[WSL 2/4] Installing ROS 2 Humble and build dependencies..."
sudo apt-get update
sudo apt-get install -y \
  build-essential cmake git python3-pip python3-yaml python3-rosdep python3-colcon-common-extensions \
  libeigen3-dev libopencv-dev libyaml-cpp-dev \
  ros-humble-ros-base ros-humble-backward-ros ros-humble-behaviortree-cpp-v3 \
  ros-humble-diagnostic-msgs ros-humble-tf2-ros ros-humble-tf2-geometry-msgs \
  ros-humble-visualization-msgs

source /opt/ros/humble/setup.bash
if [[ ! -f /etc/ros/rosdep/sources.list.d/20-default.list ]]; then
  sudo rosdep init
fi

echo "[WSL 3/4] Resolving package dependencies..."
rosdep update
rosdep install --from-paths src --ignore-src --rosdistro humble -r -y

echo "[WSL 4/4] Building the simulator..."
./scripts/build_dual_brain.sh

echo "[OK] WSL setup and build completed."
