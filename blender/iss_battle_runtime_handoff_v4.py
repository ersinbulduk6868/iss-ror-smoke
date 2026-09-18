from __future__ import annotations

from collections.abc import Mapping, Sequence
import math
from typing import Any

SEMANTIC_SURFACE_TRANSACTION_MODEL = "LIVE_PAIR_SURFACE_SEMANTIC_HANDOFF_TRANSACTION_V1"


def _xyz(value: Any) -> tuple[float, float, float]:
    return (float(value[0]), float(value[1]), float(value[2]))


def select_semantic_zone_for_local_surface(
    surface_local: Sequence[float],
    zones: Mapping[str, Sequence[float]],
    visual_offset: Sequence[float] = (0.0, 0.0, 0.0),
) -> tuple[str, float]:
    """Select the asset semantic zone nearest a live pair-contact surface point.

    This helper is intentionally pure and asset-identity agnostic. The surface
    point is derived at runtime from current pair geometry; Story does not supply
    it. No tolerance, collision threshold, trajectory, world coordinate, impact
    speed or impact energy is accepted by this API.
    """
    sx, sy, sz = _xyz(surface_local)
    ox, oy, oz = _xyz(visual_offset)
    candidates: list[tuple[float, str]] = []
    for raw_name, raw_point in zones.items():
        name = str(raw_name)
        if not name:
            continue
        zx, zy, zz = _xyz(raw_point)
        dx = sx - (zx + ox)
        dy = sy - (zy + oy)
        dz = sz - (zz + oz)
        distance = math.sqrt(dx * dx + dy * dy + dz * dz)
        if math.isfinite(distance):
            candidates.append((float(distance), name))
    if not candidates:
        raise ValueError("HANDOFF_SEMANTIC_SURFACE_ZONE_SET_EMPTY")
    candidates.sort(key=lambda row: (row[0], row[1]))
    distance, name = candidates[0]
    return name, float(distance)
