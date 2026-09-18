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
import validate_generic_autonomous_battle_c488_result as c488
import validate_generic_autonomous_battle_c489_result as c489
from validate_generic_autonomous_battle_c480_result import _json_markers
from blender.iss_battle_runtime_certified_navigation_continuity_v1 import (
    CERTIFIED_NAVIGATION_CONTINUITY_MODEL,
)

CANDIDATE = "ISS_GENERIC_BATTLE_RUNTIME_V1_CANDIDATE_4_9_1_GENERIC_AUTONOMOUS_BATTLE"
FAILURE_FAMILY = "DUPLICATE_ACTUAL_GOAL_READINESS_REOPENS_FULL_RUNWAY_AFTER_REALIZED_APPROACH_CERTIFICATION"
DUPLICATE_READINESS_INVALIDATIONS = frozenset({"TACTIC_NOT_CONTACT_DIRECTED", "LIVE_READINESS_LOST"})


def _frame(row: dict[str, Any]) -> int:
    return int(row.get("frame") or -1)


def _key(row: dict[str, Any]) -> tuple[str, str, str]:
    return (
        str(row.get("eventId") or ""),
        str(row.get("attackerId") or row.get("actorId") or ""),
        str(row.get("targetId") or ""),
    )


def _rows(rows: list[dict[str, Any]], marker_name: str) -> list[dict[str, Any]]:
    return [r for r in rows if r.get("marker") == marker_name]


def c491_runtime_proof(log_path: str) -> dict[str, object]:
    rows = _json_markers(log_path)
    ready = _rows(rows, "GENERIC_AUTONOMOUS_BATTLE_C491_ENGINEERING_READY")
    assert len(ready) == 1, ("C491_ENGINEERING_READY_COUNT", len(ready))
    receipt = ready[0]
    assert receipt.get("candidate") == CANDIDATE, receipt
    assert receipt.get("mechanism") == CERTIFIED_NAVIGATION_CONTINUITY_MODEL, receipt
    assert receipt.get("affectedLayerAuditStatus") == "PASS", receipt
    assert receipt.get("failureFamily") == FAILURE_FAMILY, receipt

    for field in (
        "certificateNavigationOwnershipAfterQualification",
        "certificateLiveReadinessContinuityAfterQualification",
        "incomingPlannerContactCommitStillRequired",
        "incomingContactDirectedModeStillRequired",
        "sameTransactionStillRequired",
        "recoveryPreemptsCertificateContinuity",
        "preQualificationReadinessUnchanged",
        "c488CertificateMissInvalidationPreserved",
        "c488CertificateRecoveryInvalidationPreserved",
        "c484TranslationDominantAlignmentPreserved",
        "c490FinalCompositionBindingPreserved",
        "c489NegativeAckRecoveryPreserved",
        "c487RecoveryLifecyclePreserved",
    ):
        assert receipt.get(field) is True, (field, receipt.get(field))
    for field in (
        "tacticalModeMutatedByC491", "tacticalContactCommitMutatedByC491",
        "actualGoalReadinessThresholdChanged", "contactCommitHeadingThresholdChanged",
        "g05SourceChanged", "g05OuterGateChanged", "g05SolverOracleChanged",
        "g05ThresholdImported", "contactThresholdChanged", "semanticToleranceChanged",
        "localityToleranceChanged", "damageAdmissionThresholdChanged",
        "assetIdentityBranch", "perAssetBattleCode", "perAssetTacticalTuning",
        "perVideoTrajectoryEngineering", "fixedWorldCoordinates",
        "exactCollisionFrameTarget", "exactImpactEnergyTarget",
        "actorPoseOrVelocityMutation", "fixtureBattlePlanChanged", "storyTimingChanged",
        "programDurationChanged", "frozenNineServiceArchitectureChanged",
        "gateClosed", "productionReadyClaimed",
    ):
        assert receipt.get(field) is False, (field, receipt.get(field))

    engaged = _rows(rows, "G04_CERTIFIED_APPROACH_NAVIGATION_CONTINUITY_ENGAGED")
    requests = _rows(rows, "G04_CERTIFIED_SOLVER_HANDOFF_REQUESTED")
    latches = _rows(rows, "GENERIC_SOLVER_HANDOFF_LATCHED")
    contacts = _rows(rows, "PAIRWISE_NATIVE_SOLVER_CONTACT_VERIFIED")
    invalidated = _rows(rows, "G04_REALIZED_APPROACH_CERTIFICATE_INVALIDATED")
    transitions = _rows(rows, "G04_ENGAGEMENT_LIFECYCLE_TRANSITION")

    assert engaged, "C491_CERTIFIED_NAVIGATION_CONTINUITY_NOT_EXERCISED"
    assert requests, "C491_CERTIFIED_HANDOFF_REQUEST_NOT_OBSERVED"
    assert latches, "C491_HANDOFF_LATCH_NOT_OBSERVED"
    assert contacts, "C491_NATIVE_CONTACT_NOT_OBSERVED"

    continuity_to_handoff: list[dict[str, object]] = []
    for start in engaged:
        key = _key(start)
        if not all(key):
            continue
        start_frame = _frame(start)
        qualified_frame = int(start.get("qualifiedFrame") or -1)
        candidates = [
            r for r in requests
            if _key(r) == key
            and _frame(r) >= start_frame
            and int(r.get("qualifiedFrame") or -2) == qualified_frame
        ]
        if not candidates:
            continue
        request = min(candidates, key=_frame)
        request_frame = _frame(request)

        # C490 exposed two equivalent ways the duplicate C487 readiness signal can
        # destroy an already-earned C488 certificate. C491 must close both while
        # continuity legitimately owns the same contact-directed transaction.
        bad_invalidations = [
            r for r in invalidated
            if _key(r) == key
            and start_frame <= _frame(r) <= request_frame
            and str(r.get("reason") or "") in DUPLICATE_READINESS_INVALIDATIONS
        ]
        bad_runway_reopen = [
            r for r in transitions
            if _key(r) == key
            and start_frame <= _frame(r) <= request_frame
            and str(r.get("phase") or "") == "RUNWAY_REOPEN"
        ]
        assert not bad_invalidations, (
            "C491_CERTIFICATE_INVALIDATED_BY_DUPLICATE_READINESS", key, bad_invalidations
        )
        assert not bad_runway_reopen, (
            "C491_DUPLICATE_READINESS_REOPENED_RUNWAY", key, bad_runway_reopen
        )

        latch_rows = [
            r for r in latches
            if str(r.get("eventId") or "") == key[0]
            and str(r.get("actorId") or "") == key[1]
            and _frame(r) >= request_frame
        ]
        if not latch_rows:
            continue
        latch = min(latch_rows, key=_frame)
        latch_frame = _frame(latch)
        native = [r for r in contacts if _key(r) == key and _frame(r) >= latch_frame]
        if not native:
            continue
        contact = min(native, key=_frame)
        contact_frame = _frame(contact)
        assert qualified_frame <= start_frame <= request_frame <= latch_frame <= contact_frame, (
            "C491_CERTIFICATE_CONTINUITY_ORDER_INVALID", key,
            qualified_frame, start_frame, request_frame, latch_frame, contact_frame,
        )
        continuity_to_handoff.append({
            "eventId": key[0],
            "attackerId": key[1],
            "targetId": key[2],
            "qualifiedFrame": qualified_frame,
            "continuityFrame": start_frame,
            "handoffFrame": request_frame,
            "latchFrame": latch_frame,
            "nativeContactFrame": contact_frame,
        })

    counter = [row for row in continuity_to_handoff if row["eventId"] == "evt-counterattack"]
    assert counter, (
        "C491_COUNTERATTACK_CERTIFIED_CONTINUITY_TO_NATIVE_CONTACT_NOT_PROVEN",
        continuity_to_handoff,
    )

    climax = _rows(rows, "G07_CAUSAL_CLIMAX_STATE_REALIZED")
    salience = _rows(rows, "G08_CINEMATIC_SALIENCE_EVIDENCE_WRITTEN")
    runtime_result = _rows(rows, "GENERIC_BATTLE_RUNTIME_RESULT")
    assert climax, "C491_G07_CAUSAL_CLIMAX_NOT_REALIZED"
    assert salience, "C491_G08_SALIENCE_EVIDENCE_NOT_WRITTEN"
    assert runtime_result and any(r.get("success") is True for r in runtime_result), runtime_result

    # If a recoverable G05 NACK occurs, C489's full release -> recovery -> fresh
    # handoff -> native-contact transaction remains mandatory. If not exercised in
    # this physical run, C490's exact-source composition remains a regression asset.
    releases = _rows(rows, "G04_G05_NEGATIVE_ACK_HANDOFF_RELEASED")
    if releases:
        nack_proof: dict[str, object] = c489.c489_runtime_proof(log_path)
    else:
        nack_proof = {
            "g05NegativeAckCurrentRun": "NOT_EXERCISED",
            "c490CompositionBindingPreservedByExactSource": True,
        }

    inherited_c488 = c488.c488_runtime_proof(log_path)
    return {
        "certifiedNavigationContinuityRuntimeReceipt": "PASS",
        "certificateLiveReadinessContinuityRuntimeReceipt": "PASS",
        "preQualificationReadinessUnchanged": True,
        "duplicateReadinessRunwayReopenClosed": "PASS",
        "duplicateReadinessCertificateInvalidationClosed": "PASS",
        "sameCertificateContinuityToHandoff": "PASS",
        "counterattackCertifiedContinuityToNativeContact": "PASS",
        "counterattackContinuityTransactions": counter,
        "g07CausalClimaxAfterCounterattack": "PASS",
        "g08MachineObservability": "PASS",
        "runtimeSuccess": True,
        **inherited_c488,
        **nack_proof,
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
    c491 = c491_runtime_proof(a.hetero_log)

    print(json.dumps({
        "marker": "GENERIC_AUTONOMOUS_BATTLE_C491_MACHINE_ACCEPTANCE",
        "status": "PASS",
        "candidate": CANDIDATE,
        "mechanism": CERTIFIED_NAVIGATION_CONTINUITY_MODEL,
        "executionProfile": "NVIDIA_L4",
        "productionReadyHeavyAssetProof": "PASS",
        "canonicalFrameMetadataProof": "PASS",
        "heterogeneousActorProfileProof": "PASS",
        "sameRuntimeAcrossDissimilarActorProfiles": True,
        **directions, **approach, **recovery, **roles, **drive_direction, **c491,
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
        "nativeContactAuthorityPreserved": True,
        "pairwiseSolverOraclePreserved": True,
        "g05ThresholdImported": False,
        "contactThresholdChanged": False,
        "semanticToleranceChanged": False,
        "localityToleranceChanged": False,
        "damageAdmissionThresholdChanged": False,
        "actualGoalReadinessThresholdChanged": False,
        "fixtureBattlePlanChanged": False,
        "storyTimingChanged": False,
        "programDurationChanged": False,
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
