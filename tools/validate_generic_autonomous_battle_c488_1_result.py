#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
TOOLS = ROOT / "tools"
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

import validate_generic_autonomous_battle_c483_result as c483
from validate_generic_autonomous_battle_c480_result import _json_markers
from blender.iss_battle_runtime_precontact_realization_v1 import PRECONTACT_REALIZATION_MODEL

CANDIDATE = "ISS_GENERIC_BATTLE_RUNTIME_V1_CANDIDATE_4_8_8_1_GENERIC_AUTONOMOUS_BATTLE"


def _frame(row: dict[str, Any]) -> int:
    return int(row.get("frame") or -1)


def c488_1_runtime_proof(log_path: str) -> dict[str, object]:
    rows = _json_markers(log_path)
    ready = [r for r in rows if r.get("marker") == "GENERIC_AUTONOMOUS_BATTLE_C488_1_ENGINEERING_READY"]
    assert len(ready) == 1, ("C488_1_ENGINEERING_READY_COUNT", len(ready))
    receipt = ready[0]
    assert receipt.get("candidate") == CANDIDATE, receipt
    assert receipt.get("mechanism") == PRECONTACT_REALIZATION_MODEL, receipt
    assert receipt.get("affectedLayerAuditStatus") == "PASS", receipt
    for field in (
        "c488RejectedBySourceAudit",
        "previousFrameOnlyEvidence",
        "eventActorTargetScopedEvidence",
        "staleEvidenceRejected",
        "recoveryEvidenceRejected",
        "currentNonNegativeClosingRequired",
        "precontactOutsideExistingHandoffGapRequired",
        "c487LifecyclePreserved",
        "c485CapabilityFloorPreserved",
        "c484AlignmentSemanticsPreserved",
        "c465CutoffFrameStabilityPreserved",
        "g05NativeSolverFinalAuthorityPreserved",
    ):
        assert receipt.get(field) is True, (field, receipt.get(field))
    for field in (
        "g05SourceChanged", "g06SourceChanged", "g07SourceChanged", "g08SourceChanged",
        "g05ThresholdImported", "contactThresholdChanged", "semanticToleranceChanged",
        "localityToleranceChanged", "damageAdmissionThresholdChanged", "assetIdentityBranch",
        "perAssetBattleCode", "perAssetTacticalTuning", "perVideoTrajectoryEngineering",
        "fixedWorldCoordinates", "exactCollisionFrameTarget", "exactImpactEnergyTarget",
        "actorPoseOrVelocityMutation", "fixtureBattlePlanChanged",
        "frozenNineServiceArchitectureChanged", "gateClosed", "productionReadyClaimed",
    ):
        assert receipt.get(field) is False, (field, receipt.get(field))
    assert receipt.get("runtimeFrameOrderVerified") == "PHYSICS_SAMPLE_THEN_G05_DETECT_THEN_G04_CONTROLS", receipt

    # The rejected broad C488 mechanism must not execute in this run.
    assert not any(r.get("marker") == "GENERIC_AUTONOMOUS_BATTLE_C488_ENGINEERING_READY" for r in rows), \
        "SUPERSEDED_C488_EXECUTED"

    armed = [r for r in rows if r.get("marker") == "G04_PRECONTACT_REALIZATION_SAMPLE_ARMED"]
    carried = [r for r in rows if r.get("marker") == "G04_PRECONTACT_REALIZATION_CARRIED_TO_HANDOFF"]
    handoffs = [r for r in rows if r.get("marker") == "GENERIC_SOLVER_HANDOFF_LATCHED"]
    contacts = [r for r in rows if r.get("marker") == "PAIRWISE_NATIVE_SOLVER_CONTACT_VERIFIED"]
    assert armed, "C488_1_PRECONTACT_SAMPLE_NOT_ARMED"
    assert carried, "C488_1_PRECONTACT_SAMPLE_NOT_CARRIED"
    assert handoffs, "C488_1_SOLVER_HANDOFF_NOT_OBSERVED"
    assert contacts, "C488_1_NATIVE_SOLVER_CONTACT_NOT_OBSERVED"

    armed_keys = {
        (str(r.get("eventId") or ""), str(r.get("attackerId") or ""), str(r.get("targetId") or ""), _frame(r))
        for r in armed
    }
    valid_transactions: list[tuple[str, str, str]] = []
    for carry in carried:
        key = (
            str(carry.get("eventId") or ""),
            str(carry.get("attackerId") or ""),
            str(carry.get("targetId") or ""),
        )
        assert all(key), ("C488_1_CARRY_TRANSACTION_INCOMPLETE", carry)
        assert carry.get("model") == PRECONTACT_REALIZATION_MODEL, carry
        frame = _frame(carry)
        evidence_frame = int(carry.get("evidenceFrame") or -1)
        age = int(carry.get("evidenceAgeFrames") or -1)
        assert age == 1 and evidence_frame == frame - 1, ("C488_1_EVIDENCE_NOT_IMMEDIATE_PREVIOUS_FRAME", carry)
        assert float(carry.get("currentClosingSpeedMps")) >= 0.0, ("C488_1_NEGATIVE_CURRENT_CLOSING", carry)
        assert float(carry.get("evidenceForwardSpeedMps")) >= float(carry.get("evidenceCapabilityFloorMps")), carry
        assert float(carry.get("evidenceClosingSpeedMps")) >= float(carry.get("evidenceCapabilityFloorMps")), carry
        assert (key[0], key[1], key[2], evidence_frame) in armed_keys, ("C488_1_CARRY_WITHOUT_SAME_TRANSACTION_ARM", carry)

        h = [r for r in handoffs if str(r.get("eventId") or "") == key[0] and str(r.get("actorId") or "") == key[1] and _frame(r) >= frame]
        assert h, ("C488_1_CARRY_WITHOUT_HANDOFF", key, frame)
        handoff_frame = min(_frame(r) for r in h)
        assert handoff_frame == frame, ("C488_1_HANDOFF_NOT_AT_CARRY_FRAME", key, frame, handoff_frame)

        n = [r for r in contacts if str(r.get("eventId") or "") == key[0] and str(r.get("attackerId") or "") == key[1] and str(r.get("targetId") or "") == key[2] and _frame(r) >= handoff_frame]
        assert n, ("C488_1_HANDOFF_WITHOUT_SAME_TRANSACTION_NATIVE_CONTACT", key, handoff_frame)
        valid_transactions.append(key)

    assert valid_transactions, "C488_1_NO_VALID_CARRY_HANDOFF_NATIVE_CONTACT_TRANSACTION"

    # G05 must no longer reject the successfully carried transaction for controller
    # authority after the handoff frame. Other exploratory attempts may still be
    # rejected before their own handoff and are not hidden by this check.
    rejects = [r for r in rows if r.get("marker") == "G05_OUTER_CONTACT_AUTHORITY_REJECTED" and r.get("reason") == "CONTROLLER_AUTHORITY_NOT_RELEASED"]
    for key in set(valid_transactions):
        handoff_frame = min(_frame(r) for r in handoffs if str(r.get("eventId") or "") == key[0] and str(r.get("actorId") or "") == key[1])
        post = [r for r in rejects if str(r.get("eventId") or "") == key[0] and str(r.get("attackerId") or "") == key[1] and str(r.get("targetId") or "") == key[2] and _frame(r) > handoff_frame]
        # A same-frame/next-sample observation may precede contact resolution, but
        # persistent authority rejection through the transaction is forbidden.
        if post:
            native_frame = min(_frame(r) for r in contacts if str(r.get("eventId") or "") == key[0] and str(r.get("attackerId") or "") == key[1] and str(r.get("targetId") or "") == key[2] and _frame(r) >= handoff_frame)
            assert all(_frame(r) < native_frame for r in post), ("C488_1_AUTHORITY_REJECTION_PERSISTED_AFTER_NATIVE_CONTACT", key, native_frame, post[-3:])

    return {
        "precontactSampleRuntimeReceipt": "PASS",
        "previousFrameCarryRuntimeReceipt": "PASS",
        "sameTransactionCarryToHandoffToNativeContact": "PASS",
        "carriedTransactionCount": len(set(valid_transactions)),
        "currentNonNegativeClosingAtCarry": True,
        "supersededBroadC488NotExecuted": True,
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
        a.hetero_battle, a.hetero_g06, a.hetero_g07, a.hetero_g08,
    )
    cutoff = c483._cutoff_runtime_proof(a.hetero_battle)
    surface = c483._surface_transaction_runtime_proof(a.hetero_log)
    transaction = c483._transaction_sampling_runtime_proof(a.hetero_log)
    progress = c483._progress_runtime_proof(a.hetero_log)
    approach = c483.approach_transaction_proof(a.hetero_log, a.hetero_g07)
    recovery = c483.deferred_handoff_recovery_proof(a.hetero_log)
    roles = c483.collision_role_runtime_proof(a.hetero_log)
    drive_direction = c483.drive_direction_runtime_proof(a.hetero_log)
    c488_1 = c488_1_runtime_proof(a.hetero_log)

    print(json.dumps({
        "marker": "GENERIC_AUTONOMOUS_BATTLE_C488_1_MACHINE_ACCEPTANCE",
        "status": "PASS",
        "candidate": CANDIDATE,
        "mechanism": PRECONTACT_REALIZATION_MODEL,
        "executionProfile": "NVIDIA_L4",
        "productionReadyHeavyAssetProof": "PASS",
        "canonicalFrameMetadataProof": "PASS",
        "heterogeneousActorProfileProof": "PASS",
        "sameRuntimeAcrossDissimilarActorProfiles": True,
        **directions, **approach, **recovery, **roles, **drive_direction, **c488_1,
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
        "g05ThresholdImported": False,
        "contactThresholdChanged": False,
        "semanticToleranceChanged": False,
        "localityToleranceChanged": False,
        "damageAdmissionThresholdChanged": False,
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
