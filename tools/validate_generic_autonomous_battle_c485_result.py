#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
TOOLS = ROOT / "tools"
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

import validate_generic_autonomous_battle_c483_result as c483
from validate_generic_autonomous_battle_c480_result import _json_markers

CONTACT_COMMIT_MODEL = "G04_GENERIC_REALIZED_CONTACT_COMMIT_V2"


def c485_runtime_proof(log_path: str) -> dict[str, object]:
    rows = _json_markers(log_path)
    ready = [
        r for r in rows
        if r.get("marker") == "GENERIC_AUTONOMOUS_BATTLE_C485_ENGINEERING_READY"
    ]
    assert len(ready) == 1, ("C485_ENGINEERING_READY_COUNT", len(ready))
    receipt = ready[0]
    assert receipt.get("candidate") == "ISS_GENERIC_BATTLE_RUNTIME_V1_CANDIDATE_4_8_5_GENERIC_AUTONOMOUS_BATTLE", receipt
    assert receipt.get("mechanism") == CONTACT_COMMIT_MODEL, receipt
    assert receipt.get("singleCommitContractAcrossEngageAndCounter") is True, receipt
    assert receipt.get("realizedForwardMotionRequiredBeforeHandoff") is True, receipt
    assert receipt.get("realizedPairwiseClosingRequiredBeforeHandoff") is True, receipt
    assert receipt.get("capabilityDerivedMotionFloor") is True, receipt
    assert receipt.get("existingGenericRecoveryReused") is True, receipt
    assert receipt.get("c484TranslationDominantAlignmentPreserved") is True, receipt
    assert receipt.get("c483DriveDirectionPreserved") is True, receipt
    assert receipt.get("c482CollisionRolesPreserved") is True, receipt
    assert receipt.get("c481DeferredHandoffProgressPreserved") is True, receipt
    assert receipt.get("c480ApproachSemanticTransactionPreserved") is True, receipt
    assert receipt.get("c474ObbHandoffEligibilityPreserved") is True, receipt
    assert receipt.get("g05NativeSolverFinalAuthorityPreserved") is True, receipt
    assert receipt.get("g05ThresholdImported") is False, receipt
    assert receipt.get("contactThresholdChanged") is False, receipt
    assert receipt.get("damageAdmissionThresholdChanged") is False, receipt
    assert receipt.get("damageThresholdAwareControl") is False, receipt
    assert receipt.get("targetToughnessAwareControl") is False, receipt
    assert receipt.get("desiredImpactSpeedControl") is False, receipt
    assert receipt.get("desiredImpactEnergyControl") is False, receipt
    assert receipt.get("assetIdentityBranch") is False, receipt
    assert receipt.get("perAssetBattleCode") is False, receipt
    assert receipt.get("perAssetTacticalTuning") is False, receipt
    assert receipt.get("perVideoTrajectoryEngineering") is False, receipt
    assert receipt.get("fixedWorldCoordinates") is False, receipt
    assert receipt.get("actorPoseOrVelocityMutation") is False, receipt
    assert receipt.get("fixtureBattlePlanChanged") is False, receipt

    commit_deferred = [
        r for r in rows
        if r.get("marker") == "G04_CONTACT_COMMIT_DEFERRED_BY_LIVE_READINESS"
    ]
    commit_ready = [
        r for r in rows
        if r.get("marker") == "G04_CONTACT_COMMIT_LIVE_READINESS_READY"
    ]
    realized_deferred = [
        r for r in rows
        if r.get("marker") == "G04_CONTACT_HANDOFF_DEFERRED_BY_REALIZED_APPROACH"
    ]
    realized_ready = [
        r for r in rows
        if r.get("marker") == "G04_CONTACT_HANDOFF_REALIZED_APPROACH_READY"
    ]

    assert commit_deferred, "C485_LIVE_CONTACT_COMMIT_DEFER_NOT_OBSERVED"
    assert commit_ready, "C485_LIVE_CONTACT_COMMIT_READY_NOT_OBSERVED"
    assert realized_deferred, "C485_REALIZED_APPROACH_DEFER_NOT_OBSERVED"
    assert realized_ready, "C485_REALIZED_APPROACH_READY_NOT_OBSERVED"

    commit_deferred_pairs = {
        (str(r.get("attackerId") or ""), str(r.get("targetId") or ""))
        for r in commit_deferred
    }
    commit_ready_pairs = {
        (str(r.get("attackerId") or ""), str(r.get("targetId") or ""))
        for r in commit_ready
    }
    realized_deferred_pairs = {
        (str(r.get("attackerId") or ""), str(r.get("targetId") or ""))
        for r in realized_deferred
    }
    realized_ready_pairs = {
        (str(r.get("attackerId") or ""), str(r.get("targetId") or ""))
        for r in realized_ready
    }
    for pairs in (
        commit_deferred_pairs,
        commit_ready_pairs,
        realized_deferred_pairs,
        realized_ready_pairs,
    ):
        assert pairs and all(a and b for a, b in pairs), pairs

    assert commit_deferred_pairs & commit_ready_pairs, (
        "C485_NO_PAIR_TRANSITIONED_FROM_COMMIT_DEFER_TO_READY",
        sorted(commit_deferred_pairs), sorted(commit_ready_pairs),
    )
    assert realized_deferred_pairs & realized_ready_pairs, (
        "C485_NO_PAIR_TRANSITIONED_FROM_REALIZATION_DEFER_TO_READY",
        sorted(realized_deferred_pairs), sorted(realized_ready_pairs),
    )

    for row in realized_deferred:
        floor = float(row.get("capabilityFloorMps"))
        forward = float(row.get("realizedForwardSpeedMps"))
        closing = float(row.get("realizedClosingSpeedMps"))
        assert floor > 0.0, row
        assert forward < floor or closing < floor, row

    for row in realized_ready:
        floor = float(row.get("capabilityFloorMps"))
        forward = float(row.get("realizedForwardSpeedMps"))
        closing = float(row.get("realizedClosingSpeedMps"))
        assert floor > 0.0, row
        assert forward >= floor and closing >= floor, row

    return {
        "liveContactCommitRuntimeReceipt": "PASS",
        "realizedMotionHandoffRuntimeReceipt": "PASS",
        "commitDeferralObserved": True,
        "commitReadyTransitionObserved": True,
        "realizedApproachDeferralObserved": True,
        "realizedApproachReadyTransitionObserved": True,
        "commitDeferredPairCount": len(commit_deferred_pairs),
        "realizationDeferredPairCount": len(realized_deferred_pairs),
    }


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--base-request", required=True)
    p.add_argument("--hetero-request", required=True)
    p.add_argument("--asset-library-metadata", required=True)
    for key in ("battle", "g06", "g07", "g08", "log"):
        p.add_argument(f"--hetero-{key}", required=True)
    a = p.parse_args()

    base_req = c483.load(a.base_request)
    hetero_req = c483.load(a.hetero_request)
    ready_meta = c483.load(a.asset_library_metadata)
    profile = c483.profile_and_metadata_proof(base_req, hetero_req, ready_meta)
    g06 = c483.load(a.hetero_g06)
    directions = c483.direction_proof(g06)

    cross_gate = c483.heterogeneous_cross_gate_proof(
        "generic-hypercar-production-ready-heavy-asset",
        a.hetero_battle,
        a.hetero_g06,
        a.hetero_g07,
        a.hetero_g08,
    )
    cutoff = c483._cutoff_runtime_proof(a.hetero_battle)
    surface = c483._surface_transaction_runtime_proof(a.hetero_log)
    transaction = c483._transaction_sampling_runtime_proof(a.hetero_log)
    progress = c483._progress_runtime_proof(a.hetero_log)
    approach = c483.approach_transaction_proof(a.hetero_log, a.hetero_g07)
    recovery = c483.deferred_handoff_recovery_proof(a.hetero_log)
    roles = c483.collision_role_runtime_proof(a.hetero_log)
    drive_direction = c483.drive_direction_runtime_proof(a.hetero_log)
    c485 = c485_runtime_proof(a.hetero_log)

    print(json.dumps({
        "marker": "GENERIC_AUTONOMOUS_BATTLE_C485_MACHINE_ACCEPTANCE",
        "status": "PASS",
        "candidate": "ISS_GENERIC_BATTLE_RUNTIME_V1_CANDIDATE_4_8_5_GENERIC_AUTONOMOUS_BATTLE",
        "mechanism": CONTACT_COMMIT_MODEL,
        "executionProfile": "NVIDIA_L4",
        "productionReadyHeavyAssetProof": "PASS",
        "canonicalFrameMetadataProof": "PASS",
        "heterogeneousActorProfileProof": "PASS",
        "sameRuntimeAcrossDissimilarActorProfiles": True,
        **directions,
        **approach,
        **recovery,
        **roles,
        **drive_direction,
        **c485,
        "radialNavigationContractPreserved": "PASS",
        "obbHandoffEligibilityPreserved": "PASS",
        "translationDominantHandoffEligibility": "PASS",
        "tacticalGoalProgressRebase": "PASS",
        "collisionProxyProgressRefresh": "PASS",
        "transactionBoundedLocalityWindow": "PASS",
        "livePairSurfaceSemanticSelection": "PASS",
        "secondNativeContact": "PASS",
        "damageThresholdSemantics": "PASS",
        "physicsThresholdDrivenDamageOutcome": "PASS",
        "visibleCausalDamageDebris": "PASS",
        "g07AdaptiveCausalDrama": "PASS",
        "g08MachineObservability": "PASS",
        "nativeContactAuthorityPreserved": True,
        "pairwiseSolverOraclePreserved": True,
        "c484AlignmentSemanticsPreserved": True,
        "c483DriveDirectionPreserved": True,
        "c482CollisionRolesPreserved": True,
        "c481DeferredHandoffProgressPreserved": True,
        "c480ApproachSemanticTransactionPreserved": True,
        "g05ThresholdImported": False,
        "contactThresholdChanged": False,
        "semanticToleranceChanged": False,
        "localityToleranceChanged": False,
        "damageAdmissionThresholdChanged": False,
        "damageThresholdAwareControl": False,
        "targetToughnessAwareControl": False,
        "desiredImpactSpeedControl": False,
        "desiredImpactEnergyControl": False,
        "fixtureBattlePlanChanged": False,
        "perAssetBattleCode": False,
        "perAssetTacticalTuning": False,
        "perVideoTrajectoryEngineering": False,
        "canonicalFrameFixtureHardcode": False,
        "humanCinematicAcceptance": "PENDING",
        "gateClosed": False,
        "productionReadyClaimed": False,
        "profileAndMetadataProof": profile,
        "crossGateProof": cross_gate,
        "cutoffRuntimeProof": cutoff,
        "surfaceTransactionRuntimeProof": surface,
        "transactionSamplingRuntimeProof": transaction,
        "progressRuntimeProof": progress,
    }, sort_keys=True))


if __name__ == "__main__":
    main()
