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

CANDIDATE = "ISS_GENERIC_BATTLE_RUNTIME_V1_CANDIDATE_4_8_8_GENERIC_AUTONOMOUS_BATTLE"
MECHANISM = "G04_EVENT_SCOPED_ENGAGEMENT_AUTHORITY_V2"
CERT_MODEL = "G04_CONTINUOUS_REALIZED_APPROACH_CERTIFICATE_V1"
FAILURE_FAMILY = "POSTPROXIMITY_HANDOFF_DEADZONE_AND_RECOVERY_OWNERSHIP_COMPOSITION"


def _frame(row: dict[str, Any]) -> int:
    return int(row.get("frame") or 0)


def _key(row: dict[str, Any]) -> tuple[str, str, str]:
    return (
        str(row.get("eventId") or ""),
        str(row.get("attackerId") or row.get("actorId") or ""),
        str(row.get("targetId") or ""),
    )


def c488_runtime_proof(log_path: str) -> dict[str, object]:
    rows = _json_markers(log_path)
    ready = [r for r in rows if r.get("marker") == "GENERIC_AUTONOMOUS_BATTLE_C488_ENGINEERING_READY"]
    assert len(ready) == 1, ("C488_ENGINEERING_READY_COUNT", len(ready))
    receipt = ready[0]
    assert receipt.get("candidate") == CANDIDATE, receipt
    assert receipt.get("mechanism") == MECHANISM, receipt
    assert receipt.get("approachCertificateModel") == CERT_MODEL, receipt
    assert receipt.get("affectedLayerAuditStatus") == "PASS", receipt
    assert receipt.get("failureFamily") == FAILURE_FAMILY, receipt

    required_true = (
        "eventScopedRecoveryOwnershipOutermost",
        "outerRecoveryClearSuppressedUntilNaturalCompletion",
        "continuousRealizedApproachCertificate",
        "certificateQualifiedOutsideHandoffProximity",
        "certificateInvalidatedOnReadinessLoss",
        "certificateInvalidatedOnRecovery",
        "certificateInvalidatedOnTacticExit",
        "certificateInvalidatedOnPrecontactMiss",
        "certificateInvalidatedOnEventEnd",
        "atomicMotorToCoastAtCertifiedProximity",
        "c487EventTransactionScopePreserved",
        "c487ActualGoalReadinessPreserved",
        "c485CapabilityDerivedMotionFloorPreserved",
        "c484TranslationDominantAlignmentPreserved",
        "c483DriveDirectionPreserved",
        "c482CollisionRolesPreserved",
        "c480SemanticTransactionPreserved",
        "g05NativeSolverFinalAuthorityPreserved",
    )
    for field in required_true:
        assert receipt.get(field) is True, (field, receipt.get(field))
    assert receipt.get("currentClosingSignRequiredAfterCertifiedProximity") is False, receipt

    required_false = (
        "g05SourceChanged", "g06SourceChanged", "g07SourceChanged", "g08SourceChanged",
        "g05ThresholdImported", "contactThresholdChanged", "semanticToleranceChanged",
        "localityToleranceChanged", "damageAdmissionThresholdChanged",
        "damageThresholdAwareControl", "targetToughnessAwareControl",
        "desiredImpactSpeedControl", "desiredImpactEnergyControl", "assetIdentityBranch",
        "perAssetBattleCode", "perAssetTacticalTuning", "perVideoTrajectoryEngineering",
        "fixedWorldCoordinates", "exactCollisionFrameTarget", "exactImpactEnergyTarget",
        "actorPoseOrVelocityMutation", "fixtureBattlePlanChanged",
        "frozenNineServiceArchitectureChanged", "gateClosed", "productionReadyClaimed",
    )
    for field in required_false:
        assert receipt.get(field) is False, (field, receipt.get(field))

    certs = [r for r in rows if r.get("marker") == "G04_REALIZED_APPROACH_CERTIFICATE_QUALIFIED"]
    requests = [r for r in rows if r.get("marker") == "G04_CERTIFIED_SOLVER_HANDOFF_REQUESTED"]
    latches = [r for r in rows if r.get("marker") == "GENERIC_SOLVER_HANDOFF_LATCHED"]
    contacts = [r for r in rows if r.get("marker") == "PAIRWISE_NATIVE_SOLVER_CONTACT_VERIFIED"]
    rejects = [r for r in rows if r.get("marker") == "G05_OUTER_CONTACT_AUTHORITY_REJECTED" and r.get("reason") == "CONTROLLER_AUTHORITY_NOT_RELEASED"]

    assert certs, "C488_REALIZED_APPROACH_CERTIFICATE_NOT_OBSERVED"
    assert requests, "C488_CERTIFIED_SOLVER_HANDOFF_REQUEST_NOT_OBSERVED"
    assert latches, "C488_SOLVER_HANDOFF_LATCH_NOT_OBSERVED"
    assert contacts, "C488_NATIVE_SOLVER_CONTACT_NOT_OBSERVED"

    cert_by_key: dict[tuple[str, str, str], list[int]] = {}
    req_by_key: dict[tuple[str, str, str], list[int]] = {}
    contact_by_key: dict[tuple[str, str, str], list[int]] = {}
    target_by_event_actor: dict[tuple[str, str], set[str]] = {}

    for row in certs:
        key = _key(row)
        assert all(key), ("C488_CERT_TRANSACTION_INCOMPLETE", row)
        assert row.get("model") == CERT_MODEL, row
        assert float(row.get("capabilityFloorMps") or 0.0) > 0.0, row
        assert float(row.get("realizedForwardSpeedMps") or 0.0) >= float(row.get("capabilityFloorMps") or 0.0), row
        assert float(row.get("realizedClosingSpeedMps") or 0.0) >= float(row.get("capabilityFloorMps") or 0.0), row
        assert float(row.get("effectiveCollisionProxyGapM") or 0.0) > float(row.get("handoffGapM") or 0.0), row
        cert_by_key.setdefault(key, []).append(_frame(row))
        target_by_event_actor.setdefault((key[0], key[1]), set()).add(key[2])

    for row in requests:
        key = _key(row)
        assert all(key), ("C488_HANDOFF_REQUEST_TRANSACTION_INCOMPLETE", row)
        assert row.get("model") == MECHANISM, row
        assert row.get("currentClosingSignRequired") is False, row
        assert row.get("qualifiedFrame") is not None, row
        req_by_key.setdefault(key, []).append(_frame(row))
        target_by_event_actor.setdefault((key[0], key[1]), set()).add(key[2])

    for row in contacts:
        key = _key(row)
        assert all(key), ("C488_CONTACT_TRANSACTION_INCOMPLETE", row)
        contact_by_key.setdefault(key, []).append(_frame(row))
        target_by_event_actor.setdefault((key[0], key[1]), set()).add(key[2])

    for key2, targets in target_by_event_actor.items():
        assert len(targets) == 1, ("C488_AMBIGUOUS_EVENT_ACTOR_TARGET", key2, sorted(targets))

    latch_by_key: dict[tuple[str, str, str], list[int]] = {}
    for row in latches:
        event_id = str(row.get("eventId") or "")
        actor_id = str(row.get("actorId") or "")
        targets = target_by_event_actor.get((event_id, actor_id), set())
        assert len(targets) == 1, ("C488_LATCH_TRANSACTION_UNRESOLVED", row, sorted(targets))
        key = (event_id, actor_id, next(iter(targets)))
        latch_by_key.setdefault(key, []).append(_frame(row))

    valid: list[tuple[str, str, str]] = []
    for key in sorted(set(cert_by_key) & set(req_by_key) & set(latch_by_key) & set(contact_by_key)):
        q = min(cert_by_key[key])
        r = min(x for x in req_by_key[key] if x >= q)
        h = min(x for x in latch_by_key[key] if x >= r)
        n = min(x for x in contact_by_key[key] if x >= h)
        assert q <= r <= h <= n, ("C488_CERT_HANDOFF_CONTACT_ORDER_INVALID", key, q, r, h, n)
        post_rejects = [
            x for x in rejects
            if _key(x) == key and _frame(x) >= h and _frame(x) >= n
        ]
        assert not post_rejects, ("C488_AUTHORITY_REJECTION_PERSISTED_AFTER_NATIVE_CONTACT", key, post_rejects[-3:])
        valid.append(key)

    assert valid, (
        "C488_NO_SINGLE_TRANSACTION_CERTIFIED_HANDOFF_TO_NATIVE_CONTACT",
        sorted(cert_by_key), sorted(req_by_key), sorted(latch_by_key), sorted(contact_by_key),
    )

    counter = [key for key in valid if key[0] == "evt-counterattack"]
    assert counter, ("C488_COUNTERATTACK_CERTIFIED_NATIVE_CONTACT_NOT_OBSERVED", valid)

    recovery_replans = [r for r in rows if r.get("marker") == "G04_EVENT_SCOPED_RECOVERY_REPLAN_PROPAGATED"]
    recovery_completed = [r for r in rows if r.get("marker") == "G04_EVENT_SCOPED_RECOVERY_COMPLETED_RUNWAY_INVALIDATED"]
    suppressed = [r for r in rows if r.get("marker") == "G04_OUTER_RECOVERY_CLEAR_SUPPRESSED"]
    if recovery_replans:
        epochs = set()
        for row in recovery_replans:
            key = (*_key(row), int(row.get("recoveryEpoch") or 0))
            assert all(key[:3]) and key[3] > 0, row
            assert key not in epochs, ("C488_DUPLICATE_RECOVERY_REPLAN_EPOCH", key)
            epochs.add(key)
        assert recovery_completed, "C488_RECOVERY_OCCURRED_WITHOUT_NATURAL_COMPLETION_EVIDENCE"
    if suppressed:
        for row in suppressed:
            assert row.get("model") == MECHANISM, row
            assert str(row.get("autonomyMode") or "").upper().startswith("RECOVER_"), row

    return {
        "eventScopedAuthorityV2RuntimeReceipt": "PASS",
        "continuousRealizedApproachCertificateRuntimeReceipt": "PASS",
        "atomicCertifiedMotorToCoastRuntimeReceipt": "PASS",
        "sameTransactionCertificateToHandoffToNativeContact": "PASS",
        "counterattackCertifiedNativeContact": "PASS",
        "certifiedNativeContactTransactionCount": len(set(valid)),
        "recoveryOwnershipRuntimeObserved": bool(recovery_replans),
        "outerRecoveryClearSuppressionObservedWhenApplicable": bool(suppressed),
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
    c488 = c488_runtime_proof(a.hetero_log)

    print(json.dumps({
        "marker": "GENERIC_AUTONOMOUS_BATTLE_C488_MACHINE_ACCEPTANCE",
        "status": "PASS",
        "candidate": CANDIDATE,
        "mechanism": MECHANISM,
        "executionProfile": "NVIDIA_L4",
        "productionReadyHeavyAssetProof": "PASS",
        "canonicalFrameMetadataProof": "PASS",
        "heterogeneousActorProfileProof": "PASS",
        "sameRuntimeAcrossDissimilarActorProfiles": True,
        **directions, **approach, **recovery, **roles, **drive_direction, **c488,
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
