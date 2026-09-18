from __future__ import annotations

from dataclasses import dataclass

PRECONTACT_CORRIDOR_MODEL = "G04_LIVE_PRECONTACT_CORRIDOR_V1"
ALLOW_CONTACT = "ALLOW_CONTACT"
DEFER_TO_BASE = "DEFER_TO_BASE"
HOLD_STANDOFF = "HOLD_STANDOFF"
REOPEN_DISTANCE = "REOPEN_DISTANCE"


@dataclass(slots=True, frozen=True)
class PrecontactCorridorDecision:
    action: str
    desired_surface_gap_m: float
    runway_armed_after: bool


def decide_precontact_corridor(
    *,
    requires_contact: bool,
    runway_armed: bool,
    contact_commit_ready: bool,
    surface_gap_m: float,
    runway_required_m: float,
) -> PrecontactCorridorDecision:
    """Continuously revalidate the generic pre-contact movement corridor.

    The engagement runway is geometry/capability state, not a one-way permission
    latch. If live commit readiness disappears before contact, the actor must not
    keep driving a contact-directed goal into the target. At/above the existing
    runway distance it holds/repositions on that live stand-off surface. If the
    runway has already collapsed, it reopens distance using the existing generic
    OPEN_DISTANCE policy. No asset identity, G05 threshold, desired impact speed,
    collision frame or fixture coordinate enters this decision.
    """
    runway = max(0.0, float(runway_required_m))
    if not requires_contact:
        return PrecontactCorridorDecision(DEFER_TO_BASE, runway, bool(runway_armed))
    if contact_commit_ready:
        return PrecontactCorridorDecision(ALLOW_CONTACT, runway, bool(runway_armed))
    if not runway_armed:
        return PrecontactCorridorDecision(DEFER_TO_BASE, runway, False)
    if float(surface_gap_m) < runway:
        return PrecontactCorridorDecision(REOPEN_DISTANCE, runway, False)
    return PrecontactCorridorDecision(HOLD_STANDOFF, runway, True)
