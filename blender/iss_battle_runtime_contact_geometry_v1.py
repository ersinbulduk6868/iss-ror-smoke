from __future__ import annotations

import math
from typing import Iterable

COLLIDER_GAP_MODEL = "G04_CONSERVATIVE_BOX_SAT_CONTACT_GAP_V1"

Vec2 = tuple[float, float]


def _vec2(value: Iterable[float]) -> Vec2:
    rows = tuple(float(x) for x in value)
    if len(rows) != 2:
        raise ValueError("CONTACT_GEOMETRY_VEC2_REQUIRED")
    return rows[0], rows[1]


def _dot(a: Vec2, b: Vec2) -> float:
    return a[0] * b[0] + a[1] * b[1]


def _unit(value: Iterable[float]) -> Vec2:
    x, y = _vec2(value)
    length = math.hypot(x, y)
    if length <= 1.0e-12:
        raise ValueError("CONTACT_GEOMETRY_AXIS_DEGENERATE")
    return x / length, y / length


def _projection_radius(
    half_extents: Iterable[float],
    axis_x: Iterable[float],
    axis_y: Iterable[float],
    test_axis: Iterable[float],
) -> float:
    hx, hy = _vec2(half_extents)
    x_axis = _unit(axis_x)
    y_axis = _unit(axis_y)
    axis = _unit(test_axis)
    return abs(float(hx)) * abs(_dot(x_axis, axis)) + abs(float(hy)) * abs(_dot(y_axis, axis))


def obb_signed_separation_2d(
    center_a: Iterable[float],
    axis_a_x: Iterable[float],
    axis_a_y: Iterable[float],
    half_a: Iterable[float],
    center_b: Iterable[float],
    axis_b_x: Iterable[float],
    axis_b_y: Iterable[float],
    half_b: Iterable[float],
) -> float:
    """Return the 2D SAT signed separation for two rigid BOX footprints.

    Positive means at least one separating axis remains. Zero is touching.
    Negative means all SAT axes overlap. This is a geometry observation only;
    it does not declare G05 contact or solver success.
    """
    ca = _vec2(center_a)
    cb = _vec2(center_b)
    a_x = _unit(axis_a_x)
    a_y = _unit(axis_a_y)
    b_x = _unit(axis_b_x)
    b_y = _unit(axis_b_y)
    delta = (cb[0] - ca[0], cb[1] - ca[1])

    gaps: list[float] = []
    for axis in (a_x, a_y, b_x, b_y):
        center_projection = abs(_dot(delta, axis))
        radius_a = _projection_radius(half_a, a_x, a_y, axis)
        radius_b = _projection_radius(half_b, b_x, b_y, axis)
        gaps.append(center_projection - radius_a - radius_b)
    return max(gaps)


def conservative_contact_gap(radial_gap_m: float, sat_gap_m: float) -> float:
    """Never report contact proximity closer than either geometry model allows."""
    return max(float(radial_gap_m), float(sat_gap_m))
