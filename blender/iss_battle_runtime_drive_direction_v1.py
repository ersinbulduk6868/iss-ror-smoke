from __future__ import annotations

CANONICAL_DRIVE_DIRECTION_MODEL = "GENERIC_CANONICAL_DRIVE_DIRECTION_V1"


def motor_inputs_for_canonical_linear_commands(
    left_mps: float,
    right_mps: float,
) -> tuple[float, float]:
    """Map canonical vehicle linear commands to Blender wheel-motor inputs.

    The runtime defines vehicle forward as chassis local +X. Blender's current
    wheel-axis convention realizes a positive angular motor target as chassis
    motion along local -X. Therefore the motor input sign is the inverse of the
    canonical linear command sign. This mapping is purely coordinate-convention
    reconciliation: it contains no asset identity, mass branch, trajectory,
    collision target, impact speed, or damage threshold.
    """
    return -float(left_mps), -float(right_mps)
