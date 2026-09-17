from __future__ import annotations

import copy
from dataclasses import asdict
from typing import Any

from blender.iss_battle_runtime_contract import (
    BattleCompiler,
    BattleProgram,
    BattleRuntimeContractError,
)

INTENT_CONTRACT = "ISS_INTENT_ONLY_EXECUTION_CONTRACT_V2"

# Story may carry historical/diagnostic physicsRequirements for compatibility, but
# these fields are never allowed to become runtime choreography inputs.
FORBIDDEN_CHOREOGRAPHY_KEYS = {
    "collisionframe",
    "contactframe",
    "impactframe",
    "impacttime",
    "trajectory",
    "trajectorypoints",
    "pathpoints",
    "waypoints",
    "coordinates",
    "worldcoordinates",
    "targetimpactspeedmps",
    "impactspeedmps",
    "targetenergyj",
    "impactenergyj",
    "jouletarget",
    "steeringangle",
    "brakingpoint",
    "approachvector",
    "collisionpoint",
    "contactpoint",
    "positionkeyframes",
    "velocitykeyframes",
    "forcedwinner",
    "winnerid",
}

# Generic declarative constraints are allowed because they do not prescribe how
# collision/motion is realized. Runtime physics remains authoritative.
ALLOWED_PHYSICS_CONSTRAINT_KEYS = {
    "minqualifiedcontacts",
    "mindistinctattackers",
}


def _norm_key(value: Any) -> str:
    return "".join(ch.lower() for ch in str(value or "") if ch.isalnum())


def _walk_forbidden(value: Any, path: tuple[str, ...] = ()) -> list[str]:
    hits: list[str] = []
    if isinstance(value, dict):
        for key, child in value.items():
            nk = _norm_key(key)
            next_path = path + (str(key),)
            if nk in FORBIDDEN_CHOREOGRAPHY_KEYS:
                hits.append(".".join(next_path))
            hits.extend(_walk_forbidden(child, next_path))
    elif isinstance(value, list):
        for idx, child in enumerate(value):
            hits.extend(_walk_forbidden(child, path + (str(idx),)))
    return hits


def _actor_only_target(raw: Any) -> str:
    text = str(raw or "").strip()
    if not text:
        return ""
    return text.split(":", 1)[0].strip()


def _sanitize_event(raw: dict[str, Any], event_id: str) -> tuple[dict[str, Any], dict[str, Any]]:
    event = copy.deepcopy(raw)
    provenance: dict[str, Any] = {}

    # Direct executable choreography fields are a hard contract violation. They
    # are not silently ignored because that would hide a Story→Runtime mismatch.
    direct_hits = [
        str(key)
        for key in event
        if _norm_key(key) in FORBIDDEN_CHOREOGRAPHY_KEYS
    ]
    if direct_hits:
        raise BattleRuntimeContractError(
            f"INTENT_ONLY_DIRECT_CHOREOGRAPHY_FORBIDDEN:{event_id}:{','.join(sorted(direct_hits))}"
        )

    physics = event.pop("physicsRequirements", None)
    if physics is not None:
        if not isinstance(physics, dict):
            raise BattleRuntimeContractError(
                f"INTENT_ONLY_PHYSICS_REQUIREMENTS_NOT_OBJECT:{event_id}"
            )
        provenance["legacyPhysicsRequirements"] = copy.deepcopy(physics)
        choreography_hits = _walk_forbidden(physics, ("physicsRequirements",))
        constraints: dict[str, Any] = {}
        for key, value in physics.items():
            if _norm_key(key) in ALLOWED_PHYSICS_CONSTRAINT_KEYS:
                constraints[str(key)] = copy.deepcopy(value)
        if constraints:
            # Keep only non-choreographic, generic success constraints. The
            # legacy BattleCompiler does not use these to steer motion/contact.
            event["physicsRequirements"] = constraints
        provenance["ignoredLegacyChoreographyPaths"] = sorted(set(choreography_hits))

    # R042: collision realization belongs to G04/G05 runtime. Preserve only the
    # target actor as executable battle intent. A legacy actor:zone suffix is
    # retained in provenance, never as collision choreography.
    target_raw = str(event.get("attackTarget") or "")
    target_actor = _actor_only_target(target_raw)
    if target_raw and target_raw != target_actor:
        provenance["legacyAttackTarget"] = target_raw
        event["attackTarget"] = target_actor

    # Damage may describe desired persistent consequence, but a Story-authored
    # target/contact zone must not decide collision realization. We keep the
    # consequence contract while moving the zone to non-executable provenance.
    damage = event.get("damage")
    if isinstance(damage, dict):
        for key in ("zone", "targetZone"):
            if key in damage and str(damage.get(key) or "").strip():
                provenance.setdefault("legacyDamageTarget", {})[key] = copy.deepcopy(damage[key])
                damage.pop(key, None)
        # The legacy compiler requires a zone when damage.required=true. That
        # requirement belongs to the old execution contract, so the new intent
        # compiler treats Story damage as desired consequence metadata and lets
        # G06 earn damage from actual native contact instead of scripting it.
        if bool(damage.get("required")):
            provenance["legacyDamageRequired"] = True
            damage["required"] = False

    event["intentContract"] = INTENT_CONTRACT
    return event, provenance


def sanitize_intent_request(request: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    if not isinstance(request, dict):
        raise BattleRuntimeContractError("INTENT_ONLY_REQUEST_NOT_OBJECT")
    cleaned = copy.deepcopy(request)
    plan_key = "battlePlan" if isinstance(cleaned.get("battlePlan"), dict) else "physicsPlan"
    plan = cleaned.get(plan_key)
    if not isinstance(plan, dict):
        raise BattleRuntimeContractError("INTENT_ONLY_BATTLE_PLAN_REQUIRED")
    events = plan.get("events")
    if not isinstance(events, list) or not events:
        raise BattleRuntimeContractError("INTENT_ONLY_BATTLE_EVENTS_REQUIRED")

    provenance: dict[str, Any] = {
        "contract": INTENT_CONTRACT,
        "legacyFieldsExecutable": False,
        "storyCollisionChoreography": False,
        "runtimeOwnsCollisionRealization": True,
        "events": {},
    }
    sanitized: list[dict[str, Any]] = []
    for idx, row in enumerate(events):
        if not isinstance(row, dict):
            raise BattleRuntimeContractError(f"INTENT_ONLY_EVENT_NOT_OBJECT:{idx}")
        event_id = str(row.get("eventId") or f"evt-{idx+1:03d}")
        clean_row, event_provenance = _sanitize_event(row, event_id)
        sanitized.append(clean_row)
        if event_provenance:
            provenance["events"][event_id] = event_provenance
    plan["events"] = sanitized

    execution_policy = dict(cleaned.get("executionPolicy") or {})
    execution_policy.update(
        {
            "intentOnlyExecutionContract": INTENT_CONTRACT,
            "legacyPhysicsRequirementsExecutable": False,
            "storyCollisionChoreography": False,
            "runtimeOwnsCollisionRealization": True,
        }
    )
    cleaned["executionPolicy"] = execution_policy
    return cleaned, provenance


class IntentOnlyBattleCompiler:
    """Canonical G02 compiler boundary for all post-repair successors.

    Historical G04-G08 accepted commits remain immutable. New successors compile
    Story data through this boundary before the established BattleCompiler.
    """

    @staticmethod
    def compile(
        request: dict[str, Any],
        asset_bindings: list[dict[str, Any]],
    ) -> tuple[BattleProgram, dict[str, Any]]:
        cleaned, provenance = sanitize_intent_request(request)
        program = BattleCompiler.compile(cleaned, asset_bindings)
        program.policies.update(
            {
                "intentOnlyExecutionContract": INTENT_CONTRACT,
                "legacyPhysicsRequirementsExecutable": False,
                "storyCollisionChoreography": False,
                "runtimeOwnsCollisionRealization": True,
            }
        )
        return program, provenance


def program_intent_signature(program: BattleProgram) -> dict[str, Any]:
    return {
        "contract": INTENT_CONTRACT,
        "actorIds": list(program.actor_ids),
        "objective": program.objective,
        "events": [
            {
                "eventId": event.event_id,
                "type": event.type,
                "phase": event.phase,
                "attackers": list(event.attackers),
                "targetId": event.target_id,
                "tactic": event.tactic,
                "speedIntent": event.speed_intent,
                "dependencies": list(event.dependencies),
                "requiresContact": event.requires_contact,
            }
            for event in program.events
        ],
        "scenes": [asdict(scene) for scene in program.scenes],
        "policy": {
            "intentOnlyExecutionContract": program.policies.get("intentOnlyExecutionContract"),
            "legacyPhysicsRequirementsExecutable": program.policies.get("legacyPhysicsRequirementsExecutable"),
            "storyCollisionChoreography": program.policies.get("storyCollisionChoreography"),
            "runtimeOwnsCollisionRealization": program.policies.get("runtimeOwnsCollisionRealization"),
        },
    }
