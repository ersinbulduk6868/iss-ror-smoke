from __future__ import annotations

from dataclasses import replace
import json
from pathlib import Path
import sys
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from blender import run_generic_battle_runtime_v1_candidate484_generic_battle as candidate484
from blender.iss_battle_runtime_assets import marker
from blender.iss_battle_runtime_autonomy import ClosedLoopGoalController
from blender.iss_battle_runtime_g05_handoff_readiness_v1 import (
    G05_HANDOFF_READINESS_MODEL,
    handoff_readiness_recovery_required,
    required_normal_closing_speed_mps,
)

CANDIDATE = "ISS_GENERIC_BATTLE_RUNTIME_V1_CANDIDATE_4_8_5_GENERIC_AUTONOMOUS_BATTLE"
MECHANISM = G05_HANDOFF_READINESS_MODEL
AUDIT = "G04_G05_PRE_HANDOFF_READINESS_FULL_AFFECTED_LAYER_AUDIT_20260918"
FAILURE_FAMILY = "G04_RELEASES_MOTOR_AUTHORITY_BEFORE_G05_SOLVER_ADMISSION_IS_PHYSICALLY_POSSIBLE"

_ORIGINAL_C484_ALIGNMENT_UPDATE = candidate484.alignment_aware_base_autonomy_update
_ORIGINAL_BASE_AUTONOMY_UPDATE = candidate484._ORIGINAL_BASE_AUTONOMY_UPDATE
_readiness_recovery_rows: list[dict[str, Any]] = []
_readiness_confirmed_pairs: set[tuple[str, str]] = set()


def g05_readiness_aware_base_autonomy_update(
    memory: Any,
    obs: Any,
    *,
    recovery_bias: float = 1.0,
) -> Any:
    if not bool(obs.requires_contact):
        return _ORIGINAL_C484_ALIGNMENT_UPDATE(
            memory,
            obs,
            recovery_bias=recovery_bias,
        )

    # Probe the unchanged base controller on shadow memory.  No production state is
    # mutated until we know whether the controller is actually about to hand off.
    handoff_probe = _ORIGINAL_BASE_AUTONOMY_UPDATE(
        replace(memory),
        obs,
        recovery_bias=recovery_bias,
    )
    contact_handoff_requested = bool(
        str(handoff_probe.motor_authority).upper() == "COAST"
        and str(handoff_probe.mode).upper() == "CONTACT_HANDOFF"
    )

    pair_key = candidate484._pair_key()
    if handoff_readiness_recovery_required(
        contact_handoff_requested=contact_handoff_requested,
        live_normal_closing_speed_mps=float(obs.closing_speed_mps),
    ):
        previous_mode = str(memory.mode or "")
        if not previous_mode.startswith("RECOVER_"):
            ClosedLoopGoalController._begin_recovery(
                memory,
                obs,
                "G05_PRE_HANDOFF_READINESS_INSUFFICIENT",
                recovery_bias,
            )
            row = {
                "frame": int(obs.frame),
                "attackerId": pair_key[0] or None,
                "targetId": pair_key[1] or None,
                "liveNormalClosingSpeedMps": float(obs.closing_speed_mps),
                "requiredNormalClosingSpeedMps": required_normal_closing_speed_mps(),
                "characteristicLengthM": float(obs.characteristic_length_m),
                "previousControllerMode": previous_mode,
                "recoveryMechanism": "EXISTING_CLOSED_LOOP_RECOVERY",
                "model": MECHANISM,
            }
            _readiness_recovery_rows.append(row)
            marker("G04_G05_HANDOFF_READINESS_RECOVERY_TRIGGERED", **row)

        timeout = ClosedLoopGoalController.progress_timeout_frames(obs)
        handoff_gap = ClosedLoopGoalController.contact_handoff_gap(obs)
        recovery = ClosedLoopGoalController._recovery_command(
            memory,
            obs,
            timeout,
            handoff_gap,
        )
        if recovery is None:
            # A recovery window can terminate on this exact frame.  Re-evaluate the
            # ordinary C484 path on the next frame rather than fabricating motion.
            return _ORIGINAL_C484_ALIGNMENT_UPDATE(
                memory,
                obs,
                recovery_bias=recovery_bias,
            )
        return recovery

    if contact_handoff_requested and pair_key not in _readiness_confirmed_pairs:
        _readiness_confirmed_pairs.add(pair_key)
        marker(
            "G04_G05_HANDOFF_READINESS_CONFIRMED",
            frame=int(obs.frame),
            attackerId=pair_key[0] or None,
            targetId=pair_key[1] or None,
            liveNormalClosingSpeedMps=float(obs.closing_speed_mps),
            requiredNormalClosingSpeedMps=required_normal_closing_speed_mps(),
            model=MECHANISM,
        )

    return _ORIGINAL_C484_ALIGNMENT_UPDATE(
        memory,
        obs,
        recovery_bias=recovery_bias,
    )


def main() -> None:
    _readiness_recovery_rows.clear()
    _readiness_confirmed_pairs.clear()

    # C484 owns the alignment-aware hook installed beneath C481.  Replace only that
    # hook with a generic G04->G05 readiness adapter.  All C480-C484 behavior,
    # collision roles, canonical drive direction, OBB eligibility and native G05
    # solver authority remain in the existing wrapper chain.
    candidate484.alignment_aware_base_autonomy_update = g05_readiness_aware_base_autonomy_update

    print(json.dumps({
        "marker": "GENERIC_AUTONOMOUS_BATTLE_C485_ENGINEERING_READY",
        "candidate": CANDIDATE,
        "mechanism": MECHANISM,
        "affectedLayerAudit": AUDIT,
        "failureFamily": FAILURE_FAMILY,
        "rootCause": "G04_CONTACT_HANDOFF_ONLY_REQUIRED_NONNEGATIVE_CLOSING_WHILE_LOCKED_G05_SOLVER_ORACLE_REQUIRES_PHYSICALLY_MEANINGFUL_NORMAL_CLOSING",
        "g05ReadinessUsesAuthoritativeOracleConstant": True,
        "g05ThresholdCopiedOrRetuned": False,
        "g05NativeSolverFinalAuthorityPreserved": True,
        "existingGenericRecoveryReused": True,
        "desiredImpactSpeedControl": False,
        "desiredImpactEnergyControl": False,
        "damageThresholdAwareControl": False,
        "targetToughnessAwareControl": False,
        "assetIdentityBranch": False,
        "perAssetBattleCode": False,
        "perAssetTacticalTuning": False,
        "perVideoTrajectoryEngineering": False,
        "fixedWorldCoordinates": False,
        "exactCollisionFrameTarget": False,
        "exactImpactEnergyTarget": False,
        "actorPoseOrVelocityMutation": False,
        "fixtureBattlePlanChanged": False,
        "contactThresholdChanged": False,
        "damageAdmissionThresholdChanged": False,
        "c484AlignmentLayerPreserved": True,
        "c483DriveDirectionPreserved": True,
        "c482CollisionRolesPreserved": True,
        "c481DeferredHandoffProgressPreserved": True,
        "c480ApproachSemanticTransactionPreserved": True,
        "g01ToG03Changed": False,
        "frozenNineServiceArchitectureChanged": False,
        "gateClosed": False,
        "productionReadyClaimed": False,
    }, sort_keys=True), flush=True)

    candidate484.main()


if __name__ == "__main__":
    main()
