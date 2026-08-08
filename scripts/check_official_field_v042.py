#!/usr/bin/env python3
"""Static V0.4.2 field/referee configuration check (no Webots or ROS 2 required)."""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CFG = json.loads((ROOT / "sim_webots/config/bridge.json").read_text(encoding="utf-8"))
WORLD = (ROOT / "sim_webots/worlds/football_5v5_brain.wbt").read_text(encoding="utf-8")

expected = {
    "length": 22.0,
    "width": 14.0,
    "turf_length": 26.0,
    "turf_width": 18.0,
    "safety_buffer": 2.0,
    "line_width": 0.08,
    "center_circle_radius": 2.0,
    "penalty_area_width": 8.0,
    "penalty_area_depth": 5.0,
    "goal_area_width": 5.0,
    "goal_area_depth": 2.0,
    "penalty_mark_distance": 3.5,
    "corner_arc_radius": 0.7,
    "goal_width": 3.0,
    "goal_height": 2.0,
}

errors = []
for key, value in expected.items():
    actual = CFG["field"].get(key)
    if actual != value:
        errors.append(f"field.{key}: expected {value}, got {actual}")

if "geometry Box { size 26 18 0.1 }" not in WORLD:
    errors.append("26 m x 18 m turf geometry not found in world")
if "REFEREE: INTERNAL SIMULATED" not in (ROOT / "sim_webots/controllers/webots_gateway/webots_gateway.py").read_text(encoding="utf-8"):
    errors.append("internal simulated referee overlay not found")
if CFG.get("referee", {}).get("mode") != "internal_simulated":
    errors.append("referee.mode is not internal_simulated")

if errors:
    print("[FAIL] V0.4.2 field check")
    for error in errors:
        print(f"  - {error}")
    raise SystemExit(1)

print("[PASS] V0.4.2 official-field baseline")
for key, value in expected.items():
    print(f"  field.{key} = {value}")
print("  referee.mode = internal_simulated")
print("  official_udp_game_controller_enabled = false")
