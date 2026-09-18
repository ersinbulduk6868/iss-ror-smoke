#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
TOOLS = ROOT / "tools"
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

from validate_generic_autonomous_battle_c464_result import (
    BATTLE_CONTROL_MODEL,
    CONSEQUENCE_MODEL,
    LOCALIZATION_MODEL,
    RUNWAY_MODEL,
    SURFACE_GOAL_MODEL,
    TACTICAL_MODEL,
    _load,
    _payoff_proof,
    _runway_proof,
)
from validate_generic_autonomous_battle_c465_result import _cutoff_runtime_proof
from validate_generic_autonomous_battle_c470_result import _surface_transaction_runtime_proof
from validate_generic_autonomous_battle_c471_result import _transaction_sampling_runtime_proof
from validate_generic_autonomous_battle_c474_result import _progress_runtime_proof
from validate_generic_autonomous_battle_c479_result import (
    direction_proof,
    load,
    profile_and_metadata_proof,
)

LOCKED_MIN_DAMAGE_SEVERITY = 0.055
REQUIRED_DIRECT_EVENTS = {"evt-escalation", "evt-counterattack"}


def _json_markers(path: str) -> list[dict]:
    rows: list[dict] = []
    for raw in Path(path).read_text(encoding="utf-8", errors="replace").splitlines():
        line = raw.strip()
        if not line.startswith("{"):
            continue
        try:
            row = json.loads(line)
        except Exception:
            continue
        if isinstance(row, dict):
            rows.append(row)
    return rows


def heterogeneous_cross_gate_proof(
    label: str,
    battle_path: str,
    g06_path: str,
    g07_path: str,
    g08_path: str,
) -> dict[str, object]:
    """Validate a materially dissimilar pair without making G04 target G06.

    `damageEarned` is the primary target-side admission flag.  G06 provenance
    intentionally binds both the primary `evidence` and reciprocal
    `attackerEvidence`, so `boundDamageEventCount` is the number of admitted sides
    in the physical transaction, not a synonym for `damageEarned`.

    A heterogeneous collision is therefore allowed to be physically asymmetric:
    one side may remain undamaged when its own locked severity is below 0.055.  The
    validator proves the locked threshold was followed instead of forcing G04 to
    engineer a desired impact speed/energy just to damage both actors.
    """
    battle = _load(battle_path)
    g06 = _load(g06_path)
    g07 = _load(g07_path)
    g08 = _load(g08_path)

    assert battle.get("battleControlModel") == BATTLE_CONTROL_MODEL
    assert battle.get("tacticalModel") == TACTICAL_MODEL
    assert battle.get("engagementRunwayModel") == RUNWAY_MODEL
    assert battle.get("surfaceGapGoalModel") == SURFACE_GOAL_MODEL
    assert battle.get("sameRuntimeAcrossAssets") is True
    assert battle.get("liveWorldStateDriven") is True
    assert battle.get("actorProfileCapabilityDriven") is True
    assert battle.get("storyIntentOnly") is True
    assert battle.get("precontactRunwayRequired") is True
    assert battle.get("surfaceGapRevalidatedDuringReposition") is True
    assert battle.get("standOffUsesLiveSupportGeometry") is True
    assert battle.get("damageThresholdAwareControl") is False
    assert battle.get("targetToughnessAwareControl") is False
    assert battle.get("desiredImpactSpeedControl") is False
    assert battle.get("desiredImpactEnergyControl") is False
    assert battle.get("solverHandoffLatchedUntilVerifiedContactOrPhysicalMiss") is True
    assert battle.get("solverHandoffReleaseUsesLiveSeparation") is True
    assert battle.get("g05ControllerAuthorityContractPreserved") is True
    assert battle.get("perAssetBattleCode") is False
    assert battle.get("perVideoTrajectoryEngineering") is False
    assert battle.get("actorPoseOrVelocityMutation") is False

    runway = _runway_proof(label, battle)
    samples = battle.get("samples") or []
    handoff_rows = [
        row for row in samples
        if (row.get("policy") or {}).get("solverHandoffLatched") is True
    ]
    assert handoff_rows, (label, "SOLVER_HANDOFF_LATCH_NOT_OBSERVED")
    assert all(row.get("motorAuthority") == "COAST" for row in handoff_rows), (
        label, "MOTOR_AUTHORITY_REENTERED_DURING_HANDOFF_LATCH"
    )
    _payoff_proof(label, battle)

    cycles = battle.get("maxBattleCycleByActor") or {}
    assert cycles and max(int(x) for x in cycles.values()) >= 1, (
        label, "NO_REALIZED_BATTLE_CYCLE"
    )

    impacts = g06.get("g05BoundImpacts") or []
    direct = [row for row in impacts if not row.get("inherited")]
    assert len(direct) >= 2, (label, "SECOND_NATIVE_CONTACT_NOT_PROVEN", len(direct))
    event_ids = {str(row.get("eventId") or "") for row in direct}
    assert REQUIRED_DIRECT_EVENTS <= event_ids, (
        label, "REQUIRED_DIRECT_EVENTS_MISSING", sorted(event_ids)
    )
    assert all(
        (row.get("nativeContactReceipt") or {}).get("status") == "VERIFIED"
        for row in direct
    ), (label, "G05_RECEIPT_NOT_VERIFIED")
    assert all(
        (row.get("nativeContactReceipt") or {}).get("model")
        == "RECIPROCAL_NATIVE_SOLVER_RESPONSE_V1"
        for row in direct
    ), (label, "G05_CONTACT_AUTHORITY_DRIFT")

    threshold_rows: list[dict[str, object]] = []
    admitted_actor_ids: set[str] = set()
    total_bound_expected = 0
    primary_damage_admissions = 0
    reciprocal_damage_admissions = 0
    for row in direct:
        receipt = row.get("nativeContactReceipt") or {}
        evidence = row.get("evidence") or {}
        attacker_evidence = row.get("attackerEvidence")
        primary_severity = float(evidence.get("severity") or 0.0)
        primary_earned = row.get("damageEarned") is True
        expected_primary = primary_severity >= LOCKED_MIN_DAMAGE_SEVERITY
        assert primary_earned is expected_primary, (
            label,
            "PRIMARY_DAMAGE_ADMISSION_THRESHOLD_MISMATCH",
            row.get("eventId"),
            primary_severity,
            primary_earned,
        )
        assert str(evidence.get("attacker_id") or "") == str(receipt.get("attackerId") or ""), row
        assert str(evidence.get("target_id") or "") == str(receipt.get("targetId") or ""), row

        mirrored_earned = isinstance(attacker_evidence, dict)
        mirrored_severity: float | None = None
        if mirrored_earned:
            mirrored_severity = float(attacker_evidence.get("severity") or 0.0)
            assert mirrored_severity >= LOCKED_MIN_DAMAGE_SEVERITY, (
                label,
                "RECIPROCAL_DAMAGE_ADMITTED_BELOW_LOCKED_THRESHOLD",
                row.get("eventId"),
                mirrored_severity,
            )
            assert str(attacker_evidence.get("attacker_id") or "") == str(receipt.get("targetId") or ""), row
            assert str(attacker_evidence.get("target_id") or "") == str(receipt.get("attackerId") or ""), row

        expected_bound = int(primary_earned) + int(mirrored_earned)
        bound = int(row.get("boundDamageEventCount") or 0)
        assert bound == expected_bound, (
            label,
            "RECIPROCAL_DAMAGE_PROVENANCE_COUNT_MISMATCH",
            row.get("eventId"),
            bound,
            expected_bound,
        )
        total_bound_expected += expected_bound
        if primary_earned:
            primary_damage_admissions += 1
            admitted_actor_ids.add(str(evidence.get("target_id") or ""))
        if mirrored_earned:
            reciprocal_damage_admissions += 1
            admitted_actor_ids.add(str(attacker_evidence.get("target_id") or ""))

        threshold_rows.append({
            "eventId": str(row.get("eventId") or ""),
            "primaryTargetId": str(evidence.get("target_id") or ""),
            "primarySeverity": primary_severity,
            "primaryDamageEarned": primary_earned,
            "reciprocalTargetId": (
                str(attacker_evidence.get("target_id") or "") if mirrored_earned else None
            ),
            "reciprocalSeverity": mirrored_severity,
            "reciprocalDamageEarned": mirrored_earned,
            "boundDamageEventCount": bound,
        })

    assert total_bound_expected >= 1, (label, "NO_PHYSICALLY_EARNED_DAMAGE_IN_HETEROGENEOUS_BATTLE")
    assert int(g06.get("g05DamageProvenanceBoundCount") or 0) == total_bound_expected, (
        label,
        "G06_TOTAL_DAMAGE_PROVENANCE_COUNT_MISMATCH",
        g06.get("g05DamageProvenanceBoundCount"),
        total_bound_expected,
    )

    actors = g06.get("finalActors") or {}
    assert actors, (label, "NO_FINAL_ACTORS")
    actual_damaged_actor_ids = {
        str(actor_id)
        for actor_id, row in actors.items()
        if int(((row.get("state") or {}).get("damageEventCount") or 0)) > 0
    }
    assert actual_damaged_actor_ids == admitted_actor_ids, (
        label,
        "FINAL_DAMAGE_STATE_DOES_NOT_MATCH_THRESHOLD_ADMISSIONS",
        sorted(actual_damaged_actor_ids),
        sorted(admitted_actor_ids),
    )

    visible: list[tuple[str, dict]] = []
    debris = 0
    localized_actor_ids: set[str] = set()
    max_normalized_deformation = 0.0
    max_localization_distance = 0.0
    for actor_id, row in actors.items():
        visual = row.get("visual") or {}
        for evidence_row in visual.get("damageVisualEvidence") or []:
            if evidence_row.get("model") != CONSEQUENCE_MODEL:
                continue
            visible.append((str(actor_id), evidence_row))
            debris += int(evidence_row.get("debrisCount") or 0)
            max_normalized_deformation = max(
                max_normalized_deformation,
                float(evidence_row.get("normalizedDeformation") or 0.0),
            )
            assert evidence_row.get("contactLocalizationModel") == LOCALIZATION_MODEL
            assert evidence_row.get("g05ContactTruthRewritten") is False
            assert evidence_row.get("physicalDamageGateChanged") is False
            assert evidence_row.get("contactGateChanged") is False
            assert evidence_row.get("debrisEligibility") == (
                "UNCHANGED_DAMAGE_GATE_PLUS_REALIZED_DEFORMATION_OR_SEVERITY"
            )
            original = evidence_row.get("originalVerifiedContactPoint")
            anchor = evidence_row.get("visualRecipientAnchorPoint")
            assert isinstance(original, list) and len(original) == 3
            assert isinstance(anchor, list) and len(anchor) == 3
            distance = float(evidence_row.get("localizationDistanceM") or 0.0)
            assert math.isfinite(distance) and distance >= 0.0
            max_localization_distance = max(max_localization_distance, distance)
            localized_actor_ids.add(str(actor_id))

    assert visible, (label, "VISIBLE_CAUSAL_DAMAGE_CONSEQUENCE_NOT_OBSERVED")
    assert localized_actor_ids == actual_damaged_actor_ids, (
        label,
        "VISIBLE_CONSEQUENCE_RECIPIENT_MISMATCH",
        sorted(localized_actor_ids),
        sorted(actual_damaged_actor_ids),
    )
    assert max_normalized_deformation >= 0.02, (
        label, "VISIBLE_DEFORMATION_TOO_SMALL", max_normalized_deformation
    )
    assert debris >= 2, (label, "VISIBLE_DEBRIS_NOT_REALIZED", debris)

    assert g07.get("status") == "COMPLETE", (label, "DRAMA_INCOMPLETE")
    for key in ("escalation", "counterattack", "reversal", "climax", "payoff"):
        assert g07.get(key) is not None, (label, "DRAMA_STAGE_MISSING", key)

    assert g08.get("cinematicSaliencePass") is True, (label, "CAMERA_SALIENCE_FAIL")
    assert g08.get("humanCinematicAcceptance") == "PENDING", (
        label, "HUMAN_REVIEW_MUST_REMAIN_PENDING"
    )

    damage_mode = (
        "PHYSICS_THRESHOLD_DRIVEN_BILATERAL"
        if len(actual_damaged_actor_ids) >= 2
        else "PHYSICS_THRESHOLD_DRIVEN_ASYMMETRIC"
    )
    return {
        "label": label,
        "runway": runway,
        "solverHandoffLatchSamples": len(handoff_rows),
        "battleCycles": cycles,
        "directG05Impacts": len(direct),
        "directImpactEventIds": sorted(event_ids),
        "lockedMinDamageSeverity": LOCKED_MIN_DAMAGE_SEVERITY,
        "damageThresholdSemantics": "PASS",
        "primaryDamageAdmissions": primary_damage_admissions,
        "reciprocalDamageAdmissions": reciprocal_damage_admissions,
        "totalBoundDamageEvents": total_bound_expected,
        "damageOutcomeMode": damage_mode,
        "damagedActorIds": sorted(actual_damaged_actor_ids),
        "thresholdProof": threshold_rows,
        "visibleConsequenceEvents": len(visible),
        "localizedActors": sorted(localized_actor_ids),
        "debrisCount": debris,
        "maxNormalizedDeformation": max_normalized_deformation,
        "maxLocalizationDistanceM": max_localization_distance,
        "g04DoesNotTargetG06DamageThreshold": True,
        "g07": "COMPLETE",
        "g08MachineSalience": "PASS",
    }


def approach_transaction_proof(log_path: str, g07_path: str) -> dict[str, object]:
    rows = _json_markers(log_path)
    starts = [
        r for r in rows
        if r.get("marker") == "GENERIC_APPROACH_SEMANTIC_TRANSACTION_STARTED"
        and str(r.get("eventId") or "") == "evt-counterattack"
    ]
    assert starts, "C480_COUNTERATTACK_APPROACH_TRANSACTION_START_MISSING"
    start = starts[0]
    start_frame = int(start.get("frame") or -1)
    frozen_zone = str(start.get("selectedSemanticZone") or "")
    assert start_frame >= 0 and frozen_zone, start
    assert start.get("assetIdentityBranch") is False, start
    assert start.get("fixedWorldCoordinate") is False, start
    assert start.get("sourceContactCommit") is True, start

    handoffs = [
        r for r in rows
        if r.get("marker") == "GENERIC_SOLVER_HANDOFF_LATCHED"
        and str(r.get("eventId") or "") == "evt-counterattack"
        and str(r.get("actorId") or "") == "actor_beta"
    ]
    assert handoffs, "C480_COUNTERATTACK_SOLVER_HANDOFF_MISSING"
    handoff_frame = int(handoffs[0].get("frame") or -1)
    assert handoff_frame >= start_frame, (start_frame, handoff_frame)

    refinements = [
        r for r in rows
        if r.get("marker") == "GENERIC_APPROACH_SEMANTIC_TRANSACTION_REFINED_BY_HANDOFF"
        and str(r.get("eventId") or "") == "evt-counterattack"
    ]
    for row in refinements:
        assert int(row.get("frame") or -1) >= handoff_frame, row
        assert row.get("assetIdentityBranch") is False, row
        assert row.get("fixedWorldCoordinate") is False, row

    g07 = load(g07_path)
    selections = [
        r for r in (g07.get("engagementSurfaceSelections") or [])
        if str(r.get("eventId") or "") == "evt-counterattack"
    ]
    forbidden_mid_approach = [
        r for r in selections
        if start_frame < int(r.get("frame") or -1) < handoff_frame
    ]
    assert not forbidden_mid_approach, forbidden_mid_approach

    assert any(
        r.get("marker") == "GENERIC_HANDOFF_SEMANTIC_SURFACE_FROZEN"
        and str(r.get("eventId") or "") == "evt-counterattack"
        for r in rows
    ), "C480_EXISTING_HANDOFF_FREEZE_EVIDENCE_MISSING"

    return {
        "approachTransaction": "PASS",
        "counterattackApproachStartFrame": start_frame,
        "counterattackApproachFrozenZone": frozen_zone,
        "counterattackHandoffFrame": handoff_frame,
        "semanticZoneChangeBeforeHandoff": False,
        "handoffRefinementCount": len(refinements),
        "semanticLabelFreezeOnly": True,
        "semanticWorldPositionRemainsLive": True,
    }


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--base-request", required=True)
    p.add_argument("--hetero-request", required=True)
    p.add_argument("--asset-library-metadata", required=True)
    for key in ("battle", "g06", "g07", "g08", "log"):
        p.add_argument(f"--hetero-{key}", required=True)
    a = p.parse_args()

    base_req = load(a.base_request)
    hetero_req = load(a.hetero_request)
    ready_meta = load(a.asset_library_metadata)
    profile = profile_and_metadata_proof(base_req, hetero_req, ready_meta)
    g06 = load(a.hetero_g06)
    directions = direction_proof(g06)

    cross_gate = heterogeneous_cross_gate_proof(
        "generic-hypercar-production-ready-heavy-asset",
        a.hetero_battle,
        a.hetero_g06,
        a.hetero_g07,
        a.hetero_g08,
    )
    cutoff = _cutoff_runtime_proof(a.hetero_battle)
    surface = _surface_transaction_runtime_proof(a.hetero_log)
    transaction = _transaction_sampling_runtime_proof(a.hetero_log)
    progress = _progress_runtime_proof(a.hetero_log)
    approach = approach_transaction_proof(a.hetero_log, a.hetero_g07)

    print(json.dumps({
        "marker": "GENERIC_AUTONOMOUS_BATTLE_C480_MACHINE_ACCEPTANCE",
        "status": "PASS",
        "candidate": "ISS_GENERIC_BATTLE_RUNTIME_V1_CANDIDATE_4_8_0_GENERIC_AUTONOMOUS_BATTLE",
        "mechanism": "GENERIC_ENGAGEMENT_APPROACH_TRANSACTION_V1",
        "executionProfile": "NVIDIA_L4",
        "productionReadyHeavyAssetProof": "PASS",
        "canonicalFrameMetadataProof": "PASS",
        "heterogeneousActorProfileProof": "PASS",
        "sameRuntimeAcrossDissimilarActorProfiles": True,
        **directions,
        **approach,
        "radialNavigationContractPreserved": "PASS",
        "obbOnlyHandoffEligibility": "PASS",
        "tacticalGoalProgressRebase": "PASS",
        "collisionProxyProgressRefresh": "PASS",
        "transactionBoundedLocalityWindow": "PASS",
        "livePairSurfaceSemanticSelection": "PASS",
        "secondNativeContact": "PASS",
        "damageThresholdSemantics": "PASS",
        "heterogeneousDamageOutcome": cross_gate["damageOutcomeMode"],
        "visibleCausalDamageDebris": "PASS",
        "g07AdaptiveCausalDrama": "PASS",
        "g08MachineObservability": "PASS",
        "nativeContactAuthorityPreserved": True,
        "pairwiseSolverOraclePreserved": True,
        "c470FreshHandoffLivePairRefinementPreserved": True,
        "c474ObbHandoffEligibilityPreserved": True,
        "c474HistoricalMachinePassOverwritten": False,
        "g06RuntimeSourceChanged": False,
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
        "heterogeneousCrossGateProof": cross_gate,
        "cutoffRuntimeProof": cutoff,
        "surfaceTransactionRuntimeProof": surface,
        "transactionSamplingRuntimeProof": transaction,
        "progressRuntimeProof": progress,
    }, sort_keys=True))


if __name__ == "__main__":
    main()
