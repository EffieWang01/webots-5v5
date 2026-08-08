#!/usr/bin/env bash
set -eo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
source /opt/ros/humble/setup.bash
if [[ -f "$ROOT/install/setup.bash" ]]; then source "$ROOT/install/setup.bash"; fi
colcon build --symlink-install --packages-select brain_red_v3
echo "[OK] Rebuilt RED brain_v3 only."
