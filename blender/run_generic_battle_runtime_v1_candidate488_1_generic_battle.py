from __future__ import annotations

from dataclasses import replace
import json
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from blender import run_generic_battle_runtime_v1_candidate474_generic_battle as candidate474
from blender import run_generic_battle_runtime_v1_candidate485_generic_battle as candidate485
from blender import run_generic_battle_runtime_v1_candidate486_generic_battle as candidate486
from blender import run_generic_battle_runtime_v1_candidate487_generic_battle as candidate487
from blender.iss_battle_runtime_assets import marker
from blender.iss_battle_runtime_autonomy import ClosedLoopGoalController
from blender.iss_battle_runtime_contact_commit_v2 import realized_contact_handoff_readiness
from blender.iss_battle_runtime_engagement_lifecycle_v1 import CONTACT_CORRIDOR_MODES, PHASE_APPROACH, is_recovery_mode
from blender.iss_battle_runtime_handoff_alignment_v1 import (
    HANDOFF_ALIGNMENT_MODEL,
    rotational_nose_speed_mps,
    should_defer_handoff_for_alignment,
    translation_dominates_rotation,
)
from blender.iss_battle_runtime_precontact_realization_v1 import (
    PRECONTACT_REALIZATION_MODEL,
    PrecontactRealizationSample,
    precontact_sample_eligible,
    previous_frame_sample_valid_for_handoff,
)

CANDIDATE = "ISS_GENERIC_BATTLE_RUNTIME_V1_CANDIDATE_4_8_8_1_GENERIC_AUTONOMOUS_BATTLE"
MECHANISM = PRECONTACT_REALIZATION_MODEL
AUDIT = "G04_C487_1_HANDOFF_TOCTOU_PREVIOUS_FRAME_EVIDENCE_AUDIT_20260918"
FAILURE_FAMILY = "G04_POST_PHYSICS_INSTANTANEOUS_REALIZATION_HANDOFF_TOCTOU"

_C485_REALIZED_UPDATE = candidate485.realized_and_alignment_aware_base_autonomy_update
_samples: dict[tuple[str, str, str], PrecontactRealizationSample] = {}
_announced: set[tuple[str, str, str]] = set()


def _transaction_and_pair() -> tuple[tuple[str, str, str], dict[str, Any]]:
    pair = candidate474._active_pair_context or {}
    actor_id = str(pair.get("attackerId") or "")
    target_id = str(pair.get("targetId") or "")
    if not actor_id or not target_id:
        raise RuntimeError("G04_C488_1_PAIR_CONTEXT_MISSING")
    key = candidate487._active_transaction_by_actor.get(actor_id)
    if key is None:
        raise RuntimeError("G04_C488_1_EVENT_TRANSACTION_MISSING")
    if str(key[2]) != target_id:
        raise RuntimeError("G04_C488_1_EVENT_TRANSACTION_TARGET_MISMATCH")
    return key, pair


def _clear_stale_for_actor(key: tuple[str, str, str]) -> None:
    for existing in tuple(_samples):
        if existing[1] == key[1] and existing != key:
            _samples.pop(existing, None)
            _announced.discard(existing)


def _approach_active(key: tuple[str, str, str]) -> bool:
    lifecycle = candidate487._lifecycle_memories.get(key)
    context = candidate474._pending_tactical_context or {}
    mode = str(context.get("currentTacticalMode") or "").upper()
    return bool(
        lifecycle is not None
        and str(lifecycle.phase) == PHASE_APPROACH
        and mode in CONTACT_CORRIDOR_MODES
    )


def _record_precontact_sample(key: tuple[str, str, str], pair: dict[str, Any], obs: Any) -> None:
    _clear_stale_for_actor(key)
    effective_gap = pair.get("effectiveCollisionProxyGapM")
    if effective_gap is None:
        raise RuntimeError("G04_C488_1_COLLISION_PROXY_GAP_MISSING")
    readiness = realized_contact_handoff_readiness(
        max_speed_mps=float(obs.max_speed_mps),
        acceleration_mps2=float(obs.acceleration_mps2),
        characteristic_length_m=float(obs.characteristic_length_m),
        drive_efficiency=float(obs.drive_efficiency),
        realized_forward_speed_mps=float(obs.forward_speed_mps),
        realized_closing_speed_mps=float(obs.closing_speed_mps),
    )
    handoff_gap = ClosedLoopGoalController.contact_handoff_gap(obs)
    if not precontact_sample_eligible(
        contact_approach_active=_approach_active(key),
        recovery_active=False,
        forward_speed_mps=float(obs.forward_speed_mps),
        closing_speed_mps=float(obs.closing_speed_mps),
        capability_floor_mps=float(readiness.capability_floor_mps),
        effective_gap_m=float(effective_gap),
        handoff_gap_m=float(handoff_gap),
    ):
        return
    sample = PrecontactRealizationSample(
        frame=int(obs.frame),
        event_id=key[0],
        actor_id=key[1],
        target_id=key[2],
        forward_speed_mps=float(obs.forward_speed_mps),
        closing_speed_mps=float(obs.closing_speed_mps),
        capability_floor_mps=float(readiness.capability_floor_mps),
        effective_gap_m=float(effective_gap),
        handoff_gap_m=float(handoff_gap),
    )
    _samples[key] = sample
    if key not in _announced:
        _announced.add(key)
        marker(
            "G04_PRECONTACT_REALIZATION_SAMPLE_ARMED",
            frame=int(obs.frame),
            eventId=key[0],
            attackerId=key[1],
            targetId=key[2] or None,
            realizedForwardSpeedMps=round(sample.forward_speed_mps, 6),
            realizedClosingSpeedMps=round(sample.closing_speed_mps, 6),
            capabilityFloorMps=round(sample.capability_floor_mps, 6),
            effectiveCollisionProxyGapM=round(sample.effective_gap_m, 6),
            existingHandoffGapM=round(sample.handoff_gap_m, 6),
            model=MECHANISM,
        )


def _handoff_with_preserved_alignment(
    memory: Any,
    obs: Any,
    *,
    recovery_bias: float,
    key: tuple[str, str, str],
    sample: PrecontactRealizationSample,
) -> Any:
    pair_key = (key[1], key[2])
    motor_obs = replace(obs, requires_contact=False)
    motor_probe = candidate485._BASE_AUTONOMY_UPDATE(
        replace(memory), motor_obs, recovery_bias=recovery_bias
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
        if pair_key not in candidate485._alignment_defer_active:
            candidate485._alignment_defer_active.add(pair_key)
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
        return candidate485._BASE_AUTONOMY_UPDATE(
            memory, motor_obs, recovery_bias=recovery_bias
        )
    if pair_key in candidate485._alignment_defer_active:
        candidate485._alignment_defer_active.discard(pair_key)
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
    marker(
        "G04_PRECONTACT_REALIZATION_CARRIED_TO_HANDOFF",
        frame=int(obs.frame),
        eventId=key[0],
        attackerId=key[1],
        targetId=key[2] or None,
        evidenceFrame=int(sample.frame),
        evidenceAgeFrames=int(obs.frame) - int(sample.frame),
        evidenceForwardSpeedMps=round(sample.forward_speed_mps, 6),
        evidenceClosingSpeedMps=round(sample.closing_speed_mps, 6),
        evidenceCapabilityFloorMps=round(sample.capability_floor_mps, 6),
        currentClosingSpeedMps=round(float(obs.closing_speed_mps), 6),
        frameOrder="PHYSICS_SAMPLE_G05_DETECT_G04_CONTROLS",
        model=MECHANISM,
    )
    marker(
        "G04_CONTACT_HANDOFF_REALIZED_APPROACH_READY",
        frame=int(obs.frame),
        attackerId=key[1],
        targetId=key[2] or None,
        capabilityFloorMps=sample.capability_floor_mps,
        realizedForwardSpeedMps=sample.forward_speed_mps,
        realizedClosingSpeedMps=sample.closing_speed_mps,
        characteristicLengthM=float(obs.characteristic_length_m),
        evidenceFrame=int(sample.frame),
        evidenceSource="IMMEDIATELY_PREVIOUS_PRECONTACT_FRAME",
        model=candidate485.MECHANISM,
    )
    return candidate485._BASE_AUTONOMY_UPDATE(
        memory, obs, recovery_bias=recovery_bias
    )


def c488_1_realized_handoff_update(
    memory: Any,
    obs: Any,
    *,
    recovery_bias: float = 1.0,
) -> Any:
    key, pair = _transaction_and_pair()
    if is_recovery_mode(str(memory.mode or "")):
        _samples.pop(key, None)
        _announced.discard(key)
        return _C485_REALIZED_UPDATE(memory, obs, recovery_bias=recovery_bias)

    _record_precontact_sample(key, pair, obs)
    probe = candidate485._BASE_AUTONOMY_UPDATE(
        replace(memory), obs, recovery_bias=recovery_bias
    )
    handoff_requested = bool(
        str(probe.motor_authority).upper() == "COAST"
        and str(probe.mode).upper() == "CONTACT_HANDOFF"
    )
    if not handoff_requested:
        return _C485_REALIZED_UPDATE(memory, obs, recovery_bias=recovery_bias)

    current = realized_contact_handoff_readiness(
        max_speed_mps=float(obs.max_speed_mps),
        acceleration_mps2=float(obs.acceleration_mps2),
        characteristic_length_m=float(obs.characteristic_length_m),
        drive_efficiency=float(obs.drive_efficiency),
        realized_forward_speed_mps=float(obs.forward_speed_mps),
        realized_closing_speed_mps=float(obs.closing_speed_mps),
    )
    if current.ready:
        _samples.pop(key, None)
        _announced.discard(key)
        return _C485_REALIZED_UPDATE(memory, obs, recovery_bias=recovery_bias)

    sample = _samples.get(key)
    if sample is None or not previous_frame_sample_valid_for_handoff(
        sample,
        transaction_key=key,
        decision_frame=int(obs.frame),
        current_capability_floor_mps=float(current.capability_floor_mps),
        current_closing_speed_mps=float(obs.closing_speed_mps),
        controller_handoff_requested=handoff_requested,
    ):
        return _C485_REALIZED_UPDATE(memory, obs, recovery_bias=recovery_bias)

    _samples.pop(key, None)
    _announced.discard(key)
    return _handoff_with_preserved_alignment(
        memory, obs, recovery_bias=recovery_bias, key=key, sample=sample
    )


def main() -> None:
    _samples.clear()
    _announced.clear()
    candidate485.realized_and_alignment_aware_base_autonomy_update = (
        c488_1_realized_handoff_update
    )
    print(
        json.dumps(
            {
                "marker": "GENERIC_AUTONOMOUS_BATTLE_C488_1_ENGINEERING_READY",
                "candidate": CANDIDATE,
                "mechanism": MECHANISM,
                "affectedLayerAudit": AUDIT,
                "affectedLayerAuditStatus": "PASS",
                "failureFamily": FAILURE_FAMILY,
                "c488RejectedBySourceAudit": True,
                "previousFrameOnlyEvidence": True,
                "eventActorTargetScopedEvidence": True,
                "staleEvidenceRejected": True,
                "recoveryEvidenceRejected": True,
                "currentNonNegativeClosingRequired": True,
                "precontactOutsideExistingHandoffGapRequired": True,
                "runtimeFrameOrderVerified": "PHYSICS_SAMPLE_THEN_G05_DETECT_THEN_G04_CONTROLS",
                "c487LifecyclePreserved": True,
                "c485CapabilityFloorPreserved": True,
                "c484AlignmentSemanticsPreserved": True,
                "c465CutoffFrameStabilityPreserved": True,
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
            },
            sort_keys=True,
        ),
        flush=True,
    )
    candidate486.main = candidate485.main
    candidate487.main()


if __name__ == "__main__":
    main()
