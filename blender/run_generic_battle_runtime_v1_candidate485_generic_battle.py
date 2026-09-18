from __future__ import annotations

from dataclasses import replace
import json
from pathlib import Path
import sys
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from blender import run_generic_battle_runtime_v1_candidate483_generic_battle as candidate483
from blender import run_generic_battle_runtime_v1_candidate481_generic_battle as candidate481
from blender import run_generic_battle_runtime_v1_candidate474_generic_battle as candidate474
from blender import run_generic_battle_runtime_v1_candidate472_generic_battle as candidate472
from blender.iss_battle_runtime_assets import marker
from blender.iss_battle_runtime_autonomy import ClosedLoopGoalController
from blender.iss_battle_runtime_contact_commit_v2 import (
    CONTACT_COMMIT_MODEL,
    live_contact_commit_ready,
    realized_contact_handoff_readiness,
)
from blender.iss_battle_runtime_handoff_alignment_v1 import (
    HANDOFF_ALIGNMENT_MODEL,
    rotational_nose_speed_mps,
    should_defer_handoff_for_alignment,
    translation_dominates_rotation,
)

CANDIDATE = "ISS_GENERIC_BATTLE_RUNTIME_V1_CANDIDATE_4_8_5_GENERIC_AUTONOMOUS_BATTLE"
MECHANISM = CONTACT_COMMIT_MODEL
AUDIT = "G04_GENERIC_CONTACT_COMMIT_REALIZATION_FULL_AFFECTED_LAYER_AUDIT_20260918"
FAILURE_FAMILY = "CONTACT_COMMIT_AND_HANDOFF_PRECEDE_REALIZED_HETEROGENEOUS_APPROACH_READINESS"

_BASE_TACTICAL_DECIDE = candidate472._ORIGINAL_TACTICAL_DECIDE
_BASE_AUTONOMY_UPDATE = candidate481._BASE_AUTONOMY_UPDATE
_commit_defer_active: set[tuple[str, str]] = set()
_realization_defer_active: set[tuple[str, str]] = set()
_alignment_defer_active: set[tuple[str, str]] = set()
_commit_rows: list[dict[str, Any]] = []
_realization_rows: list[dict[str, Any]] = []
_alignment_rows: list[dict[str, Any]] = []


def _pair_key() -> tuple[str, str]:
    pair = candidate474._active_pair_context or {}
    return (
        str(pair.get("attackerId") or ""),
        str(pair.get("targetId") or ""),
    )


def generic_contact_commit_decide(
    memory: Any,
    obs: Any,
    *,
    symmetry_bias: float = 1.0,
) -> Any:
    """Apply one live-state contact-commit contract to ENGAGE and COUNTER."""
    goal = _BASE_TACTICAL_DECIDE(
        memory,
        obs,
        symmetry_bias=symmetry_bias,
    )
    if str(goal.mode).upper() not in {"ENGAGE", "COUNTER"}:
        return goal

    ready = live_contact_commit_ready(
        requires_contact=bool(obs.requires_contact),
        engagement_runway_armed=bool(memory.engagement_runway_armed),
        heading_error_rad=float(obs.heading_error_rad),
        contention=float(obs.contention),
    )
    pair_key = _pair_key()

    if bool(goal.contact_commit) and not ready:
        if pair_key not in _commit_defer_active:
            _commit_defer_active.add(pair_key)
            row = {
                "frame": int(obs.frame),
                "attackerId": pair_key[0] or None,
                "targetId": pair_key[1] or None,
                "tacticalMode": str(goal.mode),
                "headingErrorRad": float(obs.heading_error_rad),
                "contention": float(obs.contention),
                "engagementRunwayArmed": bool(memory.engagement_runway_armed),
                "model": MECHANISM,
            }
            _commit_rows.append(row)
            marker("G04_CONTACT_COMMIT_DEFERRED_BY_LIVE_READINESS", **row)
        return replace(goal, contact_commit=False)

    if ready and pair_key in _commit_defer_active:
        _commit_defer_active.discard(pair_key)
        row = {
            "frame": int(obs.frame),
            "attackerId": pair_key[0] or None,
            "targetId": pair_key[1] or None,
            "tacticalMode": str(goal.mode),
            "headingErrorRad": float(obs.heading_error_rad),
            "contention": float(obs.contention),
            "engagementRunwayArmed": bool(memory.engagement_runway_armed),
            "model": MECHANISM,
        }
        _commit_rows.append(row)
        marker("G04_CONTACT_COMMIT_LIVE_READINESS_READY", **row)

    if bool(goal.contact_commit) != ready:
        return replace(goal, contact_commit=ready)
    return goal


def realized_and_alignment_aware_base_autonomy_update(
    memory: Any,
    obs: Any,
    *,
    recovery_bias: float = 1.0,
) -> Any:
    """Require realized approach motion, then preserve C484 alignment semantics.

    G04 may request G05 solver authority only after live chassis motion has
    physically realized the existing capability-derived engagement floor. A weak
    or unrealized near-contact attempt is recovered and replanned by the existing
    generic recovery mechanism instead of being allowed to coast indefinitely.
    """
    if not bool(obs.requires_contact):
        return _BASE_AUTONOMY_UPDATE(
            memory,
            obs,
            recovery_bias=recovery_bias,
        )

    handoff_probe = _BASE_AUTONOMY_UPDATE(
        replace(memory),
        obs,
        recovery_bias=recovery_bias,
    )
    contact_handoff_requested = bool(
        str(handoff_probe.motor_authority).upper() == "COAST"
        and str(handoff_probe.mode).upper() == "CONTACT_HANDOFF"
    )
    if not contact_handoff_requested:
        return _BASE_AUTONOMY_UPDATE(
            memory,
            obs,
            recovery_bias=recovery_bias,
        )

    pair_key = _pair_key()
    realized = realized_contact_handoff_readiness(
        max_speed_mps=float(obs.max_speed_mps),
        acceleration_mps2=float(obs.acceleration_mps2),
        characteristic_length_m=float(obs.characteristic_length_m),
        drive_efficiency=float(obs.drive_efficiency),
        realized_forward_speed_mps=float(obs.forward_speed_mps),
        realized_closing_speed_mps=float(obs.closing_speed_mps),
    )

    if not realized.ready:
        if pair_key not in _realization_defer_active:
            _realization_defer_active.add(pair_key)
            row = {
                "frame": int(obs.frame),
                "attackerId": pair_key[0] or None,
                "targetId": pair_key[1] or None,
                "capabilityFloorMps": realized.capability_floor_mps,
                "realizedForwardSpeedMps": realized.realized_forward_speed_mps,
                "realizedClosingSpeedMps": realized.realized_closing_speed_mps,
                "characteristicLengthM": float(obs.characteristic_length_m),
                "model": MECHANISM,
            }
            _realization_rows.append(row)
            marker("G04_CONTACT_HANDOFF_DEFERRED_BY_REALIZED_APPROACH", **row)

        if not str(memory.mode or "").upper().startswith("RECOVER_"):
            ClosedLoopGoalController._begin_recovery(
                memory,
                obs,
                "PREHANDOFF_REALIZED_APPROACH_NOT_READY",
                recovery_bias,
            )
        timeout_frames = ClosedLoopGoalController.progress_timeout_frames(obs)
        handoff_gap = ClosedLoopGoalController.contact_handoff_gap(obs)
        command = ClosedLoopGoalController._recovery_command(
            memory,
            obs,
            timeout_frames,
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

    if pair_key in _realization_defer_active:
        _realization_defer_active.discard(pair_key)
        row = {
            "frame": int(obs.frame),
            "attackerId": pair_key[0] or None,
            "targetId": pair_key[1] or None,
            "capabilityFloorMps": realized.capability_floor_mps,
            "realizedForwardSpeedMps": realized.realized_forward_speed_mps,
            "realizedClosingSpeedMps": realized.realized_closing_speed_mps,
            "characteristicLengthM": float(obs.characteristic_length_m),
            "model": MECHANISM,
        }
        _realization_rows.append(row)
        marker("G04_CONTACT_HANDOFF_REALIZED_APPROACH_READY", **row)

    # Preserve C484's independent geometry-derived check: even with sufficient
    # realized approach speed, do not hand off while the prospective command is
    # still rotation-dominant at the chassis nose.
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
        if pair_key not in _alignment_defer_active:
            _alignment_defer_active.add(pair_key)
            row = {
                "frame": int(obs.frame),
                "attackerId": pair_key[0] or None,
                "targetId": pair_key[1] or None,
                "prospectiveMotorAuthority": str(motor_probe.motor_authority),
                "prospectiveForwardSpeedMps": prospective_forward,
                "prospectiveYawRateRadS": prospective_yaw,
                "rotationalNoseSpeedMps": rotational_nose_speed,
                "characteristicLengthM": characteristic_length,
                "translationDominant": translation_dominant,
                "model": HANDOFF_ALIGNMENT_MODEL,
            }
            _alignment_rows.append(row)
            marker("G04_CONTACT_HANDOFF_DEFERRED_BY_ROTATIONAL_DOMINANCE", **row)
        return _BASE_AUTONOMY_UPDATE(
            memory,
            motor_obs,
            recovery_bias=recovery_bias,
        )

    if pair_key in _alignment_defer_active:
        _alignment_defer_active.discard(pair_key)
        row = {
            "frame": int(obs.frame),
            "attackerId": pair_key[0] or None,
            "targetId": pair_key[1] or None,
            "prospectiveMotorAuthority": str(motor_probe.motor_authority),
            "prospectiveForwardSpeedMps": prospective_forward,
            "prospectiveYawRateRadS": prospective_yaw,
            "rotationalNoseSpeedMps": rotational_nose_speed,
            "characteristicLengthM": characteristic_length,
            "translationDominant": translation_dominant,
            "model": HANDOFF_ALIGNMENT_MODEL,
        }
        _alignment_rows.append(row)
        marker("G04_CONTACT_HANDOFF_ALIGNMENT_READY", **row)

    return _BASE_AUTONOMY_UPDATE(
        memory,
        obs,
        recovery_bias=recovery_bias,
    )


def main() -> None:
    _commit_defer_active.clear()
    _realization_defer_active.clear()
    _alignment_defer_active.clear()
    _commit_rows.clear()
    _realization_rows.clear()
    _alignment_rows.clear()

    # Patch only the established generic extension points. Historical candidate
    # source stays immutable; C474 progress ownership, C480 semantic transaction,
    # C481 stall recovery, C482 collision roles and C483 drive mapping remain in
    # their existing chain.
    candidate472._ORIGINAL_TACTICAL_DECIDE = generic_contact_commit_decide
    candidate481._BASE_AUTONOMY_UPDATE = realized_and_alignment_aware_base_autonomy_update

    print(json.dumps({
        "marker": "GENERIC_AUTONOMOUS_BATTLE_C485_ENGINEERING_READY",
        "candidate": CANDIDATE,
        "mechanism": MECHANISM,
        "affectedLayerAudit": AUDIT,
        "failureFamily": FAILURE_FAMILY,
        "rootCauses": [
            "COUNTER_CONTACT_COMMIT_BYPASSED_EXISTING_LIVE_HEADING_AND_CONTENTION_READINESS",
            "HANDOFF_READINESS_USED_COMMAND_INTENT_WITHOUT_REQUIRING_REALIZED_PAIRWISE_APPROACH",
            "WEAK_NEAR_CONTACT_COULD_ENTER_SOLVER_LATCH_WITHOUT_ENOUGH_REALIZED_G04_MOTION",
        ],
        "singleCommitContractAcrossEngageAndCounter": True,
        "realizedForwardMotionRequiredBeforeHandoff": True,
        "realizedPairwiseClosingRequiredBeforeHandoff": True,
        "capabilityDerivedMotionFloor": True,
        "existingGenericRecoveryReused": True,
        "c484TranslationDominantAlignmentPreserved": True,
        "c483DriveDirectionPreserved": True,
        "c482CollisionRolesPreserved": True,
        "c481DeferredHandoffProgressPreserved": True,
        "c480ApproachSemanticTransactionPreserved": True,
        "c474ObbHandoffEligibilityPreserved": True,
        "g05NativeSolverFinalAuthorityPreserved": True,
        "g05ThresholdImported": False,
        "contactThresholdChanged": False,
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
        "g01ToG03Changed": False,
        "frozenNineServiceArchitectureChanged": False,
        "gateClosed": False,
        "productionReadyClaimed": False,
    }, sort_keys=True), flush=True)

    candidate483.main()


if __name__ == "__main__":
    main()
