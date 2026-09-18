from __future__ import annotations

CERTIFIED_NAVIGATION_CONTINUITY_MODEL = "G04_CERTIFIED_APPROACH_NAVIGATION_CONTINUITY_V1"
CONTACT_DIRECTED_MODES = frozenset({"ENGAGE", "COUNTER"})


def certified_approach_owns_navigation(
    *,
    transaction_active: bool,
    certificate_qualified: bool,
    incoming_tactical_mode: str | None,
    incoming_contact_commit: bool,
    recovery_active: bool,
) -> bool:
    """Keep an already proven approach under certificate navigation ownership.

    This is an ownership rule, not a contact/readiness threshold. It never decides
    whether native contact is valid and never weakens recovery. The incoming
    tactical planner must still be contact-directed and committed, the same event/
    actor/target transaction must remain active, and low-level recovery always
    preempts continuity. G05 remains final native-contact authority.
    """
    return bool(
        transaction_active
        and certificate_qualified
        and str(incoming_tactical_mode or "").upper() in CONTACT_DIRECTED_MODES
        and incoming_contact_commit
        and not recovery_active
    )
