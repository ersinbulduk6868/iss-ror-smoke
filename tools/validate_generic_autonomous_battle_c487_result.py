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

import validate_generic_autonomous_battle_c485_result as c485

MODEL = "G04_EVENT_SCOPED_ENGAGEMENT_AUTHORITY_LIFECYCLE_V1"
CANDIDATE = "ISS_GENERIC_BATTLE_RUNTIME_V1_CANDIDATE_4_8_7_GENERIC_AUTONOMOUS_BATTLE"


def _frame(row: dict[str, Any]) -> int:
    return int(row.get("frame") or 0)


def _key(row: dict[str, Any]) -> tuple[str, str, str]:
    return (
        str(row.get("eventId") or ""),
        str(row.get("attackerId") or row.get("actorId") or ""),
        str(row.get("targetId") or ""),
    )


def c487_runtime_proof(log_path: str) -> dict[str, object]:
    rows = c485._json_markers(log_path)
    ready = [r for r in rows if r.get("marker") == "GENERIC_AUTONOMOUS_BATTLE_C487_ENGINEERING_READY"]
    assert len(ready) == 1, ("C487_ENGINEERING_READY_COUNT", len(ready))
    receipt = ready[0]
    assert receipt.get("candidate") == CANDIDATE, receipt
    assert receipt.get("mechanism") == MODEL, receipt
    assert receipt.get("affectedLayerAuditStatus") == "PASS", receipt
    for field in (
        "eventActorTargetTransactionScope",
        "eventScopedTacticalMemory",
        "actualNavigationGoalReadiness",
        "tacticalMutationProgressContextSynchronized",
        "modeAwareContactCorridor",
        "recoveryOwnsMotorAuthorityUntilCompletion",
        "recoveryReplanPropagatedExactlyOncePerEpoch",
        "runwayInvalidatedAfterRecovery",
        "legacyPairStateClearedOnEventTransition",
        "flankBrakeEvadeOwnershipPreserved",
        "c486ModeBlindCorridorSuperseded",
        "c485RealizedMotionHandoffPreserved",
        "c484AlignmentSemanticsPreserved",
        "c483DriveDirectionPreserved",
        "c482CollisionRolesPreserved",
        "c480SemanticTransactionPreserved",
        "g05NativeSolverFinalAuthorityPreserved",
    ):
        assert receipt.get(field) is True, (field, receipt.get(field))
    for field in (
        "g05SourceChanged",
        "g06SourceChanged",
        "g07SourceChanged",
        "g08SourceChanged",
        "g05ThresholdImported",
        "contactThresholdChanged",
        "semanticToleranceChanged",
        "localityToleranceChanged",
        "damageAdmissionThresholdChanged",
        "damageThresholdAwareControl",
        "targetToughnessAwareControl",
        "desiredImpactSpeedControl",
        "desiredImpactEnergyControl",
        "assetIdentityBranch",
        "perAssetBattleCode",
        "perAssetTacticalTuning",
        "perVideoTrajectoryEngineering",
        "fixedWorldCoordinates",
        "actorPoseOrVelocityMutation",
        "fixtureBattlePlanChanged",
        "frozenNineServiceArchitectureChanged",
        "gateClosed",
        "productionReadyClaimed",
    ):
        assert receipt.get(field) is False, (field, receipt.get(field))

    lifecycle = [r for r in rows if r.get("marker") == "G04_ENGAGEMENT_LIFECYCLE_TRANSITION"]
    stalls = [r for r in rows if r.get("marker") == "G04_EVENT_SCOPED_STALL_RECOVERY_TRIGGERED"]
    replans = [r for r in rows if r.get("marker") == "G04_EVENT_SCOPED_RECOVERY_REPLAN_PROPAGATED"]
    completions = [r for r in rows if r.get("marker") == "G04_EVENT_SCOPED_RECOVERY_COMPLETED_RUNWAY_INVALIDATED"]
    readiness = [r for r in rows if r.get("marker") == "G04_ACTUAL_GOAL_CONTACT_READINESS_RECOVERED"]
    handoffs = [r for r in rows if r.get("marker") == "GENERIC_SOLVER_HANDOFF_LATCHED"]
    contacts = [r for r in rows if r.get("marker") == "PAIRWISE_NATIVE_SOLVER_CONTACT_VERIFIED"]
    generic_replans = [r for r in rows if r.get("marker") == "AUTONOMY_REPLAN_TRIGGERED"]

    assert lifecycle, "C487_LIFECYCLE_TRANSITIONS_NOT_OBSERVED"
    assert stalls, "C487_EVENT_SCOPED_STALL_RECOVERY_NOT_OBSERVED"
    assert replans, "C487_RECOVERY_REPLAN_PROPAGATION_NOT_OBSERVED"
    assert completions, "C487_RECOVERY_COMPLETION_NOT_OBSERVED"
    assert readiness, "C487_ACTUAL_GOAL_READINESS_RECOVERY_NOT_OBSERVED"
    assert handoffs, "C487_SOLVER_HANDOFF_NOT_OBSERVED"
    assert contacts, "C487_NATIVE_SOLVER_CONTACT_NOT_OBSERVED"

    scoped_rows = lifecycle + stalls + replans + completions + readiness
    for row in scoped_rows:
        key = _key(row)
        assert all(key), ("C487_TRANSACTION_IDENTITY_INCOMPLETE", row)
        if row.get("model") is not None:
            assert row.get("model") == MODEL, ("C487_WRONG_LIFECYCLE_MODEL", row)

    # Exactly one propagated replan per event-scoped recovery epoch.
    replan_epochs: set[tuple[str, str, str, int]] = set()
    for row in replans:
        key = (*_key(row), int(row.get("recoveryEpoch") or 0))
        assert key[3] > 0, row
        assert key not in replan_epochs, ("C487_DUPLICATE_REPLAN_FOR_RECOVERY_EPOCH", key)
        replan_epochs.add(key)
        assert any(
            _frame(g) == _frame(row)
            and str(g.get("eventId") or "") == key[0]
            and str(g.get("actorId") or "") == key[1]
            for g in generic_replans
        ), ("C487_REPLAN_NOT_PROPAGATED_TO_EVENT_STATE", row)

    # Map legacy handoff markers, which do not carry targetId, back to exactly one
    # C487 event transaction. This prevents pair-only evidence from satisfying a
    # different sequential event.
    target_by_event_actor: dict[tuple[str, str], set[str]] = {}
    for row in scoped_rows:
        event_id, actor_id, target_id = _key(row)
        target_by_event_actor.setdefault((event_id, actor_id), set()).add(target_id)
    for key2, targets in target_by_event_actor.items():
        assert len(targets) == 1, ("C487_AMBIGUOUS_EVENT_ACTOR_TARGET", key2, sorted(targets))

    handoff_by_key: dict[tuple[str, str, str], list[int]] = {}
    for row in handoffs:
        event_id = str(row.get("eventId") or "")
        actor_id = str(row.get("actorId") or "")
        targets = target_by_event_actor.get((event_id, actor_id), set())
        assert len(targets) == 1, ("C487_HANDOFF_TRANSACTION_UNRESOLVED", row, sorted(targets))
        key = (event_id, actor_id, next(iter(targets)))
        handoff_by_key.setdefault(key, []).append(_frame(row))

    contact_by_key: dict[tuple[str, str, str], list[int]] = {}
    for row in contacts:
        key = _key(row)
        assert all(key), row
        contact_by_key.setdefault(key, []).append(_frame(row))

    stall_by_key: dict[tuple[str, str, str], list[int]] = {}
    replan_by_key: dict[tuple[str, str, str], list[int]] = {}
    completion_by_key: dict[tuple[str, str, str], list[int]] = {}
    ready_by_key: dict[tuple[str, str, str], list[int]] = {}
    for row in stalls:
        stall_by_key.setdefault(_key(row), []).append(_frame(row))
    for row in replans:
        replan_by_key.setdefault(_key(row), []).append(_frame(row))
    for row in completions:
        completion_by_key.setdefault(_key(row), []).append(_frame(row))
    for row in readiness:
        ready_by_key.setdefault(_key(row), []).append(_frame(row))

    recovered_contact_transactions: list[tuple[str, str, str]] = []
    for key in sorted(set(stall_by_key) & set(replan_by_key) & set(completion_by_key) & set(ready_by_key) & set(handoff_by_key) & set(contact_by_key)):
        s = min(stall_by_key[key])
        r = min(x for x in replan_by_key[key] if x >= s)
        c = min(x for x in completion_by_key[key] if x >= r)
        q = min(x for x in ready_by_key[key] if x >= c)
        h = min(x for x in handoff_by_key[key] if x >= q)
        n = min(x for x in contact_by_key[key] if x >= h)
        assert s <= r <= c <= q <= h <= n, ("C487_RECOVERY_TO_NATIVE_CONTACT_ORDER_INVALID", key, s, r, c, q, h, n)
        recovered_contact_transactions.append(key)

    assert recovered_contact_transactions, (
        "C487_NO_SINGLE_EVENT_TRANSACTION_RECOVERED_THROUGH_NATIVE_CONTACT",
        sorted(stall_by_key), sorted(replan_by_key), sorted(completion_by_key),
        sorted(ready_by_key), sorted(handoff_by_key), sorted(contact_by_key),
    )

    # C485's realized-motion gate remains a runtime regression signal, but its old
    # pair-only markers are not used as C487 transaction authority.
    assert any(r.get("marker") == "G04_CONTACT_HANDOFF_DEFERRED_BY_REALIZED_APPROACH" for r in rows), "C485_REALIZED_APPROACH_DEFER_REGRESSION_MISSING"
    assert any(r.get("marker") == "G04_CONTACT_HANDOFF_REALIZED_APPROACH_READY" for r in rows), "C485_REALIZED_APPROACH_READY_REGRESSION_MISSING"

    return {
        "eventScopedLifecycleRuntimeReceipt": "PASS",
        "eventScopedRecoveryObserved": True,
        "replanPropagationObserved": True,
        "runwayInvalidationAfterRecoveryObserved": True,
        "actualGoalReadinessRecoveryObserved": True,
        "sameTransactionRecoveryToHandoffToNativeContact": "PASS",
        "recoveredNativeContactTransactionCount": len(recovered_contact_transactions),
        "recoveryEpochCount": len(replan_epochs),
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
    c487 = c487_runtime_proof(a.hetero_log)

    print(json.dumps({
        "marker": "GENERIC_AUTONOMOUS_BATTLE_C487_MACHINE_ACCEPTANCE",
        "status": "PASS",
        "candidate": CANDIDATE,
        "mechanism": MODEL,
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
        **c487,
        "radialNavigationContractPreserved": "PASS",
        "obbHandoffEligibilityPreserved": "PASS",
        "translationDominantHandoffEligibility": "PASS",
        "realizedMotionHandoffPreserved": "PASS",
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
