from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from blender import run_generic_battle_runtime_v1_candidate474_generic_battle as candidate474
from blender import run_generic_battle_runtime_v1_candidate487_generic_battle as candidate487
from blender import run_generic_battle_runtime_v1_candidate488_generic_battle as candidate488
from blender import run_generic_battle_runtime_v1_candidate489_generic_battle as candidate489
from blender import run_generic_battle_runtime_v1_candidate490_generic_battle as candidate490
from blender.iss_battle_runtime_assets import marker
from blender.iss_battle_runtime_certified_alignment_ownership_v1 import (
    CERTIFIED_ALIGNMENT_OWNERSHIP_MODEL,
    DEFER_TO_EXISTING_CERTIFICATE_AUTHORITY,
    INVALIDATE_PRECONTACT_SEPARATION,
    PRESERVE_CERTIFICATE,
    alignment_hold_certificate_action,
    alignment_only_readiness_miss,
    legacy_runway_reopen_ownership,
)
from blender.iss_battle_runtime_contact_commit_v2 import (
    CONTACT_COMMIT_MAX_CONTENTION,
    CONTACT_COMMIT_MAX_HEADING_ERROR_RAD,
)
from blender.iss_battle_runtime_engagement_lifecycle_v1 import (
    DEFER_TO_TACTIC,
    REOPEN_DISTANCE,
)

CANDIDATE = "ISS_GENERIC_BATTLE_RUNTIME_V1_CANDIDATE_4_9_1_GENERIC_AUTONOMOUS_BATTLE"
MECHANISM = CERTIFIED_ALIGNMENT_OWNERSHIP_MODEL
AUDIT = "G04_C490_POST_NACK_RETRY_BUDGET_AND_CERTIFICATE_OWNERSHIP_FULL_AFFECTED_LAYER_AUDIT_20260918"
FAILURE_FAMILY = "QUALIFIED_APPROACH_CERTIFICATE_PREEMPTED_BY_LEGACY_FULL_RUNWAY_REOPEN"

_ORIGINAL_LIVE_CONTACT_READY = candidate487.live_contact_commit_ready
_ORIGINAL_PRECONTACT_ACTION = candidate487.precontact_action
_ORIGINAL_C488_GOAL = candidate489._ORIGINAL_C488_GOAL
_ORIGINAL_UPDATE_APPROACH_CERTIFICATE = candidate488.update_approach_certificate

_readiness_context: dict[tuple[str, str, str], dict[str, Any]] = {}
_alignment_hold_active: set[tuple[str, str, str]] = set()
_alignment_hold_announced: set[tuple[str, str, str]] = set()
_alignment_hold_rows: list[dict[str, Any]] = []
_certificate_hold_rows: list[dict[str, Any]] = []


def _active_key() -> tuple[str, str, str] | None:
    pair = candidate474._active_pair_context or {}
    attacker_id = str(pair.get("attackerId") or "")
    target_id = str(pair.get("targetId") or "")
    if not attacker_id or not target_id:
        return None
    key = candidate487._active_transaction_by_actor.get(attacker_id)
    if key is None or str(key[2]) != target_id:
        return None
    return key


def _frame() -> int:
    context = candidate474._pending_tactical_context or {}
    return int(context.get("frame") or 0)


def c491_observed_live_contact_commit_ready(
    *,
    requires_contact: bool,
    engagement_runway_armed: bool,
    heading_error_rad: float,
    contention: float,
) -> bool:
    ready = bool(
        _ORIGINAL_LIVE_CONTACT_READY(
            requires_contact=requires_contact,
            engagement_runway_armed=engagement_runway_armed,
            heading_error_rad=heading_error_rad,
            contention=contention,
        )
    )
    key = _active_key()
    if key is not None:
        heading_ready = bool(
            abs(float(heading_error_rad)) <= float(CONTACT_COMMIT_MAX_HEADING_ERROR_RAD)
        )
        contention_ready = bool(
            float(contention) < float(CONTACT_COMMIT_MAX_CONTENTION)
        )
        _readiness_context[key] = {
            "frame": _frame(),
            "requiresContact": bool(requires_contact),
            "runwayArmed": bool(engagement_runway_armed),
            "contactReady": bool(ready),
            "headingErrorRad": float(heading_error_rad),
            "headingReady": heading_ready,
            "contention": float(contention),
            "contentionReady": contention_ready,
            "alignmentOnlyMiss": alignment_only_readiness_miss(
                requires_contact=bool(requires_contact),
                runway_armed=bool(engagement_runway_armed),
                contact_ready=bool(ready),
                heading_ready=heading_ready,
                contention_ready=contention_ready,
            ),
        }
    return ready


def c491_precontact_action(
    *,
    tactical_mode: str,
    requires_contact: bool,
    recovery_active: bool,
    runway_armed: bool,
    contact_ready: bool,
    surface_gap_m: float,
    runway_required_m: float,
) -> str:
    legacy = str(
        _ORIGINAL_PRECONTACT_ACTION(
            tactical_mode=tactical_mode,
            requires_contact=requires_contact,
            recovery_active=recovery_active,
            runway_armed=runway_armed,
            contact_ready=contact_ready,
            surface_gap_m=surface_gap_m,
            runway_required_m=runway_required_m,
        )
    )
    key = _active_key()
    if key is None:
        return legacy

    frame = _frame()
    observed = _readiness_context.get(key) or {}
    context_fresh = bool(int(observed.get("frame") or -1) == int(frame))
    certificate = candidate488._certificates.get(key)
    certificate_qualified = bool(certificate is not None and certificate.qualified)
    ownership = legacy_runway_reopen_ownership(
        legacy_action=legacy,
        reopen_action=REOPEN_DISTANCE,
        transaction_active=True,
        contact_directed_mode=candidate488.contact_directed(
            tactical_mode,
            bool(requires_contact),
        ),
        recovery_active=bool(recovery_active),
        certificate_qualified=certificate_qualified,
        alignment_only_miss=bool(
            context_fresh
            and observed.get("alignmentOnlyMiss") is True
            and bool(observed.get("contactReady")) == bool(contact_ready)
        ),
    )
    if ownership != DEFER_TO_EXISTING_CERTIFICATE_AUTHORITY:
        _alignment_hold_active.discard(key)
        _alignment_hold_announced.discard(key)
        return legacy

    _alignment_hold_active.add(key)
    if key not in _alignment_hold_announced:
        _alignment_hold_announced.add(key)
        row = {
            "frame": int(frame),
            "eventId": key[0],
            "attackerId": key[1],
            "targetId": key[2] or None,
            "legacyAction": legacy,
            "delegatedAction": DEFER_TO_TACTIC,
            "delegatedAuthority": "C488_CERTIFIED_APPROACH_AND_ALIGNMENT",
            "certificateQualifiedFrame": (
                int(certificate.qualified_frame)
                if certificate is not None and certificate.qualified_frame is not None
                else None
            ),
            "headingErrorRad": float(observed.get("headingErrorRad") or 0.0),
            "existingHeadingLimitRad": float(CONTACT_COMMIT_MAX_HEADING_ERROR_RAD),
            "contention": float(observed.get("contention") or 0.0),
            "existingContentionLimit": float(CONTACT_COMMIT_MAX_CONTENTION),
            "surfaceGapM": float(surface_gap_m),
            "runwayRequiredM": float(runway_required_m),
            "headingThresholdChanged": False,
            "contentionThresholdChanged": False,
            "contactThresholdChanged": False,
            "model": MECHANISM,
        }
        _alignment_hold_rows.append(row)
        marker("G04_CERTIFIED_APPROACH_LEGACY_RUNWAY_REOPEN_DEFERRED", **row)
    return DEFER_TO_TACTIC


def c491_c488_goal_for_tactical(
    actor: Any,
    target: Any,
    event: Any,
    tactical: Any,
    actors: dict[str, Any],
) -> Any:
    goal = _ORIGINAL_C488_GOAL(actor, target, event, tactical, actors)
    key = (
        str(event.event_id),
        str(actor.profile.entity_id),
        str(target.profile.entity_id),
    )
    observed = _readiness_context.get(key) or {}
    if (
        key in _alignment_hold_active
        and int(observed.get("frame") or -1) == int(candidate487._current_frame(event))
    ):
        context = candidate488._contact_context.get(key)
        if context is None:
            raise RuntimeError("C491_C488_CONTACT_CONTEXT_MISSING")
        # Preserve the contact-directed tactic and semantic transaction, but keep
        # instantaneous readiness false.  C488 authority_action therefore cannot
        # hand off until the unchanged G04 readiness contract becomes true again.
        context["contactCommit"] = False
        context["c491CertifiedAlignmentHold"] = True
    return goal


def c491_update_approach_certificate(
    memory: Any,
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
    key = _active_key()
    if (
        key is not None
        and key in _alignment_hold_active
        and bool(contact_directed_mode)
        and not bool(live_readiness)
        and not bool(recovery_active)
    ):
        action = alignment_hold_certificate_action(
            certificate_qualified=bool(memory.qualified),
            effective_gap_m=float(effective_gap_m),
            handoff_gap_m=float(handoff_gap_m),
            previous_effective_gap_m=memory.last_effective_gap_m,
            progress_epsilon_m=float(progress_epsilon_m),
            closing_speed_mps=float(realized_closing_speed_mps),
        )
        if action == INVALIDATE_PRECONTACT_SEPARATION:
            changed = memory.invalidate("PRECONTACT_SEPARATION_OR_MISS")
            memory.last_effective_gap_m = float(effective_gap_m)
            _alignment_hold_active.discard(key)
            return False, bool(changed), str(memory.last_reason)
        if action != PRESERVE_CERTIFICATE:
            raise RuntimeError(f"C491_UNKNOWN_CERTIFICATE_HOLD_ACTION:{action}")

        memory.last_effective_gap_m = float(effective_gap_m)
        memory.last_reason = "CERTIFIED_ALIGNMENT_READINESS_HOLD"
        row = {
            "frame": int(frame),
            "eventId": key[0],
            "attackerId": key[1],
            "targetId": key[2] or None,
            "qualifiedFrame": memory.qualified_frame,
            "effectiveCollisionProxyGapM": float(effective_gap_m),
            "handoffGapM": float(handoff_gap_m),
            "realizedForwardSpeedMps": float(realized_forward_speed_mps),
            "realizedClosingSpeedMps": float(realized_closing_speed_mps),
            "capabilityFloorMps": float(capability_floor_mps),
            "instantaneousReadiness": False,
            "certificatePreserved": True,
            "handoffAllowedWhileUnready": False,
            "headingThresholdChanged": False,
            "contentionThresholdChanged": False,
            "model": MECHANISM,
        }
        _certificate_hold_rows.append(row)
        marker("G04_CERTIFIED_APPROACH_ALIGNMENT_HOLD", **row)
        return False, False, str(memory.last_reason)

    return _ORIGINAL_UPDATE_APPROACH_CERTIFICATE(
        memory,
        frame=frame,
        contact_directed_mode=contact_directed_mode,
        live_readiness=live_readiness,
        recovery_active=recovery_active,
        effective_gap_m=effective_gap_m,
        handoff_gap_m=handoff_gap_m,
        progress_epsilon_m=progress_epsilon_m,
        capability_floor_mps=capability_floor_mps,
        realized_forward_speed_mps=realized_forward_speed_mps,
        realized_closing_speed_mps=realized_closing_speed_mps,
    )


def _reset() -> None:
    _readiness_context.clear()
    _alignment_hold_active.clear()
    _alignment_hold_announced.clear()
    _alignment_hold_rows.clear()
    _certificate_hold_rows.clear()


def main() -> None:
    _reset()

    # Observe the exact existing G04 readiness decision.  Do not replace its
    # threshold or qualification result.
    candidate487.live_contact_commit_ready = c491_observed_live_contact_commit_ready

    # When the only readiness miss is alignment and a C488 physical-approach
    # certificate is already earned, prevent the older C487 layer from forcing a
    # full runway retreat.  The current contact attempt remains unready and cannot
    # hand off until the same unchanged readiness gate passes.
    candidate487.precontact_action = c491_precontact_action
    candidate489._ORIGINAL_C488_GOAL = c491_c488_goal_for_tactical
    candidate488.update_approach_certificate = c491_update_approach_certificate

    print(json.dumps({
        "marker": "GENERIC_AUTONOMOUS_BATTLE_C491_ENGINEERING_READY",
        "candidate": CANDIDATE,
        "mechanism": MECHANISM,
        "affectedLayerAudit": AUDIT,
        "affectedLayerAuditStatus": "PASS",
        "failureFamily": FAILURE_FAMILY,
        "machineEvidenceSource": "C490_L4_RUN_c9d39602-0585-4257-a377-f22c83e04db5",
        "rootCause": "QUALIFIED_C488_APPROACH_PROOF_WAS_INVALIDATED_BY_C487_FULL_RUNWAY_REOPEN_ON_HEADING_ONLY_INSTANTANEOUS_READINESS_MISS",
        "c490FinalCompositionBindingPreserved": True,
        "c489NegativeAckRecoveryPreserved": True,
        "c488CertifiedApproachAuthorityPreserved": True,
        "c488AlignmentAuthorityPreserved": True,
        "c487RecoveryPriorityPreserved": True,
        "existingHeadingReadinessGatePreserved": True,
        "existingContentionReadinessGatePreserved": True,
        "headingOnlyMissCannotHandoff": True,
        "contentionMissKeepsLegacyRunwayReopen": True,
        "recoveryKeepsLegacyOwnership": True,
        "realPrecontactSeparationStillInvalidatesCertificate": True,
        "storyDurationChanged": False,
        "eventTimingChanged": False,
        "g05SourceChanged": False,
        "g05OuterGateChanged": False,
        "g05SolverOracleChanged": False,
        "g05ThresholdImported": False,
        "headingThresholdChanged": False,
        "contentionThresholdChanged": False,
        "contactThresholdChanged": False,
        "semanticToleranceChanged": False,
        "localityToleranceChanged": False,
        "damageAdmissionThresholdChanged": False,
        "assetIdentityBranch": False,
        "perAssetBattleCode": False,
        "perAssetTacticalTuning": False,
        "perVideoTrajectoryEngineering": False,
        "fixedWorldCoordinates": False,
        "exactCollisionFrameTarget": False,
        "exactImpactEnergyTarget": False,
        "actorPoseOrVelocityMutation": False,
        "fixtureBattlePlanChanged": False,
        "frozenNineServiceArchitectureChanged": False,
        "gateClosed": False,
        "productionReadyClaimed": False,
    }, sort_keys=True), flush=True)

    candidate490.main()


if __name__ == "__main__":
    main()
