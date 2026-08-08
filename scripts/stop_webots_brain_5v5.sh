#!/usr/bin/env bash
set -eo pipefail

# Ask the launch process and child nodes to stop cleanly first.
pkill -INT -f "ros2 launch webots_ros2_bridge brain_5v5.launch.py" 2>/dev/null || true
sleep 1

# Clean up any orphaned processes left after an interrupted terminal session.
pkill -TERM -f "webots_ros2_bridge.*bridge_node" 2>/dev/null || true
pkill -TERM -f "sim_game_controller_node" 2>/dev/null || true
pkill -TERM -f "brain_node" 2>/dev/null || true
sleep 1

rm -f /tmp/webots_5v5_brain_simulator.lock
echo "Stopped simulated GameController, Webots bridge, and both independent Brain teams."
