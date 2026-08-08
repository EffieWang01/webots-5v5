#!/usr/bin/env bash
set -eo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
source /opt/ros/humble/setup.bash
if [[ -f "$ROOT/install/setup.bash" ]]; then source "$ROOT/install/setup.bash"; fi
colcon build --symlink-install --packages-select brain_blue_wangyifei_v1
echo "[OK] Rebuilt BLUE wangyifei_v1 only."
