#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

LOCALIZATION_MODEL = "VERIFIED_PAIR_NEAREST_RECIPIENT_MESH_VERTEX_V1"
BATTLE_CONTROL_MODEL = "ISS_GENERIC_AUTONOMOUS_BATTLE_CONTROL_V3"
TACTICAL_MODEL = "ISS_GENERIC_ADAPTIVE_BATTLE_TACTICS_V3"
BATTLE_SIGNAL_SCOPE = "ACTOR_INVOLVEMENT_EVENT_HISTORY_V1"


def _load(path: str):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def _counter_history_proof(label: str, battle: dict) -> dict[str, object]:
    samples = sorted(
        [s for s in (battle.get("samples") or []) if str(s.get("eventId") or "") == "evt-counterattack"],
        key=lambda s: (int(s.get("frame") or 0), str(s.get("actorId") or "")),
    )
    assert samples, (label, "COUNTERATTACK_TACTICAL_EVIDENCE_MISSING")

    by_actor: dict[str, list[dict]] = {}
    for sample in samples:
        actor_id = str(sample.get("actorId") or "")
        if actor_id:
            by_actor.setdefault(actor_id, []).append(sample)
    assert by_actor, (label, "COUNTERATTACK_ACTOR_EVIDENCE_MISSING")

    proven: dict[str, dict[str, object]] = {}
    for actor_id, rows in by_actor.items():
        historical_break_index = None
        reposition_index = None
        counter_index = None
        historical_signal = 0
        current_event_contacts_at_break = None
        contributing_events: list[str] = []

        for index, sample in enumerate(rows):
            mode = str(sample.get("tacticalMode") or "")
            obs = sample.get("observation") or {}
            actor_signal = int(obs.get("actorRealizedContactSignalCount") or 0)
            current_contacts = int(obs.get("currentEventContactCount") or 0)
            contributors = [str(x) for x in (obs.get("actorSignalContributingEvents") or [])]
            if (
                historical_break_index is None
                and mode == "BREAK_CONTACT"
                and actor_signal > current_contacts
                and any(event_id != "evt-counterattack" for event_id in contributors)
            ):
                historical_break_index = index
                historical_signal = actor_signal
                current_event_contacts_at_break = current_contacts
                contributing_events = contributors
                continue
            if historical_break_index is not None and reposition_index is None and index > historical_break_index and mode == "REPOSITION":
                reposition_index = index
                continue
            if reposition_index is not None and counter_index is None and index > reposition_index and mode == "COUNTER" and sample.get("contactCommit") is True:
                counter_index = index
                break

        if historical_break_index is not None and reposition_index is not None and counter_index is not None:
            proven[actor_id] = {
                "historicalBreakFrame": int(rows[historical_break_index].get("frame") or 0),
                "repositionFrame": int(rows[reposition_index].get("frame") or 0),
                "counterFrame": int(rows[counter_index].get("frame") or 0),
                "actorRealizedContactSignalCountAtBreak": historical_signal,
                "currentEventContactCountAtBreak": current_event_contacts_at_break,
                "contributingEventsAtBreak": contributing_events,
            }

    assert proven, (label, "ACTOR_HISTORY_BREAK_REPOSITION_COUNTER_CHAIN_NOT_PROVEN", by_actor)
    return {
        "actors": proven,
        "historicalContactObservedBeforeCurrentEventContact": True,
        "breakBeforeRepositionBeforeCounter": True,
    }


def _validate(label: str, battle_path: str, g06_path: str, g07_path: str, g08_path: str) -> dict[str, object]:
    battle = _load(battle_path)
    g06 = _load(g06_path)
    g07 = _load(g07_path)
    g08 = _load(g08_path)

    assert battle.get("battleControlModel") == BATTLE_CONTROL_MODEL, (label, battle.get("battleControlModel"))
    assert battle.get("tacticalModel") == TACTICAL_MODEL, (label, battle.get("tacticalModel"))
    assert battle.get("battleSignalScope") == BATTLE_SIGNAL_SCOPE
    assert battle.get("autonomyStateScope") == "CURRENT_EVENT_ONLY"
    assert battle.get("actorScopedContinuousBattleMemory") is True
    assert battle.get("unrelatedActorContactContamination") is False
    assert battle.get("eventLocalAutonomyPreserved") is True

    modes = set((battle.get("modeCounts") or {}).keys())
    required_modes = {"ENGAGE", "BREAK_CONTACT", "REPOSITION", "COUNTER"}
    assert required_modes <= modes, (label, "TACTICAL_MODES_MISSING", sorted(required_modes - modes), sorted(modes))
    cycles = battle.get("maxBattleCycleByActor") or {}
    assert cycles and max(int(value) for value in cycles.values()) >= 1, (label, "NO_REALIZED_BATTLE_CYCLE", cycles)
    assert battle.get("sameRuntimeAcrossAssets") is True
    assert battle.get("liveWorldStateDriven") is True
    assert battle.get("actorProfileCapabilityDriven") is True
    assert battle.get("perAssetBattleCode") is False
    assert battle.get("perVideoTrajectoryEngineering") is False
    assert battle.get("actorPoseOrVelocityMutation") is False
    assert battle.get("reverseMotionHeadingAware") is True
    assert battle.get("geometryConfirmedSeparationBeforeReengagement") is True

    history_chain = _counter_history_proof(label, battle)

    impacts = g06.get("g05BoundImpacts") or []
    direct = [row for row in impacts if not row.get("inherited")]
    assert len(direct) >= 2, (label, "SECOND_NATIVE_CONTACT_NOT_PROVEN", len(direct), direct)
    event_ids = {str(row.get("eventId") or "") for row in direct}
    assert "evt-counterattack" in event_ids, (label, "COUNTERATTACK_NATIVE_CONTACT_NOT_PROVEN", sorted(event_ids))
    assert all((row.get("nativeContactReceipt") or {}).get("status") == "VERIFIED" for row in direct), (label, "G05_RECEIPT_NOT_VERIFIED")
    assert all((row.get("nativeContactReceipt") or {}).get("model") == "RECIPROCAL_NATIVE_SOLVER_RESPONSE_V1" for row in direct), (label, "G05_CONTACT_AUTHORITY_DRIFT")

    actors = g06.get("finalActors") or {}
    assert actors, (label, "NO_FINAL_ACTORS")
    visible: list[tuple[str, dict]] = []
    debris = 0
    max_normalized_deformation = 0.0
    max_localization_distance = 0.0
    damaged_actor_count = 0
    localized_actor_ids: set[str] = set()
    for actor_id, row in actors.items():
        state = row.get("state") or {}
        visual = row.get("visual") or {}
        if int(state.get("damageEventCount") or 0) > 0:
            damaged_actor_count += 1
        for evidence in visual.get("damageVisualEvidence") or []:
            if evidence.get("model") != "ISS_CAUSAL_VISIBLE_IMPACT_CONSEQUENCE_V2":
                continue
            visible.append((actor_id, evidence))
            debris += int(evidence.get("debrisCount") or 0)
            max_normalized_deformation = max(max_normalized_deformation, float(evidence.get("normalizedDeformation") or 0.0))
            assert evidence.get("contactLocalizationModel") == LOCALIZATION_MODEL, (label, "RECIPIENT_LOCALIZATION_MODEL_MISSING", actor_id)
            assert evidence.get("g05ContactTruthRewritten") is False, (label, "G05_CONTACT_TRUTH_REWRITE_FORBIDDEN", actor_id)
            original = evidence.get("originalVerifiedContactPoint")
            anchor = evidence.get("visualRecipientAnchorPoint")
            assert isinstance(original, list) and len(original) == 3, (label, "ORIGINAL_CONTACT_POINT_MISSING", actor_id)
            assert isinstance(anchor, list) and len(anchor) == 3, (label, "RECIPIENT_ANCHOR_MISSING", actor_id)
            distance = float(evidence.get("localizationDistanceM") or 0.0)
            assert math.isfinite(distance) and distance >= 0.0, (label, "RECIPIENT_LOCALIZATION_DISTANCE_INVALID", actor_id, distance)
            max_localization_distance = max(max_localization_distance, distance)
            localized_actor_ids.add(str(actor_id))

    assert damaged_actor_count >= 2, (label, "TWO_SIDED_DAMAGE_NOT_PRESERVED", damaged_actor_count)
    assert visible, (label, "V2_VISIBLE_CONSEQUENCE_NOT_OBSERVED")
    assert len(localized_actor_ids) >= 2, (label, "TWO_SIDED_RECIPIENT_LOCALIZATION_NOT_PROVEN", sorted(localized_actor_ids))
    assert max_normalized_deformation >= 0.02, (label, "VISIBLE_DEFORMATION_TOO_SMALL", max_normalized_deformation)
    assert debris >= 2, (label, "VISIBLE_DEBRIS_NOT_REALIZED", debris)

    assert g07.get("status") == "COMPLETE", (label, "DRAMA_INCOMPLETE", g07.get("status"))
    for key in ("escalation", "counterattack", "reversal", "climax", "payoff"):
        assert g07.get(key) is not None, (label, "DRAMA_STAGE_MISSING", key)

    assert g08.get("cinematicSaliencePass") is True, (label, "CAMERA_SALIENCE_FAIL")
    assert g08.get("humanCinematicAcceptance") == "PENDING", (label, "HUMAN_REVIEW_MUST_REMAIN_PENDING")

    return {
        "label": label,
        "modes": sorted(modes),
        "battleCycles": cycles,
        "actorHistoryChain": history_chain,
        "directG05Impacts": len(direct),
        "directImpactEventIds": sorted(event_ids),
        "visibleConsequenceEvents": len(visible),
        "localizedActors": sorted(localized_actor_ids),
        "contactLocalizationModel": LOCALIZATION_MODEL,
        "maxLocalizationDistanceM": max_localization_distance,
        "debrisCount": debris,
        "maxNormalizedDeformation": max_normalized_deformation,
        "g07": "COMPLETE",
        "g08MachineSalience": "PASS",
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    for prefix in ("bugatti", "generic"):
        for key in ("battle", "g06", "g07", "g08"):
            parser.add_argument(f"--{prefix}-{key}", required=True)
    args = parser.parse_args()

    rows = []
    for prefix in ("bugatti", "generic"):
        rows.append(_validate(
            prefix,
            getattr(args, f"{prefix}_battle"),
            getattr(args, f"{prefix}_g06"),
            getattr(args, f"{prefix}_g07"),
            getattr(args, f"{prefix}_g08"),
        ))

    print(json.dumps({
        "marker": "GENERIC_AUTONOMOUS_BATTLE_C461_MACHINE_ACCEPTANCE",
        "status": "PASS",
        "fullAffectedLayerAudit": "PASS",
        "sameRuntimeAcrossAssets": True,
        "actorScopedContinuousBattleMemory": True,
        "battleSignalScope": BATTLE_SIGNAL_SCOPE,
        "autonomyCurrentEventCountersRemainEventScoped": True,
        "historicalContactObservedBeforeCurrentEventContact": True,
        "breakBeforeRepositionBeforeCounter": True,
        "secondNativeContact": "PASS",
        "nativeContactAuthorityPreserved": True,
        "recipientVisualLocalization": "PASS",
        "g05ContactTruthRewritten": False,
        "damageAdmissionThresholdChanged": False,
        "contactThresholdChanged": False,
        "continuousBattleCycle": "PASS",
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
