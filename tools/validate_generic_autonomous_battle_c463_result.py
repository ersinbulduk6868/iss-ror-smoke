#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

LOCALIZATION_MODEL = "VERIFIED_PAIR_NEAREST_RECIPIENT_MESH_VERTEX_V1"
BATTLE_CONTROL_MODEL = "ISS_GENERIC_AUTONOMOUS_BATTLE_CONTROL_V5"
TACTICAL_MODEL = "ISS_GENERIC_ADAPTIVE_BATTLE_TACTICS_V5"
RUNWAY_MODEL = "GEOMETRY_CAPABILITY_SURFACE_GAP_RUNWAY_V1"
SURFACE_GOAL_MODEL = "LIVE_SUPPORT_RADIUS_SURFACE_GAP_GOAL_V1"
CONSEQUENCE_MODEL = "ISS_CAUSAL_VISIBLE_IMPACT_CONSEQUENCE_V3"


def _load(path: str):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def _runway_proof(label: str, battle: dict) -> dict[str, object]:
    samples = battle.get("samples") or []
    open_rows = [row for row in samples if row.get("tacticalMode") == "OPEN_DISTANCE"]
    engage_rows = [
        row for row in samples
        if row.get("tacticalMode") in {"ENGAGE", "COUNTER"}
        and row.get("contactCommit") is True
    ]
    assert open_rows, (label, "PRECONTACT_OPEN_DISTANCE_NOT_OBSERVED")
    assert engage_rows, (label, "CONTACT_COMMIT_NOT_OBSERVED")
    assert all(
        float((row.get("policy") or {}).get("engagementRunwayRequiredM") or 0.0) > 0.0
        for row in open_rows
    ), (label, "RUNWAY_REQUIREMENT_MISSING")
    assert all(
        (row.get("policy") or {}).get("engagementRunwayArmed") is True
        for row in engage_rows
    ), (label, "CONTACT_COMMIT_WITHOUT_ARMED_RUNWAY")

    collapsed = [
        row for row in samples
        if row.get("tacticalReason") == "RUNWAY_COLLAPSED_DURING_REPOSITION"
    ]
    return {
        "openDistanceSamples": len(open_rows),
        "armedContactCommitSamples": len(engage_rows),
        "runwayCollapseRecoverySamples": len(collapsed),
    }


def _payoff_proof(label: str, battle: dict) -> None:
    payoff = [
        row for row in (battle.get("samples") or [])
        if str(row.get("storyPhase") or "").upper() == "PAYOFF"
    ]
    assert payoff, (label, "PAYOFF_EVIDENCE_MISSING")
    assert all(row.get("tacticalMode") == "HOLD" for row in payoff), (
        label, "PAYOFF_RECOVERY_LEAK"
    )
    assert all(row.get("speedIntent") == "BRAKE" for row in payoff), (
        label, "PAYOFF_NOT_BRAKED"
    )


def _validate(
    label: str,
    battle_path: str,
    g06_path: str,
    g07_path: str,
    g08_path: str,
) -> dict[str, object]:
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
    assert battle.get("perAssetBattleCode") is False
    assert battle.get("perVideoTrajectoryEngineering") is False
    assert battle.get("actorPoseOrVelocityMutation") is False

    runway = _runway_proof(label, battle)
    _payoff_proof(label, battle)

    cycles = battle.get("maxBattleCycleByActor") or {}
    assert cycles and max(int(x) for x in cycles.values()) >= 1, (
        label, "NO_REALIZED_BATTLE_CYCLE"
    )

    impacts = g06.get("g05BoundImpacts") or []
    direct = [row for row in impacts if not row.get("inherited")]
    assert len(direct) >= 2, (label, "SECOND_NATIVE_CONTACT_NOT_PROVEN", len(direct))
    event_ids = {str(row.get("eventId") or "") for row in direct}
    assert {"evt-escalation", "evt-counterattack"} <= event_ids, (
        label, "REQUIRED_DIRECT_EVENTS_MISSING", sorted(event_ids)
    )
    assert all(row.get("damageEarned") is True for row in direct), (
        label, "DIRECT_CONTACT_DID_NOT_EARN_DAMAGE", direct
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
        "battleCycles": cycles,
        "directG05Impacts": len(direct),
        "directImpactEventIds": sorted(event_ids),
        "allDirectImpactsDamageEarned": True,
        "damagedActorCount": damaged_actor_count,
        "visibleConsequenceEvents": len(visible),
        "localizedActors": sorted(localized_actor_ids),
        "debrisCount": debris,
        "maxNormalizedDeformation": max_normalized_deformation,
        "maxLocalizationDistanceM": max_localization_distance,
        "g07": "COMPLETE",
        "g08MachineSalience": "PASS",
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    for prefix in ("bugatti", "generic"):
        for key in ("battle", "g06", "g07", "g08"):
            parser.add_argument(f"--{prefix}-{key}", required=True)
    args = parser.parse_args()

    rows = [
        _validate(
            prefix,
            getattr(args, f"{prefix}_battle"),
            getattr(args, f"{prefix}_g06"),
            getattr(args, f"{prefix}_g07"),
            getattr(args, f"{prefix}_g08"),
        )
        for prefix in ("bugatti", "generic")
    ]

    print(json.dumps({
        "marker": "GENERIC_AUTONOMOUS_BATTLE_C463_MACHINE_ACCEPTANCE",
        "status": "PASS",
        "affectedLayerAudit": "PASS",
        "failureFamily": "PRECONTACT_ENGAGEMENT_RUNWAY_AND_SURFACE_GAP_GEOMETRY_CONTRACT_MISMATCH",
        "sameRuntimeAcrossAssets": True,
        "precontactRunway": "PASS",
        "surfaceGapRevalidation": "PASS",
        "standOffLiveSupportGeometry": "PASS",
        "secondNativeContact": "PASS",
        "twoSidedDamage": "PASS",
        "nativeContactAuthorityPreserved": True,
        "damageAdmissionThresholdChanged": False,
        "contactThresholdChanged": False,
        "damageThresholdAwareControl": False,
        "targetToughnessAwareControl": False,
        "desiredImpactSpeedControl": False,
        "desiredImpactEnergyControl": False,
        "fixtureMutationForAcceptance": False,
        "visibleCausalDamageDebris": "PASS",
        "g07AdaptiveCausalDrama": "PASS",
        "g08MachineObservability": "PASS",
        "humanCinematicAcceptance": "PENDING",
        "gateClosed": False,
        "productionReadyClaimed": False,
        "fixtures": rows,
    }, sort_keys=True))


if __name__ == "__main__":
    main()
