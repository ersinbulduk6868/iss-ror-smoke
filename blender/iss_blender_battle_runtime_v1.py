from __future__ import annotations

import argparse
import hashlib
import json
import math
import sys
from dataclasses import asdict
from pathlib import Path
from typing import Any

import bpy
from mathutils import Vector

from blender.iss_battle_runtime_core import (
    ActorProfile,
    BattleCompiler,
    DamageAccumulator,
    EventState,
    ImpactEvidence,
    ImpactModel,
    OutcomeResolver,
    RuntimeEvent,
    SpawnPlanner,
    WaveScheduler,
    clamp,
    norm,
)
from blender.iss_battle_runtime_assets import (
    AssetPrototypeCache,
    BlenderBattleRuntimeError,
    add_passive_rigid_body,
    cube,
    marker,
)
from blender.iss_battle_runtime_camera import CameraDirector, CAMERA_MODEL
from blender.iss_battle_runtime_consequences import (
    ConsequenceEngine,
    CONSEQUENCE_MODEL,
    DEBRIS_REPRESENTATION,
)
from blender.iss_battle_runtime_physics import (
    CONTROL_MODEL,
    PendingContact,
    RuntimeActor,
    active_event_for_actor,
    choose_initial_yaw,
    create_runtime_actor,
    drive_command,
    event_dependency_ready,
    event_target_point,
    obb_overlap_2d,
)

RUNTIME_VERSION = "ISS_GENERIC_BATTLE_RUNTIME_V1_CANDIDATE_1"
CONTACT_MODEL = "SOLVER_CORRELATED_OBB_RESPONSE_V1"


def _argv() -> list[str]:
    if "--" in sys.argv:
        return sys.argv[sys.argv.index("--") + 1 :]
    return []


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--request", required=True)
    parser.add_argument("--asset-map", required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--render-previews", action="store_true")
    parser.add_argument("--save-blend", action="store_true")
    return parser.parse_args(_argv())


def load_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _asset_map_entry(asset_map: dict[str, Any], binding: dict[str, Any]) -> tuple[Path, str | None]:
    keys = [
        str(binding.get("entityId") or ""),
        str(binding.get("sourceUid") or ""),
        str(binding.get("readyAssetId") or ""),
        str(binding.get("assetId") or ""),
    ]
    entry: Any = None
    for key in keys:
        if key and key in asset_map:
            entry = asset_map[key]
            break
    if entry is None:
        direct = binding.get("localPath") or binding.get("downloadedPath")
        if direct:
            entry = str(direct)
    if entry is None:
        raise BlenderBattleRuntimeError(
            f"LOCAL_ASSET_PATH_REQUIRED:{binding.get('entityId')}"
        )

    if isinstance(entry, str):
        return Path(entry), None
    if isinstance(entry, dict):
        raw = entry.get("path") or entry.get("localPath")
        if not raw:
            raise BlenderBattleRuntimeError(
                f"ASSET_MAP_PATH_REQUIRED:{binding.get('entityId')}"
            )
        explicit_sha = str(entry.get("sha256") or "").lower() or None
        return Path(str(raw)), explicit_sha
    raise BlenderBattleRuntimeError(
        f"ASSET_MAP_ENTRY_INVALID:{binding.get('entityId')}"
    )


def _expected_identity_hash(
    binding: dict[str, Any],
    path: Path,
    explicit_sha: str | None,
) -> str:
    if explicit_sha:
        return explicit_sha
    suffix = path.suffix.lower()
    if suffix in {".glb", ".gltf"}:
        candidates = (
            binding.get("runtimeAssetSha256"),
            binding.get("downloadedSha256"),
            binding.get("sourceSha256"),
        )
    else:
        candidates = (
            binding.get("runtimeAssetSha256"),
            binding.get("downloadedSha256"),
            binding.get("readySha256"),
            binding.get("dynamicMasterSha256"),
        )
    for value in candidates:
        text = str(value or "").lower().strip()
        if len(text) == 64:
            return text
    raise BlenderBattleRuntimeError(
        f"ASSET_IDENTITY_SHA_REQUIRED:{binding.get('entityId')}:{suffix}"
    )


def resolve_asset(
    asset_map: dict[str, Any],
    binding: dict[str, Any],
) -> tuple[Path, str]:
    path, explicit_sha = _asset_map_entry(asset_map, binding)
    path = path.expanduser().resolve()
    if not path.is_file():
        raise BlenderBattleRuntimeError(
            f"LOCAL_ASSET_FILE_MISSING:{binding.get('entityId')}:{path}"
        )
    actual = sha256_file(path)
    expected = _expected_identity_hash(binding, path, explicit_sha)
    if actual.lower() != expected.lower():
        raise BlenderBattleRuntimeError(
            f"ASSET_IDENTITY_SHA_MISMATCH:{binding.get('entityId')}:{actual}:{expected}"
        )
    binding["downloadedSha256"] = actual
    marker(
        "ASSET_IDENTITY_VERIFIED",
        entityId=binding.get("entityId"),
        path=str(path),
        sha256=actual,
    )
    return path, actual


def reset_scene() -> None:
    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.object.delete(use_global=False)
    scene = bpy.context.scene
    scene.frame_start = 1
    scene.frame_end = 2


def setup_world(request: dict[str, Any], program: Any) -> None:
    scene = bpy.context.scene
    scene.frame_start = 1
    scene.frame_end = int(program.total_frames)
    scene.render.fps = int(program.fps)
    render = request.get("renderSpec") or {}
    resolution = render.get("resolution") or {}
    scene.render.resolution_x = int(resolution.get("width") or 720)
    scene.render.resolution_y = int(resolution.get("height") or 1280)
    scene.render.resolution_percentage = 100
    scene.render.engine = "BLENDER_EEVEE_NEXT"
    scene.render.image_settings.file_format = "PNG"
    scene.world.color = (0.035, 0.035, 0.045)

    if scene.rigidbody_world is None:
        bpy.ops.rigidbody.world_add()
    world = scene.rigidbody_world
    physics_fps = int(request.get("physicsFps") or max(120, program.fps))
    world.substeps_per_frame = max(1, min(20, int(math.ceil(physics_fps / program.fps))))
    world.solver_iterations = 30
    world.point_cache.frame_start = 1
    world.point_cache.frame_end = int(program.total_frames)


def setup_lighting() -> None:
    bpy.ops.object.light_add(type="SUN", location=(0.0, 0.0, 12.0))
    sun = bpy.context.object
    sun.name = "ISS_RUNTIME_SUN"
    sun.data.energy = 2.2
    sun.rotation_euler = (math.radians(35), math.radians(-18), math.radians(28))

    bpy.ops.object.light_add(type="AREA", location=(4.0, -5.0, 10.0))
    area = bpy.context.object
    area.name = "ISS_RUNTIME_FILL"
    area.data.energy = 1100.0
    area.data.shape = "DISK"
    area.data.size = 8.0


def create_ground(
    spawn: dict[str, tuple[float, float, float]],
    actors: dict[str, RuntimeActor],
) -> bpy.types.Object:
    extent = 18.0
    for entity, pos in spawn.items():
        actor = actors[entity]
        radial = math.hypot(float(pos[0]), float(pos[1]))
        extent = max(
            extent,
            radial
            + max(float(actor.dimensions.x), float(actor.dimensions.y)) * 3.0
            + 8.0,
        )
    ground = cube(
        "ISS_RUNTIME_GROUND",
        (0.0, 0.0, -0.5),
        (extent * 2.0, extent * 2.0, 1.0),
    )
    add_passive_rigid_body(ground, shape="BOX", friction=1.15)
    return ground


def reconcile_total_mass(actor: RuntimeActor) -> dict[str, float]:
    wheels = list(actor.rig.wheels_left) + list(actor.rig.wheels_right)
    wheel_mass = sum(float(w.rigid_body.mass) for w in wheels)
    total = float(actor.profile.mass_kg)
    if wheel_mass <= 0.0 or wheel_mass >= total * 0.35:
        raise BlenderBattleRuntimeError(
            f"DRIVE_WHEEL_MASS_BUDGET_INVALID:{actor.profile.entity_id}:{wheel_mass}:{total}"
        )
    chassis_mass = total - wheel_mass
    actor.chassis.rigid_body.mass = chassis_mass
    measured = chassis_mass + wheel_mass
    error = abs(measured - total)
    if error > max(1e-5, total * 1e-9):
        raise BlenderBattleRuntimeError(
            f"ACTOR_TOTAL_MASS_RECONCILIATION_FAILED:{actor.profile.entity_id}:{measured}:{total}"
        )
    return {
        "declaredMassKg": total,
        "chassisMassKg": chassis_mass,
        "wheelMassKg": wheel_mass,
        "reconciledMassKg": measured,
    }


def sample_actor(actor: RuntimeActor, frame: int, fps: int) -> None:
    pos = actor.chassis.matrix_world.translation.copy()
    quat = actor.chassis.matrix_world.to_quaternion().copy()
    actor.motion[frame] = (pos, quat)
    if frame <= 1 or frame - 1 not in actor.motion:
        velocity = Vector((0.0, 0.0, 0.0))
    else:
        prev = actor.motion[frame - 1][0]
        velocity = (pos - prev) * float(fps)
    actor.velocity[frame] = velocity


def _surface_point(actor: RuntimeActor, toward_world: Vector) -> Vector:
    direction = toward_world.copy()
    if direction.length < 1e-7:
        return actor.chassis.matrix_world.translation.copy()
    direction.normalize()
    local = actor.chassis.matrix_world.to_quaternion().inverted() @ direction
    half = actor.chassis.dimensions * 0.5
    extent = (
        abs(local.x) * float(half.x)
        + abs(local.y) * float(half.y)
        + abs(local.z) * float(half.z)
    )
    return actor.chassis.matrix_world.translation + direction * extent


def _semantic_tolerance(actor: RuntimeActor, zone: str | None) -> float:
    dims = actor.dimensions
    base = max(
        0.45,
        min(float(dims.x), float(dims.y)) * 0.34
        + float(dims.z) * 0.24,
    )
    if norm(zone) in {
        "front",
        "rear",
        "body",
        "chassis",
        "blade",
        "left_side",
        "right_side",
    }:
        base *= 1.20
    return base


def _reactive_avoidance(
    actor: RuntimeActor,
    desired: Vector,
    actors: dict[str, RuntimeActor],
    target_id: str | None,
) -> Vector:
    pos = actor.chassis.matrix_world.translation
    repulsion = Vector((0.0, 0.0, 0.0))
    own_radius = max(float(actor.dimensions.x), float(actor.dimensions.y)) * 0.48
    for other_id, other in actors.items():
        if other_id == actor.profile.entity_id or other_id == target_id:
            continue
        delta = pos - other.chassis.matrix_world.translation
        delta.z = 0.0
        distance = delta.length
        other_radius = max(float(other.dimensions.x), float(other.dimensions.y)) * 0.48
        safe = max(1.2, own_radius + other_radius)
        influence = safe * 2.3
        if distance < 1e-5 or distance >= influence:
            continue
        delta.normalize()
        weight = (influence - distance) / influence
        repulsion += delta * safe * weight * weight
    if repulsion.length > 0.0:
        desired = desired + repulsion
    return desired


def resolve_target_point(
    actor: RuntimeActor,
    event: RuntimeEvent,
    actors: dict[str, RuntimeActor],
    frame: int,
    state: EventState,
) -> Vector | None:
    pos = actor.chassis.matrix_world.translation
    forward = actor.chassis.matrix_world.to_quaternion() @ Vector((1.0, 0.0, 0.0))

    if event.target_id:
        target = actors[event.target_id]
        active = WaveScheduler.active_attackers(event, frame)
        index = active.index(actor.profile.entity_id) if actor.profile.entity_id in active else 0
        desired = event_target_point(
            event,
            actor,
            target,
            index,
            max(1, len(active)),
            frame,
            state,
        )
        return _reactive_avoidance(actor, desired, actors, event.target_id)

    if event.tactic == "EVADE":
        nearest: RuntimeActor | None = None
        nearest_distance = float("inf")
        for other_id, other in actors.items():
            if other_id == actor.profile.entity_id:
                continue
            distance = (pos - other.chassis.matrix_world.translation).length
            if distance < nearest_distance:
                nearest = other
                nearest_distance = distance
        if nearest is not None:
            away = pos - nearest.chassis.matrix_world.translation
            away.z = 0.0
            if away.length > 1e-5:
                away.normalize()
                return pos + away * max(6.0, float(actor.dimensions.x) * 2.0)

    if event.tactic == "REGROUP":
        peers = [
            actors[x].chassis.matrix_world.translation
            for x in event.attackers
            if x in actors and x != actor.profile.entity_id
        ]
        if peers:
            center = sum(peers, Vector((0.0, 0.0, 0.0))) / len(peers)
            return _reactive_avoidance(actor, center, actors, None)

    return pos + forward * max(4.0, float(actor.dimensions.x) * 1.6)


def dominant_event(
    frame: int,
    program: Any,
    states: dict[str, EventState],
) -> RuntimeEvent | None:
    priorities = {
        "CLIMAX": 0,
        "SPECIAL_ATTACK": 1,
        "COUNTERATTACK": 2,
        "FIRST_ATTACK": 3,
        "ESCALATION": 4,
        "HOOK": 5,
        "PAYOFF": 6,
    }
    rows: list[RuntimeEvent] = []
    for event in program.events:
        state = states[event.event_id]
        grace = program.fps if event.requires_contact else 0
        if (
            event.start_frame <= frame <= min(program.total_frames, event.end_frame + grace)
            and state.status not in {"SUCCEEDED", "SETTLED", "FAILED", "FAILED_DEPENDENCY"}
            and event_dependency_ready(event, states)
        ):
            rows.append(event)
    if not rows:
        return None
    rows.sort(
        key=lambda e: (
            priorities.get(e.phase, 50),
            e.end_frame,
            e.start_frame,
            e.event_id,
        )
    )
    return rows[0]


def set_controls(
    frame: int,
    program: Any,
    actors: dict[str, RuntimeActor],
    states: dict[str, EventState],
    control_samples: list[dict[str, Any]],
) -> None:
    for entity, actor in actors.items():
        event = active_event_for_actor(entity, frame, program, states)
        if event is None:
            actor.rig.brake()
            continue

        wave = WaveScheduler.active_attackers(event, frame)
        if entity not in wave:
            actor.rig.brake()
            continue

        state = states[event.event_id]
        target_point = resolve_target_point(actor, event, actors, frame, state)
        current_velocity = actor.velocity.get(frame, Vector((0.0, 0.0, 0.0)))
        left, right, telemetry = drive_command(
            actor,
            event,
            target_point,
            current_velocity,
        )
        actor.rig.command(
            left,
            right,
            impulse_scale=max(0.12, actor.state.drive_efficiency),
        )

        if frame == event.start_frame or frame % max(1, program.fps // 2) == 0:
            control_samples.append(
                {
                    "frame": frame,
                    "eventId": event.event_id,
                    "actorId": entity,
                    "tactic": event.tactic,
                    "leftMps": left,
                    "rightMps": right,
                    "driveEfficiency": actor.state.drive_efficiency,
                    "telemetry": telemetry,
                }
            )


def _pending_key(pending: PendingContact) -> tuple[str, str, str]:
    return pending.event_id, pending.attacker_id, pending.target_id


def detect_contacts(
    frame: int,
    program: Any,
    actors: dict[str, RuntimeActor],
    states: dict[str, EventState],
    pending: list[PendingContact],
    cooldown: dict[tuple[str, str, str], int],
) -> None:
    pending_keys = {_pending_key(p) for p in pending}
    for event in program.events:
        state = states[event.event_id]
        if not event.requires_contact or state.status in {
            "SUCCEEDED",
            "FAILED",
            "FAILED_DEPENDENCY",
        }:
            continue
        if not event_dependency_ready(event, states):
            continue
        grace = program.fps if program.policies.get("replanOnPhysicalImpossibility", True) else 0
        if not (event.start_frame <= frame <= min(program.total_frames, event.end_frame + grace)):
            continue

        target = actors[event.target_id]
        for attacker_id in WaveScheduler.active_attackers(event, frame):
            if attacker_id not in actors:
                continue
            attacker = actors[attacker_id]
            if attacker.state.disabled:
                continue
            key = (event.event_id, attacker_id, event.target_id)
            if key in pending_keys or cooldown.get(key, 0) > frame:
                continue
            if not obb_overlap_2d(attacker, target):
                continue

            delta = target.chassis.matrix_world.translation - attacker.chassis.matrix_world.translation
            delta.z = 0.0
            if delta.length < 1e-7:
                continue
            normal = delta.normalized()
            contact_point = _surface_point(target, -normal)
            zone_point = target.zone_world(event.target_zone)
            semantic_distance = (contact_point - zone_point).length
            tolerance = _semantic_tolerance(target, event.target_zone)
            if semantic_distance > tolerance:
                cooldown[key] = frame + max(2, program.fps // 8)
                marker(
                    "SEMANTIC_CONTACT_MISS",
                    frame=frame,
                    eventId=event.event_id,
                    attackerId=attacker_id,
                    targetId=event.target_id,
                    targetZone=event.target_zone,
                    semanticDistance=round(float(semantic_distance), 6),
                    tolerance=round(float(tolerance), 6),
                )
                continue

            pending.append(
                PendingContact(
                    event_id=event.event_id,
                    attacker_id=attacker_id,
                    target_id=event.target_id,
                    target_zone=event.target_zone,
                    frame=frame,
                    resolve_frame=min(program.total_frames, frame + 2),
                    pre_attacker_velocity=attacker.velocity.get(frame, Vector()).copy(),
                    pre_target_velocity=target.velocity.get(frame, Vector()).copy(),
                    contact_point=contact_point.copy(),
                    contact_normal=normal.copy(),
                    semantic_distance=float(semantic_distance),
                )
            )
            cooldown[key] = frame + max(3, program.fps // 4)
            marker(
                "SOLVER_CONTACT_CANDIDATE",
                frame=frame,
                eventId=event.event_id,
                attackerId=attacker_id,
                targetId=event.target_id,
                targetZone=event.target_zone,
                semanticDistance=round(float(semantic_distance), 6),
            )


def _mirror_impact(
    evidence: ImpactEvidence,
    attacker: RuntimeActor,
    target: RuntimeActor,
    frame: int,
    response_attacker: float,
    response_target: float,
) -> ImpactEvidence:
    normal = -Vector(evidence.contact_normal)
    contact_point = _surface_point(attacker, -normal)
    return ImpactModel.estimate(
        frame=frame,
        attacker_id=target.profile.entity_id,
        target_id=attacker.profile.entity_id,
        target_zone="front",
        attacker_mass_kg=target.profile.mass_kg,
        target_mass_kg=attacker.profile.mass_kg,
        relative_speed_mps=evidence.relative_speed_mps,
        normal_closing_speed_mps=evidence.normal_closing_speed_mps,
        contact_point=tuple(contact_point),
        contact_normal=tuple(normal),
        response_delta_attacker_mps=response_target,
        response_delta_target_mps=response_attacker,
        target_toughness_j_per_kg=attacker.profile.toughness_j_per_kg,
    )


def resolve_pending_contacts(
    frame: int,
    actors: dict[str, RuntimeActor],
    states: dict[str, EventState],
    events_by_id: dict[str, RuntimeEvent],
    pending: list[PendingContact],
    camera: CameraDirector,
    impact_log: list[dict[str, Any]],
) -> None:
    keep: list[PendingContact] = []
    for item in pending:
        if frame < item.resolve_frame:
            keep.append(item)
            continue

        attacker = actors[item.attacker_id]
        target = actors[item.target_id]
        post_attacker = attacker.velocity.get(frame, Vector((0.0, 0.0, 0.0)))
        post_target = target.velocity.get(frame, Vector((0.0, 0.0, 0.0)))
        response_attacker = (post_attacker - item.pre_attacker_velocity).length
        response_target = (post_target - item.pre_target_velocity).length
        relative = item.pre_attacker_velocity - item.pre_target_velocity
        relative_speed = relative.length
        normal = item.contact_normal.normalized()
        closing = max(0.0, relative.dot(normal))

        evidence = ImpactModel.estimate(
            frame=item.frame,
            attacker_id=item.attacker_id,
            target_id=item.target_id,
            target_zone=item.target_zone,
            attacker_mass_kg=attacker.profile.mass_kg,
            target_mass_kg=target.profile.mass_kg,
            relative_speed_mps=relative_speed,
            normal_closing_speed_mps=closing,
            contact_point=tuple(item.contact_point),
            contact_normal=tuple(normal),
            response_delta_attacker_mps=response_attacker,
            response_delta_target_mps=response_target,
            target_toughness_j_per_kg=target.profile.toughness_j_per_kg,
        )
        state = states[item.event_id]
        if not ImpactModel.qualifies(evidence):
            marker(
                "SOLVER_CONTACT_REJECTED",
                frame=item.frame,
                eventId=item.event_id,
                attackerId=item.attacker_id,
                targetId=item.target_id,
                closingSpeed=round(float(closing), 6),
                responseAttacker=round(float(response_attacker), 6),
                responseTarget=round(float(response_target), 6),
            )
            continue

        state.contact_count += 1
        state.evidence.append(evidence)
        target_damage = DamageAccumulator.apply(target.state, evidence)
        target_visual = ConsequenceEngine.apply(target, evidence)
        state.damage_count += 1
        state.status = "SUCCEEDED"
        state.completed_frame = frame

        mirrored: ImpactEvidence | None = None
        attacker_visual: dict[str, Any] | None = None
        mirrored_candidate = _mirror_impact(
            evidence,
            attacker,
            target,
            item.frame,
            response_attacker,
            response_target,
        )
        if ImpactModel.qualifies(mirrored_candidate) and mirrored_candidate.severity >= 0.035:
            mirrored = mirrored_candidate
            DamageAccumulator.apply(attacker.state, mirrored)
            receipt = ConsequenceEngine.apply(attacker, mirrored)
            attacker_visual = asdict(receipt)

        event = events_by_id.get(item.event_id)
        camera.mark_impact(item.frame, event, actors)

        impact_log.append(
            {
                "eventId": item.event_id,
                "evidence": asdict(evidence),
                "semanticDistance": item.semantic_distance,
                "targetDamage": target_damage,
                "targetVisual": asdict(target_visual),
                "attackerEvidence": asdict(mirrored) if mirrored else None,
                "attackerVisual": attacker_visual,
            }
        )
        marker(
            "QUALIFIED_NATIVE_RESPONSE_IMPACT",
            frame=item.frame,
            eventId=item.event_id,
            attackerId=item.attacker_id,
            targetId=item.target_id,
            severity=round(float(evidence.severity), 6),
            impactEnergyJ=round(float(evidence.impact_energy_j), 3),
        )

    pending[:] = keep


def update_event_lifecycle(
    frame: int,
    program: Any,
    states: dict[str, EventState],
) -> None:
    for event in program.events:
        state = states[event.event_id]
        if state.status in {"SUCCEEDED", "SETTLED", "OBSERVED", "FAILED", "FAILED_DEPENDENCY"}:
            continue

        deps_ready = event_dependency_ready(event, states)
        if not deps_ready:
            if frame >= event.end_frame + program.fps:
                dep_states = [states[d].status for d in event.dependencies]
                if any(x in {"FAILED", "FAILED_DEPENDENCY"} for x in dep_states):
                    state.status = "FAILED_DEPENDENCY"
                    state.completed_frame = frame
            continue

        if frame >= event.start_frame and state.first_active_frame is None:
            state.first_active_frame = frame
            state.status = "ACTIVE"

        if state.status != "ACTIVE":
            continue

        if not event.requires_contact:
            if frame >= event.end_frame:
                state.status = "SETTLED" if event.phase == "PAYOFF" else "OBSERVED"
                state.completed_frame = frame
            continue

        if (
            frame >= event.end_frame
            and state.last_replan_frame is None
            and program.policies.get("replanOnPhysicalImpossibility", True)
        ):
            state.attempts += 1
            state.last_replan_frame = frame
            marker(
                "EVENT_REPLAN_WINDOW_OPENED",
                eventId=event.event_id,
                frame=frame,
                attempt=state.attempts,
            )

        grace_end = min(program.total_frames, event.end_frame + program.fps)
        if frame >= grace_end and state.status != "SUCCEEDED":
            state.status = "FAILED"
            state.completed_frame = frame


def assert_no_actor_pose_keyframes(actors: dict[str, RuntimeActor]) -> None:
    forbidden = {
        "location",
        "rotation_euler",
        "rotation_quaternion",
        "scale",
    }
    for actor in actors.values():
        objects = [actor.chassis] + actor.rig.wheels_left + actor.rig.wheels_right
        for obj in objects:
            animation = obj.animation_data
            action = animation.action if animation else None
            if action is None:
                continue
            for curve in action.fcurves:
                if curve.data_path in forbidden:
                    raise BlenderBattleRuntimeError(
                        f"ACTOR_POSE_KEYFRAME_FORBIDDEN:{actor.profile.entity_id}:{obj.name}:{curve.data_path}"
                    )


def render_previews(
    output_dir: Path,
    camera: CameraDirector,
    total_frames: int,
) -> list[dict[str, Any]]:
    scene = bpy.context.scene
    labels = ("approach", "impact", "aftermath")
    frames = camera.preview_frames(total_frames)
    rows: list[dict[str, Any]] = []
    for label, frame in zip(labels, frames):
        scene.frame_set(frame)
        path = output_dir / f"preview-{label}-f{frame:04d}.png"
        scene.render.filepath = str(path)
        bpy.ops.render.render(write_still=True)
        if not path.is_file() or path.stat().st_size < 5000:
            raise BlenderBattleRuntimeError(
                f"PREVIEW_RENDER_INVALID:{label}:{frame}:{path}"
            )
        rows.append(
            {
                "label": label,
                "frame": frame,
                "path": str(path),
                "bytes": path.stat().st_size,
                "sha256": sha256_file(path),
            }
        )
    return rows


def main() -> None:
    args = parse_args()
    request_path = Path(args.request).expanduser().resolve()
    asset_map_path = Path(args.asset_map).expanduser().resolve()
    output_dir = Path(args.output_dir).expanduser().resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    request = load_json(request_path)
    asset_map = load_json(asset_map_path)
    if not isinstance(request, dict) or not isinstance(asset_map, dict):
        raise BlenderBattleRuntimeError("REQUEST_OR_ASSET_MAP_NOT_OBJECT")

    bindings = [dict(x) for x in (request.get("assetBindings") or [])]
    if not bindings:
        raise BlenderBattleRuntimeError("ASSET_BINDINGS_REQUIRED")

    program = BattleCompiler.compile(request, bindings)
    reset_scene()
    setup_world(request, program)

    cache = AssetPrototypeCache()
    prototypes: dict[str, Any] = {}
    resolved_assets: dict[str, dict[str, Any]] = {}
    for binding in bindings:
        entity = str(binding.get("entityId") or "")
        path, digest = resolve_asset(asset_map, binding)
        prototype = cache.load(binding, path)
        prototypes[entity] = prototype
        resolved_assets[entity] = {
            "path": str(path),
            "sha256": digest,
            "visibleMeshCount": len(prototype.meshes),
            "dimensions": [float(x) for x in prototype.dimensions],
            "semanticZones": sorted(prototype.zones.keys()),
        }

    spawn = SpawnPlanner.plan(program)
    actors: dict[str, RuntimeActor] = {}
    mass_receipts: dict[str, dict[str, float]] = {}
    bindings_by_entity = {str(x["entityId"]): x for x in bindings}
    for entity in program.actor_ids:
        binding = bindings_by_entity[entity]
        prototype = prototypes[entity]
        profile = ActorProfile.from_binding(binding, prototype.zones.keys())
        yaw = choose_initial_yaw(entity, spawn, program)
        actor = create_runtime_actor(binding, profile, prototype, spawn[entity], yaw)
        actors[entity] = actor
        mass_receipts[entity] = reconcile_total_mass(actor)

    create_ground(spawn, actors)
    setup_lighting()

    scene = bpy.context.scene
    states = {event.event_id: EventState(event.event_id) for event in program.events}
    events_by_id = {event.event_id: event for event in program.events}
    pending: list[PendingContact] = []
    cooldown: dict[tuple[str, str, str], int] = {}
    impact_log: list[dict[str, Any]] = []
    control_samples: list[dict[str, Any]] = []
    camera = CameraDirector(program.fps)
    camera.setup()

    scene.frame_set(1)
    for actor in actors.values():
        sample_actor(actor, 1, program.fps)
    update_event_lifecycle(1, program, states)
    set_controls(1, program, actors, states, control_samples)
    camera.observe(1, dominant_event(1, program, states), actors, force_key=True)

    for frame in range(2, program.total_frames + 1):
        scene.frame_set(frame)
        for actor in actors.values():
            sample_actor(actor, frame, program.fps)

        resolve_pending_contacts(
            frame,
            actors,
            states,
            events_by_id,
            pending,
            camera,
            impact_log,
        )
        detect_contacts(
            frame,
            program,
            actors,
            states,
            pending,
            cooldown,
        )
        update_event_lifecycle(frame, program, states)
        active = dominant_event(frame, program, states)
        camera.observe(frame, active, actors)
        set_controls(frame, program, actors, states, control_samples)

    if pending:
        resolve_pending_contacts(
            program.total_frames,
            actors,
            states,
            events_by_id,
            pending,
            camera,
            impact_log,
        )
    update_event_lifecycle(program.total_frames, program, states)

    for event in program.events:
        state = states[event.event_id]
        if state.status in {"PENDING", "ACTIVE"}:
            state.status = "FAILED_DEPENDENCY" if event.dependencies else "FAILED"
            state.completed_frame = program.total_frames

    camera.finalize(program.total_frames)
    assert_no_actor_pose_keyframes(actors)
    outcome = OutcomeResolver.resolve(
        {k: v.state for k, v in actors.items()},
        states,
    )

    previews: list[dict[str, Any]] = []
    if args.render_previews:
        previews = render_previews(output_dir, camera, program.total_frames)

    if args.save_blend:
        blend_path = output_dir / "generic-battle-runtime-v1.blend"
        bpy.ops.wm.save_as_mainfile(filepath=str(blend_path))

    actor_damage = {
        entity: {
            "state": {
                "structuralIntegrity": actor.state.structural_integrity,
                "driveEfficiency": actor.state.drive_efficiency,
                "disabled": actor.state.disabled,
                "zoneIntegrity": actor.state.zone_integrity,
                "damageEvents": actor.state.damage_events,
            },
            "visualEvidence": actor.damage_visual_evidence,
        }
        for entity, actor in actors.items()
    }
    debris_objects = [
        obj.name for obj in bpy.data.objects if obj.name.startswith("ISS_DEBRIS_")
    ]
    event_rows = {
        event_id: {
            "status": state.status,
            "attempts": state.attempts,
            "contactCount": state.contact_count,
            "damageCount": state.damage_count,
            "firstActiveFrame": state.first_active_frame,
            "completedFrame": state.completed_frame,
            "lastReplanFrame": state.last_replan_frame,
            "evidence": [asdict(x) for x in state.evidence],
        }
        for event_id, state in states.items()
    }

    gates = {
        "continuousWorld": True,
        "noActorPoseKeyframes": True,
        "assetIdentityVerified": len(resolved_assets) == len(program.actor_ids),
        "massReconciled": all(
            abs(v["reconciledMassKg"] - v["declaredMassKg"])
            <= max(1e-5, v["declaredMassKg"] * 1e-9)
            for v in mass_receipts.values()
        ),
        "solverCorrelatedImpactEvidence": bool(impact_log),
        "damageCausallyImpactGated": all(
            any(
                row["evidence"]["frame"] == damage["frame"]
                for row in impact_log
            )
            for actor in actor_damage.values()
            for damage in actor["state"]["damageEvents"]
        ),
        "persistentDebrisMaterialized": len(debris_objects) > 0
        if any(e.damage_required for e in program.events)
        else True,
        "allRequiredEventsSucceeded": bool(outcome["allRequiredEventsSucceeded"]),
    }

    evidence = {
        "success": all(gates.values()),
        "runtime": RUNTIME_VERSION,
        "models": {
            "control": CONTROL_MODEL,
            "contact": CONTACT_MODEL,
            "consequence": CONSEQUENCE_MODEL,
            "debris": DEBRIS_REPRESENTATION,
            "camera": CAMERA_MODEL,
        },
        "program": {
            "fps": program.fps,
            "totalFrames": program.total_frames,
            "actorCount": len(program.actor_ids),
            "eventCount": len(program.events),
        },
        "resolvedAssets": resolved_assets,
        "massReceipts": mass_receipts,
        "events": event_rows,
        "impacts": impact_log,
        "actors": actor_damage,
        "debrisObjects": debris_objects,
        "controlSamples": control_samples,
        "outcome": outcome,
        "gates": gates,
        "previews": previews,
    }
    evidence_path = output_dir / "generic-battle-runtime-v1-evidence.json"
    evidence_path.write_text(
        json.dumps(evidence, indent=2, sort_keys=True),
        encoding="utf-8",
    )
    marker(
        "GENERIC_BATTLE_RUNTIME_RESULT",
        success=evidence["success"],
        evidencePath=str(evidence_path),
        actorCount=len(program.actor_ids),
        eventCount=len(program.events),
        impactCount=len(impact_log),
        debrisCount=len(debris_objects),
    )
    if not evidence["success"]:
        raise BlenderBattleRuntimeError(
            "GENERIC_BATTLE_RUNTIME_ACCEPTANCE_GATES_FAILED:"
            + ",".join(k for k, v in gates.items() if not v)
        )


if __name__ == "__main__":
    main()
