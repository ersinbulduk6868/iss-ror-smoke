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

import validate_generic_autonomous_battle_c489_result as c489
from validate_generic_autonomous_battle_c480_result import _json_markers

CANDIDATE = "ISS_GENERIC_BATTLE_RUNTIME_V1_CANDIDATE_4_9_1_GENERIC_AUTONOMOUS_BATTLE"
MECHANISM = "G04_CERTIFIED_APPROACH_ALIGNMENT_OWNERSHIP_V1"
FAILURE_FAMILY = "QUALIFIED_APPROACH_CERTIFICATE_PREEMPTED_BY_LEGACY_FULL_RUNWAY_REOPEN"


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
    assert receipt.get("mechanism") == MECHANISM, receipt
    assert receipt.get("affectedLayerAuditStatus") == "PASS", receipt
    assert receipt.get("failureFamily") == FAILURE_FAMILY, receipt

    for field in (
        "c490FinalCompositionBindingPreserved",
        "c489NegativeAckRecoveryPreserved",
        "c488CertifiedApproachAuthorityPreserved",
        "c488AlignmentAuthorityPreserved",
        "c487RecoveryPriorityPreserved",
        "existingHeadingReadinessGatePreserved",
        "existingContentionReadinessGatePreserved",
        "headingOnlyMissCannotHandoff",
        "contentionMissKeepsLegacyRunwayReopen",
        "recoveryKeepsLegacyOwnership",
        "realPrecontactSeparationStillInvalidatesCertificate",
    ):
        assert receipt.get(field) is True, (field, receipt.get(field))

    for field in (
        "storyDurationChanged", "eventTimingChanged",
        "g05SourceChanged", "g05OuterGateChanged", "g05SolverOracleChanged",
        "g05ThresholdImported", "headingThresholdChanged", "contentionThresholdChanged",
        "contactThresholdChanged", "semanticToleranceChanged",
        "localityToleranceChanged", "damageAdmissionThresholdChanged",
        "assetIdentityBranch", "perAssetBattleCode", "perAssetTacticalTuning",
        "perVideoTrajectoryEngineering", "fixedWorldCoordinates",
        "exactCollisionFrameTarget", "exactImpactEnergyTarget",
        "actorPoseOrVelocityMutation", "fixtureBattlePlanChanged",
        "frozenNineServiceArchitectureChanged", "gateClosed", "productionReadyClaimed",
    ):
        assert receipt.get(field) is False, (field, receipt.get(field))

    defers = _rows(rows, "G04_CERTIFIED_APPROACH_LEGACY_RUNWAY_REOPEN_DEFERRED")
    holds = _rows(rows, "G04_CERTIFIED_APPROACH_ALIGNMENT_HOLD")
    qualified = _rows(rows, "G04_REALIZED_APPROACH_CERTIFICATE_QUALIFIED")
    invalidated = _rows(rows, "G04_REALIZED_APPROACH_CERTIFICATE_INVALIDATED")
    handoff_requests = _rows(rows, "G04_CERTIFIED_SOLVER_HANDOFF_REQUESTED")
    latches = _rows(rows, "GENERIC_SOLVER_HANDOFF_LATCHED")
    tactics = _rows(rows, "GENERIC_BATTLE_TACTIC_CHANGED")

    assert defers, "C491_CERTIFIED_RUNWAY_REOPEN_DEFER_NOT_OBSERVED"
    assert holds, "C491_CERTIFICATE_ALIGNMENT_HOLD_NOT_OBSERVED"

    proven: list[tuple[str, str, str]] = []
    for defer in defers:
        key = _key(defer)
        if key[0] != "evt-counterattack":
            continue
        assert all(key), ("C491_DEFER_TRANSACTION_INCOMPLETE", defer)
        defer_frame = _frame(defer)
        heading = abs(float(defer.get("headingErrorRad") or 0.0))
        heading_limit = float(defer.get("existingHeadingLimitRad") or 0.0)
        contention = float(defer.get("contention") or 0.0)
        contention_limit = float(defer.get("existingContentionLimit") or 0.0)
        assert heading_limit > 0.0 and heading > heading_limit, defer
        assert contention_limit > 0.0 and contention < contention_limit, defer
        assert defer.get("headingThresholdChanged") is False, defer
        assert defer.get("contentionThresholdChanged") is False, defer
        assert defer.get("contactThresholdChanged") is False, defer
        assert defer.get("delegatedAction") == "DEFER_TO_TACTIC", defer
        assert defer.get("delegatedAuthority") == "C488_CERTIFIED_APPROACH_AND_ALIGNMENT", defer

        prior_cert = [
            r for r in qualified
            if _key(r) == key and _frame(r) <= defer_frame
        ]
        assert prior_cert, ("C491_DEFER_WITHOUT_PRIOR_CERTIFICATE", key, defer_frame)
        qualified_frame = max(_frame(r) for r in prior_cert)
        assert qualified_frame <= defer_frame, (key, qualified_frame, defer_frame)

        same_holds = [
            r for r in holds
            if _key(r) == key and _frame(r) >= defer_frame
        ]
        assert same_holds, ("C491_DEFER_WITHOUT_CERTIFICATE_HOLD", key, defer_frame)
        for hold in same_holds:
            assert hold.get("certificatePreserved") is True, hold
            assert hold.get("instantaneousReadiness") is False, hold
            assert hold.get("handoffAllowedWhileUnready") is False, hold
            assert hold.get("headingThresholdChanged") is False, hold
            assert hold.get("contentionThresholdChanged") is False, hold

        next_requests = [
            r for r in handoff_requests
            if _key(r) == key and _frame(r) > defer_frame
        ]
        assert next_requests, ("C491_NO_HANDOFF_AFTER_ALIGNMENT_HOLD", key, defer_frame)
        handoff_frame = min(_frame(r) for r in next_requests)
        next_latches = [
            r for r in latches
            if str(r.get("eventId") or "") == key[0]
            and str(r.get("actorId") or "") == key[1]
            and _frame(r) >= handoff_frame
        ]
        assert next_latches, ("C491_HANDOFF_REQUEST_WITHOUT_LATCH", key, handoff_frame)

        lost = [
            r for r in invalidated
            if _key(r) == key
            and defer_frame <= _frame(r) < handoff_frame
            and str(r.get("reason") or "") in {
                "TACTIC_NOT_CONTACT_DIRECTED",
                "LIVE_READINESS_LOST",
            }
        ]
        assert not lost, ("C491_CERTIFICATE_LOST_DURING_ALIGNMENT_HOLD", key, lost[-3:])

        full_retreat = [
            r for r in tactics
            if str(r.get("eventId") or "") == key[0]
            and str(r.get("actorId") or "") == key[1]
            and defer_frame <= _frame(r) < handoff_frame
            and str(r.get("reason") or "") == "ACTUAL_GOAL_READINESS_RUNWAY_REOPEN"
        ]
        assert not full_retreat, ("C491_LEGACY_FULL_RUNWAY_REOPEN_NOT_SUPPRESSED", key, full_retreat[-3:])
        proven.append(key)

    assert proven, "C491_COUNTERATTACK_ALIGNMENT_OWNERSHIP_NOT_PROVEN"

    # The successor must still close the complete C489 physical negative-ack family:
    # handoff -> confirmed G05 NACK -> release -> recovery/replan completion -> fresh
    # semantic transaction -> fresh handoff -> native contact.  This prevents C491
    # from merely making the first handoff earlier while leaving retry broken.
    nack = c489.c489_runtime_proof(log_path)

    return {
        "certifiedAlignmentOwnershipRuntimeProof": "PASS",
        "headingThresholdPreservedAtRuntime": True,
        "contentionThresholdPreservedAtRuntime": True,
        "instantaneousReadinessBlockedHandoffDuringHold": True,
        "legacyFullRunwayReopenSuppressedOnlyForCertifiedAlignmentHold": True,
        "certificateContinuityToHandoff": "PASS",
        "counterattackAlignmentOwnershipTransactionCount": len(set(proven)),
        "completeC489NegativeAckRecovery": "PASS",
        "negativeAckProof": nack,
    }


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--log", required=True)
    a = p.parse_args()
    proof = c491_runtime_proof(a.log)

    print(json.dumps({
        "marker": "GENERIC_AUTONOMOUS_BATTLE_C491_MACHINE_ACCEPTANCE",
        "status": "PASS",
        "candidate": CANDIDATE,
        "mechanism": MECHANISM,
        "failureFamily": FAILURE_FAMILY,
        "executionProfile": "NVIDIA_L4",
        **proof,
        "c490FinalCompositionPreserved": True,
        "c489NegativeAckRecoveryPreserved": True,
        "c488AuthorityTransferPreserved": True,
        "c487RecoveryPriorityPreserved": True,
        "g05AuthorityPreserved": True,
        "headingThresholdChanged": False,
        "contentionThresholdChanged": False,
        "contactThresholdChanged": False,
        "semanticToleranceChanged": False,
        "localityToleranceChanged": False,
        "damageAdmissionThresholdChanged": False,
        "storyDurationChanged": False,
        "eventTimingChanged": False,
        "perAssetBattleCode": False,
        "perAssetTacticalTuning": False,
        "perVideoTrajectoryEngineering": False,
        "gateClosed": False,
        "productionReadyClaimed": False,
    }, sort_keys=True))


if __name__ == "__main__":
    main()
