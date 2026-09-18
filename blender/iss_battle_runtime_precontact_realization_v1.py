from __future__ import annotations

from dataclasses import dataclass

PRECONTACT_REALIZATION_MODEL = "G04_EVENT_SCOPED_PRECONTACT_REALIZATION_WINDOW_V1"


@dataclass(slots=True, frozen=True)
class PrecontactRealizationSample:
    frame: int
    event_id: str
    actor_id: str
    target_id: str
    forward_speed_mps: float
    closing_speed_mps: float
    capability_floor_mps: float
    effective_gap_m: float
    handoff_gap_m: float

    @property
    def transaction_key(self) -> tuple[str, str, str]:
        return (self.event_id, self.actor_id, self.target_id)


def precontact_sample_eligible(
    *,
    contact_approach_active: bool,
    recovery_active: bool,
    forward_speed_mps: float,
    closing_speed_mps: float,
    capability_floor_mps: float,
    effective_gap_m: float,
    handoff_gap_m: float,
) -> bool:
    """Return whether this frame is valid pre-handoff realized-motion evidence.

    C474 intentionally masks ``requires_contact`` while OBB handoff eligibility is
    still deferred.  Therefore this contract uses the event-scoped APPROACH phase
    plus the live collision-proxy gap rather than the controller's masked flag.
    The sample must come from outside the existing handoff region and must already
    realize the unchanged capability-derived G04 motion floor.
    """
    floor = float(capability_floor_mps)
    return bool(
        contact_approach_active
        and not recovery_active
        and floor > 0.0
        and float(forward_speed_mps) >= floor
        and float(closing_speed_mps) >= floor
        and float(effective_gap_m) > float(handoff_gap_m)
    )


def previous_frame_sample_valid_for_handoff(
    sample: PrecontactRealizationSample | None,
    *,
    transaction_key: tuple[str, str, str],
    decision_frame: int,
    current_capability_floor_mps: float,
    current_closing_speed_mps: float,
    controller_handoff_requested: bool,
) -> bool:
    """Carry exactly the immediately preceding precontact sample into handoff.

    Runtime order is physics/sample -> G05 detect -> G04 controls.  The handoff
    decision therefore sees post-physics state, while the immediately preceding
    control frame is the latest unambiguous precontact realization sample.  No
    broader time window is accepted: stale samples, recovery-era samples and prior
    event samples fail closed.
    """
    if sample is None or not controller_handoff_requested:
        return False
    if sample.transaction_key != tuple(str(x or "") for x in transaction_key):
        return False
    if int(decision_frame) - int(sample.frame) != 1:
        return False
    floor = float(current_capability_floor_mps)
    if floor <= 0.0:
        return False
    if sample.forward_speed_mps < floor or sample.closing_speed_mps < floor:
        return False
    # The base controller independently requires non-negative current closing speed
    # for CONTACT_HANDOFF. Preserve that current-state safety condition here too.
    if float(current_closing_speed_mps) < 0.0:
        return False
    return True
