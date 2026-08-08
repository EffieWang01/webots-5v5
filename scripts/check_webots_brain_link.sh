#!/usr/bin/env bash
set -eo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
source /opt/ros/humble/setup.bash
source "$ROOT/install/setup.bash"
exec python3 "$ROOT/scripts/check_webots_brain_link.py"
