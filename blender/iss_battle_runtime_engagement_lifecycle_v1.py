from __future__ import annotations

from dataclasses import dataclass

ENGAGEMENT_LIFECYCLE_MODEL = "G04_EVENT_SCOPED_ENGAGEMENT_AUTHORITY_LIFECYCLE_V1"

DEFER_TO_TACTIC = "DEFER_TO_TACTIC"
ALLOW_CONTACT = "ALLOW_CONTACT"
REOPEN_DISTANCE = "REOPEN_DISTANCE"
HOLD_STANDOFF = "HOLD_STANDOFF"
SUSPEND_FOR_RECOVERY = "SUSPEND_FOR_RECOVERY"

PHASE_PREPARE = "PREPARE"
PHASE_RUNWAY_REOPEN = "RUNWAY_REOPEN"
PHASE_ALIGN_STANDOFF = "ALIGN_STANDOFF"
PHASE_APPROACH = "APPROACH"
PHASE_RECOVERING = "RECOVERING"
PHASE_HANDOFF_READY = "HANDOFF_READY"
PHASE_SOLVER_OWNED = "SOLVER_OWNED"

CONTACT_CORRIDOR_MODES = frozenset({"ENGAGE", "COUNTER"})


def transaction_key(event_id: str, actor_id: str, target_id: str | None) -> tuple[str, str, str]:
    return (str(event_id or ""), str(actor_id or ""), str(target_id or ""))


def is_recovery_mode(mode: str | None) -> bool:
    return str(mode or "").upper().startswith("RECOVER_")


@dataclass(slots=True)
class EngagementLifecycleMemory:
    phase: str = PHASE_PREPARE
    last_transition_frame: int = 0
    recovery_epoch: int = 0
    recovery_replan_reported: bool = False

    def transition(self, phase: str, frame: int) -> bool:
        phase = str(phase)
        changed = self.phase != phase
        if changed:
            self.phase = phase
            self.last_transition_frame = int(frame)
        return changed


def precontact_action(
    *,
    tactical_mode: str,
    requires_contact: bool,
    recovery_active: bool,
    runway_armed: bool,
    contact_ready: bool,
    surface_gap_m: float,
    runway_required_m: float,
) -> str:
    """Choose G04 pre-contact ownership without overriding unrelated tactics.

    Only the two contact-directed tactical modes are eligible for corridor control.
    FLANK/BRAKE_APPROACH/EVADE/BREAK_CONTACT/REPOSITION/HOLD remain owned by the
    existing tactical planner.  Recovery has explicit priority over contact commit.
    No G05 threshold, target toughness, impact target, fixture identity, collision
    frame, or world coordinate enters this decision.
    """
    mode = str(tactical_mode or "").upper()
    if not bool(requires_contact) or mode not in CONTACT_CORRIDOR_MODES:
        return DEFER_TO_TACTIC
    if bool(recovery_active):
        return SUSPEND_FOR_RECOVERY
    if bool(contact_ready):
        return ALLOW_CONTACT

    runway = max(0.0, float(runway_required_m))
    gap = float(surface_gap_m)
    if bool(runway_armed) and gap < runway:
        return REOPEN_DISTANCE
    return HOLD_STANDOFF


def note_recovery_transition(
    memory: EngagementLifecycleMemory,
    *,
    frame: int,
    previous_controller_mode: str | None,
    current_controller_mode: str | None,
) -> tuple[bool, bool]:
    """Return (started, completed) and keep recovery lifecycle explicit."""
    was_recovery = is_recovery_mode(previous_controller_mode)
    is_recovery = is_recovery_mode(current_controller_mode)
    started = bool(is_recovery and not was_recovery)
    completed = bool(was_recovery and not is_recovery)
    if started:
        memory.recovery_epoch += 1
        memory.recovery_replan_reported = False
        memory.transition(PHASE_RECOVERING, int(frame))
    elif completed:
        memory.recovery_replan_reported = False
        memory.transition(PHASE_PREPARE, int(frame))
    elif is_recovery:
        memory.transition(PHASE_RECOVERING, int(frame))
    return started, completed
