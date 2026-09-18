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
from blender.iss_battle_runtime_assets import marker
from blender.iss_battle_runtime_handoff_alignment_v1 import (
    HANDOFF_ALIGNMENT_MODEL,
    rotational_nose_speed_mps,
    should_defer_handoff_for_alignment,
    translation_dominates_rotation,
)

CANDIDATE = "ISS_GENERIC_BATTLE_RUNTIME_V1_CANDIDATE_4_8_4_GENERIC_AUTONOMOUS_BATTLE"
MECHANISM = HANDOFF_ALIGNMENT_MODEL
AUDIT = "G04_PREHANDOFF_ALIGNMENT_FULL_AFFECTED_LAYER_AUDIT_20260918"
FAILURE_FAMILY = "SOLVER_HANDOFF_BEGINS_WHILE_CONTACT_APPROACH_IS_ROTATIONALLY_DOMINANT"

_ORIGINAL_BASE_AUTONOMY_UPDATE = candidate481._BASE_AUTONOMY_UPDATE
_alignment_defer_active: set[tuple[str, str]] = set()
_alignment_defer_rows: list[dict[str, Any]] = []
_alignment_ready_rows: list[dict[str, Any]] = []


def _pair_key() -> tuple[str, str]:
    pair = candidate474._active_pair_context or {}
    return (
        str(pair.get("attackerId") or ""),
        str(pair.get("targetId") or ""),
    )


def alignment_aware_base_autonomy_update(
    memory: Any,
    obs: Any,
    *,
    recovery_bias: float = 1.0,
) -> Any:
    """Preserve motor authority until the live contact approach is translation-dominant.

    Two shadow-memory probes reuse the established closed-loop controller without
    mutating production memory.  The real memory is updated exactly once.
    """
    if not bool(obs.requires_contact):
        return _ORIGINAL_BASE_AUTONOMY_UPDATE(
            memory,
            obs,
            recovery_bias=recovery_bias,
        )

    handoff_probe = _ORIGINAL_BASE_AUTONOMY_UPDATE(
        replace(memory),
        obs,
        recovery_bias=recovery_bias,
    )
    contact_handoff_requested = bool(
        str(handoff_probe.motor_authority).upper() == "COAST"
        and str(handoff_probe.mode).upper() == "CONTACT_HANDOFF"
    )
    if not contact_handoff_requested:
        return _ORIGINAL_BASE_AUTONOMY_UPDATE(
            memory,
            obs,
            recovery_bias=recovery_bias,
        )

    motor_obs = replace(obs, requires_contact=False)
    motor_probe = _ORIGINAL_BASE_AUTONOMY_UPDATE(
        replace(memory),
        motor_obs,
        recovery_bias=recovery_bias,
    )
    forward_speed = float(motor_probe.forward_speed_mps)
    yaw_rate = float(motor_probe.yaw_rate_rad_s)
    characteristic_length = max(0.0, float(obs.characteristic_length_m))
    rotational_nose_speed = rotational_nose_speed_mps(
        yaw_rate_rad_s=yaw_rate,
        characteristic_length_m=characteristic_length,
    )
    translation_dominant = translation_dominates_rotation(
        forward_speed_mps=forward_speed,
        yaw_rate_rad_s=yaw_rate,
        characteristic_length_m=characteristic_length,
    )
    defer = should_defer_handoff_for_alignment(
        contact_handoff_requested=contact_handoff_requested,
        prospective_motor_authority=str(motor_probe.motor_authority),
        forward_speed_mps=forward_speed,
        yaw_rate_rad_s=yaw_rate,
        characteristic_length_m=characteristic_length,
    )
    pair_key = _pair_key()

    if defer:
        if pair_key not in _alignment_defer_active:
            _alignment_defer_active.add(pair_key)
            row = {
                "frame": int(obs.frame),
                "attackerId": pair_key[0] or None,
                "targetId": pair_key[1] or None,
                "prospectiveMotorAuthority": str(motor_probe.motor_authority),
                "prospectiveForwardSpeedMps": forward_speed,
                "prospectiveYawRateRadS": yaw_rate,
                "rotationalNoseSpeedMps": rotational_nose_speed,
                "characteristicLengthM": characteristic_length,
                "translationDominant": translation_dominant,
                "model": MECHANISM,
            }
            _alignment_defer_rows.append(row)
            marker("G04_CONTACT_HANDOFF_DEFERRED_BY_ROTATIONAL_DOMINANCE", **row)
        return _ORIGINAL_BASE_AUTONOMY_UPDATE(
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
            "prospectiveForwardSpeedMps": forward_speed,
            "prospectiveYawRateRadS": yaw_rate,
            "rotationalNoseSpeedMps": rotational_nose_speed,
            "characteristicLengthM": characteristic_length,
            "translationDominant": translation_dominant,
            "model": MECHANISM,
        }
        _alignment_ready_rows.append(row)
        marker("G04_CONTACT_HANDOFF_ALIGNMENT_READY", **row)

    return _ORIGINAL_BASE_AUTONOMY_UPDATE(
        memory,
        obs,
        recovery_bias=recovery_bias,
    )


def main() -> None:
    _alignment_defer_active.clear()
    _alignment_defer_rows.clear()
    _alignment_ready_rows.clear()

    # C481 remains the owner of deferred-handoff stall recovery.  C484 only
    # replaces the base controller call beneath it, so C474 OBB eligibility,
    # C481 recovery, C480 semantic transactions, C482 collision roles and C483
    # drive-direction mapping remain in the established wrapper chain.
    candidate481._BASE_AUTONOMY_UPDATE = alignment_aware_base_autonomy_update

    print(json.dumps({
        "marker": "GENERIC_AUTONOMOUS_BATTLE_C484_ENGINEERING_READY",
        "candidate": CANDIDATE,
        "mechanism": MECHANISM,
        "affectedLayerAudit": AUDIT,
        "failureFamily": FAILURE_FAMILY,
        "rootCause": "G04_CONTACT_HANDOFF_USED_PROXIMITY_AND_CLOSING_SIGN_WITHOUT_CHECKING_WHETHER_LIVE_CHASSIS_MOTION_WAS_STILL_ROTATIONALLY_DOMINANT",
        "translationVsRotationDerivedFromLiveControllerCommand": True,
        "rotationalLeverArmDerivedFromCharacteristicLength": True,
        "shadowMemoryProbeOnly": True,
        "realMemoryUpdatedOncePerFrame": True,
        "c483DriveDirectionPreserved": True,
        "c482CollisionRolesPreserved": True,
        "c481DeferredHandoffProgressPreserved": True,
        "c480ApproachSemanticTransactionPreserved": True,
        "c474ObbHandoffEligibilityPreserved": True,
        "g05NativeSolverFinalAuthorityPreserved": True,
        "pairwiseSolverOraclePreserved": True,
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
        "g01ToG03Changed": False,
        "frozenNineServiceArchitectureChanged": False,
        "gateClosed": False,
        "productionReadyClaimed": False,
    }, sort_keys=True), flush=True)

    candidate483.main()


if __name__ == "__main__":
    main()
