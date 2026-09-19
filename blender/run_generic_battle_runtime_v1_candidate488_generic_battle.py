from __future__ import annotations

from dataclasses import replace
import json
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from blender import iss_battle_runtime_generic_battle_v6 as battle_v6
from blender import run_generic_battle_runtime_v1_candidate465_generic_battle as candidate465
from blender import run_generic_battle_runtime_v1_candidate472_generic_battle as candidate472
from blender import run_generic_battle_runtime_v1_candidate474_generic_battle as candidate474
from blender import run_generic_battle_runtime_v1_candidate481_generic_battle as candidate481
from blender import run_generic_battle_runtime_v1_candidate483_generic_battle as candidate483
from blender import run_generic_battle_runtime_v1_candidate485_generic_battle as candidate485
from blender import run_generic_battle_runtime_v1_candidate486_generic_battle as candidate486
from blender import run_generic_battle_runtime_v1_candidate487_generic_battle as candidate487
from blender.iss_battle_runtime_assets import marker
from blender.iss_battle_runtime_autonomy import AutonomyCommand, ClosedLoopGoalController
from blender.iss_battle_runtime_contact_commit_v2 import (
    capability_motion_realization_floor_mps,
)
from blender.iss_battle_runtime_engagement_authority_v2 import (
    APPROACH_CERTIFICATE_MODEL,
    CONTINUE_APPROACH,
    DEFER_TO_BASE,
    ENGAGEMENT_AUTHORITY_MODEL,
    HANDOFF_TO_SOLVER,
    RECOVER_UNQUALIFIED_PROXIMITY,
    RECOVERY_OWNS,
    ApproachMotionCertificate,
    allow_outer_tactical_recovery_clear,
    authority_action,
    contact_directed,
    is_recovery_mode,
    update_approach_certificate,
)
from blender.iss_battle_runtime_handoff_alignment_v1 import (
    HANDOFF_ALIGNMENT_MODEL,
    rotational_nose_speed_mps,
    should_defer_handoff_for_alignment,
    translation_dominates_rotation,
)
from blender.iss_battle_runtime_progress_contract_v1 import progress_epsilon_m

CANDIDATE = "ISS_GENERIC_BATTLE_RUNTIME_V1_CANDIDATE_4_8_8_GENERIC_AUTONOMOUS_BATTLE"
MECHANISM = ENGAGEMENT_AUTHORITY_MODEL
AUDIT = "G04_C487_1_POSTPROXIMITY_HANDOFF_AND_RECOVERY_COMPOSITION_AUDIT_20260918"
FAILURE_FAMILY = "POSTPROXIMITY_HANDOFF_DEADZONE_AND_RECOVERY_OWNERSHIP_COMPOSITION"

_ORIGINAL_RECOVERY_CLEAR = candidate472.should_clear_stale_autonomy_recovery
_ORIGINAL_C487_END_TRANSACTION = candidate487._end_transaction
_BASE_AUTONOMY_UPDATE = candidate485._BASE_AUTONOMY_UPDATE

_certificates: dict[tuple[str, str, str], ApproachMotionCertificate] = {}
_contact_context: dict[tuple[str, str, str], dict[str, Any]] = {}
_certificate_rows: list[dict[str, Any]] = []
_recovery_clear_suppressed: list[dict[str, Any]] = []
_handoff_rows: list[dict[str, Any]] = []
_alignment_defer_active: set[tuple[str, str, str]] = set()


def _transaction_key_from_pair() -> tuple[str, str, str]:
    pair = candidate474._active_pair_context or {}
    attacker_id = str(pair.get("attackerId") or "")
    target_id = str(pair.get("targetId") or "")
    key = candidate487._active_transaction_by_actor.get(attacker_id)
    if key is None:
        raise RuntimeError("C488_EVENT_TRANSACTION_CONTEXT_MISSING")
    if key[2] != target_id:
        raise RuntimeError("C488_EVENT_TRANSACTION_TARGET_MISMATCH")
    return key


def c488_goal_for_tactical(
    actor: Any,
    target: Any,
    event: Any,
    tactical: Any,
    actors: dict[str, Any],
):
    goal = candidate487.actual_goal_lifecycle_goal_for_tactical(
        actor,
        target,
        event,
        tactical,
        actors,
    )
    key = (
        str(event.event_id),
        str(actor.profile.entity_id),
        str(target.profile.entity_id),
    )
    _contact_context[key] = {
        "frame": int(candidate487._current_frame(event)),
        "tacticalMode": str(tactical.mode),
        "requiresContact": bool(event.requires_contact),
        "contactCommit": bool(tactical.contact_commit),
    }
    return goal


def c488_end_transaction(entity: str, key: tuple[str, str, str], frame: int) -> None:
    _ORIGINAL_C487_END_TRANSACTION(entity, key, frame)
    certificate = _certificates.pop(key, None)
    _contact_context.pop(key, None)
    _alignment_defer_active.discard(key)
    if certificate is not None and certificate.qualified:
        marker(
            "G04_REALIZED_APPROACH_CERTIFICATE_INVALIDATED",
            frame=int(frame),
            eventId=key[0],
            attackerId=key[1],
            targetId=key[2] or None,
            reason="EVENT_TRANSACTION_ENDED",
            qualifiedFrame=certificate.qualified_frame,
            model=APPROACH_CERTIFICATE_MODEL,
        )


def c488_recovery_clear_guard(
    *,
    previous_tactical_mode: str | None,
    current_tactical_mode: str,
    tactical_transition: bool,
    autonomy_mode: str,
    speed_intent: str,
) -> bool:
    legacy = _ORIGINAL_RECOVERY_CLEAR(
        previous_tactical_mode=previous_tactical_mode,
        current_tactical_mode=current_tactical_mode,
        tactical_transition=tactical_transition,
        autonomy_mode=autonomy_mode,
        speed_intent=speed_intent,
    )
    pair = candidate474._active_pair_context or {}
    attacker_id = str(pair.get("attackerId") or "")
    key = candidate487._active_transaction_by_actor.get(attacker_id)
    decision = allow_outer_tactical_recovery_clear(
        transaction_active=key is not None,
        autonomy_mode=autonomy_mode,
        legacy_decision=legacy,
    )
    if legacy and not decision and key is not None:
        row = {
            "frame": int((candidate474._pending_tactical_context or {}).get("frame") or 0),
            "eventId": key[0],
            "attackerId": key[1],
            "targetId": key[2] or None,
            "previousTacticalMode": previous_tactical_mode,
            "currentTacticalMode": current_tactical_mode,
            "autonomyMode": str(autonomy_mode),
            "speedIntent": str(speed_intent),
            "model": MECHANISM,
        }
        _recovery_clear_suppressed.append(row)
        marker("G04_OUTER_RECOVERY_CLEAR_SUPPRESSED", **row)
    return bool(decision)


def _mark_certificate(
    marker_name: str,
    key: tuple[str, str, str],
    *,
    obs: Any,
    certificate: ApproachMotionCertificate,
    effective_gap_m: float,
    handoff_gap_m: float,
    floor_mps: float,
    reason: str,
) -> None:
    row = {
        "frame": int(obs.frame),
        "eventId": key[0],
        "attackerId": key[1],
        "targetId": key[2] or None,
        "effectiveCollisionProxyGapM": float(effective_gap_m),
        "handoffGapM": float(handoff_gap_m),
        "capabilityFloorMps": float(floor_mps),
        "realizedForwardSpeedMps": float(obs.forward_speed_mps),
        "realizedClosingSpeedMps": float(obs.closing_speed_mps),
        "qualifiedFrame": certificate.qualified_frame,
        "qualificationCount": int(certificate.qualification_count),
        "invalidationCount": int(certificate.invalidation_count),
        "reason": str(reason),
        "model": APPROACH_CERTIFICATE_MODEL,
    }
    _certificate_rows.append(row)
    marker(marker_name, **row)


def certified_event_scoped_autonomy_update(
    memory: Any,
    obs: Any,
    *,
    recovery_bias: float = 1.0,
) -> Any:
    key = _transaction_key_from_pair()
    pair = candidate474._active_pair_context or {}
    effective_gap = pair.get("effectiveCollisionProxyGapM")
    if effective_gap is None:
        raise RuntimeError("C488_EFFECTIVE_COLLISION_PROXY_GAP_MISSING")
    effective_gap = float(effective_gap)

    context = _contact_context.get(key)
    if context is None or int(context.get("frame") or -1) != int(obs.frame):
        raise RuntimeError("C488_CONTACT_CONTEXT_STALE_OR_MISSING")

    tactical_mode = str(context.get("tacticalMode") or "")
    live_readiness = bool(context.get("contactCommit"))
    # Intent persists during a temporary readiness miss. C491 may preserve an
    # already-earned approach certificate; current handoff readiness stays false.
    directed = contact_directed(tactical_mode, bool(context["requiresContact"]))
    recovery_active = is_recovery_mode(memory.mode)
    handoff_gap = float(ClosedLoopGoalController.contact_handoff_gap(obs))
    floor = float(
        capability_motion_realization_floor_mps(
            max_speed_mps=float(obs.max_speed_mps),
            acceleration_mps2=float(obs.acceleration_mps2),
            characteristic_length_m=float(obs.characteristic_length_m),
            drive_efficiency=float(obs.drive_efficiency),
        )
    )
    certificate = _certificates.setdefault(key, ApproachMotionCertificate())
    was_qualified = bool(certificate.qualified)
    qualified, invalidated, cert_reason = update_approach_certificate(
        certificate,
        frame=int(obs.frame),
        contact_directed_mode=directed,
        live_readiness=live_readiness,
        recovery_active=recovery_active,
        effective_gap_m=effective_gap,
        handoff_gap_m=handoff_gap,
        progress_epsilon_m=progress_epsilon_m(float(obs.characteristic_length_m)),
        capability_floor_mps=floor,
        realized_forward_speed_mps=float(obs.forward_speed_mps),
        realized_closing_speed_mps=float(obs.closing_speed_mps),
    )
    if qualified:
        _mark_certificate(
            "G04_REALIZED_APPROACH_CERTIFICATE_QUALIFIED",
            key,
            obs=obs,
            certificate=certificate,
            effective_gap_m=effective_gap,
            handoff_gap_m=handoff_gap,
            floor_mps=floor,
            reason=cert_reason,
        )
        # Compatibility evidence for the C485 failure-family regression: the
        # same capability-derived realized forward and closing floor was earned.
        marker(
            "G04_CONTACT_HANDOFF_REALIZED_APPROACH_READY",
            frame=int(obs.frame),
            attackerId=key[1],
            targetId=key[2] or None,
            capabilityFloorMps=floor,
            realizedForwardSpeedMps=float(obs.forward_speed_mps),
            realizedClosingSpeedMps=float(obs.closing_speed_mps),
            characteristicLengthM=float(obs.characteristic_length_m),
            model=candidate485.MECHANISM,
        )
    elif invalidated and was_qualified:
        _mark_certificate(
            "G04_REALIZED_APPROACH_CERTIFICATE_INVALIDATED",
            key,
            obs=obs,
            certificate=certificate,
            effective_gap_m=effective_gap,
            handoff_gap_m=handoff_gap,
            floor_mps=floor,
            reason=cert_reason,
        )

    action = authority_action(
        certificate,
        contact_directed_mode=directed,
        live_readiness=live_readiness,
        recovery_active=recovery_active,
        effective_gap_m=effective_gap,
        handoff_gap_m=handoff_gap,
    )

    if action in {DEFER_TO_BASE, CONTINUE_APPROACH, RECOVERY_OWNS}:
        # Delegation must not let the base proximity controller re-authorize a
        # handoff rejected by this layer. This changes a control observation,
        # never an actor pose/velocity or the original event's intent.
        base_obs = obs if live_readiness else replace(obs, requires_contact=False)
        return _BASE_AUTONOMY_UPDATE(
            memory,
            base_obs,
            recovery_bias=recovery_bias,
        )

    if action == RECOVER_UNQUALIFIED_PROXIMITY:
        if not is_recovery_mode(memory.mode):
            marker(
                "G04_CONTACT_HANDOFF_DEFERRED_BY_REALIZED_APPROACH",
                frame=int(obs.frame),
                attackerId=key[1],
                targetId=key[2] or None,
                capabilityFloorMps=floor,
                realizedForwardSpeedMps=float(obs.forward_speed_mps),
                realizedClosingSpeedMps=float(obs.closing_speed_mps),
                characteristicLengthM=float(obs.characteristic_length_m),
                model=candidate485.MECHANISM,
            )
            marker(
                "G04_CERTIFIED_HANDOFF_DEFERRED_CERTIFICATE_MISSING",
                frame=int(obs.frame),
                eventId=key[0],
                attackerId=key[1],
                targetId=key[2] or None,
                effectiveCollisionProxyGapM=effective_gap,
                handoffGapM=handoff_gap,
                capabilityFloorMps=floor,
                realizedForwardSpeedMps=float(obs.forward_speed_mps),
                realizedClosingSpeedMps=float(obs.closing_speed_mps),
                model=MECHANISM,
            )
            ClosedLoopGoalController._begin_recovery(
                memory,
                obs,
                "PREHANDOFF_REALIZED_APPROACH_CERTIFICATE_MISSING",
                recovery_bias,
            )
        timeout = ClosedLoopGoalController.progress_timeout_frames(obs)
        command = ClosedLoopGoalController._recovery_command(
            memory,
            obs,
            timeout,
            handoff_gap,
        )
        if command is None:
            return _BASE_AUTONOMY_UPDATE(
                memory,
                replace(obs, requires_contact=False),
                recovery_bias=recovery_bias,
            )
        command.replan_triggered = True
        return command

    if action != HANDOFF_TO_SOLVER:
        raise RuntimeError(f"C488_UNKNOWN_AUTHORITY_ACTION:{action}")

    # Preserve C484's independent translation-vs-rotation readiness before
    # releasing motor authority. The approach certificate replaces only C485's
    # instantaneous speed check; it does not bypass alignment.
    motor_obs = replace(obs, requires_contact=False)
    motor_probe = _BASE_AUTONOMY_UPDATE(
        replace(memory),
        motor_obs,
        recovery_bias=recovery_bias,
    )
    prospective_forward = float(motor_probe.forward_speed_mps)
    prospective_yaw = float(motor_probe.yaw_rate_rad_s)
    characteristic_length = max(0.0, float(obs.characteristic_length_m))
    rotational_nose_speed = rotational_nose_speed_mps(
        yaw_rate_rad_s=prospective_yaw,
        characteristic_length_m=characteristic_length,
    )
    translation_dominant = translation_dominates_rotation(
        forward_speed_mps=prospective_forward,
        yaw_rate_rad_s=prospective_yaw,
        characteristic_length_m=characteristic_length,
    )
    defer_alignment = should_defer_handoff_for_alignment(
        contact_handoff_requested=True,
        prospective_motor_authority=str(motor_probe.motor_authority),
        forward_speed_mps=prospective_forward,
        yaw_rate_rad_s=prospective_yaw,
        characteristic_length_m=characteristic_length,
    )
    if defer_alignment:
        if key not in _alignment_defer_active:
            _alignment_defer_active.add(key)
            marker(
                "G04_CONTACT_HANDOFF_DEFERRED_BY_ROTATIONAL_DOMINANCE",
                frame=int(obs.frame),
                attackerId=key[1],
                targetId=key[2] or None,
                prospectiveMotorAuthority=str(motor_probe.motor_authority),
                prospectiveForwardSpeedMps=prospective_forward,
                prospectiveYawRateRadS=prospective_yaw,
                rotationalNoseSpeedMps=rotational_nose_speed,
                characteristicLengthM=characteristic_length,
                translationDominant=translation_dominant,
                model=HANDOFF_ALIGNMENT_MODEL,
            )
        return _BASE_AUTONOMY_UPDATE(
            memory,
            motor_obs,
            recovery_bias=recovery_bias,
        )

    if key in _alignment_defer_active:
        _alignment_defer_active.discard(key)
        marker(
            "G04_CONTACT_HANDOFF_ALIGNMENT_READY",
            frame=int(obs.frame),
            attackerId=key[1],
            targetId=key[2] or None,
            prospectiveMotorAuthority=str(motor_probe.motor_authority),
            prospectiveForwardSpeedMps=prospective_forward,
            prospectiveYawRateRadS=prospective_yaw,
            rotationalNoseSpeedMps=rotational_nose_speed,
            characteristicLengthM=characteristic_length,
            translationDominant=translation_dominant,
            model=HANDOFF_ALIGNMENT_MODEL,
        )

    row = {
        "frame": int(obs.frame),
        "eventId": key[0],
        "attackerId": key[1],
        "targetId": key[2] or None,
        "qualifiedFrame": certificate.qualified_frame,
        "effectiveCollisionProxyGapM": effective_gap,
        "handoffGapM": handoff_gap,
        "currentClosingSpeedMps": float(obs.closing_speed_mps),
        "currentForwardSpeedMps": float(obs.forward_speed_mps),
        "capabilityFloorMps": floor,
        "currentClosingSignRequired": False,
        "model": MECHANISM,
    }
    _handoff_rows.append(row)
    marker("G04_CERTIFIED_SOLVER_HANDOFF_REQUESTED", **row)

    timeout = ClosedLoopGoalController.progress_timeout_frames(obs)
    memory.mode = "CONTACT_HANDOFF"
    memory.reason = "CERTIFIED_REALIZED_APPROACH_SOLVER_HANDOFF"
    memory.last_command_speed_mps = 0.0
    memory.last_distance_m = float(obs.distance_m)
    memory.last_surface_gap_m = float(obs.surface_gap_m)
    return AutonomyCommand(
        0.0,
        0.0,
        "COAST",
        "CONTACT_HANDOFF",
        memory.reason,
        False,
        int(timeout),
        float(handoff_gap),
    )


def _reset() -> None:
    _certificates.clear()
    _contact_context.clear()
    _certificate_rows.clear()
    _recovery_clear_suppressed.clear()
    _handoff_rows.clear()
    _alignment_defer_active.clear()


def main() -> None:
    _reset()
    candidate487._event_tactical_memories.clear()
    candidate487._event_last_tactical_mode.clear()
    candidate487._active_transaction_by_actor.clear()
    candidate487._lifecycle_memories.clear()
    candidate487._lifecycle_rows.clear()
    candidate487._actual_readiness_deferred.clear()

    # Preserve C487 event-scoped tactical/lifecycle ownership, but replace its
    # inner instantaneous realized-handoff decision with C488's event-local
    # approach certificate. C486's mode-blind corridor remains superseded.
    candidate486.corridor_aware_tactical_decide = candidate486._C485_TACTICAL_DECIDE
    candidate487._end_transaction = c488_end_transaction
    battle_v6._goal_for_tactical = c488_goal_for_tactical
    candidate481.defer_progress_aware_base_autonomy_update = (
        candidate487.event_scoped_recovery_autonomy_update
    )
    candidate465.generic_battle_set_controls = (
        candidate487.event_scoped_generic_battle_set_controls
    )
    candidate472.should_clear_stale_autonomy_recovery = c488_recovery_clear_guard

    # Preserve C485's ENGAGE/COUNTER live contact-commit rule. Replace only its
    # instantaneous handoff-speed gate with the event-scoped certificate model.
    candidate472._ORIGINAL_TACTICAL_DECIDE = candidate485.generic_contact_commit_decide
    candidate481._BASE_AUTONOMY_UPDATE = certified_event_scoped_autonomy_update

    print(json.dumps({
        "marker": "GENERIC_AUTONOMOUS_BATTLE_C488_ENGINEERING_READY",
        "candidate": CANDIDATE,
        "mechanism": MECHANISM,
        "approachCertificateModel": APPROACH_CERTIFICATE_MODEL,
        "affectedLayerAudit": AUDIT,
        "affectedLayerAuditStatus": "PASS",
        "failureFamily": FAILURE_FAMILY,
        "machineEvidenceSource": "C487.1_L4_RUN_78a032b8-76c7-43df-b82d-5853264fc650",
        "eventScopedRecoveryOwnershipOutermost": True,
        "outerRecoveryClearSuppressedUntilNaturalCompletion": True,
        "continuousRealizedApproachCertificate": True,
        "certificateQualifiedOutsideHandoffProximity": True,
        "certificateInvalidatedOnReadinessLoss": True,
        "certificateInvalidatedOnRecovery": True,
        "certificateInvalidatedOnTacticExit": True,
        "certificateInvalidatedOnPrecontactMiss": True,
        "certificateInvalidatedOnEventEnd": True,
        "atomicMotorToCoastAtCertifiedProximity": True,
        "currentClosingSignRequiredAfterCertifiedProximity": False,
        "c487EventTransactionScopePreserved": True,
        "c487ActualGoalReadinessPreserved": True,
        "c485CapabilityDerivedMotionFloorPreserved": True,
        "c484TranslationDominantAlignmentPreserved": True,
        "c483DriveDirectionPreserved": True,
        "c482CollisionRolesPreserved": True,
        "c480SemanticTransactionPreserved": True,
        "g05NativeSolverFinalAuthorityPreserved": True,
        "g05SourceChanged": False,
        "g06SourceChanged": False,
        "g07SourceChanged": False,
        "g08SourceChanged": False,
        "g05ThresholdImported": False,
        "contactThresholdChanged": False,
        "semanticToleranceChanged": False,
        "localityToleranceChanged": False,
        "damageAdmissionThresholdChanged": False,
        "damageThresholdAwareControl": False,
        "targetToughnessAwareControl": False,
        "desiredImpactSpeedControl": False,
        "desiredImpactEnergyControl": False,
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

    # Continue through the preserved predecessor chain without executing the now
    # superseded C485/C486/C487 top-level receipts as if their handoff mechanism
    # were still the final authority.
    candidate483.main()


if __name__ == "__main__":
    main()
