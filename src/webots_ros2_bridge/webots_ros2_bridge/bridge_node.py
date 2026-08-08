"""ROS 2 side of the Webots bridge.

It translates existing Brain topics without embedding tactical logic. V0.3.3
adds a small UDP acknowledgement so the Webots UI can distinguish a healthy
Webots -> WSL world-state path from the opposite command path.
"""
from __future__ import annotations

import json
import math
import os
import socket
import time
from functools import partial

import rclpy
from builtin_interfaces.msg import Time
from booster_interface.msg import LowState, MotorState, Odometer, RawBytesMsg
from booster_msgs.msg import RpcReqMsg
from brain_red_v3.msg import Kick as RedKick
from brain_blue_wangyifei_v1.msg import Kick as BlueKick
from geometry_msgs.msg import Pose
from rclpy.node import Node
from rosgraph_msgs.msg import Clock
from std_msgs.msg import String

ROBOTS = [f"{team}_{index}" for team in ("red", "blue") for index in range(1, 6)]
API_MOVE = 2001
API_ROTATE_HEAD = 2004
API_GET_UP = 2008


def wrap(angle):
    while angle > math.pi:
        angle -= 2.0 * math.pi
    while angle < -math.pi:
        angle += 2.0 * math.pi
    return angle


def team_pose(name, x, y, theta):
    if name.startswith("blue_"):
        return -x, -y, wrap(theta - math.pi)
    return x, y, wrap(theta)


class Bridge(Node):
    def __init__(self):
        self.role = os.environ.get("WEBOTS_BRIDGE_ROLE", "all")
        super().__init__(f"webots_{self.role}_bridge")
        self.declare_parameter("gateway_host", "127.0.0.1")
        self.declare_parameter("state_port", 10081)
        self.declare_parameter("command_port", 10082)
        self.declare_parameter("transport", "tcp_relay")
        self.declare_parameter("relay_port", 10083)
        self.declare_parameter("status_hz", 2.0)

        self.host = str(self.get_parameter("gateway_host").value)
        self.state_port = int(self.get_parameter("state_port").value)
        self.command_port = int(self.get_parameter("command_port").value)
        self.transport = str(self.get_parameter("transport").value)
        self.relay_port = int(self.get_parameter("relay_port").value)
        status_hz = max(0.2, float(self.get_parameter("status_hz").value))
        self.status_period = 1.0 / status_hz

        self.rx = None
        self.tx = None
        self.relay = None
        self.relay_buffer = b""
        self.relay_last_attempt = -1e9
        if self.transport == "udp":
            self.rx = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            self.rx.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            self.rx.bind(("0.0.0.0", self.state_port))
            self.rx.setblocking(False)
            self.tx = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            self.target = (self.host, self.command_port)
        else:
            self.target = f"tcp://{self.host}:{self.relay_port}"

        self.world_pub = self.create_publisher(String, "/webots/world_state", 10)
        self.clock_pub = self.create_publisher(Clock, "/clock", 10)

        self.odom = {}
        self.low = {}
        self.head = {}
        self.recovery = {}
        self._subscriptions = []
        for name in ROBOTS:
            self.odom[name] = self.create_publisher(Odometer, f"/odometer_state/{name}", 10)
            self.low[name] = self.create_publisher(LowState, f"/low_state/{name}", 10)
            self.head[name] = self.create_publisher(Pose, f"/head_pose/{name}", 10)
            self.recovery[name] = self.create_publisher(
                RawBytesMsg, f"fall_down_recovery_state/{name}", 10
            )
            if self.role in ("all", "command"):
                self._subscriptions.append(
                    self.create_subscription(
                        RpcReqMsg, f"LocoApiTopic/{name}Req", partial(self.on_rpc, name), 10
                    )
                )
                kick_type = RedKick if name.startswith("red_") else BlueKick
                self._subscriptions.append(
                    self.create_subscription(
                        kick_type, f"/kick_ball/{name}", partial(self.on_kick, name), 10
                    )
                )

        self.last_state = None
        self.state_packets_received = 0
        self.rpc_packets_received = 0
        self.kick_packets_received = 0
        self.command_packets_sent = 0
        self.status_packets_sent = 0
        self.malformed_state_packets = 0
        self.malformed_rpc_packets = 0
        self.last_state_wall = None
        self.last_status_wall = -1e9
        self.first_rpc_logged = False
        self.first_state_logged = False

        self.timer = self.create_timer(0.01, self.poll)
        self.diag_timer = self.create_timer(2.0, self.diagnostics)
        self.get_logger().info(
            f"transport={self.transport}; state :{self.state_port}; commands/status -> {self.target}"
        )

    def ensure_relay(self):
        if self.transport == "udp" and self.relay is None:
            return False
        if self.relay is not None:
            return True
        now = time.monotonic()
        if now - self.relay_last_attempt < 1.0:
            return False
        self.relay_last_attempt = now
        try:
            relay = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            relay.settimeout(0.5)
            relay.connect((self.host, self.relay_port))
            relay.setblocking(False)
            self.relay = relay
            self.get_logger().info(f"Connected TCP relay {self.host}:{self.relay_port}")
            return True
        except OSError as error:
            self.get_logger().warning(f"TCP relay unavailable: {error}")
            try:
                relay.close()
            except UnboundLocalError:
                pass
            return False

    def close_relay(self):
        if self.relay is not None:
            try:
                self.relay.close()
            except OSError:
                pass
        self.relay = None
        self.relay_buffer = b""

    def send_frame(self, payload):
        if not self.ensure_relay():
            return False
        try:
            self.relay.sendall((json.dumps(payload, separators=(",", ":")) + "\n").encode())
            return True
        except OSError as error:
            self.get_logger().warning(f"TCP relay send: {error}")
            self.close_relay()
            return False

    def send_datagram(self, payload):
        if self.transport != "udp":
            return self.send_frame(payload)
        try:
            self.tx.sendto(json.dumps(payload, separators=(",", ":")).encode(), self.target)
            return True
        except OSError as error:
            self.get_logger().error(f"UDP send: {error}")
            return False

    def send_command(self, payload):
        packet = {"version": 1, "type": "robot_command", **payload}
        if self.send_datagram(packet):
            self.command_packets_sent += 1

    def send_status(self):
        now = time.monotonic()
        if now - self.last_status_wall < self.status_period:
            return
        self.last_status_wall = now
        packet = {
            "version": 1,
            "type": "bridge_status",
            "action": "world_state_ack",
            "state_rx": self.state_packets_received,
            "state_age": 0.0 if self.last_state_wall is not None else -1.0,
        }
        if self.send_datagram(packet):
            self.status_packets_sent += 1

    @staticmethod
    def finite_float(value, default=0.0):
        try:
            parsed = float(value)
        except (TypeError, ValueError):
            return default, False
        return (parsed, True) if math.isfinite(parsed) else (default, False)

    def on_rpc(self, name, msg):
        self.rpc_packets_received += 1
        if not self.first_rpc_logged:
            self.first_rpc_logged = True
            self.get_logger().info(f"First Brain RPC received from {name}")
        try:
            api = int(json.loads(msg.header or "{}").get("api_id", -1))
            body = json.loads(msg.body or "{}")
        except Exception as error:
            self.malformed_rpc_packets += 1
            self.get_logger().warning(f"{name} malformed RPC: {error}")
            return

        if api == API_MOVE:
            vx, ok_x = self.finite_float(body.get("vx", 0.0))
            vy, ok_y = self.finite_float(body.get("vy", 0.0))
            vyaw, ok_yaw = self.finite_float(body.get("vyaw", 0.0))
            if not (ok_x and ok_y and ok_yaw):
                self.malformed_rpc_packets += 1
                self.get_logger().warning(f"{name} rejected non-finite velocity RPC")
                return
            self.send_command(
                {
                    "robot": name,
                    "action": "move",
                    "vx": vx,
                    "vy": vy,
                    "vyaw": vyaw,
                }
            )
        elif api == API_GET_UP:
            self.send_command({"robot": name, "action": "get_up"})
        elif api == API_ROTATE_HEAD:
            pass

    def on_kick(self, name, msg):
        self.kick_packets_received += 1
        values = [msg.dir, msg.power, msg.x, msg.y, msg.goal_x, msg.goal_y]
        if not all(math.isfinite(float(value)) for value in values):
            self.malformed_rpc_packets += 1
            self.get_logger().warning(f"{name} rejected non-finite kick request")
            return
        self.send_command(
            {
                "robot": name,
                "action": "kick",
                "dir": float(msg.dir),
                "power": float(msg.power),
                "ball_x": float(msg.x),
                "ball_y": float(msg.y),
                "goal_x": float(msg.goal_x),
                "goal_y": float(msg.goal_y),
            }
        )

    def poll(self):
        if self.transport != "udp":
            self.poll_relay()
            return
        newest = None
        while True:
            try:
                raw, _ = self.rx.recvfrom(65535)
            except BlockingIOError:
                break
            try:
                obj = json.loads(raw.decode())
                if obj.get("version") == 1 and obj.get("type") == "world_state":
                    newest = obj
                    self.state_packets_received += 1
                    self.last_state_wall = time.monotonic()
                    if not self.first_state_logged:
                        self.first_state_logged = True
                        self.get_logger().info("First Webots world_state packet received")
            except Exception:
                self.malformed_state_packets += 1
                continue

        if newest is None:
            return
        self.last_state = newest
        self.publish(newest)
        self.send_status()

    def poll_relay(self):
        if not self.ensure_relay():
            return
        newest = None
        while True:
            try:
                chunk = self.relay.recv(65535)
                if not chunk:
                    self.close_relay()
                    return
                self.relay_buffer += chunk
            except BlockingIOError:
                break
            except OSError as error:
                self.get_logger().warning(f"TCP relay receive: {error}")
                self.close_relay()
                return
        while b"\n" in self.relay_buffer:
            raw, self.relay_buffer = self.relay_buffer.split(b"\n", 1)
            if not raw:
                continue
            try:
                obj = json.loads(raw.decode())
                if obj.get("version") == 1 and obj.get("type") == "world_state":
                    if self.role == "command":
                        continue
                    newest = obj
                    self.state_packets_received += 1
                    self.last_state_wall = time.monotonic()
                    if not self.first_state_logged:
                        self.first_state_logged = True
                        self.get_logger().info("First Webots world_state packet received through TCP relay")
            except Exception:
                self.malformed_state_packets += 1
        if newest is not None:
            self.last_state = newest
            self.publish(newest)
            self.send_status()

    def diagnostics(self):
        if self.last_state_wall is None:
            state_status = "NO WEBOTS STATE"
        else:
            age = time.monotonic() - self.last_state_wall
            state_status = f"state age={age:.2f}s"
        self.get_logger().info(
            f"[DIAG] {state_status}; state_rx={self.state_packets_received}; "
            f"state_ack_tx={self.status_packets_sent}; brain_rpc={self.rpc_packets_received}; "
            f"kicks={self.kick_packets_received}; command_tx={self.command_packets_sent}; "
            f"bad_state={self.malformed_state_packets}; bad_rpc={self.malformed_rpc_packets}; "
            f"target={self.target}"
        )

    @staticmethod
    def ros_time(seconds):
        seconds_int = int(max(0.0, seconds))
        return Time(
            sec=seconds_int,
            nanosec=int((seconds - seconds_int) * 1e9),
        )

    def publish(self, state):
        clock = Clock()
        clock.clock = self.ros_time(float(state.get("sim_time", 0.0)))
        self.clock_pub.publish(clock)

        text = String()
        text.data = json.dumps(state, separators=(",", ":"))
        self.world_pub.publish(text)

        for name, data in state["robots"].items():
            x, y, theta = team_pose(
                name,
                float(data["x"]),
                float(data["y"]),
                float(data["theta"]),
            )
            odometer = Odometer()
            odometer.x = x
            odometer.y = y
            odometer.theta = theta
            self.odom[name].publish(odometer)

            low_state = LowState()
            for _ in range(2):
                motor_state = MotorState()
                motor_state.q = 0.0
                low_state.motor_state_serial.append(motor_state)
            self.low[name].publish(low_state)

            pose = Pose()
            pose.orientation.w = 1.0
            self.head[name].publish(pose)

            recovery = RawBytesMsg()
            recovery.msg = [
                int(data.get("recovery_state", 0)),
                1 if data.get("recovery_available", True) else 0,
                0,
            ]
            self.recovery[name].publish(recovery)


def main(args=None):
    rclpy.init(args=args)
    node = Bridge()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == "__main__":
    main()
