"""Small 2-D geometry and quaternion helpers."""

from __future__ import annotations

import math


def clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def wrap_angle(angle: float) -> float:
    while angle > math.pi:
        angle -= 2.0 * math.pi
    while angle < -math.pi:
        angle += 2.0 * math.pi
    return angle


def distance(a: tuple[float, float], b: tuple[float, float]) -> float:
    return math.hypot(a[0] - b[0], a[1] - b[1])


def world_to_local(dx: float, dy: float, yaw: float) -> tuple[float, float]:
    c = math.cos(yaw)
    s = math.sin(yaw)
    return c * dx + s * dy, -s * dx + c * dy


def local_to_world(vx: float, vy: float, yaw: float) -> tuple[float, float]:
    c = math.cos(yaw)
    s = math.sin(yaw)
    return c * vx - s * vy, s * vx + c * vy


def quat_multiply(a: tuple[float, float, float, float], b: tuple[float, float, float, float]) -> tuple[float, float, float, float]:
    aw, ax, ay, az = a
    bw, bx, by, bz = b
    return (
        aw * bw - ax * bx - ay * by - az * bz,
        aw * bx + ax * bw + ay * bz - az * by,
        aw * by - ax * bz + ay * bw + az * bx,
        aw * bz + ax * by - ay * bx + az * bw,
    )


def axis_angle_quat(axis: tuple[float, float, float], angle: float) -> tuple[float, float, float, float]:
    norm = math.sqrt(sum(v * v for v in axis))
    if norm < 1e-9 or abs(angle) < 1e-9:
        return (1.0, 0.0, 0.0, 0.0)
    x, y, z = (v / norm for v in axis)
    half = angle * 0.5
    s = math.sin(half)
    return (math.cos(half), x * s, y * s, z * s)


def quat_to_axis_angle(q: tuple[float, float, float, float]) -> list[float]:
    w, x, y, z = q
    norm = math.sqrt(w * w + x * x + y * y + z * z)
    if norm < 1e-12:
        return [0.0, 0.0, 1.0, 0.0]
    w, x, y, z = w / norm, x / norm, y / norm, z / norm
    w = clamp(w, -1.0, 1.0)
    angle = 2.0 * math.acos(w)
    s = math.sqrt(max(0.0, 1.0 - w * w))
    if s < 1e-7:
        return [0.0, 0.0, 1.0, 0.0]
    return [x / s, y / s, z / s, angle]


def yaw_tilt_rotation(yaw: float, pitch: float = 0.0, roll: float = 0.0) -> list[float]:
    # Body local tilt followed by world yaw.
    q_yaw = axis_angle_quat((0.0, 0.0, 1.0), yaw)
    q_pitch = axis_angle_quat((0.0, 1.0, 0.0), pitch)
    q_roll = axis_angle_quat((1.0, 0.0, 0.0), roll)
    return quat_to_axis_angle(quat_multiply(q_yaw, quat_multiply(q_pitch, q_roll)))
