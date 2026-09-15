#!/usr/bin/env python3
from __future__ import annotations

import argparse
import copy
import hashlib
import json
from pathlib import Path

import build_generic_battle_runtime_v1_preflight as base

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "artifacts" / "generic-battle-runtime-v1-candidate44-g07"
EXPECTED_BUGATTI_SHA = "8cc074c40fe9ced7271cbeddf223cd9a520dee868977ffcbd439cec1c2b62cb4"
EXPECTED_BUGATTI_BYTES = 31576440
BUGATTI_SOURCE_UID = "4af92c51ecdd4efa9b1c19a1163d9f46"


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def drama_request(template: dict, bindings: list[dict]) -> dict:
    request = copy.deepcopy(template)
    request["durationSeconds"] = 30
    request["assetBindings"] = copy.deepcopy(bindings)
    request["requiredEvidence"]["visibleDamage"] = True
    request["requiredEvidence"]["persistentDebris"] = True
    request["battlePlan"]["objective"] = (
        "Escalate from a real opening strike into a state-earned counterattack, a physical initiative reversal/comeback, a causally unlocked climax and a final payoff in one continuous world."
    )
    request["battlePlan"]["finalOutcome"] = (
        "Resolve the winner/order from the final physical actor state only after escalation, counterattack, comeback, climax and payoff have been physically earned."
    )

    setup = {
        "eventId": "evt-setup",
        "type": "BATTLE_HOOK",
        "phase": "HOOK",
        "startTime": 0.0,
        "endTime": 0.5,
        "actors": ["actor_alpha", "actor_beta"],
        "attackTarget": "",
        "causedByEventIds": [],
        "damage": {"required": False},
        "tacticalPurpose": "HOLD",
        "physicsRequirements": {"speedIntent": "hold", "targetArea": "none"},
        "requiredOutcome": "Actors remain in the same continuous physical world.",
        "usesPersistentWorldState": True,
    }
    escalation = {
        "eventId": "evt-escalation",
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
        "requiredOutcome": "Alpha earns the opening escalation through a G05-verified native physical transaction that causes persistent damage.",
        "usesPersistentWorldState": True,
    }
    counter = {
        "eventId": "evt-counterattack",
        "type": "COUNTERATTACK",
        "phase": "COUNTERATTACK",
        "startTime": 4.0,
        "endTime": 14.0,
        "actors": ["actor_beta"],
        "attackTarget": "actor_alpha:front",
        "causedByEventIds": ["evt-escalation"],
        "damage": {"required": True, "persistent": True, "zone": "front"},
        "tacticalPurpose": "COUNTER",
        "physicsRequirements": {
            "speedIntent": "accelerate",
            "targetArea": "front",
            "minQualifiedContacts": 1,
            "minDistinctAttackers": 1,
        },
        "requiredOutcome": "Beta may counter only because it carries prior verified damage from alpha; a newer direct G05 damage transaction must physically reverse battle initiative.",
        "usesPersistentWorldState": True,
    }
    climax = {
        "eventId": "evt-climax",
        "type": "CLIMAX_ATTACK",
        "phase": "CLIMAX",
        "startTime": 10.0,
        "endTime": 24.0,
        "actors": ["actor_alpha"],
        "attackTarget": "actor_beta:front",
        "causedByEventIds": ["evt-counterattack"],
        "damage": {"required": True, "persistent": True, "zone": "front"},
        "tacticalPurpose": "RAM",
        "physicsRequirements": {
            "speedIntent": "accelerate",
            "targetArea": "front",
            "minQualifiedContacts": 1,
            "minDistinctAttackers": 1,
        },
        "requiredOutcome": "The climax is ineligible until the physical comeback/reversal exists, then must itself earn a G05-verified damage transaction.",
        "usesPersistentWorldState": True,
    }
    payoff = {
        "eventId": "evt-payoff",
        "type": "OUTCOME",
        "phase": "PAYOFF",
        "startTime": 22.0,
        "endTime": 29.0,
        "actors": ["actor_alpha", "actor_beta"],
        "attackTarget": "",
        "causedByEventIds": ["evt-climax"],
        "damage": {"required": False, "persistent": True},
        "tacticalPurpose": "SETTLE",
        "physicsRequirements": {"speedIntent": "settle", "targetArea": "none"},
        "requiredOutcome": "The final continuous-world payoff preserves all prior damage/debris and reports the physical-state outcome without forcing a winner.",
        "usesPersistentWorldState": True,
    }
    request["battlePlan"]["events"] = [setup, escalation, counter, climax, payoff]
    request["scenes"] = [
        {
            "sceneNumber": 1,
            "startSecond": 0.0,
            "endSecond": 5.0,
            "eventIds": ["evt-setup", "evt-escalation", "evt-counterattack"],
            "cameraIntent": "Establish the continuous world, opening escalation and the physically earned counterattack eligibility.",
        },
        {
            "sceneNumber": 2,
            "startSecond": 5.0,
            "endSecond": 10.0,
            "eventIds": ["evt-counterattack"],
            "cameraIntent": "Track the damaged actor's autonomous counterattack and physical initiative reversal.",
        },
        {
            "sceneNumber": 3,
            "startSecond": 10.0,
            "endSecond": 15.0,
            "eventIds": ["evt-counterattack", "evt-climax"],
            "cameraIntent": "Transition from comeback into a climax only after the reversal is realized.",
        },
        {
            "sceneNumber": 4,
            "startSecond": 15.0,
            "endSecond": 20.0,
            "eventIds": ["evt-climax"],
            "cameraIntent": "Track the autonomous climax in the same persistent physical world.",
        },
        {
            "sceneNumber": 5,
            "startSecond": 20.0,
            "endSecond": 25.0,
            "eventIds": ["evt-climax", "evt-payoff"],
            "cameraIntent": "Follow climax consequences into persistent aftermath.",
        },
        {
            "sceneNumber": 6,
            "startSecond": 25.0,
            "endSecond": 30.0,
            "eventIds": ["evt-payoff"],
            "cameraIntent": "Hold on the causal payoff and final world state without reset.",
        },
    ]
    return request


def write_fixture(name: str, request: dict, amap: dict) -> dict:
    out = OUT / name
    out.mkdir(parents=True, exist_ok=True)
    request_path = out / "request.json"
    asset_map_path = out / "asset-map.json"
    request_path.write_text(json.dumps(request, indent=2, sort_keys=True), encoding="utf-8")
    asset_map_path.write_text(json.dumps(amap, indent=2, sort_keys=True), encoding="utf-8")
    return {
        "request": str(request_path.resolve()),
        "assetMap": str(asset_map_path.resolve()),
        "actorCount": len(request["assetBindings"]),
        "eventCount": len(request["battlePlan"]["events"]),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--bugatti-primary", required=True)
    args = parser.parse_args()

    base.main()
    template = json.loads((base.OUT / "request.json").read_text(encoding="utf-8"))

    generic_glb = base.GLB.resolve()
    generic_sha = sha256_file(generic_glb)
    generic_bindings = copy.deepcopy(template["assetBindings"])
    generic_request = drama_request(template, generic_bindings)
    generic_map = {
        row["entityId"]: {"path": str(generic_glb), "sha256": generic_sha}
        for row in generic_bindings
    }
    generic = write_fixture("generic-hypercar", generic_request, generic_map)

    bugatti = Path(args.bugatti_primary).expanduser().resolve()
    if not bugatti.is_file():
        raise RuntimeError(f"BUGATTI_PRIMARY_MISSING:{bugatti}")
    bugatti_sha = sha256_file(bugatti)
    if bugatti_sha != EXPECTED_BUGATTI_SHA or bugatti.stat().st_size != EXPECTED_BUGATTI_BYTES:
        raise RuntimeError("CANDIDATE44_BUGATTI_EXACT_IDENTITY_FAIL")
    common = {
        "sourceUid": BUGATTI_SOURCE_UID,
        "sourceProvider": "exact_full_source",
        "sourceSha256": bugatti_sha,
        "totalMassKg": 1570.0,
        "semanticBodies": ["front", "rear", "body", "chassis"],
        "runtimeProfile": {
            "locomotionModel": "GROUND_DIFFERENTIAL",
            "friction": 1.0,
            "restitution": 0.03,
        },
    }
    bugatti_bindings = [
        {**common, "entityId": "actor_alpha", "assetId": "bugatti-alpha"},
        {**common, "entityId": "actor_beta", "assetId": "bugatti-beta"},
    ]
    bugatti_request = drama_request(template, bugatti_bindings)
    bugatti_map = {
        row["entityId"]: {"path": str(bugatti), "sha256": bugatti_sha}
        for row in bugatti_bindings
    }
    exact = write_fixture("exact-bugatti", bugatti_request, bugatti_map)

    for req in (generic_request, bugatti_request):
        raw = json.dumps(req, sort_keys=True).lower()
        for forbidden in (
            "collisionframe", "contactframe", "impactframe", "targetenergyj",
            "impactenergyj", "targetimpactspeedmps", "trajectorypoints",
            "pathpoints", "waypoints", "positionkeyframes", "velocitykeyframes",
            "forcedwinner", "winnerid",
        ):
            if forbidden in raw:
                raise RuntimeError(f"CANDIDATE44_FORBIDDEN_EXECUTABLE_CHOREOGRAPHY:{forbidden}")

    print(json.dumps({
        "marker": "GENERIC_BATTLE_RUNTIME_CANDIDATE44_G07_FIXTURES_PASS",
        "generic": {**generic, "sha256": generic_sha},
        "exactBugatti": {**exact, "sha256": bugatti_sha, "bytes": bugatti.stat().st_size},
        "continuousWorld": True,
        "escalationRequired": True,
        "stateEarnedCounterattackRequired": True,
        "physicalDominanceReversalRequired": True,
        "climaxAfterReversalRequired": True,
        "payoffAfterClimaxRequired": True,
        "persistentDamageAndDebrisRequired": True,
        "exactCollisionFrameTarget": False,
        "exactImpactEnergyTarget": False,
        "manualTrajectoryPoints": False,
        "forcedWinner": False,
        "assetSpecificBattleTiming": False,
    }, sort_keys=True))


if __name__ == "__main__":
    main()
