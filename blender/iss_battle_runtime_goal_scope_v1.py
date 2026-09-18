from __future__ import annotations

import math
from typing import Any, Iterable

GOAL_SCOPE_MODEL = "G04_AUTONOMY_GOAL_SCOPE_V1"
SAT_GAP_MODEL = "G04_ORIENTED_CHASSIS_SAT_GAP_V1"


def goal_scope_signature(requires_contact: bool, speed_intent: str) -> tuple[bool, str]:
    return bool(requires_contact), str(speed_intent or "").upper()


def rebase_autonomy_progress(memory: Any, obs: Any) -> dict[str, object]:
    """Rebase controller-local progress to the current tactical goal.

    Battle/event/contact/damage history is deliberately not reset. Only progress
    and obsolete recovery state belonging to a previous goal scope are rebased.
    """
    before = {
        "mode": str(getattr(memory, "mode", "")),
        "attempt": int(getattr(memory, "attempt", 0)),
        "replans": int(getattr(memory, "replans", 0)),
        "lastContactCount": int(getattr(memory, "last_contact_count", 0)),
        "lastDamageCount": int(getattr(memory, "last_damage_count", 0)),
    }
    memory.mode = "TRACK"
    memory.reason = "GOAL_SCOPE_REBASED"
    memory.best_distance_m = float(obs.distance_m)
    memory.last_distance_m = float(obs.distance_m)
    memory.last_surface_gap_m = float(obs.surface_gap_m)
    memory.last_progress_frame = int(obs.frame)
    near_threshold = max(0.18, float(obs.characteristic_length_m) * 0.20)
    memory.near_seen = bool(obs.requires_contact and float(obs.surface_gap_m) <= near_threshold)
    memory.last_command_speed_mps = 0.0
    memory.recovery_reverse_until = 0
    memory.recovery_turn_until = 0
    after = {
        "mode": str(getattr(memory, "mode", "")),
        "attempt": int(getattr(memory, "attempt", 0)),
        "replans": int(getattr(memory, "replans", 0)),
        "lastContactCount": int(getattr(memory, "last_contact_count", 0)),
        "lastDamageCount": int(getattr(memory, "last_damage_count", 0)),
    }
    if (
        before["attempt"] != after["attempt"]
        or before["replans"] != after["replans"]
        or before["lastContactCount"] != after["lastContactCount"]
        or before["lastDamageCount"] != after["lastDamageCount"]
    ):
        raise RuntimeError("GOAL_SCOPE_REBASE_HISTORY_MUTATION")
    return {"before": before, "after": after}


def _dot2(a: tuple[float, float], b: tuple[float, float]) -> float:
    return float(a[0]) * float(b[0]) + float(a[1]) * float(b[1])


def _unit2(v: tuple[float, float]) -> tuple[float, float]:
    length = math.hypot(float(v[0]), float(v[1]))
    if length <= 1.0e-12:
        raise ValueError("SAT_AXIS_DEGENERATE")
    return float(v[0]) / length, float(v[1]) / length


def oriented_box_separation_2d(
    center_delta_xy: tuple[float, float],
    a_axis_x_xy: tuple[float, float],
    a_axis_y_xy: tuple[float, float],
    a_half_xy: tuple[float, float],
    b_axis_x_xy: tuple[float, float],
    b_axis_y_xy: tuple[float, float],
    b_half_xy: tuple[float, float],
) -> float:
    """Return SAT separation: positive=separated, <=0=overlapping.

    The value is the largest separating-axis gap over both boxes' planar axes.
    It is pure geometry and does not declare G05 contact authority.
    """
    ax = _unit2(a_axis_x_xy)
    ay = _unit2(a_axis_y_xy)
    bx = _unit2(b_axis_x_xy)
    by = _unit2(b_axis_y_xy)
    half_a = (max(0.0, float(a_half_xy[0])), max(0.0, float(a_half_xy[1])))
    half_b = (max(0.0, float(b_half_xy[0])), max(0.0, float(b_half_xy[1])))
    delta = (float(center_delta_xy[0]), float(center_delta_xy[1]))

    gaps: list[float] = []
    for axis in (ax, ay, bx, by):
        center_distance = abs(_dot2(delta, axis))
        radius_a = half_a[0] * abs(_dot2(ax, axis)) + half_a[1] * abs(_dot2(ay, axis))
        radius_b = half_b[0] * abs(_dot2(bx, axis)) + half_b[1] * abs(_dot2(by, axis))
        gaps.append(center_distance - radius_a - radius_b)
    return max(gaps)


def conservative_physical_gap(base_support_gap_m: float, sat_separation_m: float) -> float:
    """Use the more-separated geometry estimate for G04 control/handoff."""
    return max(float(base_support_gap_m), float(sat_separation_m))
