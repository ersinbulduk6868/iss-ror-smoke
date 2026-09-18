from __future__ import annotations

import math

from blender.iss_battle_runtime_contact_truth import PairwiseSolverResponseOracle

G05_HANDOFF_READINESS_MODEL = "G04_G05_PRE_HANDOFF_READINESS_V1"


def required_normal_closing_speed_mps() -> float:
    """Return the authoritative locked G05 solver-admission closing-speed floor.

    C485 does not duplicate or tune this value.  G05 remains the single source of
    truth; G04 only decides whether it is physically meaningful to relinquish motor
    authority to that unchanged downstream oracle.
    """
    return float(PairwiseSolverResponseOracle.MIN_CLOSING_SPEED_MPS)


def handoff_readiness_recovery_required(
    *,
    contact_handoff_requested: bool,
    live_normal_closing_speed_mps: float,
) -> bool:
    if not bool(contact_handoff_requested):
        return False
    closing = float(live_normal_closing_speed_mps)
    if not math.isfinite(closing):
        return True
    return closing < required_normal_closing_speed_mps()
