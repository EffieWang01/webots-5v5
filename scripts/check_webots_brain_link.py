#!/usr/bin/env python3
"""One-shot, cleanly terminating ROS 2 link check for the 5v5 simulator."""
from __future__ import annotations

import collections
import json
import time

import rclpy
from booster_msgs.msg import RpcReqMsg
from rclpy.node import Node
from std_msgs.msg import String

EXPECTED_MAIN_NODES = {
    "/webots_ros2_bridge",
    *{f"/brain_{team}_{index}" for team in ("red", "blue") for index in range(1, 6)},
}


class LinkCheck(Node):
    def __init__(self):
        super().__init__("webots_brain_link_check")
        self.world = None
        self.rpc = None
        self._subscriptions = [
            self.create_subscription(String, "/webots/world_state", self.on_world, 10),
            self.create_subscription(RpcReqMsg, "LocoApiTopic/red_5Req", self.on_rpc, 10),
        ]

    def on_world(self, message):
        self.world = message.data

    def on_rpc(self, message):
        self.rpc = message


def full_node_name(namespace, name):
    if namespace == "/":
        return f"/{name}"
    return f"{namespace.rstrip('/')}/{name}"


def main():
    rclpy.init()
    node = LinkCheck()
    deadline = time.monotonic() + 5.0
    try:
        while time.monotonic() < deadline and (node.world is None or node.rpc is None):
            rclpy.spin_once(node, timeout_sec=0.1)

        discovered = [full_node_name(ns, name) for name, ns in node.get_node_names_and_namespaces()]
        counts = collections.Counter(discovered)
        duplicates = sorted(name for name, count in counts.items() if count > 1)
        present = sorted(EXPECTED_MAIN_NODES.intersection(counts))
        missing = sorted(EXPECTED_MAIN_NODES.difference(counts))

        print("=== Nodes ===")
        print(f"Expected main nodes: {len(present)} / {len(EXPECTED_MAIN_NODES)}")
        if missing:
            print("Missing:", ", ".join(missing))
        if duplicates:
            print("Duplicate names:", ", ".join(duplicates))
        else:
            print("Duplicate names: none")

        print("\n=== Webots world state ===")
        if node.world is None:
            print("[FAIL] No /webots/world_state within 5 seconds.")
        else:
            try:
                state = json.loads(node.world)
                ball = state.get("ball", {})
                print(
                    "[OK] Webots -> WSL works. "
                    f"phase={state.get('phase')} "
                    f"ball=({ball.get('x')},{ball.get('y')},{ball.get('z')})"
                )
            except Exception:
                print("[OK] Topic received, but JSON parsing failed.")

        print("\n=== Brain command ===")
        if node.rpc is None:
            print("[FAIL] No red_5 Brain RPC within 5 seconds.")
        else:
            print(f"[OK] header={node.rpc.header} body={node.rpc.body}")

        success = not missing and node.world is not None and node.rpc is not None
        return 0 if success else 1
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == "__main__":
    raise SystemExit(main())
