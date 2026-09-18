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
from blender.iss_battle_runtime_g05_handoff_readiness_v1 import (
    G05_HANDOFF_READINESS_MODEL,
    required_normal_closing_speed_mps,
)


def readiness_runtime_proof(log_path: str) -> dict[str, object]:
    rows = _json_markers(log_path)
    ready = [r for r in rows if r.get("marker") == "GENERIC_AUTONOMOUS_BATTLE_C485_ENGINEERING_READY"]
    assert len(ready) == 1, ("C485_ENGINEERING_READY_COUNT", len(ready))
    receipt = ready[0]
    assert receipt.get("candidate") == "ISS_GENERIC_BATTLE_RUNTIME_V1_CANDIDATE_4_8_5_GENERIC_AUTONOMOUS_BATTLE", receipt
    assert receipt.get("mechanism") == G05_HANDOFF_READINESS_MODEL, receipt
    assert receipt.get("g05ReadinessUsesAuthoritativeOracleConstant") is True, receipt
    assert receipt.get("g05ThresholdCopiedOrRetuned") is False, receipt
    assert receipt.get("g05NativeSolverFinalAuthorityPreserved") is True, receipt
    assert receipt.get("existingGenericRecoveryReused") is True, receipt
    assert receipt.get("desiredImpactSpeedControl") is False, receipt
    assert receipt.get("desiredImpactEnergyControl") is False, receipt
    assert receipt.get("assetIdentityBranch") is False, receipt
    assert receipt.get("perAssetBattleCode") is False, receipt
    assert receipt.get("perAssetTacticalTuning") is False, receipt
    assert receipt.get("perVideoTrajectoryEngineering") is False, receipt
    assert receipt.get("actorPoseOrVelocityMutation") is False, receipt
    assert receipt.get("fixtureBattlePlanChanged") is False, receipt
    assert receipt.get("contactThresholdChanged") is False, receipt
    assert receipt.get("damageAdmissionThresholdChanged") is False, receipt

    recovery = [r for r in rows if r.get("marker") == "G04_G05_HANDOFF_READINESS_RECOVERY_TRIGGERED"]
    confirmed = [r for r in rows if r.get("marker") == "G04_G05_HANDOFF_READINESS_CONFIRMED"]
    assert recovery, "C485_G05_READINESS_RECOVERY_NOT_OBSERVED"
    assert confirmed, "C485_G05_READINESS_CONFIRMATION_NOT_OBSERVED"

    authoritative = required_normal_closing_speed_mps()
    recovery_pairs: set[tuple[str, str]] = set()
    for row in recovery:
        assert row.get("model") == G05_HANDOFF_READINESS_MODEL, row
        assert row.get("recoveryMechanism") == "EXISTING_CLOSED_LOOP_RECOVERY", row
        assert float(row.get("requiredNormalClosingSpeedMps")) == authoritative, row
        assert float(row.get("liveNormalClosingSpeedMps")) < authoritative, row
        pair = (str(row.get("attackerId") or ""), str(row.get("targetId") or ""))
        assert all(pair), row
        recovery_pairs.add(pair)

    confirmed_pairs: set[tuple[str, str]] = set()
    for row in confirmed:
        assert row.get("model") == G05_HANDOFF_READINESS_MODEL, row
        assert float(row.get("requiredNormalClosingSpeedMps")) == authoritative, row
        assert float(row.get("liveNormalClosingSpeedMps")) >= authoritative, row
        pair = (str(row.get("attackerId") or ""), str(row.get("targetId") or ""))
        assert all(pair), row
        confirmed_pairs.add(pair)

    transitioned = recovery_pairs & confirmed_pairs
    assert transitioned, (
        "C485_NO_PAIR_RECOVERED_FROM_UNREADY_TO_READY_HANDOFF",
        sorted(recovery_pairs),
        sorted(confirmed_pairs),
    )

    c484_receipts = [r for r in rows if r.get("marker") == "GENERIC_AUTONOMOUS_BATTLE_C484_ENGINEERING_READY"]
    assert len(c484_receipts) == 1, ("C485_C484_LAYER_MISSING", len(c484_receipts))
    assert c484_receipts[0].get("c483DriveDirectionPreserved") is True
    assert c484_receipts[0].get("c482CollisionRolesPreserved") is True

    return {
        "g05PreHandoffReadinessRuntimeProof": "PASS",
        "authoritativeG05ClosingSpeedMps": authoritative,
        "readinessRecoveryCount": len(recovery),
        "readinessConfirmationCount": len(confirmed),
        "recoveredPairCount": len(transitioned),
        "existingGenericRecoveryReused": True,
        "g05ThresholdCopiedOrRetuned": False,
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
    readiness = readiness_runtime_proof(a.hetero_log)

    print(json.dumps({
        "marker": "GENERIC_AUTONOMOUS_BATTLE_C485_MACHINE_ACCEPTANCE",
        "status": "PASS",
        "candidate": "ISS_GENERIC_BATTLE_RUNTIME_V1_CANDIDATE_4_8_5_GENERIC_AUTONOMOUS_BATTLE",
        "mechanism": G05_HANDOFF_READINESS_MODEL,
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
        **readiness,
        "radialNavigationContractPreserved": "PASS",
        "obbHandoffEligibilityPreserved": "PASS",
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
        "contactThresholdChanged": False,
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
