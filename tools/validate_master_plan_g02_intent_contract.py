#!/usr/bin/env python3
from __future__ import annotations

import copy
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from blender.iss_battle_runtime_contract import BattleRuntimeContractError
from blender.iss_battle_runtime_intent_contract_v2 import (
    INTENT_CONTRACT,
    IntentOnlyBattleCompiler,
    program_intent_signature,
    sanitize_intent_request,
)


def _base_request() -> dict:
    return {
        "durationSeconds": 15,
        "renderSpec": {"fps": 30},
        "executionPolicy": {
            "continuousWorld": True,
            "resetAllowed": False,
            "teleportAllowed": False,
            "silentSimplificationAllowed": False,
            "forcedTransformAfterContactAllowed": False,
            "velocityInjectionAfterContactAllowed": False,
        },
        "battlePlan": {
            "objective": "actor_alpha attacks actor_beta, actor_beta counters, battle resolves causally",
            "events": [
                {
                    "eventId": "evt-escalation",
                    "type": "ATTACK",
                    "phase": "ESCALATION",
                    "action": "attack",
                    "tacticalPurpose": "RAM",
                    "startTime": 0,
                    "endTime": 5,
                    "actors": ["actor_alpha", "actor_beta"],
                    "attackTarget": "actor_beta:front",
                    "damage": {
                        "required": True,
                        "persistent": True,
                        "zone": "front",
                        "stateChanges": ["reduced_drive_efficiency"],
                    },
                    "physicsRequirements": {
                        "minQualifiedContacts": 1,
                        "minDistinctAttackers": 1,
                        "trajectory": "THIS_MUST_NOT_EXECUTE",
                        "speedIntent": "THIS_MUST_NOT_EXECUTE",
                        "targetArea": "THIS_MUST_NOT_EXECUTE",
                        "targetEnergyJ": 999999999,
                        "collisionFrame": 42,
                    },
                    "causedByEventIds": [],
                    "requiredOutcome": "A real physical attack occurs; consequence must be earned by runtime physics.",
                },
                {
                    "eventId": "evt-counterattack",
                    "type": "COUNTERATTACK",
                    "phase": "COUNTERATTACK",
                    "action": "counterattack",
                    "tacticalPurpose": "COUNTER",
                    "startTime": 5,
                    "endTime": 10,
                    "actors": ["actor_beta", "actor_alpha"],
                    "attackTarget": "actor_alpha",
                    "damage": {"required": False, "persistent": True},
                    "physicsRequirements": {
                        "minQualifiedContacts": 1,
                        "minDistinctAttackers": 1,
                    },
                    "causedByEventIds": ["evt-escalation"],
                    "requiredOutcome": "Counterattack follows realized battle state.",
                },
                {
                    "eventId": "evt-payoff",
                    "type": "PAYOFF",
                    "phase": "PAYOFF",
                    "action": "resolve",
                    "tacticalPurpose": "SETTLE",
                    "startTime": 10,
                    "endTime": 15,
                    "actors": ["actor_alpha", "actor_beta"],
                    "attackTarget": "",
                    "damage": {"required": False, "persistent": True},
                    "physicsRequirements": {},
                    "causedByEventIds": ["evt-counterattack"],
                    "requiredOutcome": "Outcome follows realized state; no forced winner.",
                },
            ],
        },
        "scenes": [
            {"sceneNumber": 1, "startSecond": 0, "endSecond": 5, "eventIds": ["evt-escalation"], "cameraIntent": "show attack"},
            {"sceneNumber": 2, "startSecond": 5, "endSecond": 10, "eventIds": ["evt-counterattack"], "cameraIntent": "show counter"},
            {"sceneNumber": 3, "startSecond": 10, "endSecond": 15, "eventIds": ["evt-payoff"], "cameraIntent": "show payoff"},
        ],
    }


def _bindings() -> list[dict]:
    return [
        {"entityId": "actor_alpha", "massKg": 1650, "runtimeProfile": {"maxSpeedMps": 20, "accelerationMps2": 7}},
        {"entityId": "actor_beta", "massKg": 2200, "runtimeProfile": {"maxSpeedMps": 18, "accelerationMps2": 6}},
    ]


def _assert(condition: bool, message: str) -> None:
    if not condition:
        raise RuntimeError(message)


def main() -> None:
    request_a = _base_request()
    request_b = copy.deepcopy(request_a)
    poison = request_b["battlePlan"]["events"][0]["physicsRequirements"]
    poison.update(
        {
            "trajectory": "COMPLETELY_DIFFERENT_PATH",
            "speedIntent": "reverse",
            "targetArea": "rear_right_wheel",
            "targetEnergyJ": 1,
            "collisionFrame": 899,
            "steeringAngle": 73.0,
            "brakingPoint": [999, 999, 0],
            "approachVector": [-1, 0, 0],
        }
    )

    clean_a, provenance_a = sanitize_intent_request(request_a)
    clean_b, provenance_b = sanitize_intent_request(request_b)
    _assert(clean_a == clean_b, "G02_POISONED_LEGACY_CHOREOGRAPHY_CHANGED_EXECUTABLE_REQUEST")

    event = clean_a["battlePlan"]["events"][0]
    _assert(event["attackTarget"] == "actor_beta", "G02_TARGET_MUST_BE_ACTOR_ONLY")
    _assert(set(event.get("physicsRequirements") or {}) == {"minQualifiedContacts", "minDistinctAttackers"}, "G02_ONLY_GENERIC_PHYSICS_CONSTRAINTS_ALLOWED")
    _assert(event.get("intentConsequences", {}).get("damageRequired") is True, "G02_DAMAGE_INTENT_MUST_BE_PRESERVED")
    _assert((event.get("damage") or {}).get("required") is False, "G02_DAMAGE_MUST_NOT_SCRIPT_CONTACT_ZONE")
    _assert("zone" not in (event.get("damage") or {}), "G02_STORY_DAMAGE_ZONE_EXECUTION_FORBIDDEN")

    program_a, compile_provenance_a = IntentOnlyBattleCompiler.compile(request_a, _bindings())
    program_b, compile_provenance_b = IntentOnlyBattleCompiler.compile(request_b, _bindings())
    sig_a = program_intent_signature(program_a)
    sig_b = program_intent_signature(program_b)
    _assert(sig_a == sig_b, "G02_LEGACY_PHYSICS_POISON_CHANGED_COMPILED_PROGRAM")
    _assert(sig_a["policy"]["intentOnlyExecutionContract"] == INTENT_CONTRACT, "G02_INTENT_CONTRACT_MARKER_MISSING")
    _assert(sig_a["policy"]["legacyPhysicsRequirementsExecutable"] is False, "G02_LEGACY_FIELDS_STILL_EXECUTABLE")
    _assert(sig_a["policy"]["storyCollisionChoreography"] is False, "G02_STORY_CHOREOGRAPHY_NOT_DISABLED")
    _assert(sig_a["policy"]["runtimeOwnsCollisionRealization"] is True, "G02_RUNTIME_COLLISION_AUTHORITY_MISSING")

    escalation = sig_a["events"][0]
    _assert(escalation["targetId"] == "actor_beta", "G02_TARGET_ACTOR_DRIFT")
    _assert(escalation["tactic"] == "RAM", "G02_TACTIC_MUST_COME_FROM_ACTOR_LEVEL_INTENT")
    _assert(escalation["speedIntent"] == "ACCELERATE", "G02_SPEED_POLICY_MUST_DERIVE_FROM_GENERIC_TACTIC")
    _assert(escalation["intentConsequences"]["damageRequired"] is True, "G02_CONSEQUENCE_GOAL_LOST")

    ignored_a = compile_provenance_a["events"]["evt-escalation"]["ignoredLegacyChoreographyPaths"]
    ignored_b = compile_provenance_b["events"]["evt-escalation"]["ignoredLegacyChoreographyPaths"]
    _assert("physicsRequirements.trajectory" in ignored_a, "G02_TRAJECTORY_NOT_QUARANTINED")
    _assert("physicsRequirements.collisionFrame" in ignored_a, "G02_COLLISION_FRAME_NOT_QUARANTINED")
    _assert(len(ignored_b) > len(ignored_a), "G02_POISON_VARIANT_NOT_DETECTED_IN_PROVENANCE")

    direct_bad = _base_request()
    direct_bad["battlePlan"]["events"][0]["collisionFrame"] = 30
    try:
        IntentOnlyBattleCompiler.compile(direct_bad, _bindings())
    except BattleRuntimeContractError as exc:
        _assert("INTENT_ONLY_DIRECT_CHOREOGRAPHY_FORBIDDEN" in str(exc), "G02_WRONG_FAIL_CLOSED_REASON")
    else:
        raise RuntimeError("G02_DIRECT_CHOREOGRAPHY_DID_NOT_FAIL_CLOSED")

    # Original inputs are immutable: compatibility/provenance survives outside
    # the executable canonical request.
    _assert(request_a["battlePlan"]["events"][0]["physicsRequirements"]["targetEnergyJ"] == 999999999, "G02_INPUT_MUTATED")

    print(json.dumps({
        "status": "PASS",
        "gate": "ISS-G02",
        "contract": INTENT_CONTRACT,
        "storyCompatibility": "PASS",
        "legacyPhysicsRequirementsExecutable": False,
        "storyCollisionChoreography": False,
        "actorOnlyPhysicalTarget": True,
        "declarativeConsequenceIntentPreserved": True,
        "runtimeOwnsCollisionRealization": True,
        "poisonedLegacyFieldsNoEffect": True,
        "directChoreographyFailsClosed": True,
        "historicalLockedCandidatesModified": False,
        "signature": sig_a,
        "provenanceSample": provenance_a,
    }, sort_keys=True))


if __name__ == "__main__":
    main()
