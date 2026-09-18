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


@dataclass(slots=True)
class G05NegativeAckWindow:
    first_frame: int | None = None
    last_frame: int | None = None
    consecutive_frames: int = 0

    def clear(self) -> None:
        self.first_frame = None
        self.last_frame = None
        self.consecutive_frames = 0


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


def negative_ack_confirmed(
    window: G05NegativeAckWindow,
    nack: G05NegativeAcknowledgement,
    *,
    confirmation_frames: int,
) -> bool:
    """Confirm a nonproductive handoff without reacting to one-frame solver noise.

    Existing-impact-gate rejection is already a final downstream decision and is
    immediate. Outer/solver rejection must persist on consecutive physics frames for
    the caller-supplied existing G05 observation horizon. The helper knows no asset,
    threshold, semantic tolerance, collision frame target, or trajectory.
    """
    if str(nack.stage) == STAGE_IMPACT_GATE:
        window.first_frame = int(nack.frame)
        window.last_frame = int(nack.frame)
        window.consecutive_frames = 1
        return True

    required = max(1, int(confirmation_frames))
    frame = int(nack.frame)
    if window.last_frame is None or frame < int(window.last_frame) or frame > int(window.last_frame) + 1:
        window.first_frame = frame
        window.last_frame = frame
        window.consecutive_frames = 1
    elif frame == int(window.last_frame):
        pass
    else:
        window.last_frame = frame
        window.consecutive_frames += 1
    return int(window.consecutive_frames) >= required
