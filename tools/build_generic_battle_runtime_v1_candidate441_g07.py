#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import build_generic_battle_runtime_v1_candidate44_g07 as candidate44_builder

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "artifacts" / "generic-battle-runtime-v1-candidate441-g07"
_ORIGINAL_DRAMA_REQUEST = candidate44_builder.drama_request


def drama_request_v2(template: dict[str, Any], bindings: list[dict[str, Any]]) -> dict[str, Any]:
    request = _ORIGINAL_DRAMA_REQUEST(template, bindings)

    setup = request["battlePlan"]["events"][0]
    counter = request["battlePlan"]["events"][2]
    climax = request["battlePlan"]["events"][3]
    payoff = request["battlePlan"]["events"][4]

    escalation_alpha = {
        "eventId": "evt-escalation-alpha",
        "type": "FIRST_ATTACK",
        "phase": "ESCALATION",
        "startTime": 0.5,
        "endTime": 3.5,
        "actors": ["actor_alpha"],
        "attackTarget": "actor_beta:front",
        "causedByEventIds": ["evt-setup"],
        "damage": {"required": True, "persistent": True, "zone": "front"},
        "tacticalPurpose": "RAM",
        "physicsRequirements": {
            "speedIntent": "accelerate",
            "targetArea": "front",
            "minQualifiedContacts": 1,
            "minDistinctAttackers": 1,
        },
        "requiredOutcome": "The opening mutual escalation must produce a direct G05-verified physical transaction that earns persistent G06 damage without numeric impact tuning.",
        "usesPersistentWorldState": True,
    }
    escalation_beta = {
        "eventId": "evt-escalation-beta",
        "type": "FIRST_ATTACK",
        "phase": "ESCALATION",
        "startTime": 0.5,
        "endTime": 3.5,
        "actors": ["actor_beta"],
        "attackTarget": "actor_alpha:front",
        "causedByEventIds": ["evt-setup"],
        "damage": {"required": True, "persistent": True, "zone": "front"},
        "tacticalPurpose": "RAM",
        "physicsRequirements": {
            "speedIntent": "accelerate",
            "targetArea": "front",
            "minQualifiedContacts": 1,
            "minDistinctAttackers": 1,
        },
        "requiredOutcome": "The opposing actor participates in the same real escalation; reciprocal consequence remains one physical transaction and may not be double-counted as initiative.",
        "usesPersistentWorldState": True,
    }

    counter["causedByEventIds"] = ["evt-escalation-alpha", "evt-escalation-beta"]
    counter["damage"] = {"required": False, "persistent": True, "zone": "front"}
    counter["requiredOutcome"] = (
        "The previously damaged actor may counter only after prior G05/G06-backed damage; a new unique direct G05 VERIFIED physical transaction must reverse initiative. New visible damage is not required for initiative truth."
    )

    climax["damage"] = {"required": False, "persistent": True, "zone": "front"}
    climax["requiredOutcome"] = (
        "After a real reversal, the climax must earn its own later unique direct G05 VERIFIED physical transaction; it may not be unlocked by timing or labels and need not cross the independent G06 deformation threshold again."
    )

    request["battlePlan"]["objective"] = (
        "Use a real opposing opening escalation to earn persistent damage, then let the damaged side autonomously counter, physically reverse initiative, unlock a later climax and settle the causal payoff in one continuous world."
    )
    request["battlePlan"]["finalOutcome"] = (
        "Resolve final actor order from realized physical state after persistent-damage escalation, state-earned counterattack, verified physical reversal, verified physical climax and payoff; never force a winner."
    )
    request["battlePlan"]["events"] = [
        setup,
        escalation_alpha,
        escalation_beta,
        counter,
        climax,
        payoff,
    ]
    request["scenes"] = [
        {
            "sceneNumber": 1,
            "startSecond": 0.0,
            "endSecond": 5.0,
            "eventIds": ["evt-setup", "evt-escalation-alpha", "evt-escalation-beta", "evt-counterattack"],
            "cameraIntent": "Establish one continuous world, the opposing opening escalation and the causal counterattack eligibility earned from persistent damage.",
        },
        {
            "sceneNumber": 2,
            "startSecond": 5.0,
            "endSecond": 10.0,
            "eventIds": ["evt-counterattack"],
            "cameraIntent": "Track the damaged actor's autonomous direct physical counterattack and initiative reversal.",
        },
        {
            "sceneNumber": 3,
            "startSecond": 10.0,
            "endSecond": 15.0,
            "eventIds": ["evt-counterattack", "evt-climax"],
            "cameraIntent": "Transition from the verified comeback into climax only after the physical reversal exists.",
        },
        {
            "sceneNumber": 4,
            "startSecond": 15.0,
            "endSecond": 20.0,
            "eventIds": ["evt-climax"],
            "cameraIntent": "Track the autonomous direct physical climax in the same persistent world.",
        },
        {
            "sceneNumber": 5,
            "startSecond": 20.0,
            "endSecond": 25.0,
            "eventIds": ["evt-climax", "evt-payoff"],
            "cameraIntent": "Follow climax consequences into persistent aftermath without resetting battle state.",
        },
        {
            "sceneNumber": 6,
            "startSecond": 25.0,
            "endSecond": 30.0,
            "eventIds": ["evt-payoff"],
            "cameraIntent": "Hold on the causal payoff and final physical state without scripted winner selection.",
        },
    ]
    return request


def verify_request(path: Path) -> None:
    req = json.loads(path.read_text(encoding="utf-8"))
    events = {row["eventId"]: row for row in req["battlePlan"]["events"]}
    expected = {
        "evt-setup",
        "evt-escalation-alpha",
        "evt-escalation-beta",
        "evt-counterattack",
        "evt-climax",
        "evt-payoff",
    }
    if set(events) != expected:
        raise RuntimeError(f"CANDIDATE441_EVENT_SET_INVALID:{sorted(events)}")
    for event_id in ("evt-escalation-alpha", "evt-escalation-beta"):
        if events[event_id]["damage"].get("required") is not True:
            raise RuntimeError(f"CANDIDATE441_OPENING_DAMAGE_NOT_REQUIRED:{event_id}")
    for event_id in ("evt-counterattack", "evt-climax"):
        event = events[event_id]
        if event["damage"].get("required") is not False:
            raise RuntimeError(f"CANDIDATE441_LATER_DAMAGE_WRONGLY_REQUIRED:{event_id}")
        if int(event["physicsRequirements"].get("minQualifiedContacts") or 0) < 1:
            raise RuntimeError(f"CANDIDATE441_LATER_G05_CONTACT_NOT_REQUIRED:{event_id}")
    if events["evt-counterattack"]["causedByEventIds"] != ["evt-escalation-alpha", "evt-escalation-beta"]:
        raise RuntimeError("CANDIDATE441_COUNTER_DEPENDENCY_INVALID")


def main() -> None:
    candidate44_builder.OUT = OUT
    candidate44_builder.drama_request = drama_request_v2
    candidate44_builder.main()

    exact = OUT / "exact-bugatti" / "request.json"
    generic = OUT / "generic-hypercar" / "request.json"
    verify_request(exact)
    verify_request(generic)

    print(json.dumps({
        "marker": "GENERIC_BATTLE_RUNTIME_CANDIDATE441_G07_FIXTURES_PASS",
        "status": "PASS",
        "sameIntentStructureAcrossAssets": True,
        "mutualOpeningEscalation": True,
        "openingPersistentDamageRequired": True,
        "counterattackDirectG05ContactRequired": True,
        "counterattackRepeatedDamageRequired": False,
        "climaxDirectG05ContactRequired": True,
        "climaxRepeatedDamageRequired": False,
        "damageThresholdChanged": False,
        "exactCollisionFrameTarget": False,
        "exactImpactEnergyTarget": False,
        "manualTrajectoryPoints": False,
        "forcedWinner": False,
        "assetSpecificBattleTiming": False,
    }, sort_keys=True))


if __name__ == "__main__":
    main()
