from __future__ import annotations

from dataclasses import dataclass

ENGAGEMENT_AUTHORITY_MODEL = "G04_EVENT_SCOPED_ENGAGEMENT_AUTHORITY_V2"
APPROACH_CERTIFICATE_MODEL = "G04_CONTINUOUS_REALIZED_APPROACH_CERTIFICATE_V1"

DEFER_TO_BASE = "DEFER_TO_BASE"
CONTINUE_APPROACH = "CONTINUE_APPROACH"
RECOVERY_OWNS = "RECOVERY_OWNS"
HANDOFF_TO_SOLVER = "HANDOFF_TO_SOLVER"
RECOVER_UNQUALIFIED_PROXIMITY = "RECOVER_UNQUALIFIED_PROXIMITY"

CONTACT_DIRECTED_MODES = frozenset({"ENGAGE", "COUNTER"})


@dataclass(slots=True)
class ApproachMotionCertificate:
    qualified: bool = False
    qualified_frame: int | None = None
    last_effective_gap_m: float | None = None
    qualification_count: int = 0
    invalidation_count: int = 0
    last_reason: str = "INIT"

    def invalidate(self, reason: str) -> bool:
        changed = bool(self.qualified or self.qualified_frame is not None)
        if changed:
            self.invalidation_count += 1
        self.qualified = False
        self.qualified_frame = None
        self.last_reason = str(reason)
        return changed


def is_recovery_mode(mode: str | None) -> bool:
    return str(mode or "").upper().startswith("RECOVER_")


def contact_directed(tactical_mode: str | None, requires_contact: bool) -> bool:
    return bool(
        requires_contact
        and str(tactical_mode or "").upper() in CONTACT_DIRECTED_MODES
    )


def update_approach_certificate(
    memory: ApproachMotionCertificate,
    *,
    frame: int,
    contact_directed_mode: bool,
    live_readiness: bool,
    recovery_active: bool,
    effective_gap_m: float,
    handoff_gap_m: float,
    progress_epsilon_m: float,
    capability_floor_mps: float,
    realized_forward_speed_mps: float,
    realized_closing_speed_mps: float,
) -> tuple[bool, bool, str]:
    """Update event-local proof that a contact approach was physically realized.

    The certificate is earned outside the handoff corridor from live chassis motion.
    It remains valid while the same contact-directed transaction remains live and
    continues toward proximity. It is invalidated immediately by recovery, loss of
    contact readiness, tactical ownership leaving ENGAGE/COUNTER, or a meaningful
    pre-contact separation/miss. Current closing speed is deliberately not required
    after the pair has entered handoff proximity because solver response can change
    the sign between sampled frames. G05 remains the final contact authority.
    """
    if not bool(contact_directed_mode):
        changed = memory.invalidate("TACTIC_NOT_CONTACT_DIRECTED")
        memory.last_effective_gap_m = float(effective_gap_m)
        return False, changed, memory.last_reason
    if not bool(live_readiness):
        changed = memory.invalidate("LIVE_READINESS_LOST")
        memory.last_effective_gap_m = float(effective_gap_m)
        return False, changed, memory.last_reason
    if bool(recovery_active):
        changed = memory.invalidate("RECOVERY_ACTIVE")
        memory.last_effective_gap_m = float(effective_gap_m)
        return False, changed, memory.last_reason

    gap = float(effective_gap_m)
    handoff_gap = max(0.0, float(handoff_gap_m))
    epsilon = max(0.0, float(progress_epsilon_m))
    closing = float(realized_closing_speed_mps)
    forward = float(realized_forward_speed_mps)
    floor = max(0.0, float(capability_floor_mps))

    previous_gap = memory.last_effective_gap_m
    if (
        memory.qualified
        and gap > handoff_gap
        and previous_gap is not None
        and gap > float(previous_gap) + epsilon
        and closing <= 0.0
    ):
        changed = memory.invalidate("PRECONTACT_SEPARATION_OR_MISS")
        memory.last_effective_gap_m = gap
        return False, changed, memory.last_reason

    newly_qualified = False
    if (
        gap > handoff_gap
        and floor > 0.0
        and forward >= floor
        and closing >= floor
    ):
        if not memory.qualified:
            newly_qualified = True
            memory.qualification_count += 1
        memory.qualified = True
        memory.qualified_frame = int(frame)
        memory.last_reason = "REALIZED_APPROACH_QUALIFIED"

    memory.last_effective_gap_m = gap
    return newly_qualified, False, memory.last_reason


def authority_action(
    memory: ApproachMotionCertificate,
    *,
    contact_directed_mode: bool,
    live_readiness: bool,
    recovery_active: bool,
    effective_gap_m: float,
    handoff_gap_m: float,
) -> str:
    if not bool(contact_directed_mode) or not bool(live_readiness):
        return DEFER_TO_BASE
    if bool(recovery_active):
        return RECOVERY_OWNS
    if float(effective_gap_m) > float(handoff_gap_m):
        return CONTINUE_APPROACH
    if bool(memory.qualified):
        return HANDOFF_TO_SOLVER
    return RECOVER_UNQUALIFIED_PROXIMITY


def allow_outer_tactical_recovery_clear(
    *,
    transaction_active: bool,
    autonomy_mode: str | None,
    legacy_decision: bool,
) -> bool:
    """Recovery owns motor authority until its own controller completes.

    C474 may still clear historical recovery state outside a C488 transaction. For
    an active event-scoped transaction, RECOVER_* cannot be silently rewritten to
    TRACK by the outer tactical-progress adapter; natural controller completion is
    the only permitted RECOVER_* -> TRACK transition.
    """
    if bool(transaction_active) and is_recovery_mode(autonomy_mode):
        return False
    return bool(legacy_decision)
