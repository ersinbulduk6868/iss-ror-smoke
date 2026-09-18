from __future__ import annotations

import math
from typing import Iterable

PURSUIT_MODEL = "G04_LIVE_PAIR_CENTER_INTERCEPT_GOAL_V1"


def _v2(value: Iterable[float]) -> tuple[float, float]:
    rows = tuple(float(x) for x in value)
    if len(rows) < 2:
        raise ValueError("PURSUIT_VECTOR_REQUIRES_XY")
    return rows[0], rows[1]


def _positive_intercept_time(
    relative_xy: Iterable[float],
    target_velocity_xy: Iterable[float],
    pursuer_speed_mps: float,
) -> float | None:
    rx, ry = _v2(relative_xy)
    vx, vy = _v2(target_velocity_xy)
    speed = max(0.0, float(pursuer_speed_mps))
    if speed <= 1.0e-6:
        return None

    # |r + v*t| == pursuer_speed*t.  This is a live interception estimate,
    # not a cached path or prescribed collision time.
    a = vx * vx + vy * vy - speed * speed
    b = 2.0 * (rx * vx + ry * vy)
    c = rx * rx + ry * ry

    if c <= 1.0e-12:
        return 0.0
    if abs(a) <= 1.0e-9:
        if abs(b) <= 1.0e-9:
            return None
        t = -c / b
        return t if t > 0.0 else None

    disc = b * b - 4.0 * a * c
    if disc < 0.0:
        return None
    root = math.sqrt(max(0.0, disc))
    roots = [t for t in ((-b - root) / (2.0 * a), (-b + root) / (2.0 * a)) if t > 0.0]
    return min(roots) if roots else None


def capability_bounded_lead_seconds(
    *,
    relative_xy: Iterable[float],
    target_velocity_xy: Iterable[float],
    pursuer_speed_mps: float,
    max_yaw_rate_rad_s: float,
    characteristic_length_m: float,
) -> float:
    """Return a short, capability-derived live lead horizon.

    The horizon is recomputed every frame.  It never encodes asset identity,
    world coordinates, a collision frame, impact speed, impact energy or a
    precomputed trajectory.
    """
    rx, ry = _v2(relative_xy)
    vx, vy = _v2(target_velocity_xy)
    distance = math.hypot(rx, ry)
    target_speed = math.hypot(vx, vy)
    pursuer_speed = max(0.5, float(pursuer_speed_mps))
    yaw_rate = max(0.15, float(max_yaw_rate_rad_s))
    characteristic = max(0.25, float(characteristic_length_m))

    intercept = _positive_intercept_time((rx, ry), (vx, vy), pursuer_speed)
    if intercept is None:
        intercept = distance / max(0.5, pursuer_speed + 0.35 * target_speed)

    # Bound look-ahead by the actor's own scale and turning capability so a
    # slow-turning/large actor does not chase a far future point and oscillate.
    scale_time = characteristic / pursuer_speed
    turn_time = 1.0 / yaw_rate
    capability_cap = max(0.10, min(1.25, 0.45 * scale_time + 0.45 * turn_time))
    if target_speed <= 0.05:
        return 0.0
    return max(0.0, min(float(intercept), capability_cap))


def predicted_target_xy(
    *,
    target_xy: Iterable[float],
    target_velocity_xy: Iterable[float],
    lead_seconds: float,
) -> tuple[float, float]:
    tx, ty = _v2(target_xy)
    vx, vy = _v2(target_velocity_xy)
    lead = max(0.0, float(lead_seconds))
    return tx + vx * lead, ty + vy * lead
