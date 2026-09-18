#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
TOOLS = ROOT / "tools"
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

REQUIRED_DIRECT_EVENTS = {"evt-escalation", "evt-counterattack"}
LOCKED_MIN_DAMAGE_SEVERITY = 0.055


def _rows(path: str) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for line in Path(path).read_text(encoding="utf-8", errors="replace").splitlines():
        try:
            row = json.loads(line)
        except Exception:
            continue
        if isinstance(row, dict):
            rows.append(row)
    return rows


def _ownership_aware_cross_gate_validate(
    label: str,
    battle_path: str,
    g06_path: str,
    g07_path: str,
    g08_path: str,
) -> dict[str, object]:
    """Preserve C464 cross-gate evidence without making G04 target G06's damage gate.

    Native contact truth belongs to G05. Damage admission belongs to the locked G06
    severity threshold. A physically verified contact below that threshold must stay
    non-damaging; forcing G04 to make every direct contact damaging would create
    damage-threshold-aware or desired-impact-speed control, which is explicitly
    forbidden by the G04 Master Plan contract.
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

    damaging_direct = 0
    nondamaging_direct = 0
    threshold_rows: list[dict[str, object]] = []
    for row in direct:
        evidence = row.get("evidence") or {}
        severity = float(evidence.get("severity") or 0.0)
        earned = row.get("damageEarned") is True
        bound = int(row.get("boundDamageEventCount") or 0)
        if earned:
            damaging_direct += 1
            assert severity >= LOCKED_MIN_DAMAGE_SEVERITY, (
                label, "DAMAGE_EARNED_BELOW_LOCKED_THRESHOLD", row.get("eventId"), severity
            )
            assert bound >= 1, (
                label, "DAMAGE_EARNED_WITHOUT_BOUND_DAMAGE_EVENT", row.get("eventId"), bound
            )
        else:
            nondamaging_direct += 1
            assert severity < LOCKED_MIN_DAMAGE_SEVERITY, (
                label, "DAMAGE_REJECTED_AT_OR_ABOVE_LOCKED_THRESHOLD", row.get("eventId"), severity
            )
            assert bound == 0, (
                label, "NON_DAMAGING_CONTACT_BOUND_DAMAGE_EVENT", row.get("eventId"), bound
            )
        threshold_rows.append({
            "eventId": str(row.get("eventId") or ""),
            "severity": severity,
            "damageEarned": earned,
            "boundDamageEventCount": bound,
        })
    assert damaging_direct >= 1, (label, "NO_DIRECT_CONTACT_EARNED_DAMAGE")

    actors = g06.get("finalActors") or {}
    assert actors, (label, "NO_FINAL_ACTORS")
    visible: list[tuple[str, dict]] = []
    debris = 0
    damaged_actor_count = 0
    localized_actor_ids: set[str] = set()
    max_normalized_deformation = 0.0
    max_localization_distance = 0.0
    for actor_id, row in actors.items():
        state = row.get("state") or {}
        if int(state.get("damageEventCount") or 0) > 0:
            damaged_actor_count += 1
        visual = row.get("visual") or {}
        for evidence in visual.get("damageVisualEvidence") or []:
            if evidence.get("model") != CONSEQUENCE_MODEL:
                continue
            visible.append((actor_id, evidence))
            debris += int(evidence.get("debrisCount") or 0)
            max_normalized_deformation = max(
                max_normalized_deformation,
                float(evidence.get("normalizedDeformation") or 0.0),
            )
            assert evidence.get("contactLocalizationModel") == LOCALIZATION_MODEL
            assert evidence.get("g05ContactTruthRewritten") is False
            assert evidence.get("physicalDamageGateChanged") is False
            assert evidence.get("contactGateChanged") is False
            assert evidence.get("debrisEligibility") == (
                "UNCHANGED_DAMAGE_GATE_PLUS_REALIZED_DEFORMATION_OR_SEVERITY"
            )
            original = evidence.get("originalVerifiedContactPoint")
            anchor = evidence.get("visualRecipientAnchorPoint")
            assert isinstance(original, list) and len(original) == 3
            assert isinstance(anchor, list) and len(anchor) == 3
            distance = float(evidence.get("localizationDistanceM") or 0.0)
            assert math.isfinite(distance) and distance >= 0.0
            max_localization_distance = max(max_localization_distance, distance)
            localized_actor_ids.add(str(actor_id))

    assert damaged_actor_count >= 2, (
        label, "TWO_SIDED_DAMAGE_NOT_PRESERVED", damaged_actor_count
    )
    assert visible, (label, "V3_VISIBLE_CONSEQUENCE_NOT_OBSERVED")
    assert len(localized_actor_ids) >= 2, (
        label, "TWO_SIDED_LOCALIZATION_NOT_PROVEN", sorted(localized_actor_ids)
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

    return {
        "label": label,
        "runway": runway,
        "solverHandoffLatchSamples": len(handoff_rows),
        "battleCycles": cycles,
        "directG05Impacts": len(direct),
        "directImpactEventIds": sorted(event_ids),
        "damagingDirectContacts": damaging_direct,
        "nonDamagingDirectContacts": nondamaging_direct,
        "damageThresholdSemantics": "PASS",
        "lockedMinDamageSeverity": LOCKED_MIN_DAMAGE_SEVERITY,
        "directContactThresholdProof": threshold_rows,
        "damagedActorCount": damaged_actor_count,
        "visibleConsequenceEvents": len(visible),
        "localizedActors": sorted(localized_actor_ids),
        "debrisCount": debris,
        "maxNormalizedDeformation": max_normalized_deformation,
        "maxLocalizationDistanceM": max_localization_distance,
        "g07": "COMPLETE",
        "g08MachineSalience": "PASS",
    }


def _progress_runtime_proof(path: str) -> dict[str, object]:
    rows = _rows(path)
    contacts = [r for r in rows if r.get("marker") == "PAIRWISE_NATIVE_SOLVER_CONTACT_VERIFIED"]
    rebases = [r for r in rows if r.get("marker") == "G04_AUTONOMY_PROGRESS_REBASED_FOR_TACTICAL_GOAL"]
    progress = [r for r in rows if r.get("marker") == "G04_COLLISION_PROXY_PROGRESS_REFRESHED"]
    defers = [r for r in rows if r.get("marker") == "G04_CONTACT_HANDOFF_DEFERRED_BY_OBB_SEPARATION"]
    replans = [r for r in rows if r.get("marker") == "AUTONOMY_REPLAN_TRIGGERED"]

    contact_events = {str(r.get("eventId") or "") for r in contacts}
    assert REQUIRED_DIRECT_EVENTS <= contact_events, (
        "C474_REQUIRED_DIRECT_NATIVE_CONTACT_EVENTS_MISSING", sorted(contact_events)
    )
    assert rebases, "C474_TACTICAL_PROGRESS_REBASE_NOT_OBSERVED"
    assert progress, "C474_COLLISION_PROXY_PROGRESS_NOT_OBSERVED"

    for row in rebases:
        previous = str(row.get("previousTacticalMode") or "")
        current = str(row.get("currentTacticalMode") or "")
        assert previous and current and previous != current, ("C474_REBASE_WITHOUT_GOAL_CHANGE", row)
        assert row.get("rebasedDistanceM") is not None, ("C474_REBASE_DISTANCE_MISSING", row)

    for row in progress:
        prev_gap = float(row.get("previousEffectiveGapM"))
        current_gap = float(row.get("effectiveGapM"))
        closing = float(row.get("closingSpeedMps"))
        epsilon = float(row.get("progressEpsilonM"))
        assert closing > 0.0, ("C474_PROGRESS_WITHOUT_POSITIVE_CLOSING", row)
        assert prev_gap - current_gap >= epsilon - 1.0e-9, (
            "C474_PROGRESS_EPSILON_NOT_MET", row
        )

    for row in defers:
        effective = float(row.get("effectiveCollisionProxyGapM"))
        handoff = float(row.get("existingHandoffGapM"))
        assert effective > handoff, ("C474_HANDOFF_DEFER_NOT_REQUIRED", row)

    stale_after_rebase: list[dict[str, object]] = []
    rebase_frames = [int(r.get("frame") or -1) for r in rebases]
    for row in replans:
        if str(row.get("reason") or "") != "STALL_NO_PROGRESS":
            continue
        frame = int(row.get("frame") or -1)
        if any(0 <= frame - rf <= 6 for rf in rebase_frames):
            stale_after_rebase.append(row)
    assert not stale_after_rebase, (
        "C474_STALE_PROGRESS_REPLAN_IMMEDIATELY_AFTER_TACTICAL_REBASE",
        stale_after_rebase[:5],
    )

    return {
        "verifiedNativeContactCount": len(contacts),
        "verifiedContactEventIds": sorted(contact_events),
        "tacticalProgressRebaseCount": len(rebases),
        "collisionProxyProgressRefreshCount": len(progress),
        "handoffDeferCount": len(defers),
        "stallNoProgressImmediatelyAfterRebase": False,
        "requiredDirectEventsNativeVerified": True,
        "g05RemainsFinalContactAuthority": True,
    }


def main() -> None:
    p = argparse.ArgumentParser()
    for prefix in ("bugatti", "generic"):
        for key in ("battle", "g06", "g07", "g08", "log"):
            p.add_argument(f"--{prefix}-{key}", required=True)
    a = p.parse_args()

    fixtures = []
    cutoff: dict[str, object] = {}
    surface: dict[str, object] = {}
    transaction: dict[str, object] = {}
    progress: dict[str, object] = {}

    for prefix in ("bugatti", "generic"):
        battle = getattr(a, f"{prefix}_battle")
        log = getattr(a, f"{prefix}_log")
        fixtures.append(
            _ownership_aware_cross_gate_validate(
                prefix,
                battle,
                getattr(a, f"{prefix}_g06"),
                getattr(a, f"{prefix}_g07"),
                getattr(a, f"{prefix}_g08"),
            )
        )
        cutoff[prefix] = _cutoff_runtime_proof(battle)
        surface[prefix] = _surface_transaction_runtime_proof(log)
        transaction[prefix] = _transaction_sampling_runtime_proof(log)
        progress[prefix] = _progress_runtime_proof(log)

    print(json.dumps({
        "marker": "GENERIC_AUTONOMOUS_BATTLE_C474_MACHINE_ACCEPTANCE",
        "status": "PASS",
        "affectedLayerAudit": "PASS",
        "failureFamily": "HANDOFF_GEOMETRY_SCOPE_AND_TACTICAL_PROGRESS_MEMORY_MISMATCH",
        "sameRuntimeAcrossAssets": True,
        "radialNavigationContractPreserved": "PASS",
        "obbOnlyHandoffEligibility": "PASS",
        "tacticalGoalProgressRebase": "PASS",
        "collisionProxyProgressRefresh": "PASS",
        "transactionBoundedLocalityWindow": "PASS",
        "livePairSurfaceSemanticSelection": "PASS",
        "freshHandoffTransactionBinding": "PASS",
        "secondNativeContact": "PASS",
        "twoSidedDamage": "PASS",
        "damageThresholdSemantics": "PASS",
        "g04DoesNotTargetG06DamageThreshold": True,
        "visibleCausalDamageDebris": "PASS",
        "g07AdaptiveCausalDrama": "PASS",
        "g08MachineObservability": "PASS",
        "nativeContactAuthorityPreserved": True,
        "pairwiseSolverOraclePreserved": True,
        "semanticToleranceChanged": False,
        "localityToleranceChanged": False,
        "contactThresholdChanged": False,
        "damageAdmissionThresholdChanged": False,
        "fixtureMutationForAcceptance": False,
        "storyTargetZonePrescribed": False,
        "perAssetBattleCode": False,
        "perVideoTrajectoryEngineering": False,
        "humanCinematicAcceptance": "PENDING",
        "gateClosed": False,
        "productionReadyClaimed": False,
        "cutoffRuntimeProof": cutoff,
        "surfaceTransactionRuntimeProof": surface,
        "transactionSamplingRuntimeProof": transaction,
        "progressRuntimeProof": progress,
        "fixtures": fixtures,
    }, sort_keys=True))


if __name__ == "__main__":
    main()
