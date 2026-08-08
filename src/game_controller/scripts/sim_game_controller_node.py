#!/usr/bin/env python3
"""Simulation-side GameController.

The Webots gateway reports raw match/restart facts in /webots/world_state.
This node is the only publisher of /robocup/game_controller in simulation mode.
Brains therefore leave a set play only after GameController publishes set_play=0.
"""
from __future__ import annotations

import json
import math
from typing import Any, Dict, Tuple

import rclpy
from game_controller_interface.msg import GameControlData
from rclpy.node import Node
from std_msgs.msg import String


class SimGameController(Node):
    def __init__(self) -> None:
        super().__init__("sim_game_controller")
        self.declare_parameter("world_state_topic", "/webots/world_state")
        self.declare_parameter("ball_move_threshold", 0.35)
        self.declare_parameter("set_play_timeout", 12.0)
        self.declare_parameter("timeout_fallback_enabled", True)

        topic = str(self.get_parameter("world_state_topic").value)
        self.ball_move_threshold = float(self.get_parameter("ball_move_threshold").value)
        self.set_play_timeout = float(self.get_parameter("set_play_timeout").value)
        self.timeout_fallback_enabled = bool(
            self.get_parameter("timeout_fallback_enabled").value
        )

        self.publisher = self.create_publisher(
            GameControlData, "/robocup/game_controller", 10
        )
        self.subscription = self.create_subscription(String, topic, self.on_world_state, 20)

        self.packet_number = 0
        self.active = False
        self.active_restart_id = -1
        self.completed_restart_id = -1
        self.active_set_play = 0
        self.active_stopped = 0
        self.active_kicking_team = 29
        self.restart_ball: Tuple[float, float] = (0.0, 0.0)
        self.restart_started_at = 0.0

        self.get_logger().info(
            "Simulation GameController active: world_state -> /robocup/game_controller"
        )

    @staticmethod
    def as_int(value: Any, default: int = 0) -> int:
        try:
            return int(value)
        except (TypeError, ValueError):
            return default

    @staticmethod
    def as_float(value: Any, default: float = 0.0) -> float:
        try:
            parsed = float(value)
        except (TypeError, ValueError):
            return default
        return parsed if math.isfinite(parsed) else default

    def begin_restart(self, state: Dict[str, Any], restart: Dict[str, Any]) -> None:
        self.active = True
        self.active_restart_id = self.as_int(restart.get("id"), 0)
        self.active_set_play = self.as_int(
            restart.get("set_play", state.get("set_play", 0)), 0
        )
        self.active_stopped = self.as_int(
            restart.get("stopped", state.get("stopped", 1)), 1
        )
        self.active_kicking_team = self.as_int(
            restart.get("kicking_team", state.get("kicking_team", 29)), 29
        )
        ball = state.get("ball", {})
        self.restart_ball = (
            self.as_float(restart.get("ball_x", ball.get("x", 0.0))),
            self.as_float(restart.get("ball_y", ball.get("y", 0.0))),
        )
        self.restart_started_at = self.as_float(
            restart.get("started_at", state.get("sim_time", 0.0)), 0.0
        )
        event = str(restart.get("event", state.get("last_event", "restart")))
        self.get_logger().info(
            f"[SET_PLAY] start id={self.active_restart_id} "
            f"type={self.active_set_play} team={self.active_kicking_team} event={event}"
        )

    def finish_restart(self, reason: str) -> None:
        if not self.active:
            return
        finished_id = self.active_restart_id
        finished_type = self.active_set_play
        self.active = False
        self.completed_restart_id = finished_id
        self.active_set_play = 0
        self.active_stopped = 0
        self.get_logger().info(
            f"[SET_PLAY] end id={finished_id} type={finished_type} reason={reason}; "
            "publishing set_play=0"
        )

    def update_restart_state(self, state: Dict[str, Any]) -> None:
        restart = state.get("restart")
        if not isinstance(restart, dict):
            # Compatibility fallback for older gateways.
            restart = {
                "id": 0,
                "active": bool(self.as_int(state.get("set_play", 0))),
                "set_play": self.as_int(state.get("set_play", 0)),
                "stopped": self.as_int(state.get("stopped", 0)),
                "kicking_team": self.as_int(state.get("kicking_team", 29)),
                "started_at": self.as_float(state.get("sim_time", 0.0)),
                "event": state.get("last_event", "legacy restart"),
            }

        restart_id = self.as_int(restart.get("id"), 0)
        requested_set_play = self.as_int(
            restart.get("set_play", state.get("set_play", 0)), 0
        )
        requested_active = bool(restart.get("active", requested_set_play != 0))

        if (
            requested_active
            and requested_set_play != 0
            and restart_id != self.active_restart_id
            and restart_id != self.completed_restart_id
        ):
            self.begin_restart(state, restart)

        if self.active and not requested_active and requested_set_play == 0:
            self.finish_restart("referee source cleared")

        if not self.active:
            return

        # The gateway only reports the referee's resume/freeze command.
        # The GameController owns the published set_play lifecycle.
        self.active_stopped = self.as_int(
            restart.get("stopped", state.get("stopped", self.active_stopped)),
            self.active_stopped,
        )

        if self.active_stopped != 0:
            return

        ball = state.get("ball", {})
        ball_x = self.as_float(ball.get("x", self.restart_ball[0]))
        ball_y = self.as_float(ball.get("y", self.restart_ball[1]))
        moved = math.hypot(ball_x - self.restart_ball[0], ball_y - self.restart_ball[1])
        if moved >= self.ball_move_threshold:
            self.finish_restart(f"ball moved {moved:.2f}m")
            return

        if self.timeout_fallback_enabled:
            sim_time = self.as_float(state.get("sim_time", self.restart_started_at))
            elapsed = sim_time - self.restart_started_at
            if elapsed >= self.set_play_timeout:
                self.finish_restart(f"timeout {elapsed:.1f}s")

    def build_message(self, state: Dict[str, Any]) -> GameControlData:
        message = GameControlData()
        message.header = list(b"RGme")
        message.version = 20
        self.packet_number = (self.packet_number + 1) % 256
        message.packet_number = self.packet_number
        message.players_per_team = 5
        message.competition_type = 0
        message.game_phase = 0
        message.state = self.as_int(state.get("gc_state", 0))
        message.set_play = self.active_set_play if self.active else 0
        message.stopped = self.active_stopped if self.active else 0
        message.kicking_team = (
            self.active_kicking_team
            if self.active
            else self.as_int(state.get("kicking_team", 29), 29)
        )
        message.first_half = 1
        message.secs_remaining = max(
            0, 300 - int(self.as_float(state.get("match_time", 0.0)))
        )
        message.secondary_time = 0

        score = state.get("score", {})
        for index, (team, team_id) in enumerate((("red", 29), ("blue", 30))):
            team_msg = message.teams[index]
            team_msg.team_number = team_id
            team_msg.goalkeeper = 1
            team_msg.score = self.as_int(score.get(team, 0))
            team_msg.message_budget = 1200
            for player in team_msg.players:
                player.penalty = 0
                player.secs_till_unpenalised = 0
                player.warnings = 0
                player.cautions = 0
        return message

    def on_world_state(self, message: String) -> None:
        try:
            state = json.loads(message.data)
        except (json.JSONDecodeError, TypeError) as error:
            self.get_logger().warning(f"Invalid /webots/world_state JSON: {error}")
            return
        if not isinstance(state, dict):
            return

        self.update_restart_state(state)
        self.publisher.publish(self.build_message(state))


def main(args=None) -> None:
    rclpy.init(args=args)
    node = SimGameController()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == "__main__":
    main()
