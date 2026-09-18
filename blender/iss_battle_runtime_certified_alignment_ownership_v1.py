from __future__ import annotations

CERTIFIED_ALIGNMENT_OWNERSHIP_MODEL = "G04_CERTIFIED_APPROACH_ALIGNMENT_OWNERSHIP_V1"

PRESERVE_CERTIFICATE = "PRESERVE_CERTIFICATE"
INVALIDATE_PRECONTACT_SEPARATION = "INVALIDATE_PRECONTACT_SEPARATION"
DEFER_TO_EXISTING_CERTIFICATE_AUTHORITY = "DEFER_TO_EXISTING_CERTIFICATE_AUTHORITY"
KEEP_LEGACY_RUNWAY_REOPEN = "KEEP_LEGACY_RUNWAY_REOPEN"


def alignment_only_readiness_miss(
    *,
    requires_contact: bool,
    runway_armed: bool,
    contact_ready: bool,
    heading_ready: bool,
    contention_ready: bool,
) -> bool:
    """Return whether instantaneous readiness failed only on heading alignment.

    The caller supplies readiness booleans produced from the already-established G04
    readiness limits.  This helper introduces no threshold and never decides G05
    contact validity, damage, target identity, or solver authority.
    """
    return bool(
        requires_contact
        and runway_armed
        and not contact_ready
        and not heading_ready
        and contention_ready
    )


def legacy_runway_reopen_ownership(
    *,
    legacy_action: str,
    reopen_action: str,
    transaction_active: bool,
    contact_directed_mode: bool,
    recovery_active: bool,
    certificate_qualified: bool,
    alignment_only_miss: bool,
) -> str:
    """Choose ownership when legacy pre-contact logic requests a full runway reset.

    A previously earned approach certificate is historical physical evidence.  A
    heading-only instantaneous miss must still block handoff, but it need not erase
    that historical proof or force a full retreat.  Recovery, contention, an
    unqualified certificate, a non-contact tactic, or any other legacy action keeps
    existing behavior unchanged.
    """
    if str(legacy_action) != str(reopen_action):
        return KEEP_LEGACY_RUNWAY_REOPEN
    if not transaction_active:
        return KEEP_LEGACY_RUNWAY_REOPEN
    if not contact_directed_mode:
        return KEEP_LEGACY_RUNWAY_REOPEN
    if recovery_active:
        return KEEP_LEGACY_RUNWAY_REOPEN
    if not certificate_qualified:
        return KEEP_LEGACY_RUNWAY_REOPEN
    if not alignment_only_miss:
        return KEEP_LEGACY_RUNWAY_REOPEN
    return DEFER_TO_EXISTING_CERTIFICATE_AUTHORITY


def alignment_hold_certificate_action(
    *,
    certificate_qualified: bool,
    effective_gap_m: float,
    handoff_gap_m: float,
    previous_effective_gap_m: float | None,
    progress_epsilon_m: float,
    closing_speed_mps: float,
) -> str:
    """Preserve earned approach proof unless live geometry proves a real miss.

    This function deliberately does not make the handoff decision.  Instantaneous
    readiness remains a separate hard gate in the existing authority action.  The
    only question here is whether historical approach proof survives a temporary
    alignment-only hold.
    """
    if not certificate_qualified:
        return INVALIDATE_PRECONTACT_SEPARATION

    gap = float(effective_gap_m)
    handoff_gap = max(0.0, float(handoff_gap_m))
    epsilon = max(0.0, float(progress_epsilon_m))
    previous = previous_effective_gap_m
    if (
        gap > handoff_gap
        and previous is not None
        and gap > float(previous) + epsilon
        and float(closing_speed_mps) <= 0.0
    ):
        return INVALIDATE_PRECONTACT_SEPARATION
    return PRESERVE_CERTIFICATE
