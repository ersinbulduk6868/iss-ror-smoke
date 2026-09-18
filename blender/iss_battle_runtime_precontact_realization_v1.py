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
    """Permit only one-frame-old, same-transaction, precontact motion evidence.

    Runtime frame order is physics/sample -> G05 detect -> G04 controls. The
    current control decision therefore observes post-physics velocity. A clean
    precontact realization fact may bridge that TOCTOU boundary only from the
    immediately preceding frame. Older evidence, other events/targets, recovery
    evidence, or negative current closing all fail closed.
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
    if float(current_closing_speed_mps) < 0.0:
        return False
    return True
