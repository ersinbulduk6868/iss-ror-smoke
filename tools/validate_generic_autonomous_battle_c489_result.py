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

CANDIDATE = "ISS_GENERIC_BATTLE_RUNTIME_V1_CANDIDATE_4_8_9_GENERIC_AUTONOMOUS_BATTLE"
MECHANISM = "G05_SOLVER_OBSERVED_CONTACT_SEMANTIC_CLASSIFICATION_V1"
FAILURE_FAMILY = "CONTROL_INTENT_SEMANTIC_FREEZE_OUTLIVES_SOLVER_OBSERVED_CONTACT_SURFACE"


def _frame(row: dict[str, Any]) -> int:
    return int(row.get("frame") or -1)


def _contact_frame(row: dict[str, Any]) -> int:
    return int(row.get("contactFrame") or -1)


def _key(row: dict[str, Any]) -> tuple[str, str, str]:
    return (
        str(row.get("eventId") or ""),
        str(row.get("attackerId") or row.get("actorId") or ""),
        str(row.get("targetId") or ""),
    )


def observed_contact_semantic_runtime_proof(log_path: str) -> dict[str, object]:
    rows = _json_markers(log_path)
    ready = [r for r in rows if r.get("marker") == "GENERIC_AUTONOMOUS_BATTLE_C489_ENGINEERING_READY"]
    assert len(ready) == 1, ("C489_ENGINEERING_READY_COUNT", len(ready))
    receipt = ready[0]
    assert receipt.get("candidate") == CANDIDATE, receipt
    assert receipt.get("mechanism") == MECHANISM, receipt
    assert receipt.get("affectedLayerAuditStatus") == "PASS", receipt
    assert receipt.get("failureFamily") == FAILURE_FAMILY, receipt

    required_true = (
        "controlIntentSemanticAndObservedContactSemanticSeparated",
        "runtimeSelectedSemanticsOnly",
        "activeSolverHandoffRequired",
        "storyPrescribedSemanticTargetRemainsStrict",
        "eventTargetZoneNeverMutatedByObservedClassification",
        "g04ControlIntentPreserved",
        "c480ApproachSemanticFreezePreserved",
        "c470HandoffIntentRefinementPreserved",
        "c467HandoffSemanticFreezePreserved",
        "c488AuthorityTransferPreserved",
        "sameG05BestRecentLocalityGeometryReused",
        "sameG05OuterAuthorityGateReused",
        "sameG05PairwiseSolverOracleReused",
        "sameG05SemanticToleranceReused",
        "observedContactZonePropagatesToPendingImpact",
        "g06DamageZoneUsesObservedContact",
    )
    for field in required_true:
        assert receipt.get(field) is True, (field, receipt.get(field))
    for field in (
        "g05SourceFileChanged", "g06SourceChanged", "g07SourceChanged", "g08SourceChanged",
        "g05ThresholdImportedIntoG04", "contactThresholdChanged", "semanticToleranceChanged",
        "localityToleranceChanged", "damageAdmissionThresholdChanged", "damageThresholdAwareControl",
        "targetToughnessAwareControl", "desiredImpactSpeedControl", "desiredImpactEnergyControl",
        "assetIdentityBranch", "perAssetBattleCode", "perAssetTacticalTuning",
        "perVideoTrajectoryEngineering", "fixedWorldCoordinates", "exactCollisionFrameTarget",
        "exactImpactEnergyTarget", "actorPoseOrVelocityMutation", "fixtureBattlePlanChanged",
        "frozenNineServiceArchitectureChanged", "gateClosed", "productionReadyClaimed",
    ):
        assert receipt.get(field) is False, (field, receipt.get(field))

    classified = [r for r in rows if r.get("marker") == "G05_OBSERVED_CONTACT_SEMANTIC_CLASSIFIED"]
    verified = [r for r in rows if r.get("marker") == "G05_OBSERVED_CONTACT_SEMANTIC_VERIFIED"]
    bound = [r for r in rows if r.get("marker") == "G05_OBSERVED_CONTACT_SEMANTIC_BOUND_TO_PENDING"]
    native = [r for r in rows if r.get("marker") == "PAIRWISE_NATIVE_SOLVER_CONTACT_VERIFIED"]
    handoffs = [r for r in rows if r.get("marker") == "GENERIC_SOLVER_HANDOFF_LATCHED"]
    intent_refinements = [r for r in rows if r.get("marker") == "GENERIC_APPROACH_SEMANTIC_TRANSACTION_REFINED_BY_HANDOFF"]

    assert classified, "C489_OBSERVED_CONTACT_CLASSIFICATION_NOT_OBSERVED"
    assert verified, "C489_OBSERVED_CONTACT_SEMANTIC_VERIFICATION_NOT_OBSERVED"
    assert bound, "C489_OBSERVED_CONTACT_PENDING_BINDING_NOT_OBSERVED"
    assert native, "C489_NATIVE_SOLVER_CONTACT_NOT_OBSERVED"
    assert handoffs, "C489_SOLVER_HANDOFF_NOT_OBSERVED"

    handoff_by_event_actor: dict[tuple[str, str], list[int]] = {}
    for row in handoffs:
        handoff_by_event_actor.setdefault(
            (str(row.get("eventId") or ""), str(row.get("actorId") or "")), []
        ).append(_frame(row))

    refinement_by_event_actor: dict[tuple[str, str], list[dict[str, Any]]] = {}
    for row in intent_refinements:
        refinement_by_event_actor.setdefault(
            (str(row.get("eventId") or ""), str(row.get("actorId") or "")), []
        ).append(row)

    class_by_key_frame: dict[tuple[str, str, str, int], list[dict[str, Any]]] = {}
    migrations: list[dict[str, Any]] = []
    for row in classified:
        key = _key(row)
        assert all(key), ("C489_CLASSIFICATION_TRANSACTION_INCOMPLETE", row)
        assert row.get("model") == MECHANISM, row
        assert row.get("storyTargetZonePrescribed") is False, row
        assert row.get("eventTargetZoneMutated") is False, row
        assert row.get("g04ControlIntentChanged") is False, row
        assert row.get("semanticToleranceChanged") is False, row
        assert row.get("localityToleranceChanged") is False, row
        assert row.get("contactThresholdChanged") is False, row
        event_actor = (key[0], key[1])
        assert event_actor in handoff_by_event_actor, ("C489_CLASSIFICATION_WITHOUT_HANDOFF", row)
        assert _frame(row) >= min(handoff_by_event_actor[event_actor]), row
        intent = str(row.get("engagementIntentZone") or "")
        observed = str(row.get("observedContactZone") or "")
        assert intent and observed, row
        if intent != observed:
            migrations.append(row)
        class_by_key_frame.setdefault((*key, _frame(row)), []).append(row)

    verified_transactions: set[tuple[str, str, str]] = set()
    counterattack_verified = False
    for row in verified:
        key = _key(row)
        assert all(key), ("C489_VERIFIED_TRANSACTION_INCOMPLETE", row)
        assert row.get("model") == MECHANISM, row
        assert str(row.get("observedContactZone") or ""), row
        matching_class = class_by_key_frame.get((*key, _frame(row)), [])
        assert matching_class, ("C489_VERIFICATION_WITHOUT_SAME_FRAME_CLASSIFICATION", row)

        matching_native = [
            n for n in native
            if _key(n) == key
            and _frame(n) == _frame(row)
            and _contact_frame(n) == _contact_frame(row)
            and str(n.get("targetZone") or "") == str(row.get("observedContactZone") or "")
        ]
        assert matching_native, ("C489_VERIFIED_CLASSIFICATION_WITHOUT_NATIVE_CONTACT", row)

        matching_bound = [
            b for b in bound
            if _key(b) == key
            and _contact_frame(b) == _contact_frame(row)
            and str(b.get("observedContactZone") or "") == str(row.get("observedContactZone") or "")
        ]
        assert matching_bound, ("C489_NATIVE_CONTACT_WITHOUT_PENDING_OBSERVED_ZONE_BINDING", row)
        assert all(b.get("g06DamageZoneUsesObservedContact") is True for b in matching_bound), matching_bound
        assert all(b.get("eventTargetZoneMutated") is False for b in matching_bound), matching_bound

        # The frozen engagement intent remains the C470/C480 handoff intent; G05
        # observation may classify a different realized contact zone without
        # rewriting that control-plane intent.
        event_actor = (key[0], key[1])
        prior_refinements = [
            r for r in refinement_by_event_actor.get(event_actor, [])
            if _frame(r) <= _frame(row)
        ]
        if prior_refinements:
            intent_zone = str(prior_refinements[-1].get("selectedSemanticZone") or "")
            assert str(row.get("engagementIntentZone") or "") == intent_zone, (
                "C489_ENGAGEMENT_INTENT_ZONE_DRIFTED", prior_refinements[-1], row
            )

        verified_transactions.add(key)
        if key[0] == "evt-counterattack":
            counterattack_verified = True

    assert verified_transactions, "C489_NO_OBSERVED_SEMANTIC_NATIVE_CONTACT_TRANSACTION"
    assert counterattack_verified, "C489_COUNTERATTACK_OBSERVED_SEMANTIC_NATIVE_CONTACT_MISSING"

    # This exact frontier was exposed by post-handoff semantic manifold migration.
    # Require the real physics run to exercise at least one intent-vs-observed-zone
    # divergence so the new authority split is not accepted solely by static proof.
    assert migrations, "C489_REAL_PHYSICS_SEMANTIC_MANIFOLD_MIGRATION_NOT_EXERCISED"

    return {
        "observedContactSemanticRuntimeReceipt": "PASS",
        "controlIntentSemanticPreservedAtRuntime": "PASS",
        "sameTransactionObservedSemanticToNativeContact": "PASS",
        "counterattackObservedSemanticNativeContact": "PASS",
        "observedSemanticVerifiedTransactionCount": len(verified_transactions),
        "semanticManifoldMigrationObserved": True,
        "semanticMigrationClassificationCount": len(migrations),
        "storyPrescribedSemanticStrictness": "PROPERTY_PRESERVED",
        "eventTargetZoneMutatedByObservation": False,
        "g06DamageZoneObservedSemanticBinding": "PASS",
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
    transaction = c483._transaction_sampling_runtime_proof(a.hetero_log)
    progress = c483._progress_runtime_proof(a.hetero_log)
    approach = c483.approach_transaction_proof(a.hetero_log, a.hetero_g07)
    recovery = c483.deferred_handoff_recovery_proof(a.hetero_log)
    roles = c483.collision_role_runtime_proof(a.hetero_log)
    drive_direction = c483.drive_direction_runtime_proof(a.hetero_log)
    c488_runtime = c488.c488_runtime_proof(a.hetero_log)
    c489_runtime = observed_contact_semantic_runtime_proof(a.hetero_log)

    print(json.dumps({
        "marker": "GENERIC_AUTONOMOUS_BATTLE_C489_MACHINE_ACCEPTANCE",
        "status": "PASS",
        "candidate": CANDIDATE,
        "mechanism": MECHANISM,
        "executionProfile": "NVIDIA_L4",
        "productionReadyHeavyAssetProof": "PASS",
        "canonicalFrameMetadataProof": "PASS",
        "heterogeneousActorProfileProof": "PASS",
        "sameRuntimeAcrossDissimilarActorProfiles": True,
        **directions, **approach, **recovery, **roles, **drive_direction,
        **c488_runtime, **c489_runtime,
        "radialNavigationContractPreserved": "PASS",
        "obbHandoffEligibilityPreserved": "PASS",
        "translationDominantHandoffEligibility": "PASS",
        "realizedMotionHandoffPreserved": "PASS",
        "eventScopedAuthorityV2Preserved": "PASS",
        "tacticalGoalProgressRebase": "PASS",
        "collisionProxyProgressRefresh": "PASS",
        "transactionBoundedLocalityWindow": "PASS",
        "livePairObservedContactSemanticClassification": "PASS",
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
        "transactionSamplingRuntimeProof": transaction,
        "progressRuntimeProof": progress,
    }, sort_keys=True))


if __name__ == "__main__":
    main()
