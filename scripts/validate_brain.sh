#!/usr/bin/env bash
set -eo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
TEAM="${1:-blue}"
python3 "$ROOT/scripts/validate_brain.py" --team "$TEAM" "${@:2}"
