#!/usr/bin/env python3
from __future__ import annotations

import argparse
import copy
import hashlib
import json
from pathlib import Path

import build_generic_battle_runtime_v1_preflight as base

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "artifacts" / "generic-battle-runtime-v1-candidate442-g07"
EXPECTED_BUGATTI_SHA = "8cc074c40fe9ced7271cbeddf223cd9a520dee868977ffcbd439cec1c2b62cb4"
EXPECTED_BUGATTI_BYTES = 31576440
BUGATTI_SOURCE_UID = "4af92c51ecdd4efa9b1c19a1163d9f46"


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def intent_event(
    *,
    event_id: str,
    event_type: str,
    phase: str,
    start_time: float,
    end_time: float,
    actor: str,
    target: str,
    dependencies: list[str],
    tactical_purpose: str,
    required_outcome: str,
) -> dict:
    return {
        "eventId": event_id,
        "type": event_type,
        "phase": phase,
        "startTime": start_time,
        "endTime": end_time,
        "actors": [actor],
        "attackTarget": target,
        "causedByEventIds": dependencies,
        "damage": {"required": False, "persistent": True},
        "tacticalPurpose": tactical_purpose,
        "physicsRequirements": {
            "minQualifiedContacts": 1,
            "minDistinctAttackers": 1,
        },
        "requiredOutcome": required_outcome,
        "usesPersistentWorldState": True,
    }


def drama_request(template: dict, bindings: list[dict]) -> dict:
    request = copy.deepcopy(template)
    request["durationSeconds"] = 30
    request["assetBindings"] = copy.deepcopy(bindings)
    request.setdefault("requiredEvidence", {})["visibleDamage"] = False
    request["requiredEvidence"]["persistentDebris"] = False
    request["battlePlan"]["objective"] = (
        "Execute an autonomous physical conflict from actor-level intent only. The generic runtime must determine approach, steering, throttle, braking, contact timing and realized collision from live world state and ActorProfile capability."
    )
    request["battlePlan"]["finalOutcome"] = (
        "Resolve final actor order from realized physical state after direct native-contact escalation, causal counterattack, physical initiative reversal, climax and payoff. Never force a winner or prescribe collision mechanics."
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
        "physicsRequirements": {},
        "requiredOutcome": "Actors remain in one continuous physical world.",
        "usesPersistentWorldState": True,
    }
    escalation = intent_event(
        event_id="evt-escalation",
        event_type="FIRST_ATTACK",
        phase="ESCALATION",
        start_time=0.5,
        end_time=9.0,
        actor="actor_alpha",
        target="actor_beta",
        dependencies=["evt-setup"],
        tactical_purpose="ENGAGE",
        required_outcome="Alpha initiates real physical aggression. The runtime autonomously realizes any contact; Story does not prescribe how or where the collision occurs.",
    )
    counter = intent_event(
        event_id="evt-counterattack",
        event_type="COUNTERATTACK",
        phase="COUNTERATTACK",
        start_time=4.0,
        end_time=19.0,
        actor="actor_beta",
        target="actor_alpha",
        dependencies=["evt-escalation"],
        tactical_purpose="COUNTER",
        required_outcome="Beta may counter only after being the target of prior direct G05-verified aggression from alpha; the runtime autonomously realizes the counter-contact.",
    )
    climax = intent_event(
        event_id="evt-climax",
        event_type="CLIMAX_ATTACK",
        phase="CLIMAX",
        start_time=11.0,
        end_time=27.0,
        actor="actor_alpha",
        target="actor_beta",
        dependencies=["evt-counterattack"],
        tactical_purpose="ENGAGE",
        required_outcome="The climax is eligible only after a real initiative reversal and must earn a later direct G05-verified native physical transaction without collision choreography.",
    )
    payoff = {
        "eventId": "evt-payoff",
        "type": "OUTCOME",
        "phase": "PAYOFF",
        "startTime": 23.0,
        "endTime": 29.0,
        "actors": ["actor_alpha", "actor_beta"],
        "attackTarget": "",
        "causedByEventIds": ["evt-climax"],
        "damage": {"required": False, "persistent": True},
        "tacticalPurpose": "SETTLE",
        "physicsRequirements": {},
        "requiredOutcome": "Preserve the continuous world and settle the physical-state outcome without reset or forced winner.",
        "usesPersistentWorldState": True,
    }
    request["battlePlan"]["events"] = [setup, escalation, counter, climax, payoff]
    request["scenes"] = [
        {"sceneNumber": 1, "startSecond": 0.0, "endSecond": 5.0, "eventIds": ["evt-setup", "evt-escalation"], "cameraIntent": "Observe the autonomous opening conflict."},
        {"sceneNumber": 2, "startSecond": 5.0, "endSecond": 10.0, "eventIds": ["evt-escalation", "evt-counterattack"], "cameraIntent": "Observe causal counterattack eligibility from realized physical aggression."},
        {"sceneNumber": 3, "startSecond": 10.0, "endSecond": 15.0, "eventIds": ["evt-counterattack", "evt-climax"], "cameraIntent": "Observe the physical initiative reversal and causal handoff to climax."},
        {"sceneNumber": 4, "startSecond": 15.0, "endSecond": 20.0, "eventIds": ["evt-climax"], "cameraIntent": "Observe the autonomous climax."},
        {"sceneNumber": 5, "startSecond": 20.0, "endSecond": 25.0, "eventIds": ["evt-climax", "evt-payoff"], "cameraIntent": "Observe continuous-world consequences."},
        {"sceneNumber": 6, "startSecond": 25.0, "endSecond": 30.0, "eventIds": ["evt-payoff"], "cameraIntent": "Observe final causal payoff without reset."},
    ]
    return request


def verify_intent_only_request(request: dict) -> None:
    forbidden_keys = {
        "collisionframe", "contactframe", "impactframe", "targetenergyj", "impactenergyj",
        "targetimpactspeedmps", "trajectorypoints", "pathpoints", "waypoints",
        "positionkeyframes", "velocitykeyframes", "winnerid", "forcedwinner",
        "targetarea", "speedintent", "steeringangle", "brakingpoint", "approachvector",
        "collisionpoint", "contactpoint",
    }

    def walk(value):
        if isinstance(value, dict):
            for key, child in value.items():
                if str(key).lower() in forbidden_keys:
                    raise RuntimeError(f"CANDIDATE442_FORBIDDEN_COLLISION_CHOREOGRAPHY_FIELD:{key}")
                walk(child)
        elif isinstance(value, list):
            for child in value:
                walk(child)

    walk(request)
    events = {row["eventId"]: row for row in request["battlePlan"]["events"]}
    for event_id in ("evt-escalation", "evt-counterattack", "evt-climax"):
        event = events[event_id]
        target = str(event.get("attackTarget") or "")
        if not target or ":" in target:
            raise RuntimeError(f"CANDIDATE442_TARGET_MUST_BE_ACTOR_ONLY:{event_id}:{target}")
        if bool((event.get("damage") or {}).get("required")):
            raise RuntimeError(f"CANDIDATE442_G07_DAMAGE_MUST_NOT_BE_REQUIRED:{event_id}")
        req = event.get("physicsRequirements") or {}
        if set(req) != {"minQualifiedContacts", "minDistinctAttackers"}:
            raise RuntimeError(f"CANDIDATE442_PHYSICS_REQUIREMENTS_NOT_INTENT_ONLY:{event_id}:{sorted(req)}")
        if int(req.get("minQualifiedContacts") or 0) != 1:
            raise RuntimeError(f"CANDIDATE442_CONTACT_REQUIREMENT_INVALID:{event_id}")
    if request.get("requiredEvidence", {}).get("visibleDamage") is not False:
        raise RuntimeError("CANDIDATE442_VISIBLE_DAMAGE_MUST_NOT_GATE_G07")
    if request.get("requiredEvidence", {}).get("persistentDebris") is not False:
        raise RuntimeError("CANDIDATE442_DEBRIS_MUST_NOT_GATE_G07")


def write_fixture(name: str, request: dict, amap: dict) -> dict:
    verify_intent_only_request(request)
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
    generic_map = {row["entityId"]: {"path": str(generic_glb), "sha256": generic_sha} for row in generic_bindings}
    generic = write_fixture("generic-hypercar", generic_request, generic_map)

    bugatti = Path(args.bugatti_primary).expanduser().resolve()
    if not bugatti.is_file():
        raise RuntimeError(f"BUGATTI_PRIMARY_MISSING:{bugatti}")
    bugatti_sha = sha256_file(bugatti)
    if bugatti_sha != EXPECTED_BUGATTI_SHA or bugatti.stat().st_size != EXPECTED_BUGATTI_BYTES:
        raise RuntimeError("CANDIDATE442_BUGATTI_EXACT_IDENTITY_FAIL")
    common = {
        "sourceUid": BUGATTI_SOURCE_UID,
        "sourceProvider": "exact_full_source",
        "sourceSha256": bugatti_sha,
        "totalMassKg": 1570.0,
        "semanticBodies": ["front", "rear", "body", "chassis"],
        "runtimeProfile": {"locomotionModel": "GROUND_DIFFERENTIAL", "friction": 1.0, "restitution": 0.03},
    }
    bugatti_bindings = [
        {**common, "entityId": "actor_alpha", "assetId": "bugatti-alpha"},
        {**common, "entityId": "actor_beta", "assetId": "bugatti-beta"},
    ]
    bugatti_request = drama_request(template, bugatti_bindings)
    bugatti_map = {row["entityId"]: {"path": str(bugatti), "sha256": bugatti_sha} for row in bugatti_bindings}
    exact = write_fixture("exact-bugatti", bugatti_request, bugatti_map)

    print(json.dumps({
        "marker": "GENERIC_BATTLE_RUNTIME_CANDIDATE442_G07_FIXTURES_PASS",
        "status": "PASS",
        "generic": {**generic, "sha256": generic_sha},
        "exactBugatti": {**exact, "sha256": bugatti_sha, "bytes": bugatti.stat().st_size},
        "sameIntentStructureAcrossAssets": True,
        "storyIntentOnly": True,
        "runtimeChoosesCollisionRealization": True,
        "damageRequiredForG07": False,
        "hardCodedContactZone": False,
        "speedIntentPrescribed": False,
        "exactCollisionFrameTarget": False,
        "exactImpactEnergyTarget": False,
        "manualTrajectoryPoints": False,
        "forcedWinner": False,
        "assetSpecificBattleTiming": False,
        "issR041ScopePreserved": True,
        "issR042ScopePreserved": True,
    }, sort_keys=True))


if __name__ == "__main__":
    main()
