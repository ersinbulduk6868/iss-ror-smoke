from __future__ import annotations

import json
from pathlib import Path
import sys
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from blender import run_generic_battle_runtime_v1_candidate480_generic_battle as candidate480
from blender import run_generic_battle_runtime_v1_candidate474_generic_battle as candidate474
from blender import run_generic_battle_runtime_v1_candidate472_generic_battle as candidate472
from blender.iss_battle_runtime_assets import marker
from blender.iss_battle_runtime_autonomy import ClosedLoopGoalController
from blender.iss_battle_runtime_handoff_progress_v1 import (
    HANDOFF_DEFER_PROGRESS_MODEL,
    deferred_handoff_stalled,
)

CANDIDATE = "ISS_GENERIC_BATTLE_RUNTIME_V1_CANDIDATE_4_8_1_GENERIC_AUTONOMOUS_BATTLE"
MECHANISM = HANDOFF_DEFER_PROGRESS_MODEL
AUDIT = "G04_DEFERRED_HANDOFF_PROGRESS_FULL_AFFECTED_LAYER_AUDIT_20260918"
FAILURE_FAMILY = "RADIAL_NAVIGATION_AND_OBB_HANDOFF_SPLIT_GEOMETRY_DEAD_ZONE"

_BASE_AUTONOMY_UPDATE = candidate472._ORIGINAL_AUTONOMY_UPDATE
_recovery_rows: list[dict[str, Any]] = []


def defer_progress_aware_base_autonomy_update(
    memory: Any,
    obs: Any,
    *,
    recovery_bias: float = 1.0,
) -> Any:
    pair = candidate474._active_pair_context or {}
    pair_key = (
        str(pair.get("attackerId") or ""),
        str(pair.get("targetId") or ""),
    )
    deferred = bool(pair_key[0] and pair_key[1] and pair_key in candidate474._defer_active)
    effective_gap = pair.get("effectiveCollisionProxyGapM")
    handoff_gap = ClosedLoopGoalController.contact_handoff_gap(obs)
    timeout = ClosedLoopGoalController.progress_timeout_frames(obs)
    previous_progress_frame = int(memory.last_progress_frame)

    if deferred_handoff_stalled(
        handoff_deferred=deferred,
        effective_collision_proxy_gap_m=(float(effective_gap) if effective_gap is not None else None),
        existing_handoff_gap_m=float(handoff_gap),
        last_command_speed_mps=float(memory.last_command_speed_mps),
        frame=int(obs.frame),
        last_progress_frame=previous_progress_frame,
        progress_timeout_frames=int(timeout),
        controller_mode=str(memory.mode or ""),
    ):
        ClosedLoopGoalController._begin_recovery(
            memory,
            obs,
            "COLLISION_PROXY_STALL_NO_PROGRESS",
            recovery_bias,
        )
        row = {
            "frame": int(obs.frame),
            "attackerId": pair_key[0] or None,
            "targetId": pair_key[1] or None,
            "effectiveCollisionProxyGapM": float(effective_gap),
            "existingHandoffGapM": float(handoff_gap),
            "previousLastProgressFrame": previous_progress_frame,
            "progressTimeoutFrames": int(timeout),
            "model": MECHANISM,
        }
        _recovery_rows.append(row)
        marker("G04_DEFERRED_HANDOFF_STALL_RECOVERY_TRIGGERED", **row)

    return _BASE_AUTONOMY_UPDATE(
        memory,
        obs,
        recovery_bias=recovery_bias,
    )


def main() -> None:
    _recovery_rows.clear()

    # C474 owns tactical/navigation geometry and the OBB handoff-defer decision.
    # C481 changes neither.  It only lets the already-existing low-level recovery
    # clock observe a stall in that deferred physical approach, preventing a state
    # where radial navigation says "near" while the collision proxy remains apart.
    candidate472._ORIGINAL_AUTONOMY_UPDATE = defer_progress_aware_base_autonomy_update

    print(json.dumps({
        "marker": "GENERIC_AUTONOMOUS_BATTLE_C481_ENGINEERING_READY",
        "candidate": CANDIDATE,
        "mechanism": MECHANISM,
        "affectedLayerAudit": AUDIT,
        "failureFamily": FAILURE_FAMILY,
        "rootCause": "LOW_LEVEL_STALL_RECOVERY_OBSERVED_RADIAL_GAP_WHILE_HANDOFF_ELIGIBILITY_OBSERVED_OBB_PROXY_GAP",
        "c480ApproachSemanticTransactionPreserved": True,
        "radialNavigationContractPreserved": True,
        "c474ObbHandoffEligibilityPreserved": True,
        "collisionProxyProgressClockReused": True,
        "existingProgressTimeoutReused": True,
        "existingRecoveryMechanismReused": True,
        "newRecoveryTrajectoryIntroduced": False,
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

    candidate480.main()


if __name__ == "__main__":
    main()
