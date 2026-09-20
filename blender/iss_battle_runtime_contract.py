from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Iterable
import hashlib
import math
import re


RUNTIME_CONTRACT = "ISS_GENERIC_BATTLE_RUNTIME_V1"
DEFAULT_FPS = 30


class BattleRuntimeContractError(RuntimeError):
    pass


def norm(value: Any) -> str:
    return re.sub(r"[^a-z0-9]+", "_", str(value or "").lower()).strip("_")


def clamp(value: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, float(value)))


def stable_unit(key: str) -> float:
    digest = hashlib.sha256(key.encode("utf-8")).digest()
    return int.from_bytes(digest[:8], "big") / float((1 << 64) - 1)


def parse_attack_target(raw: Any) -> tuple[str | None, str | None]:
    text = str(raw or "").strip()
    if not text or norm(text) in {"none", "no_target", "n_a"}:
        return None, None
    if ":" in text:
        entity, zone = text.split(":", 1)
        entity = entity.strip()
        zone = norm(zone)
        return (entity or None), (zone or None)
    return text, None


TACTIC_ALIASES = {
    "flank": "FLANK",
    "flanking": "FLANK",
    "surround": "SURROUND",
    "encircle": "SURROUND",
    "ram": "RAM",
    "direct": "RAM",
    "converg": "RAM",
    "counter": "COUNTER",
    "reverse": "REVERSE",
    "retreat": "REVERSE",
    "evade": "EVADE",
    "avoid": "EVADE",
    "regroup": "REGROUP",
    "hold": "HOLD",
    "settle": "SETTLE",
}


def infer_tactic(event: dict[str, Any]) -> str:
    probes = [
        event.get("type"),
        event.get("phase"),
        event.get("action"),
        event.get("tacticalPurpose"),
        (event.get("physicsRequirements") or {}).get("trajectory"),
        (event.get("physicsRequirements") or {}).get("speedIntent"),
    ]
    joined = norm(" ".join(str(x or "") for x in probes))
    for token, tactic in TACTIC_ALIASES.items():
        if token in joined:
            return tactic
    target_id, _ = parse_attack_target(event.get("attackTarget"))
    return "RAM" if target_id else "HOLD"


def infer_speed_intent(event: dict[str, Any]) -> str:
    req = event.get("physicsRequirements") or {}
    speed = norm(req.get("speedIntent"))
    if speed in {"accelerate", "sustain", "hold", "settle", "reverse", "brake", "stop"}:
        return speed.upper()
    tactic = infer_tactic(event)
    if tactic in {"RAM", "FLANK", "SURROUND", "COUNTER"}:
        return "ACCELERATE"
    if tactic == "REVERSE":
        return "REVERSE"
    if tactic == "SETTLE":
        return "SETTLE"
    return "HOLD"


@dataclass(slots=True)
class ActorProfile:
    entity_id: str
    mass_kg: float
    locomotion_model: str = "GROUND_DIFFERENTIAL"
    semantic_labels: tuple[str, ...] = ()
    friction: float = 1.0
    restitution: float = 0.03
    max_speed_mps: float = 18.0
    max_reverse_mps: float = 5.0
    max_yaw_rate_rad_s: float = 1.25
    acceleration_mps2: float = 7.0
    braking_mps2: float = 10.0
    toughness_j_per_kg: float = 90.0
    profile_source: str = "BINDING_OR_GEOMETRY"

    @staticmethod
    def from_binding(binding: dict[str, Any], semantic_labels: Iterable[str] = ()) -> "ActorProfile":
        entity = str(binding.get("entityId") or "").strip()
        if not entity:
            raise BattleRuntimeContractError("ACTOR_PROFILE_ENTITY_ID_EMPTY")
        mass = binding.get("totalMassKg")
        if mass is None:
            mass = binding.get("massKg")
        if mass is None:
            runtime_profile = binding.get("runtimeProfile") or {}
            mass = runtime_profile.get("massKg")
        if mass is None:
            raise BattleRuntimeContractError(f"ACTOR_MASS_REQUIRED:{entity}")
        mass = float(mass)
        if not math.isfinite(mass) or mass <= 1.0:
            raise BattleRuntimeContractError(f"ACTOR_MASS_INVALID:{entity}:{mass}")

        rp = binding.get("runtimeProfile") or {}
        loco = norm(rp.get("locomotionModel") or binding.get("locomotionModel") or "ground_differential").upper()
        labels = tuple(sorted({norm(x) for x in semantic_labels if norm(x)}))
        max_speed = float(rp.get("maxSpeedMps") or (6.5 if mass >= 8000 else 20.0))
        max_reverse = float(rp.get("maxReverseMps") or (3.5 if mass >= 8000 else 6.0))
        accel = float(rp.get("accelerationMps2") or (2.8 if mass >= 8000 else 7.0))
        brake = float(rp.get("brakingMps2") or (4.0 if mass >= 8000 else 10.0))
        yaw = float(rp.get("maxYawRateRadS") or (0.55 if mass >= 8000 else 1.35))
        toughness = float(rp.get("toughnessJPerKg") or (180.0 if mass >= 8000 else 85.0))
        return ActorProfile(
            entity_id=entity,
            mass_kg=mass,
            locomotion_model=loco,
            semantic_labels=labels,
            friction=clamp(float(rp.get("friction", 1.0)), 0.05, 3.0),
            restitution=clamp(float(rp.get("restitution", 0.03)), 0.0, 0.6),
            max_speed_mps=clamp(max_speed, 1.0, 70.0),
            max_reverse_mps=clamp(max_reverse, 0.5, 20.0),
            max_yaw_rate_rad_s=clamp(yaw, 0.1, 3.5),
            acceleration_mps2=clamp(accel, 0.2, 25.0),
            braking_mps2=clamp(brake, 0.5, 35.0),
            toughness_j_per_kg=clamp(toughness, 20.0, 1000.0),
        )


@dataclass(slots=True)
class ActorState:
    entity_id: str
    structural_integrity: float = 1.0
    drive_efficiency: float = 1.0
    zone_integrity: dict[str, float] = field(default_factory=dict)
    disabled: bool = False
    damage_events: list[dict[str, Any]] = field(default_factory=list)
    last_impact_frame: int | None = None

    def integrity_for(self, zone: str | None) -> float:
        if not zone:
            return self.structural_integrity
        return self.zone_integrity.get(norm(zone), 1.0)


@dataclass(slots=True)
class RuntimeEvent:
    event_id: str
    type: str
    phase: str
    start_frame: int
    end_frame: int
    attackers: tuple[str, ...]
    target_id: str | None
    target_zone: str | None
    tactic: str
    speed_intent: str
    damage_required: bool
    persistent_damage: bool
    dependencies: tuple[str, ...]
    required_outcome: str
    original: dict[str, Any]

    @property
    def requires_contact(self) -> bool:
        return self.target_id is not None and bool(self.attackers)


@dataclass(slots=True)
class RuntimeScene:
    scene_number: int
    start_frame: int
    end_frame: int
    event_ids: tuple[str, ...]
    camera_intent: str


@dataclass(slots=True)
class BattleProgram:
    fps: int
    duration_seconds: float
    total_frames: int
    events: tuple[RuntimeEvent, ...]
    scenes: tuple[RuntimeScene, ...]
    policies: dict[str, Any]
    actor_ids: tuple[str, ...]
    objective: str
    final_outcome: str


@dataclass(slots=True)
class ImpactEvidence:
    frame: int
    attacker_id: str
    target_id: str
    target_zone: str | None
    relative_speed_mps: float
    normal_closing_speed_mps: float
    reduced_mass_kg: float
    impact_energy_j: float
    target_specific_energy_j_per_kg: float
    severity: float
    contact_point: tuple[float, float, float]
    contact_normal: tuple[float, float, float]
    response_delta_attacker_mps: float
    response_delta_target_mps: float
    detector: str = "SOLVER_CORRELATED_OBB_CONTACT"


@dataclass(slots=True)
class EventState:
    event_id: str
    status: str = "PENDING"
    attempts: int = 0
    contact_count: int = 0
    damage_count: int = 0
    first_active_frame: int | None = None
    completed_frame: int | None = None
    last_replan_frame: int | None = None
    evidence: list[ImpactEvidence] = field(default_factory=list)


class BattleCompiler:
    @staticmethod
    def compile(request: dict[str, Any], asset_bindings: list[dict[str, Any]]) -> BattleProgram:
        if not isinstance(request, dict):
            raise BattleRuntimeContractError("REQUEST_NOT_OBJECT")
        policy = dict(request.get("executionPolicy") or {})
        if policy.get("continuousWorld") is not True:
            raise BattleRuntimeContractError("CONTINUOUS_WORLD_REQUIRED")
        for forbidden, marker in (
            ("resetAllowed", "RESET_MUST_BE_FALSE"),
            ("teleportAllowed", "TELEPORT_MUST_BE_FALSE"),
            ("silentSimplificationAllowed", "SILENT_SIMPLIFICATION_MUST_BE_FALSE"),
            ("forcedTransformAfterContactAllowed", "FORCED_TRANSFORM_AFTER_CONTACT_MUST_BE_FALSE"),
            ("velocityInjectionAfterContactAllowed", "VELOCITY_INJECTION_AFTER_CONTACT_MUST_BE_FALSE"),
        ):
            if policy.get(forbidden) is True:
                raise BattleRuntimeContractError(marker)

        fps = int(request.get("renderSpec", {}).get("fps") or request.get("physicsFps") or DEFAULT_FPS)
        fps = max(24, min(60, fps))
        duration = float(request.get("durationSeconds") or 0)
        scenes_in = request.get("scenes") or []
        if duration <= 0 and scenes_in:
            duration = max(float(s.get("endSecond", 0)) for s in scenes_in)
        if duration <= 0:
            raise BattleRuntimeContractError("DURATION_REQUIRED")
        total_frames = max(2, int(round(duration * fps)))

        actor_ids = tuple(str(b.get("entityId") or "").strip() for b in asset_bindings)
        if not actor_ids or any(not x for x in actor_ids):
            raise BattleRuntimeContractError("ASSET_BINDING_ENTITY_INVALID")
        if len(set(actor_ids)) != len(actor_ids):
            raise BattleRuntimeContractError("ASSET_BINDING_ENTITY_DUPLICATE")
        actor_set = set(actor_ids)

        plan = request.get("battlePlan") or request.get("physicsPlan") or {}
        raw_events = plan.get("events") or []
        if not raw_events:
            raise BattleRuntimeContractError("BATTLE_EVENTS_EMPTY")

        events: list[RuntimeEvent] = []
        seen: set[str] = set()
        for idx, raw in enumerate(raw_events):
            event_id = str(raw.get("eventId") or f"evt-{idx+1:03d}").strip()
            if event_id in seen:
                raise BattleRuntimeContractError(f"EVENT_ID_DUPLICATE:{event_id}")
            seen.add(event_id)
            target_id, zone_from_target = parse_attack_target(raw.get("attackTarget"))
            damage_raw = raw.get("damage") or {}
            if isinstance(damage_raw, dict):
                damage = dict(damage_raw)
            elif isinstance(damage_raw, list):
                rows = [x for x in damage_raw if isinstance(x, dict)]
                target_rows = [x for x in rows if target_id and str(x.get("entityId") or "") == target_id]
                chosen = (target_rows or rows or [{}])[0]
                damage = {
                    "zone": chosen.get("zone") or chosen.get("targetZone"),
                    "required": bool(chosen.get("required", bool(chosen.get("stateChanges")))),
                    "persistent": bool(chosen.get("persistent", True)),
                    "stateChanges": list(chosen.get("stateChanges") or []),
                }
            else:
                raise BattleRuntimeContractError(f"EVENT_DAMAGE_CONTRACT_INVALID:{event_id}")
            req = raw.get("physicsRequirements") or {}
            target_zone = zone_from_target or norm(damage.get("zone")) or norm(req.get("targetArea")) or None
            if target_zone in {"none", ""}:
                target_zone = None

            raw_actors = tuple(str(x).strip() for x in (raw.get("actors") or []) if str(x).strip())
            for actor in raw_actors:
                if actor not in actor_set:
                    raise BattleRuntimeContractError(f"EVENT_ACTOR_WITHOUT_ASSET:{event_id}:{actor}")
            if target_id and target_id not in actor_set:
                raise BattleRuntimeContractError(f"EVENT_TARGET_WITHOUT_ASSET:{event_id}:{target_id}")
            attackers = tuple(a for a in raw_actors if a != target_id)
            if target_id and not attackers:
                raise BattleRuntimeContractError(f"EVENT_ATTACKERS_EMPTY:{event_id}")
            damage_required = bool(damage.get("required"))
            if damage_required and (not target_id or not target_zone):
                raise BattleRuntimeContractError(f"DAMAGE_TARGET_ZONE_REQUIRED:{event_id}")

            start_s = max(0.0, float(raw.get("startTime", 0.0)))
            end_s = min(duration, float(raw.get("endTime", duration)))
            if end_s <= start_s:
                raise BattleRuntimeContractError(f"EVENT_TIME_INVALID:{event_id}")
            start_f = max(1, int(math.floor(start_s * fps)) + 1)
            end_f = min(total_frames, max(start_f, int(math.ceil(end_s * fps))))
            deps = tuple(str(x) for x in (raw.get("causedByEventIds") or []) if str(x))
            events.append(RuntimeEvent(
                event_id=event_id,
                type=norm(raw.get("type")).upper() or "EVENT",
                phase=norm(raw.get("phase")).upper() or "UNSPECIFIED",
                start_frame=start_f,
                end_frame=end_f,
                attackers=attackers,
                target_id=target_id,
                target_zone=target_zone,
                tactic=infer_tactic(raw),
                speed_intent=infer_speed_intent(raw),
                damage_required=damage_required,
                persistent_damage=bool(damage.get("persistent", damage_required)),
                dependencies=deps,
                required_outcome=str(raw.get("requiredOutcome") or ""),
                original=dict(raw),
            ))

        ids = {e.event_id for e in events}
        for e in events:
            missing = [d for d in e.dependencies if d not in ids]
            if missing:
                raise BattleRuntimeContractError(f"EVENT_DEPENDENCY_MISSING:{e.event_id}:{','.join(missing)}")
        BattleCompiler._assert_acyclic(events)

        scenes: list[RuntimeScene] = []
        for idx, raw in enumerate(scenes_in):
            num = int(raw.get("sceneNumber") or idx + 1)
            start_s = max(0.0, float(raw.get("startSecond", idx * 5)))
            end_s = min(duration, float(raw.get("endSecond", min(duration, (idx + 1) * 5))))
            if end_s <= start_s:
                raise BattleRuntimeContractError(f"SCENE_TIME_INVALID:{num}")
            scenes.append(RuntimeScene(
                scene_number=num,
                start_frame=max(1, int(math.floor(start_s * fps)) + 1),
                end_frame=min(total_frames, max(1, int(math.ceil(end_s * fps)))),
                event_ids=tuple(str(x) for x in (raw.get("eventIds") or []) if str(x)),
                camera_intent=str(raw.get("cameraIntent") or ""),
            ))
        if not scenes:
            scenes.append(RuntimeScene(1, 1, total_frames, tuple(e.event_id for e in events), "continuous battle"))
        scenes = sorted(scenes, key=lambda x: (x.start_frame, x.scene_number))
        if scenes[0].start_frame != 1 or scenes[-1].end_frame != total_frames:
            raise BattleRuntimeContractError("SCENE_TIMELINE_MUST_COVER_FULL_DURATION")
        cursor = 1
        for scene in scenes:
            if scene.start_frame > cursor:
                raise BattleRuntimeContractError(f"SCENE_TIMELINE_GAP:{cursor}:{scene.start_frame}")
            cursor = max(cursor, scene.end_frame + 1)

        return BattleProgram(
            fps=fps,
            duration_seconds=duration,
            total_frames=total_frames,
            events=tuple(events),
            scenes=tuple(scenes),
            policies=policy,
            actor_ids=actor_ids,
            objective=str(plan.get("objective") or ""),
            final_outcome=str(plan.get("finalOutcome") or ""),
        )

    @staticmethod
    def _assert_acyclic(events: list[RuntimeEvent]) -> None:
        graph = {e.event_id: set(e.dependencies) for e in events}
        visiting: set[str] = set()
        visited: set[str] = set()

        def visit(node: str) -> None:
            if node in visited:
                return
            if node in visiting:
                raise BattleRuntimeContractError(f"EVENT_DEPENDENCY_CYCLE:{node}")
            visiting.add(node)
            for dep in graph[node]:
                visit(dep)
            visiting.remove(node)
            visited.add(node)

        for node in graph:
            visit(node)
