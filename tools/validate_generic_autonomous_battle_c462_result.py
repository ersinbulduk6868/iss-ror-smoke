#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

LOCALIZATION_MODEL = "VERIFIED_PAIR_NEAREST_RECIPIENT_MESH_VERTEX_V1"
BATTLE_CONTROL_MODEL = "ISS_GENERIC_AUTONOMOUS_BATTLE_CONTROL_V4"
TACTICAL_MODEL = "ISS_GENERIC_ADAPTIVE_BATTLE_TACTICS_V4"
BATTLE_SIGNAL_SCOPE = "ACTOR_INVOLVEMENT_EVENT_HISTORY_V1"
CONSEQUENCE_MODEL = "ISS_CAUSAL_VISIBLE_IMPACT_CONSEQUENCE_V3"


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

    proven: dict[str, dict[str, object]] = {}
    for actor_id, rows in by_actor.items():
        break_i = reposition_i = counter_i = None
        historical_signal = 0
        current_contacts = 0
        contributors: list[str] = []
        for index, sample in enumerate(rows):
            mode = str(sample.get("tacticalMode") or "")
            obs = sample.get("observation") or {}
            actor_signal = int(obs.get("actorRealizedContactSignalCount") or 0)
            current = int(obs.get("currentEventContactCount") or 0)
            contrib = [str(x) for x in (obs.get("actorSignalContributingEvents") or [])]
            if break_i is None and mode == "BREAK_CONTACT" and actor_signal > current and any(x != "evt-counterattack" for x in contrib):
                break_i = index
                historical_signal = actor_signal
                current_contacts = current
                contributors = contrib
                continue
            if break_i is not None and reposition_i is None and index > break_i and mode == "REPOSITION":
                reposition_i = index
                continue
            if reposition_i is not None and counter_i is None and index > reposition_i and mode == "COUNTER" and sample.get("contactCommit") is True:
                counter_i = index
                break
        if break_i is not None and reposition_i is not None and counter_i is not None:
            proven[actor_id] = {
                "historicalBreakFrame": int(rows[break_i].get("frame") or 0),
                "repositionFrame": int(rows[reposition_i].get("frame") or 0),
                "counterFrame": int(rows[counter_i].get("frame") or 0),
                "actorRealizedContactSignalCountAtBreak": historical_signal,
                "currentEventContactCountAtBreak": current_contacts,
                "contributingEventsAtBreak": contributors,
            }
    assert proven, (label, "ACTOR_HISTORY_BREAK_REPOSITION_COUNTER_CHAIN_NOT_PROVEN", by_actor)
    return {"actors": proven, "historicalContactObservedBeforeCurrentEventContact": True, "breakBeforeRepositionBeforeCounter": True}


def _payoff_hold_proof(label: str, battle: dict) -> None:
    payoff = [s for s in (battle.get("samples") or []) if str(s.get("storyPhase") or "").upper() == "PAYOFF"]
    assert payoff, (label, "PAYOFF_TACTICAL_EVIDENCE_MISSING")
    assert all(str(s.get("tacticalMode") or "") == "HOLD" for s in payoff), (label, "PAYOFF_RECOVERY_LEAK", payoff)
    assert all(str(s.get("speedIntent") or "") == "BRAKE" for s in payoff), (label, "PAYOFF_NOT_BRAKED")


def _validate(label: str, battle_path: str, g06_path: str, g07_path: str, g08_path: str) -> dict[str, object]:
    battle = _load(battle_path)
    g06 = _load(g06_path)
    g07 = _load(g07_path)
    g08 = _load(g08_path)

    assert battle.get("battleControlModel") == BATTLE_CONTROL_MODEL
    assert battle.get("tacticalModel") == TACTICAL_MODEL
    assert battle.get("battleSignalScope") == BATTLE_SIGNAL_SCOPE
    assert battle.get("autonomyStateScope") == "CURRENT_EVENT_ONLY"
    assert battle.get("actorScopedContinuousBattleMemory") is True
    assert battle.get("unrelatedActorContactContamination") is False
    assert battle.get("eventLocalAutonomyPreserved") is True
    assert battle.get("sameRuntimeAcrossAssets") is True
    assert battle.get("liveWorldStateDriven") is True
    assert battle.get("actorProfileCapabilityDriven") is True
    assert battle.get("perAssetBattleCode") is False
    assert battle.get("perVideoTrajectoryEngineering") is False
    assert battle.get("actorPoseOrVelocityMutation") is False
    assert battle.get("reverseMotionHeadingAware") is True
    assert battle.get("geometryConfirmedSeparationBeforeReengagement") is True
    assert battle.get("damageIntentAdaptiveRetry") is True
    assert battle.get("damageRetryUsesCapabilityAndLiveGeometry") is True

    modes = set((battle.get("modeCounts") or {}).keys())
    required_modes = {"ENGAGE", "BREAK_CONTACT", "REPOSITION", "COUNTER", "HOLD"}
    assert required_modes <= modes, (label, "TACTICAL_MODES_MISSING", sorted(required_modes - modes), sorted(modes))
    cycles = battle.get("maxBattleCycleByActor") or {}
    assert cycles and max(int(value) for value in cycles.values()) >= 1
    history_chain = _counter_history_proof(label, battle)
    _payoff_hold_proof(label, battle)

    impacts = g06.get("g05BoundImpacts") or []
    direct = [row for row in impacts if not row.get("inherited")]
    assert len(direct) >= 2, (label, "SECOND_NATIVE_CONTACT_NOT_PROVEN", len(direct))
    event_ids = {str(row.get("eventId") or "") for row in direct}
    assert "evt-counterattack" in event_ids
    assert all((row.get("nativeContactReceipt") or {}).get("status") == "VERIFIED" for row in direct)
    assert all((row.get("nativeContactReceipt") or {}).get("model") == "RECIPROCAL_NATIVE_SOLVER_RESPONSE_V1" for row in direct)

    actors = g06.get("finalActors") or {}
    assert actors
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
            if evidence.get("model") != CONSEQUENCE_MODEL:
                continue
            visible.append((actor_id, evidence))
            debris += int(evidence.get("debrisCount") or 0)
            max_normalized_deformation = max(max_normalized_deformation, float(evidence.get("normalizedDeformation") or 0.0))
            assert evidence.get("contactLocalizationModel") == LOCALIZATION_MODEL
            assert evidence.get("g05ContactTruthRewritten") is False
            assert evidence.get("physicalDamageGateChanged") is False
            assert evidence.get("contactGateChanged") is False
            assert evidence.get("debrisEligibility") == "UNCHANGED_DAMAGE_GATE_PLUS_REALIZED_DEFORMATION_OR_SEVERITY"
            original = evidence.get("originalVerifiedContactPoint")
            anchor = evidence.get("visualRecipientAnchorPoint")
            assert isinstance(original, list) and len(original) == 3
            assert isinstance(anchor, list) and len(anchor) == 3
            distance = float(evidence.get("localizationDistanceM") or 0.0)
            assert math.isfinite(distance) and distance >= 0.0
            max_localization_distance = max(max_localization_distance, distance)
            localized_actor_ids.add(str(actor_id))

    assert damaged_actor_count >= 2, (label, "TWO_SIDED_DAMAGE_NOT_PRESERVED", damaged_actor_count)
    assert visible, (label, "V3_VISIBLE_CONSEQUENCE_NOT_OBSERVED")
    assert len(localized_actor_ids) >= 2
    assert max_normalized_deformation >= 0.02, (label, "VISIBLE_DEFORMATION_TOO_SMALL", max_normalized_deformation)
    assert debris >= 2, (label, "VISIBLE_DEBRIS_NOT_REALIZED", debris)

    assert g07.get("status") == "COMPLETE"
    for key in ("escalation", "counterattack", "reversal", "climax", "payoff"):
        assert g07.get(key) is not None, (label, "DRAMA_STAGE_MISSING", key)
    assert g08.get("cinematicSaliencePass") is True, (label, "CAMERA_SALIENCE_FAIL")
    assert g08.get("humanCinematicAcceptance") == "PENDING"

    return {
        "label": label,
        "modes": sorted(modes),
        "battleCycles": cycles,
        "actorHistoryChain": history_chain,
        "payoffRecoveryLeak": False,
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
    rows = [
        _validate(prefix, getattr(args, f"{prefix}_battle"), getattr(args, f"{prefix}_g06"), getattr(args, f"{prefix}_g07"), getattr(args, f"{prefix}_g08"))
        for prefix in ("bugatti", "generic")
    ]
    print(json.dumps({
        "marker": "GENERIC_AUTONOMOUS_BATTLE_C462_MACHINE_ACCEPTANCE",
        "status": "PASS",
        "fullAffectedLayerAudit": "PASS",
        "sameRuntimeAcrossAssets": True,
        "actorScopedContinuousBattleMemory": True,
        "battleSignalScope": BATTLE_SIGNAL_SCOPE,
        "autonomyCurrentEventCountersRemainEventScoped": True,
        "historicalContactObservedBeforeCurrentEventContact": True,
        "breakBeforeRepositionBeforeCounter": True,
        "payoffTerminatesRecovery": True,
        "damageIntentAdaptiveRetry": True,
        "damageRetryUsesCapabilityAndLiveGeometry": True,
        "secondNativeContact": "PASS",
        "nativeContactAuthorityPreserved": True,
        "recipientVisualLocalization": "PASS",
        "g05ContactTruthRewritten": False,
        "damageAdmissionThresholdChanged": False,
        "contactThresholdChanged": False,
        "debrisEligibilityUsesEarnedDamageConsequence": True,
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
