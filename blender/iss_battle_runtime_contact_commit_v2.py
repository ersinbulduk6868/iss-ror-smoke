from __future__ import annotations

import math
from dataclasses import dataclass

CONTACT_COMMIT_MODEL = "G04_GENERIC_REALIZED_CONTACT_COMMIT_V2"

# These are the already-established generic ENGAGE readiness bounds from
# GenericBattleTacticalPlanner V5. C485 does not introduce fixture tuning; it
# applies the same live-state contract to every contact-capable engagement mode.
CONTACT_COMMIT_MAX_HEADING_ERROR_RAD = 0.70
CONTACT_COMMIT_MAX_CONTENTION = 0.80

# This is the already-established capability/scale-derived engagement floor from
# ClosedLoopGoalController V1. It is a motion-realization floor, not a G05
# contact/damage threshold and not a desired impact speed.
CAPABILITY_ENGAGEMENT_FACTOR = 0.72


def _clamp(value: float, lo: float, hi: float) -> float:
    return max(float(lo), min(float(hi), float(value)))


def live_contact_commit_ready(
    *,
    requires_contact: bool,
    engagement_runway_armed: bool,
    heading_error_rad: float,
    contention: float,
) -> bool:
    """Return whether live state is ready to enter a physical contact attempt.

    The rule is intentionally mode- and asset-independent. Story phase may select
    ENGAGE or COUNTER, but neither mode may bypass the same live geometry and
    contention readiness contract.
    """
    return bool(
        requires_contact
        and engagement_runway_armed
        and abs(float(heading_error_rad)) <= CONTACT_COMMIT_MAX_HEADING_ERROR_RAD
        and float(contention) < CONTACT_COMMIT_MAX_CONTENTION
    )


def capability_motion_realization_floor_mps(
    *,
    max_speed_mps: float,
    acceleration_mps2: float,
    characteristic_length_m: float,
    drive_efficiency: float,
) -> float:
    """Return the generic capability-derived speed that must be physically realized.

    This mirrors the existing G04 contact engagement floor, then caps it by the
    actor's current usable forward capability. It depends only on ActorProfile/
    live capability state. It imports no G05 contact oracle threshold, target
    toughness, asset identity, collision frame, or desired impact energy.
    """
    efficiency = _clamp(drive_efficiency, 0.0, 1.0)
    usable_max = max(0.0, float(max_speed_mps)) * efficiency
    capability_floor = math.sqrt(
        max(0.1, float(acceleration_mps2))
        * max(0.25, float(characteristic_length_m))
    ) * CAPABILITY_ENGAGEMENT_FACTOR
    return min(usable_max, capability_floor)


@dataclass(slots=True, frozen=True)
class RealizedHandoffReadiness:
    ready: bool
    capability_floor_mps: float
    realized_forward_speed_mps: float
    realized_closing_speed_mps: float


def realized_contact_handoff_readiness(
    *,
    max_speed_mps: float,
    acceleration_mps2: float,
    characteristic_length_m: float,
    drive_efficiency: float,
    realized_forward_speed_mps: float,
    realized_closing_speed_mps: float,
) -> RealizedHandoffReadiness:
    """Require commanded approach to exist in the physical world before handoff.

    A controller command is intent, not evidence of realized chassis motion.
    Solver authority may be handed off only when the actor's live forward motion
    and live pairwise closing motion both realize the same capability-derived G04
    engagement floor. This never decides whether contact is valid; G05 remains the
    sole native contact authority after G04 releases motor authority.
    """
    floor = capability_motion_realization_floor_mps(
        max_speed_mps=max_speed_mps,
        acceleration_mps2=acceleration_mps2,
        characteristic_length_m=characteristic_length_m,
        drive_efficiency=drive_efficiency,
    )
    forward = float(realized_forward_speed_mps)
    closing = float(realized_closing_speed_mps)
    ready = bool(floor > 0.0 and forward >= floor and closing >= floor)
    return RealizedHandoffReadiness(
        ready=ready,
        capability_floor_mps=floor,
        realized_forward_speed_mps=forward,
        realized_closing_speed_mps=closing,
    )
