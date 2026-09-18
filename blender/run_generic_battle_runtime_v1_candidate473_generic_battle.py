from __future__ import annotations

import json
from pathlib import Path
import sys
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from blender import iss_battle_runtime_autonomy as autonomy
from blender import run_generic_battle_runtime_v1_candidate472_generic_battle as candidate472
from blender.iss_battle_runtime_assets import marker
from blender.iss_battle_runtime_contact_truth import PairwiseSolverResponseOracle
from blender.iss_battle_runtime_handoff_readiness_v1 import (
    HANDOFF_READINESS_MODEL,
    handoff_closing_ready,
    live_recovery_bias,
)

CANDIDATE = "ISS_GENERIC_BATTLE_RUNTIME_V1_CANDIDATE_4_7_3_GENERIC_AUTONOMOUS_BATTLE"
MECHANISM = HANDOFF_READINESS_MODEL
AUDIT = "G04_HANDOFF_READINESS_RECOVERY_DIRECTION_FULL_AFFECTED_LAYER_AUDIT_20260918"
FAILURE_FAMILIES = (
    "CONTACT_HANDOFF_CEDES_AUTHORITY_BELOW_EXISTING_G05_CLOSING_GATE",
    "RECOVERY_TURN_DIRECTION_IGNORES_LIVE_GOAL_HEADING",
)

_ORIGINAL_UPDATE = autonomy.ClosedLoopGoalController.update
_ORIGINAL_BEGIN_RECOVERY = autonomy.ClosedLoopGoalController._begin_recovery
_ORIGINAL_RECOVERY_COMMAND = autonomy.ClosedLoopGoalController._recovery_command
_readiness_rejections: list[dict[str, Any]] = []
_live_recovery_rows: list[dict[str, Any]] = []


def contract_aware_update(
    memory: Any,
    obs: Any,
    *,
    recovery_bias: float = 1.0,
) -> Any:
    live_bias = live_recovery_bias(obs.heading_error_rad, recovery_bias) if obs.requires_contact else recovery_bias
    command = _ORIGINAL_UPDATE(memory, obs, recovery_bias=live_bias)

    if bool(command.replan_triggered) and obs.requires_contact:
        row = {
            "frame": int(obs.frame),
            "reason": str(command.reason),
            "headingErrorRad": float(obs.heading_error_rad),
            "legacyRecoveryBias": 1.0 if float(recovery_bias) >= 0.0 else -1.0,
            "liveRecoveryBias": float(live_bias),
            "assetIdentityBranch": False,
            "model": HANDOFF_READINESS_MODEL,
        }
        _live_recovery_rows.append(row)
        marker("GENERIC_RECOVERY_BIAS_BOUND_TO_LIVE_HEADING", **row)

    if (
        obs.requires_contact
        and str(command.mode) == "CONTACT_HANDOFF"
        and not handoff_closing_ready(
            obs.closing_speed_mps,
            PairwiseSolverResponseOracle.MIN_CLOSING_SPEED_MPS,
        )
    ):
        minimum = float(PairwiseSolverResponseOracle.MIN_CLOSING_SPEED_MPS)
        row = {
            "frame": int(obs.frame),
            "observedClosingSpeedMps": float(obs.closing_speed_mps),
            "existingG05MinimumClosingSpeedMps": minimum,
            "headingErrorRad": float(obs.heading_error_rad),
            "liveRecoveryBias": float(live_bias),
            "desiredImpactSpeedControl": False,
            "g05ThresholdChanged": False,
            "assetIdentityBranch": False,
            "model": HANDOFF_READINESS_MODEL,
        }
        _readiness_rejections.append(row)
        marker("G04_HANDOFF_REJECTED_BELOW_EXISTING_G05_CLOSING_GATE", **row)

        timeout_frames = autonomy.ClosedLoopGoalController.progress_timeout_frames(obs)
        handoff_gap = autonomy.ClosedLoopGoalController.contact_handoff_gap(obs)
        _ORIGINAL_BEGIN_RECOVERY(
            memory,
            obs,
            "HANDOFF_CLOSING_NOT_G05_ADMISSIBLE",
            live_bias,
        )
        replacement = _ORIGINAL_RECOVERY_COMMAND(
            memory,
            obs,
            timeout_frames,
            handoff_gap,
        )
        if replacement is None:
            raise RuntimeError("C473_RECOVERY_COMMAND_MISSING_AFTER_HANDOFF_REJECTION")
        replacement.replan_triggered = True
        memory.last_distance_m = obs.distance_m
        memory.last_surface_gap_m = obs.surface_gap_m
        return replacement

    return command


def main() -> None:
    _readiness_rejections.clear()
    _live_recovery_rows.clear()

    # Preserve the locked autonomy source and every C472/C471/C470/C469/C468
    # repair. Only the G04->G05 handoff boundary and recovery direction input are
    # adapted. The existing G05 minimum closing speed is consumed as a boolean
    # admissibility contract, never as a desired impact-speed target.
    autonomy.ClosedLoopGoalController.update = staticmethod(contract_aware_update)

    candidate472.CANDIDATE = CANDIDATE
    candidate472.MECHANISM = MECHANISM
    candidate472.AUDIT = AUDIT

    print(json.dumps({
        "marker": "GENERIC_AUTONOMOUS_BATTLE_C473_ENGINEERING_READY",
        "candidate": CANDIDATE,
        "mechanism": MECHANISM,
        "affectedLayerAudit": AUDIT,
        "failureFamilies": list(FAILURE_FAMILIES),
        "rootCauses": [
            "G04_HANDOFF_ACCEPTED_ANY_NONNEGATIVE_CLOSING_WHILE_G05_REQUIRES_EXISTING_MINIMUM_CLOSING",
            "RECOVERY_BIAS_WAS_EVENT_ACTOR_HASH_INSTEAD_OF_LIVE_HEADING_ERROR",
        ],
        "liveHeadingRecoveryDirection": True,
        "g05MinimumClosingUsedOnlyAsHandoffEligibility": True,
        "desiredImpactSpeedControl": False,
        "existingG05MinimumClosingThresholdChanged": False,
        "existingG05OuterAuthorityGatePreserved": True,
        "existingPairwiseSolverOraclePreserved": True,
        "c472ColliderAwareHandoffGapPreserved": True,
        "c472RecoveryRunwayOwnershipSplitPreserved": True,
        "c471TransactionBoundedLocalityPreserved": True,
        "c470LivePairSurfaceSemanticSelectionPreserved": True,
        "c469CutoffCleanupPreserved": True,
        "c468RecencyBudgetPreserved": True,
        "semanticToleranceChanged": False,
        "localityToleranceChanged": False,
        "contactThresholdChanged": False,
        "damageAdmissionThresholdChanged": False,
        "fixtureMutationForAcceptance": False,
        "perAssetBattleCode": False,
        "perVideoTrajectoryEngineering": False,
        "fixedWorldCoordinates": False,
        "exactCollisionFrameTarget": False,
        "exactImpactEnergyTarget": False,
        "actorPoseOrVelocityMutation": False,
        "forcedWinner": False,
        "stateResetMechanism": False,
        "g01ToG03Changed": False,
        "frozenNineServiceArchitectureChanged": False,
        "gateClosed": False,
        "productionReadyClaimed": False,
    }, sort_keys=True), flush=True)

    candidate472.main()


if __name__ == "__main__":
    main()
