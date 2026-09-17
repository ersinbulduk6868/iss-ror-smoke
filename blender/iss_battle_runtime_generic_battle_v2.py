from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Callable

from mathutils import Vector

from blender import iss_battle_runtime_contract as contract
from blender import iss_battle_runtime_physics as physics
from blender import iss_blender_battle_runtime_v1 as runtime
from blender import iss_blender_battle_runtime_v1_hardened as hardened
from blender.iss_battle_runtime_assets import marker
from blender.iss_battle_runtime_autonomy import AutonomyMemory, AutonomyObservation, ClosedLoopGoalController
from blender.iss_battle_runtime_tactics_v2 import (
    TACTICAL_MODEL,
    GenericBattleTacticalPlanner,
    TacticalMemory,
    TacticalObservation,
)

BATTLE_CONTROL_MODEL = "ISS_GENERIC_AUTONOMOUS_BATTLE_CONTROL_V2"

_tactical_memories: dict[str, TacticalMemory] = {}
_autonomy_memories: dict[tuple[str, str], AutonomyMemory] = {}
_last_tactical_mode: dict[str, str] = {}
_tactical_samples: list[dict[str, Any]] = []


def reset() -> None:
    _tactical_memories.clear()
    _autonomy_memories.clear()
    _last_tactical_mode.clear()
    _tactical_samples.clear()


def _symmetry_bias(event_id: str, actor_id: str) -> float:
    return 1.0 if contract.stable_unit(f"{event_id}:{actor_id}:battle-side") >= 0.5 else -1.0


def _target_goal(actor: Any, target: Any, event: Any, tactical: Any, actors: dict[str, Any]) -> Vector:
    actor_pos = actor.chassis.matrix_world.translation.copy()
    target_pos = target.chassis.matrix_world.translation.copy()
    delta = target_pos - actor_pos
    delta.z = 0.0
    away = Vector((-1.0, 0.0, 0.0)) if delta.length <= 1.0e-8 else (-delta.normalized())

    if tactical.mode == "BREAK_CONTACT":
        return actor_pos + away * max(float(actor.dimensions.x) * 1.20, float(target.dimensions.x) * 0.75, 3.0)
    if tactical.mode == "EVADE":
        q = target.chassis.matrix_world.to_quaternion()
        lateral = q @ Vector((0.0, 1.0, 0.0))
        lateral.z = 0.0
        if lateral.length > 1.0e-8:
            lateral.normalize()
        return actor_pos + away * max(4.0, float(actor.dimensions.x) * 1.75) + lateral * tactical.lateral_offset_scale * max(1.0, float(target.dimensions.y))

    zone = target.zone_world(event.target_zone)
    if tactical.contact_commit and tactical.mode in {"ENGAGE", "COUNTER"}:
        desired = zone
    else:
        q = target.chassis.matrix_world.to_quaternion()
        forward = q @ Vector((1.0, 0.0, 0.0))
        lateral = q @ Vector((0.0, 1.0, 0.0))
        forward.z = 0.0
        lateral.z = 0.0
        if forward.length > 1.0e-8:
            forward.normalize()
        if lateral.length > 1.0e-8:
            lateral.normalize()
        desired = (
            zone
            + forward * tactical.forward_offset_scale * max(0.5, float(target.dimensions.x))
            + lateral * tactical.lateral_offset_scale * max(0.5, float(target.dimensions.y))
        )
    avoidance = getattr(runtime, "_reactive_avoidance", None)
    if callable(avoidance):
        desired = avoidance(actor, desired, actors, event.target_id)
    return desired


def _wheel_speeds(actor: Any, forward_speed: float, yaw_rate: float) -> tuple[float, float]:
    track_width = max(0.35, float(actor.dimensions.y) * 0.78)
    left = float(forward_speed) - float(yaw_rate) * track_width * 0.5
    right = float(forward_speed) + float(yaw_rate) * track_width * 0.5
    efficiency = max(0.15, float(actor.state.drive_efficiency))
    max_forward = max(0.2, float(actor.profile.max_speed_mps) * efficiency)
    max_reverse = max(0.2, float(actor.profile.max_reverse_mps) * efficiency)
    scale = max(
        1.0,
        left / max_forward if left > 0.0 else abs(left) / max_reverse,
        right / max_forward if right > 0.0 else abs(right) / max_reverse,
    )
    return left / scale, right / scale


def set_controls(
    frame: int,
    program: Any,
    actors: dict[str, Any],
    states: dict[str, Any],
    control_samples: list[dict[str, Any]],
    *,
    active_goal_resolver: Callable[[str, int, Any, dict[str, Any]], Any | None],
) -> None:
    for entity, actor in actors.items():
        event = active_goal_resolver(entity, frame, program, states)
        if event is None:
            actor.rig.coast()
            continue
        wave = runtime.WaveScheduler.active_attackers(event, frame)
        if entity not in wave:
            actor.rig.brake(0.55)
            continue

        state = states[event.event_id]
        target = actors.get(event.target_id) if event.target_id else None
        position = actor.chassis.matrix_world.translation.copy()
        q = actor.chassis.matrix_world.to_quaternion()
        forward = q @ Vector((1.0, 0.0, 0.0))
        forward.z = 0.0
        if forward.length <= 1.0e-8:
            forward = Vector((1.0, 0.0, 0.0))
        else:
            forward.normalize()
        velocity = actor.velocity.get(frame, Vector((0.0, 0.0, 0.0)))

        if target is not None:
            gap, center_distance, normal = _surface_gap(actor, target)
            target_velocity = target.velocity.get(frame, Vector((0.0, 0.0, 0.0)))
            closing = float((velocity - target_velocity).dot(normal))
            direct = target.chassis.matrix_world.translation - position
            direct.z = 0.0
            direct_heading_error = physics.signed_heading_error(forward, direct)
            target_integrity = float(target.state.structural_integrity)
            target_efficiency = float(target.state.drive_efficiency)
            target_disabled = bool(target.state.disabled)
            target_length = float(target.dimensions.x)
            target_width = float(target.dimensions.y)
            target_damage_count = len(target.state.damage_events)
            target_last_impact = target.state.last_impact_frame
        else:
            gap = center_distance = 0.0
            closing = 0.0
            direct_heading_error = 0.0
            target_integrity = target_efficiency = 1.0
            target_disabled = False
            target_length = float(actor.dimensions.x)
            target_width = float(actor.dimensions.y)
            target_damage_count = 0
            target_last_impact = None

        tactical_memory = _tactical_memories.setdefault(entity, TacticalMemory())
        tactical_obs = TacticalObservation(
            frame=int(frame), fps=int(program.fps), phase=str(event.phase), story_tactic=str(event.tactic),
            requires_contact=bool(event.requires_contact), surface_gap_m=float(gap), center_distance_m=float(center_distance),
            closing_speed_mps=float(closing), heading_error_rad=float(direct_heading_error),
            contention=float(_contention_score(entity, actor, actors, event.target_id)),
            own_integrity=float(actor.state.structural_integrity), own_drive_efficiency=float(actor.state.drive_efficiency),
            own_disabled=bool(actor.state.disabled), target_integrity=target_integrity,
            target_drive_efficiency=target_efficiency, target_disabled=target_disabled,
            own_max_speed_mps=float(actor.profile.max_speed_mps), own_max_reverse_mps=float(actor.profile.max_reverse_mps),
            own_yaw_rate_rad_s=float(actor.profile.max_yaw_rate_rad_s), own_acceleration_mps2=float(actor.profile.acceleration_mps2),
            own_braking_mps2=float(actor.profile.braking_mps2), own_length_m=max(0.25, float(actor.dimensions.x)),
            own_width_m=max(0.25, float(actor.dimensions.y)), target_length_m=max(0.25, target_length),
            target_width_m=max(0.25, target_width), contact_count=int(state.contact_count), damage_count=int(state.damage_count),
            own_damage_event_count=len(actor.state.damage_events), target_damage_event_count=int(target_damage_count),
            last_own_impact_frame=actor.state.last_impact_frame, last_target_impact_frame=target_last_impact,
        )
        tactical = GenericBattleTacticalPlanner.decide(
            tactical_memory, tactical_obs,
            symmetry_bias=_symmetry_bias(event.event_id, entity),
        )

        if target is not None:
            goal_point = _target_goal(actor, target, event, tactical, actors)
        else:
            fallback = runtime.resolve_target_point(actor, event, actors, frame, state)
            goal_point = fallback if fallback is not None else position + forward * max(3.0, float(actor.dimensions.x))
        target_vector = goal_point - position
        target_vector.z = 0.0
        heading_error = physics.signed_heading_error(forward, target_vector)
        forward_speed = float(velocity.dot(forward))

        autonomy_key = (event.event_id, entity)
        autonomy_memory = _autonomy_memories.setdefault(autonomy_key, AutonomyMemory())
        effective_requires_contact = bool(event.requires_contact and tactical.contact_commit)
        autonomy_obs = AutonomyObservation(
            frame=int(frame), fps=int(program.fps), distance_m=max(0.0, float(target_vector.length)),
            surface_gap_m=float(gap), heading_error_rad=float(heading_error), forward_speed_mps=forward_speed,
            closing_speed_mps=float(closing), contention=float(tactical_obs.contention), contact_count=int(state.contact_count),
            damage_count=int(state.damage_count), damage_required=bool(event.damage_required), actor_disabled=bool(actor.state.disabled),
            requires_contact=effective_requires_contact,
            max_speed_mps=float(actor.profile.max_speed_mps) * max(0.0, float(tactical.speed_scale)),
            max_reverse_mps=float(actor.profile.max_reverse_mps) * max(0.0, float(tactical.speed_scale)),
            max_yaw_rate_rad_s=float(actor.profile.max_yaw_rate_rad_s), acceleration_mps2=float(actor.profile.acceleration_mps2),
            braking_mps2=float(actor.profile.braking_mps2), drive_efficiency=float(actor.state.drive_efficiency),
            characteristic_length_m=max(0.25, float(actor.dimensions.x)), speed_intent=str(tactical.speed_intent),
        )

        if tactical.speed_intent == "BRAKE":
            actor.rig.brake(max(0.5, tactical.brake_strength))
            motor_authority = "BRAKE"
            left = right = 0.0
            command_mode = tactical.mode
            command_reason = tactical.reason
            command_speed = 0.0
            command_yaw = 0.0
            replan_triggered = False
            progress_timeout = ClosedLoopGoalController.progress_timeout_frames(autonomy_obs)
            handoff_gap = ClosedLoopGoalController.contact_handoff_gap(autonomy_obs)
        else:
            command = ClosedLoopGoalController.update(
                autonomy_memory, autonomy_obs,
                recovery_bias=_symmetry_bias(event.event_id, entity),
            )
            command_mode = command.mode
            command_reason = command.reason
            command_speed = float(command.forward_speed_mps)
            command_yaw = float(command.yaw_rate_rad_s)
            replan_triggered = bool(command.replan_triggered)
            progress_timeout = int(command.progress_timeout_frames)
            handoff_gap = float(command.contact_handoff_gap_m)
            if command.motor_authority == "COAST":
                actor.rig.coast()
                motor_authority = "COAST"
                left = right = 0.0
                if command.mode == "CONTACT_HANDOFF":
                    hardened._cutoff_frames[(event.event_id, entity)] = int(frame)
            else:
                left, right = _wheel_speeds(actor, command_speed, command_yaw)
                actor.rig.command(left, right, impulse_scale=max(0.12, actor.state.drive_efficiency))
                motor_authority = "MOTOR"

        if replan_triggered:
            state.attempts = max(int(state.attempts), int(autonomy_memory.attempt))
            state.last_replan_frame = int(frame)
            marker("AUTONOMY_REPLAN_TRIGGERED", frame=frame, eventId=event.event_id, actorId=entity,
                   reason=command_reason, attempt=state.attempts, model="ISS_WORLD_STATE_REPLANNER_V1")

        previous_tactical = _last_tactical_mode.get(entity)
        if previous_tactical != tactical.mode:
            _last_tactical_mode[entity] = tactical.mode
            marker(
                "GENERIC_BATTLE_TACTIC_CHANGED", frame=int(frame), eventId=event.event_id, actorId=entity,
                previousMode=previous_tactical, mode=tactical.mode, reason=tactical.reason,
                cycle=int(tactical.cycle), model=TACTICAL_MODEL,
            )

        if tactical.transition or replan_triggered or frame == event.start_frame or frame % max(1, int(program.fps) // 4) == 0:
            row = {
                "frame": int(frame), "eventId": str(event.event_id), "actorId": entity,
                "storyPhase": str(event.phase), "storyTactic": str(event.tactic),
                "tacticalMode": tactical.mode, "tacticalReason": tactical.reason, "battleCycle": int(tactical.cycle),
                "speedIntent": tactical.speed_intent, "speedScale": float(tactical.speed_scale),
                "contactCommit": bool(tactical.contact_commit), "motorAuthority": motor_authority,
                "controllerMode": command_mode, "controllerReason": command_reason,
                "leftMps": float(left), "rightMps": float(right), "forwardCommandMps": command_speed,
                "yawRateCommandRadS": command_yaw,
                "observation": {
                    "surfaceGapM": float(gap), "centerDistanceM": float(center_distance),
                    "closingSpeedMps": float(closing), "headingErrorRad": float(heading_error),
                    "contention": float(tactical_obs.contention), "ownIntegrity": float(actor.state.structural_integrity),
                    "ownDriveEfficiency": float(actor.state.drive_efficiency), "targetIntegrity": target_integrity,
                    "targetDriveEfficiency": target_efficiency, "contactCount": int(state.contact_count),
                    "damageCount": int(state.damage_count), "ownDamageEventCount": len(actor.state.damage_events),
                },
                "policy": {"progressTimeoutFrames": int(progress_timeout), "contactHandoffGapM": float(handoff_gap)},
                "assetIdentityBranch": False, "fixedWorldCoordinate": False, "exactCollisionFrameTarget": False,
                "exactImpactEnergyTarget": False, "actorPoseOrVelocityMutation": False,
            }
            control_samples.append(row)
            _tactical_samples.append(json.loads(json.dumps(row)))


def _support_radius(actor: Any, direction_world: Vector) -> float:
    if direction_world.length < 1.0e-8:
        return 0.0
    direction = direction_world.normalized()
    local = actor.chassis.matrix_world.to_quaternion().inverted() @ direction
    half = actor.chassis.dimensions * 0.5
    return abs(float(local.x)) * float(half.x) + abs(float(local.y)) * float(half.y) + abs(float(local.z)) * float(half.z)


def _surface_gap(attacker: Any, target: Any) -> tuple[float, float, Vector]:
    delta = target.chassis.matrix_world.translation - attacker.chassis.matrix_world.translation
    delta.z = 0.0
    center_distance = float(delta.length)
    if center_distance < 1.0e-8:
        return -min(float(attacker.dimensions.x), float(target.dimensions.x)), 0.0, Vector((1.0, 0.0, 0.0))
    normal = delta.normalized()
    gap = center_distance - _support_radius(attacker, normal) - _support_radius(target, -normal)
    return float(gap), center_distance, normal


def _contention_score(actor_id: str, actor: Any, actors: dict[str, Any], target_id: str | None) -> float:
    position = actor.chassis.matrix_world.translation
    own_radius = max(float(actor.dimensions.x), float(actor.dimensions.y)) * 0.50
    score = 0.0
    for other_id, other in actors.items():
        if other_id in {actor_id, target_id}:
            continue
        delta = other.chassis.matrix_world.translation - position
        delta.z = 0.0
        distance = float(delta.length)
        other_radius = max(float(other.dimensions.x), float(other.dimensions.y)) * 0.50
        safe = max(0.5, own_radius + other_radius)
        influence = safe * 1.65
        if distance < influence:
            score = max(score, (influence - distance) / influence)
    return max(0.0, min(1.0, score))


def write_evidence(output_dir: Path) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    mode_counts: dict[str, int] = {}
    actors: set[str] = set()
    cycles: dict[str, int] = {}
    for row in _tactical_samples:
        mode = str(row.get("tacticalMode") or "")
        mode_counts[mode] = mode_counts.get(mode, 0) + 1
        actor_id = str(row.get("actorId") or "")
        if actor_id:
            actors.add(actor_id)
            cycles[actor_id] = max(cycles.get(actor_id, 0), int(row.get("battleCycle") or 0))
    evidence = {
        "status": "OBSERVED",
        "battleControlModel": BATTLE_CONTROL_MODEL,
        "tacticalModel": TACTICAL_MODEL,
        "sampleCount": len(_tactical_samples),
        "actors": sorted(actors),
        "modeCounts": dict(sorted(mode_counts.items())),
        "maxBattleCycleByActor": dict(sorted(cycles.items())),
        "samples": _tactical_samples,
        "sameRuntimeAcrossAssets": True,
        "liveWorldStateDriven": True,
        "actorProfileCapabilityDriven": True,
        "storyIntentOnly": True,
        "perAssetBattleCode": False,
        "perVideoTrajectoryEngineering": False,
        "fixedWorldCoordinates": False,
        "exactCollisionFrameTarget": False,
        "exactImpactEnergyTarget": False,
        "actorPoseOrVelocityMutation": False,
        "gateClosed": False,
        "productionReadyClaimed": False,
    }
    path = output_dir / "generic-autonomous-battle-v2-evidence.json"
    path.write_text(json.dumps(evidence, indent=2, sort_keys=True), encoding="utf-8")
    marker("GENERIC_AUTONOMOUS_BATTLE_V2_EVIDENCE_WRITTEN", path=str(path), sampleCount=len(_tactical_samples), modeCount=len(mode_counts), actorCount=len(actors), model=BATTLE_CONTROL_MODEL)
    return path
