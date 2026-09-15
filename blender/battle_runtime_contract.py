"""ISS Generic Battle Runtime v1 contract compiler.

Pure-Python module: no bpy dependency. It converts Story/Battle Schema intent into
small reusable runtime commands. It deliberately contains no per-video actor names,
asset identities, coordinates, or trajectories.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence, Tuple
import math
import re

RUNTIME_CONTRACT = "iss-generic-battle-runtime-v1"
SUPPORTED_COMMANDS = {
    "HOLD", "ACCELERATE", "BRAKE", "REVERSE", "RAM", "FLANK_LEFT",
    "FLANK_RIGHT", "EVADE", "REGROUP", "PRESSURE", "SETTLE",
}


def norm(value: Any) -> str:
    return re.sub(r"[^a-z0-9]+", "_", str(value or "").lower()).strip("_")


@dataclass(frozen=True)
class TargetSpec:
    entity_id: Optional[str]
    region: Optional[str]


@dataclass(frozen=True)
class RuntimeCommand:
    event_id: str
    actor_id: str
    command: str
    start_time: float
    end_time: float
    target: TargetSpec
    speed_intent: str = ""
    trajectory_intent: str = ""
    momentum_intent: str = ""
    structural_response: str = ""
    phase: str = ""
    caused_by: Tuple[str, ...] = ()
    damage_required: bool = False
    persistent_damage: bool = False
    metadata: Mapping[str, Any] = field(default_factory=dict)


class ContractError(RuntimeError):
    pass


def parse_attack_target(value: Any) -> TargetSpec:
    raw = str(value or "").strip()
    if not raw:
        return TargetSpec(None, None)
    entity, sep, region = raw.partition(":")
    entity = entity.strip() or None
    region = norm(region) if sep and region.strip() else None
    return TargetSpec(entity, region)


def _damage_contract(event: Mapping[str, Any]) -> Tuple[bool, bool, Optional[str]]:
    damage = event.get("damage")
    if isinstance(damage, Mapping):
        return bool(damage.get("required")), bool(damage.get("persistent")), norm(damage.get("zone")) or None
    if isinstance(damage, Sequence) and not isinstance(damage, (str, bytes)):
        required = False
        persistent = False
        zone = None
        for item in damage:
            if not isinstance(item, Mapping):
                continue
            if item.get("stateChanges"):
                required = True
                persistent = True
            zone = zone or norm(item.get("zone")) or None
        return required, persistent, zone
    return False, False, None


def _infer_command(event: Mapping[str, Any], target: TargetSpec) -> str:
    etype = norm(event.get("type"))
    phase = norm(event.get("phase"))
    req = event.get("physicsRequirements") or {}
    trajectory = norm(req.get("trajectory"))
    speed = norm(req.get("speedIntent"))
    text = "_".join(x for x in (etype, phase, trajectory, speed, norm(event.get("tacticalPurpose")), norm(event.get("action"))) if x)

    if etype in {"outcome", "payoff"} or phase == "payoff" or "settle" in text:
        return "SETTLE"
    if "reverse" in text:
        return "REVERSE"
    if "brake" in text or "deceler" in text:
        return "BRAKE"
    if "evade" in text or "avoid" in text:
        return "EVADE"
    if "regroup" in text:
        return "REGROUP"
    if "flank" in text:
        # Side is allowed to come from semantic story intent; runtime still computes geometry.
        if "right" in text:
            return "FLANK_RIGHT"
        return "FLANK_LEFT"
    if "pressure" in text:
        return "PRESSURE"
    if target.entity_id:
        return "RAM"
    if speed in {"accelerate", "sustain"}:
        return "ACCELERATE"
    return "HOLD"


def _validate_event(event: Mapping[str, Any], index: int) -> None:
    event_id = str(event.get("eventId") or "").strip()
    if not event_id:
        raise ContractError(f"EVENT_ID_REQUIRED index={index}")
    try:
        start = float(event.get("startTime"))
        end = float(event.get("endTime"))
    except Exception as exc:
        raise ContractError(f"EVENT_TIME_INVALID event={event_id}") from exc
    if not math.isfinite(start) or not math.isfinite(end) or start < 0 or end <= start:
        raise ContractError(f"EVENT_TIME_RANGE_INVALID event={event_id}")
    actors = event.get("actors") or []
    if not isinstance(actors, Sequence) or isinstance(actors, (str, bytes)) or not actors:
        raise ContractError(f"EVENT_ACTORS_REQUIRED event={event_id}")


def validate_request(request: Mapping[str, Any]) -> None:
    if str(request.get("engine") or "BLENDER").upper() != "BLENDER":
        raise ContractError("ENGINE_MUST_BE_BLENDER")
    policy = request.get("executionPolicy") or {}
    required_true = (
        "continuousWorld", "persistentDamage", "persistentDebris",
    )
    for key in required_true:
        if policy.get(key) is not True:
            raise ContractError(f"EXECUTION_POLICY_REQUIRED_TRUE:{key}")
    forbidden_true = (
        "resetAllowed", "teleportAllowed", "silentSimplificationAllowed",
        "forcedTransformAfterContactAllowed", "velocityInjectionAfterContactAllowed",
    )
    for key in forbidden_true:
        if policy.get(key) is True:
            raise ContractError(f"EXECUTION_POLICY_FORBIDDEN_TRUE:{key}")

    events = (request.get("battlePlan") or {}).get("events") or []
    if not events:
        raise ContractError("BATTLE_EVENTS_REQUIRED")
    seen = set()
    for i, event in enumerate(events):
        if not isinstance(event, Mapping):
            raise ContractError(f"EVENT_NOT_OBJECT index={i}")
        _validate_event(event, i)
        eid = str(event["eventId"])
        if eid in seen:
            raise ContractError(f"EVENT_ID_DUPLICATE:{eid}")
        seen.add(eid)
        for dep in event.get("causedByEventIds") or []:
            if dep not in seen:
                raise ContractError(f"EVENT_DEPENDENCY_NOT_PRIOR event={eid} dependency={dep}")


def compile_commands(request: Mapping[str, Any], actor_ids: Iterable[str]) -> List[RuntimeCommand]:
    validate_request(request)
    actor_set = {str(x) for x in actor_ids}
    commands: List[RuntimeCommand] = []
    events = (request.get("battlePlan") or {}).get("events") or []

    for event in events:
        event_id = str(event["eventId"])
        start = float(event["startTime"])
        end = float(event["endTime"])
        target = parse_attack_target(event.get("attackTarget"))
        damage_required, persistent_damage, damage_zone = _damage_contract(event)
        if damage_zone and not target.region:
            target = TargetSpec(target.entity_id, damage_zone)
        if target.entity_id and target.entity_id not in actor_set:
            raise ContractError(f"TARGET_ACTOR_MISSING event={event_id} target={target.entity_id}")
        req = event.get("physicsRequirements") or {}
        command = _infer_command(event, target)
        if command not in SUPPORTED_COMMANDS:
            raise ContractError(f"UNSUPPORTED_COMMAND:{command}")

        event_actors = [str(a) for a in (event.get("actors") or [])]
        for actor_id in event_actors:
            if actor_id not in actor_set:
                raise ContractError(f"EVENT_ACTOR_MISSING event={event_id} actor={actor_id}")
            # Target actors listed in a multi-actor event should not attack themselves.
            if target.entity_id and actor_id == target.entity_id:
                continue
            commands.append(RuntimeCommand(
                event_id=event_id,
                actor_id=actor_id,
                command=command,
                start_time=start,
                end_time=end,
                target=target,
                speed_intent=norm(req.get("speedIntent")),
                trajectory_intent=norm(req.get("trajectory")),
                momentum_intent=norm(req.get("momentumIntent")),
                structural_response=norm(req.get("structuralResponse")),
                phase=norm(event.get("phase")),
                caused_by=tuple(str(x) for x in (event.get("causedByEventIds") or [])),
                damage_required=damage_required,
                persistent_damage=persistent_damage,
                metadata={
                    "eventType": str(event.get("type") or ""),
                    "requiredOutcome": str(event.get("requiredOutcome") or ""),
                    "tacticalPurpose": str(event.get("tacticalPurpose") or ""),
                },
            ))

    # Deterministic order; concurrent actors keep the same event time and are executed together.
    commands.sort(key=lambda c: (c.start_time, c.end_time, c.event_id, c.actor_id))
    return commands


def compiler_selftest() -> Dict[str, Any]:
    req = {
        "engine": "BLENDER",
        "executionPolicy": {
            "continuousWorld": True,
            "persistentDamage": True,
            "persistentDebris": True,
            "resetAllowed": False,
            "teleportAllowed": False,
            "silentSimplificationAllowed": False,
            "forcedTransformAfterContactAllowed": False,
            "velocityInjectionAfterContactAllowed": False,
        },
        "battlePlan": {"events": [
            {"eventId": "e1", "type": "BATTLE_HOOK", "phase": "HOOK", "startTime": 0, "endTime": 1,
             "actors": ["alpha", "beta"], "attackTarget": "", "causedByEventIds": [],
             "physicsRequirements": {"speedIntent": "hold"}},
            {"eventId": "e2", "type": "COORDINATED_ATTACK", "phase": "FIRST_ATTACK", "startTime": 1, "endTime": 4,
             "actors": ["alpha"], "attackTarget": "beta:front", "causedByEventIds": ["e1"],
             "damage": {"required": True, "persistent": True, "zone": "front"},
             "physicsRequirements": {"speedIntent": "accelerate", "trajectory": "direct approach"}},
            {"eventId": "e3", "type": "OUTCOME", "phase": "PAYOFF", "startTime": 4, "endTime": 5,
             "actors": ["alpha", "beta"], "attackTarget": "", "causedByEventIds": ["e2"],
             "physicsRequirements": {"speedIntent": "settle"}},
        ]},
    }
    cmds = compile_commands(req, ["alpha", "beta"])
    assert any(c.command == "RAM" and c.target.entity_id == "beta" and c.target.region == "front" for c in cmds)
    assert any(c.command == "SETTLE" for c in cmds)
    assert all("bugatti" not in repr(c).lower() and "bulldozer" not in repr(c).lower() for c in cmds)
    return {"contract": RUNTIME_CONTRACT, "commands": len(cmds), "status": "PASS"}


if __name__ == "__main__":
    print(compiler_selftest())
