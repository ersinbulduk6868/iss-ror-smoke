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
from validate_generic_autonomous_battle_c480_result import _json_markers
from blender.iss_battle_runtime_g05_negative_ack_v1 import (
    G05_NEGATIVE_ACK_MODEL,
    RECOVERABLE_OUTER_REASONS,
    STAGE_IMPACT_GATE,
    STAGE_OUTER,
    STAGE_SOLVER,
)

CANDIDATE = "ISS_GENERIC_BATTLE_RUNTIME_V1_CANDIDATE_4_8_9_GENERIC_AUTONOMOUS_BATTLE"
FAILURE_FAMILY = "G05_REJECTION_DOES_NOT_RETURN_CONTROL_TO_G04_RECOVERY"


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


def c489_runtime_proof(log_path: str) -> dict[str, object]:
    rows = _json_markers(log_path)
    ready = _rows(rows, "GENERIC_AUTONOMOUS_BATTLE_C489_ENGINEERING_READY")
    assert len(ready) == 1, ("C489_ENGINEERING_READY_COUNT", len(ready))
    receipt = ready[0]
    assert receipt.get("candidate") == CANDIDATE, receipt
    assert receipt.get("mechanism") == G05_NEGATIVE_ACK_MODEL, receipt
    assert receipt.get("affectedLayerAuditStatus") == "PASS", receipt
    assert receipt.get("failureFamily") == FAILURE_FAMILY, receipt

    for field in (
        "g05DecisionObservedWithoutAuthorityChange",
        "outerAuthorityNegativeAckObserved",
        "solverResponseNegativeAckObserved",
        "existingImpactGateNegativeAckObserved",
        "negativeAckConfirmationUsesExistingG05SolverWindow",
        "singleFrameOuterOrSolverNoiseDoesNotForceRecovery",
        "existingImpactGateNegativeAckImmediate",
        "recoverableGeometryNackReleasesHandoff",
        "recoverableSolverNackReleasesHandoff",
        "recoverableImpactGateNackReleasesHandoff",
        "controllerAuthorityRegressionNotHiddenByRecovery",
        "targetIdentityRegressionNotHiddenByRecovery",
        "negativeAckTriggersExistingRecoveryController",
        "negativeAckTriggersEventScopedReplan",
        "semanticTransactionCanReleaseDuringRecovery",
        "freshAttemptMayReselectLivePairSemanticSurface",
        "c488ContinuousApproachCertificatePreserved",
        "c488AtomicMotorToCoastHandoffPreserved",
        "c487EventScopedRecoveryPreserved",
        "c480SemanticTransactionPreserved",
    ):
        assert receipt.get(field) is True, (field, receipt.get(field))

    for field in (
        "g05SourceChanged", "g05OuterGateChanged", "g05SolverOracleChanged",
        "g05ThresholdImported", "contactThresholdChanged", "semanticToleranceChanged",
        "localityToleranceChanged", "damageAdmissionThresholdChanged",
        "assetIdentityBranch", "perAssetBattleCode", "perAssetTacticalTuning",
        "perVideoTrajectoryEngineering", "fixedWorldCoordinates",
        "exactCollisionFrameTarget", "exactImpactEnergyTarget",
        "actorPoseOrVelocityMutation", "fixtureBattlePlanChanged",
        "frozenNineServiceArchitectureChanged", "gateClosed", "productionReadyClaimed",
    ):
        assert receipt.get(field) is False, (field, receipt.get(field))

    observed = _rows(rows, "G04_G05_NEGATIVE_ACK_OBSERVED")
    pending = _rows(rows, "G04_G05_NEGATIVE_ACK_PENDING_CONFIRMATION")
    released = _rows(rows, "G04_G05_NEGATIVE_ACK_HANDOFF_RELEASED")
    suspended = _rows(rows, "G04_G05_NEGATIVE_ACK_CONTACT_COMMIT_SUSPENDED")
    recovery_started = _rows(rows, "G04_G05_NEGATIVE_ACK_RECOVERY_TRIGGERED")
    replans = _rows(rows, "G04_EVENT_SCOPED_RECOVERY_REPLAN_PROPAGATED")
    recovery_done = _rows(rows, "G04_EVENT_SCOPED_RECOVERY_COMPLETED_RUNWAY_INVALIDATED")
    semantic_releases = _rows(rows, "GENERIC_APPROACH_SEMANTIC_TRANSACTION_RELEASED")
    semantic_starts = _rows(rows, "GENERIC_APPROACH_SEMANTIC_TRANSACTION_STARTED")
    semantic_refines = _rows(rows, "GENERIC_HANDOFF_LIVE_PAIR_SURFACE_REFINED")
    latches = _rows(rows, "GENERIC_SOLVER_HANDOFF_LATCHED")
    contacts = _rows(rows, "PAIRWISE_NATIVE_SOLVER_CONTACT_VERIFIED")
    outer_rejects = _rows(rows, "G05_OUTER_CONTACT_AUTHORITY_REJECTED")

    assert observed, "C489_G05_NEGATIVE_ACK_NOT_OBSERVED"
    assert released, "C489_NEGATIVE_ACK_DID_NOT_RELEASE_HANDOFF"
    assert suspended, "C489_NEGATIVE_ACK_DID_NOT_SUSPEND_CONTACT_COMMIT"
    assert recovery_started, "C489_NEGATIVE_ACK_DID_NOT_START_RECOVERY"
    assert replans, "C489_NEGATIVE_ACK_DID_NOT_PROPAGATE_REPLAN"
    assert recovery_done, "C489_NEGATIVE_ACK_RECOVERY_DID_NOT_COMPLETE"
    assert contacts, "C489_NATIVE_CONTACT_NOT_OBSERVED_AFTER_RECOVERY"

    valid_recoveries: list[tuple[str, str, str]] = []
    for release in released:
        key = _key(release)
        assert all(key), ("C489_RELEASE_TRANSACTION_INCOMPLETE", release)
        stage = str(release.get("stage") or "")
        reason = str(release.get("reason") or "")
        required = int(release.get("requiredConfirmationFrames") or 0)
        observed_count = int(release.get("consecutiveRejectFrames") or 0)
        first_reject = int(release.get("firstRejectFrame") or -1)
        release_frame = _frame(release)
        handoff_start = int(release.get("handoffStartFrame") or -1)
        cutoff_frame = int(release.get("cutoffFrame") or -1)

        assert handoff_start >= 0 and cutoff_frame >= 0, release
        assert handoff_start <= first_reject <= release_frame, release
        if stage == STAGE_IMPACT_GATE:
            assert observed_count >= 1, release
        else:
            assert stage in {STAGE_OUTER, STAGE_SOLVER}, release
            assert required > 1, release
            assert observed_count >= required, release
        if stage == STAGE_OUTER:
            assert reason in RECOVERABLE_OUTER_REASONS, release

        same_pending = [r for r in pending if _key(r) == key and handoff_start <= _frame(r) <= release_frame]
        if stage != STAGE_IMPACT_GATE:
            assert same_pending, ("C489_CONFIRMATION_WINDOW_NOT_OBSERVED", key, release)

        starts = [r for r in recovery_started if _key(r) == key and _frame(r) >= release_frame]
        assert starts, ("C489_RELEASE_WITHOUT_RECOVERY_START", key, release)
        recovery_frame = min(_frame(r) for r in starts)
        susp = [r for r in suspended if _key(r) == key and release_frame <= _frame(r) <= recovery_frame]
        assert susp, ("C489_CONTACT_COMMIT_NOT_SUSPENDED_BEFORE_RECOVERY", key)

        rp = [r for r in replans if _key(r) == key and _frame(r) >= recovery_frame]
        assert rp, ("C489_RECOVERY_WITHOUT_EVENT_REPLAN", key, recovery_frame)
        replan_frame = min(_frame(r) for r in rp)

        done = [r for r in recovery_done if _key(r) == key and _frame(r) >= replan_frame]
        assert done, ("C489_RECOVERY_WITHOUT_COMPLETION", key, replan_frame)
        done_frame = min(_frame(r) for r in done)

        releases = [
            r for r in semantic_releases
            if str(r.get("eventId") or "") == key[0]
            and _frame(r) >= release_frame
            and str(r.get("releaseReason") or "") == "TACTICAL_CONTACT_COMMIT_ENDED"
        ]
        assert releases, ("C489_SEMANTIC_TRANSACTION_NOT_RELEASED_DURING_RECOVERY", key)
        semantic_release_frame = min(_frame(r) for r in releases)

        next_latches = [
            r for r in latches
            if str(r.get("eventId") or "") == key[0]
            and str(r.get("actorId") or "") == key[1]
            and _frame(r) > done_frame
        ]
        assert next_latches, ("C489_NO_FRESH_HANDOFF_AFTER_RECOVERY", key, done_frame)
        next_latch_frame = min(_frame(r) for r in next_latches)

        restarts = [
            r for r in semantic_starts
            if str(r.get("eventId") or "") == key[0]
            and _frame(r) > semantic_release_frame
            and _frame(r) <= next_latch_frame
        ]
        assert restarts, ("C489_SEMANTIC_TRANSACTION_NOT_RESTARTED", key, semantic_release_frame, next_latch_frame)

        refines = [
            r for r in semantic_refines
            if str(r.get("eventId") or "") == key[0]
            and str(r.get("actorId") or "") == key[1]
            and _frame(r) >= next_latch_frame
        ]
        assert refines, ("C489_FRESH_HANDOFF_DID_NOT_RESELECT_LIVE_PAIR_SURFACE", key, next_latch_frame)

        native = [
            r for r in contacts
            if _key(r) == key and _frame(r) >= next_latch_frame
        ]
        assert native, ("C489_FRESH_HANDOFF_WITHOUT_NATIVE_CONTACT", key, next_latch_frame)
        native_frame = min(_frame(r) for r in native)

        # C489 may recover from physical NACKs, but it must never hide G04 authority
        # or target-identity regressions after the handoff transaction begins.
        bad_contract = [
            r for r in outer_rejects
            if _key(r) == key
            and _frame(r) >= handoff_start
            and str(r.get("reason") or "") in {
                "CONTROLLER_AUTHORITY_NOT_RELEASED",
                "TARGET_IDENTITY_MISMATCH",
            }
        ]
        assert not bad_contract, ("C489_CONTRACT_REGRESSION_HIDDEN_BY_RECOVERY", key, bad_contract[-3:])

        assert handoff_start <= first_reject <= release_frame <= recovery_frame <= replan_frame <= done_frame < next_latch_frame <= native_frame, (
            "C489_RECOVERY_ORDER_INVALID",
            key,
            handoff_start,
            first_reject,
            release_frame,
            recovery_frame,
            replan_frame,
            done_frame,
            next_latch_frame,
            native_frame,
        )
        valid_recoveries.append(key)

    assert valid_recoveries, "C489_NO_COMPLETE_NACK_RECOVERY_TRANSACTION"
    counter = [key for key in valid_recoveries if key[0] == "evt-counterattack"]
    assert counter, ("C489_COUNTERATTACK_NACK_RECOVERY_NOT_PROVEN", valid_recoveries)

    return {
        "g05NegativeAckRuntimeReceipt": "PASS",
        "confirmedNackReleasesHandoff": "PASS",
        "negativeAckToRecoveryToReplan": "PASS",
        "semanticTransactionReleaseAndFreshReselection": "PASS",
        "freshHandoffToNativeContact": "PASS",
        "counterattackNegativeAckRecovery": "PASS",
        "completeNackRecoveryTransactionCount": len(set(valid_recoveries)),
        "controllerAuthorityRegressionNotHidden": True,
        "targetIdentityRegressionNotHidden": True,
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
    inherited_c488 = c488.c488_runtime_proof(a.hetero_log)
    c489 = c489_runtime_proof(a.hetero_log)

    print(json.dumps({
        "marker": "GENERIC_AUTONOMOUS_BATTLE_C489_MACHINE_ACCEPTANCE",
        "status": "PASS",
        "candidate": CANDIDATE,
        "mechanism": G05_NEGATIVE_ACK_MODEL,
        "executionProfile": "NVIDIA_L4",
        "productionReadyHeavyAssetProof": "PASS",
        "canonicalFrameMetadataProof": "PASS",
        "heterogeneousActorProfileProof": "PASS",
        "sameRuntimeAcrossDissimilarActorProfiles": True,
        **directions, **approach, **recovery, **roles, **drive_direction,
        **inherited_c488, **c489,
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
