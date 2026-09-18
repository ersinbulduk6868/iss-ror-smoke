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

ALIGNMENT_MODEL = "G04_TRANSLATION_DOMINANT_CONTACT_HANDOFF_V1"


def alignment_runtime_proof(log_path: str) -> dict[str, object]:
    rows = _json_markers(log_path)
    ready = [
        r for r in rows
        if r.get("marker") == "GENERIC_AUTONOMOUS_BATTLE_C484_ENGINEERING_READY"
    ]
    assert len(ready) == 1, ("C484_ENGINEERING_READY_COUNT", len(ready))
    receipt = ready[0]
    assert receipt.get("candidate") == "ISS_GENERIC_BATTLE_RUNTIME_V1_CANDIDATE_4_8_4_GENERIC_AUTONOMOUS_BATTLE", receipt
    assert receipt.get("mechanism") == ALIGNMENT_MODEL, receipt
    assert receipt.get("translationVsRotationDerivedFromLiveControllerCommand") is True, receipt
    assert receipt.get("rotationalLeverArmDerivedFromCharacteristicLength") is True, receipt
    assert receipt.get("shadowMemoryProbeOnly") is True, receipt
    assert receipt.get("realMemoryUpdatedOncePerFrame") is True, receipt
    assert receipt.get("c483DriveDirectionPreserved") is True, receipt
    assert receipt.get("c482CollisionRolesPreserved") is True, receipt
    assert receipt.get("c481DeferredHandoffProgressPreserved") is True, receipt
    assert receipt.get("c480ApproachSemanticTransactionPreserved") is True, receipt
    assert receipt.get("c474ObbHandoffEligibilityPreserved") is True, receipt
    assert receipt.get("g05NativeSolverFinalAuthorityPreserved") is True, receipt
    assert receipt.get("pairwiseSolverOraclePreserved") is True, receipt
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

    deferred = [
        r for r in rows
        if r.get("marker") == "G04_CONTACT_HANDOFF_DEFERRED_BY_ROTATIONAL_DOMINANCE"
    ]
    aligned = [
        r for r in rows
        if r.get("marker") == "G04_CONTACT_HANDOFF_ALIGNMENT_READY"
    ]
    assert deferred, "C484_RUNTIME_ALIGNMENT_DEFER_NOT_OBSERVED"
    assert aligned, "C484_RUNTIME_ALIGNMENT_READY_NOT_OBSERVED"

    deferred_pairs: set[tuple[str, str]] = set()
    for row in deferred:
        assert row.get("model") == ALIGNMENT_MODEL, row
        assert row.get("prospectiveMotorAuthority") == "MOTOR", row
        assert row.get("translationDominant") is False, row
        forward = float(row.get("prospectiveForwardSpeedMps"))
        rotational = float(row.get("rotationalNoseSpeedMps"))
        assert forward > 0.0, row
        assert rotational > forward, row
        pair = (str(row.get("attackerId") or ""), str(row.get("targetId") or ""))
        assert all(pair), row
        deferred_pairs.add(pair)

    ready_pairs: set[tuple[str, str]] = set()
    for row in aligned:
        assert row.get("model") == ALIGNMENT_MODEL, row
        assert row.get("prospectiveMotorAuthority") == "MOTOR", row
        assert row.get("translationDominant") is True, row
        forward = float(row.get("prospectiveForwardSpeedMps"))
        rotational = float(row.get("rotationalNoseSpeedMps"))
        assert forward > 0.0, row
        assert forward >= rotational, row
        pair = (str(row.get("attackerId") or ""), str(row.get("targetId") or ""))
        assert all(pair), row
        ready_pairs.add(pair)

    assert deferred_pairs & ready_pairs, (
        "C484_NO_PAIR_TRANSITIONED_FROM_ALIGNMENT_DEFER_TO_READY",
        sorted(deferred_pairs),
        sorted(ready_pairs),
    )

    return {
        "handoffAlignmentRuntimeReceipt": "PASS",
        "translationDominantHandoffEligibility": "PASS",
        "rotationalDominanceDeferralObserved": True,
        "alignmentReadyTransitionObserved": True,
        "alignmentDeferredPairCount": len(deferred_pairs),
        "alignmentReadyPairCount": len(ready_pairs),
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
    alignment = alignment_runtime_proof(a.hetero_log)

    print(json.dumps({
        "marker": "GENERIC_AUTONOMOUS_BATTLE_C484_MACHINE_ACCEPTANCE",
        "status": "PASS",
        "candidate": "ISS_GENERIC_BATTLE_RUNTIME_V1_CANDIDATE_4_8_4_GENERIC_AUTONOMOUS_BATTLE",
        "mechanism": ALIGNMENT_MODEL,
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
        **alignment,
        "radialNavigationContractPreserved": "PASS",
        "obbOnlyHandoffEligibility": "PASS",
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
        "c483DriveDirectionPreserved": True,
        "c482CollisionRolesPreserved": True,
        "c481DeferredHandoffProgressPreserved": True,
        "c480ApproachSemanticTransactionPreserved": True,
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
