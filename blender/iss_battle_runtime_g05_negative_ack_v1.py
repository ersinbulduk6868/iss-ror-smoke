from __future__ import annotations

from dataclasses import dataclass

G05_NEGATIVE_ACK_MODEL = "G04_G05_NEGATIVE_ACKNOWLEDGEMENT_RECOVERY_V1"

STAGE_OUTER = "OUTER_AUTHORITY"
STAGE_SOLVER = "SOLVER_RESPONSE"
STAGE_IMPACT_GATE = "EXISTING_IMPACT_GATE"

RECOVERABLE_OUTER_REASONS = frozenset({
    "SEMANTIC_ZONE_MISMATCH",
    "PAIR_NOT_LOCALLY_ADJACENT",
})


@dataclass(slots=True, frozen=True)
class G05NegativeAcknowledgement:
    frame: int
    event_id: str
    attacker_id: str
    target_id: str
    stage: str
    reason: str
    contact_frame: int | None = None
    controller_handoff: bool = False
    motor_authority_zero: bool = False

    @property
    def transaction_key(self) -> tuple[str, str, str]:
        return (self.event_id, self.attacker_id, self.target_id)


def recoverable_post_handoff_nack(
    nack: G05NegativeAcknowledgement,
    *,
    active_event_id: str,
    active_attacker_id: str,
    active_target_id: str,
    handoff_latched: bool,
) -> bool:
    """Classify an already-made G05 negative decision for G04 recovery.

    G05 remains the final contact authority. Controller-authority and target-identity
    failures are not hidden by recovery because they represent contract regressions,
    not a physical attempt that should simply be replanned.
    """
    if not bool(handoff_latched):
        return False
    if nack.transaction_key != (
        str(active_event_id),
        str(active_attacker_id),
        str(active_target_id),
    ):
        return False

    stage = str(nack.stage)
    reason = str(nack.reason)
    if stage == STAGE_OUTER:
        return bool(
            nack.controller_handoff
            and nack.motor_authority_zero
            and reason in RECOVERABLE_OUTER_REASONS
        )
    if stage in {STAGE_SOLVER, STAGE_IMPACT_GATE}:
        return True
    return False
