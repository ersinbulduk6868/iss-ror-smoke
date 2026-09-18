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

import validate_generic_autonomous_battle_c485_result as c485

PRECONTACT_CORRIDOR_MODEL = "G04_LIVE_PRECONTACT_CORRIDOR_V1"


def c486_runtime_proof(log_path: str) -> dict[str, object]:
    rows = c485._json_markers(log_path)
    ready = [
        r for r in rows
        if r.get("marker") == "GENERIC_AUTONOMOUS_BATTLE_C486_ENGINEERING_READY"
    ]
    assert len(ready) == 1, ("C486_ENGINEERING_READY_COUNT", len(ready))
    receipt = ready[0]
    assert receipt.get("candidate") == "ISS_GENERIC_BATTLE_RUNTIME_V1_CANDIDATE_4_8_6_GENERIC_AUTONOMOUS_BATTLE", receipt
    assert receipt.get("mechanism") == PRECONTACT_CORRIDOR_MODEL, receipt
    assert receipt.get("affectedLayerAuditStatus") == "PASS", receipt
    assert receipt.get("threeIterationAuditRuleSatisfied") is True, receipt
    assert receipt.get("continuousRunwayRevalidation") is True, receipt
    assert receipt.get("unreadyContactCorridorForbidden") is True, receipt
    assert receipt.get("existingOpenDistancePolicyReused") is True, receipt
    assert receipt.get("existingGeometryCapabilityRunwayReused") is True, receipt
    assert receipt.get("c485GenericCommitAndRealizedHandoffPreserved") is True, receipt
    assert receipt.get("c484TranslationDominantAlignmentPreserved") is True, receipt
    assert receipt.get("c483DriveDirectionPreserved") is True, receipt
    assert receipt.get("c482CollisionRolesPreserved") is True, receipt
    assert receipt.get("c481DeferredHandoffProgressPreserved") is True, receipt
    assert receipt.get("c480ApproachSemanticTransactionPreserved") is True, receipt
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

    reopened = [
        r for r in rows
        if r.get("marker") == "G04_PRECONTACT_CORRIDOR_REOPENED"
    ]
    standoff = [
        r for r in rows
        if r.get("marker") == "G04_PRECONTACT_CORRIDOR_STANDOFF_HELD"
    ]
    live_ready = [
        r for r in rows
        if r.get("marker") == "G04_PRECONTACT_CORRIDOR_LIVE_READINESS_READY"
    ]

    assert reopened, "C486_PRECONTACT_CORRIDOR_REOPEN_NOT_OBSERVED"
    assert live_ready, "C486_PRECONTACT_CORRIDOR_READY_NOT_OBSERVED"

    reopened_pairs = {
        (str(r.get("attackerId") or ""), str(r.get("targetId") or ""))
        for r in reopened
    }
    ready_pairs = {
        (str(r.get("attackerId") or ""), str(r.get("targetId") or ""))
        for r in live_ready
    }
    assert reopened_pairs and all(a and b for a, b in reopened_pairs), reopened_pairs
    assert ready_pairs and all(a and b for a, b in ready_pairs), ready_pairs
    recovered_pairs = reopened_pairs & ready_pairs
    assert recovered_pairs, (
        "C486_NO_PAIR_TRANSITIONED_FROM_CORRIDOR_REOPEN_TO_LIVE_READY",
        sorted(reopened_pairs), sorted(ready_pairs),
    )

    for row in reopened:
        surface_gap = float(row.get("surfaceGapM"))
        runway = float(row.get("runwayRequiredM"))
        assert runway >= 0.0, row
        assert surface_gap < runway, row
        assert row.get("model") == PRECONTACT_CORRIDOR_MODEL, row

    for row in live_ready:
        assert row.get("model") == PRECONTACT_CORRIDOR_MODEL, row
        assert abs(float(row.get("headingErrorRad"))) <= 0.70 + 1.0e-9, row
        assert float(row.get("contention")) < 0.80, row

    return {
        "livePrecontactCorridorRuntimeReceipt": "PASS",
        "corridorReopenObserved": True,
        "corridorLiveReadinessRecoveryObserved": True,
        "corridorReopenedPairCount": len(reopened_pairs),
        "corridorRecoveredPairCount": len(recovered_pairs),
        "standOffObservationCount": len(standoff),
    }


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--base-request", required=True)
    p.add_argument("--hetero-request", required=True)
    p.add_argument("--asset-library-metadata", required=True)
    for key in ("battle", "g06", "g07", "g08", "log"):
        p.add_argument(f"--hetero-{key}", required=True)
    a = p.parse_args()

    base_req = c485.c483.load(a.base_request)
    hetero_req = c485.c483.load(a.hetero_request)
    ready_meta = c485.c483.load(a.asset_library_metadata)
    profile = c485.c483.profile_and_metadata_proof(base_req, hetero_req, ready_meta)
    g06 = c485.c483.load(a.hetero_g06)
    directions = c485.c483.direction_proof(g06)

    cross_gate = c485.c483.heterogeneous_cross_gate_proof(
        "generic-hypercar-production-ready-heavy-asset",
        a.hetero_battle,
        a.hetero_g06,
        a.hetero_g07,
        a.hetero_g08,
    )
    cutoff = c485.c483._cutoff_runtime_proof(a.hetero_battle)
    surface = c485.c483._surface_transaction_runtime_proof(a.hetero_log)
    transaction = c485.c483._transaction_sampling_runtime_proof(a.hetero_log)
    progress = c485.c483._progress_runtime_proof(a.hetero_log)
    approach = c485.c483.approach_transaction_proof(a.hetero_log, a.hetero_g07)
    recovery = c485.c483.deferred_handoff_recovery_proof(a.hetero_log)
    roles = c485.c483.collision_role_runtime_proof(a.hetero_log)
    drive_direction = c485.c483.drive_direction_runtime_proof(a.hetero_log)
    c485_proof = c485.c485_runtime_proof(a.hetero_log)
    c486_proof = c486_runtime_proof(a.hetero_log)

    print(json.dumps({
        "marker": "GENERIC_AUTONOMOUS_BATTLE_C486_MACHINE_ACCEPTANCE",
        "status": "PASS",
        "candidate": "ISS_GENERIC_BATTLE_RUNTIME_V1_CANDIDATE_4_8_6_GENERIC_AUTONOMOUS_BATTLE",
        "mechanism": PRECONTACT_CORRIDOR_MODEL,
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
        **c485_proof,
        **c486_proof,
        "radialNavigationContractPreserved": "PASS",
        "obbHandoffEligibilityPreserved": "PASS",
        "translationDominantHandoffEligibility": "PASS",
        "liveContactCommitPreserved": "PASS",
        "realizedMotionHandoffPreserved": "PASS",
        "continuousRunwayRevalidation": "PASS",
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
