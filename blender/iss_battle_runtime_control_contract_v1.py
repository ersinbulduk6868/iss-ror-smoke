from __future__ import annotations

from math import hypot
from typing import Iterable

COLLISION_PROXY_PROXIMITY_MODEL = "G04_RIGID_BODY_OBB_SAT_PROXIMITY_V1"
TACTICAL_AUTONOMY_OWNERSHIP_MODEL = "G04_TACTICAL_AUTONOMY_RECOVERY_OWNERSHIP_V1"

_RECOVERY_TACTICAL_MODES = {"OPEN_DISTANCE", "BREAK_CONTACT", "REPOSITION"}
_FORWARD_TACTICAL_MODES = {"ENGAGE", "COUNTER", "FLANK"}


def _v2(value: Iterable[float]) -> tuple[float, float]:
    rows = tuple(float(x) for x in value)
    if len(rows) != 2:
        raise ValueError("G04_VECTOR2_REQUIRED")
    return rows[0], rows[1]


def _unit2(value: Iterable[float]) -> tuple[float, float]:
    x, y = _v2(value)
    length = hypot(x, y)
    if length <= 1.0e-12:
        raise ValueError("G04_AXIS_DEGENERATE")
    return x / length, y / length


def _dot2(a: tuple[float, float], b: tuple[float, float]) -> float:
    return a[0] * b[0] + a[1] * b[1]


def obb_signed_separation_2d(
    *,
    center_delta_xy: Iterable[float],
    actor_x_axis_xy: Iterable[float],
    actor_y_axis_xy: Iterable[float],
    target_x_axis_xy: Iterable[float],
    target_y_axis_xy: Iterable[float],
    actor_half_extents_xy: Iterable[float],
    target_half_extents_xy: Iterable[float],
) -> float:
    """Return SAT signed separation between two horizontal rigid-body OBBs.

    Positive means at least one separating axis exists. Zero is touching. Negative
    means the horizontal projections overlap on every SAT axis. This is only a
    controller-handoff proximity metric; it never declares G05 contact success.
    """
    delta = _v2(center_delta_xy)
    ax = _unit2(actor_x_axis_xy)
    ay = _unit2(actor_y_axis_xy)
    bx = _unit2(target_x_axis_xy)
    by = _unit2(target_y_axis_xy)
    ahx, ahy = _v2(actor_half_extents_xy)
    bhx, bhy = _v2(target_half_extents_xy)
    ahx, ahy, bhx, bhy = map(abs, (ahx, ahy, bhx, bhy))

    gaps: list[float] = []
    for axis in (ax, ay, bx, by):
        center_distance = abs(_dot2(delta, axis))
        actor_radius = ahx * abs(_dot2(ax, axis)) + ahy * abs(_dot2(ay, axis))
        target_radius = bhx * abs(_dot2(bx, axis)) + bhy * abs(_dot2(by, axis))
        gaps.append(center_distance - actor_radius - target_radius)
    return max(gaps)


def effective_collision_proxy_gap(radial_gap_m: float, obb_separation_m: float) -> float:
    """Conservative proximity: any valid separating direction keeps the pair apart."""
    return max(float(radial_gap_m), float(obb_separation_m))


def should_clear_stale_autonomy_recovery(
    *,
    previous_tactical_mode: str | None,
    current_tactical_mode: str,
    tactical_transition: bool,
    autonomy_mode: str,
    speed_intent: str,
) -> bool:
    previous = str(previous_tactical_mode or "").upper()
    current = str(current_tactical_mode or "").upper()
    controller = str(autonomy_mode or "").upper()
    intent = str(speed_intent or "").upper()
    return bool(
        tactical_transition
        and previous in _RECOVERY_TACTICAL_MODES
        and current in _FORWARD_TACTICAL_MODES
        and controller.startswith("RECOVER_")
        and intent == "ACCELERATE"
    )
