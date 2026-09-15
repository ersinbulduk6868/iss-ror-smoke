from __future__ import annotations

import copy
import json
import math
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from mathutils import Vector

from blender import iss_battle_runtime_contract as contract
from blender import iss_battle_runtime_physics as physics
from blender import iss_blender_battle_runtime_v1 as runtime
from blender import iss_blender_battle_runtime_v1_hardened as hardened
from blender import run_generic_battle_runtime_v1_candidate39 as candidate39
from blender.iss_battle_runtime_assets import BlenderBattleRuntimeError, marker
from blender.iss_battle_runtime_autonomy import (
    AUTONOMY_MODEL,
    REPLAN_MODEL,
    AutonomyMemory,
    AutonomyObservation,
    ClosedLoopGoalController,
)

CANDIDATE = "ISS_GENERIC_BATTLE_RUNTIME_V1_CANDIDATE_4_0_G04"
INTENT_FIREWALL = "ISS_INTENT_ONLY_EXECUTION_CONTRACT_V1"

_ORIGINAL_COMPILE = contract.BattleCompiler.compile
_memories: dict[tuple[str, str], AutonomyMemory] = {}
_last_reported_mode: dict[tuple[str, str], str] = {}
_overtime_marked: set[str] = set()

# Exact choreography is never executable input to Candidate 4.0.  Existing Story
# payloads remain accepted; high-level tactic intent is extracted first, then these
# fields are removed before the runtime program is created.
FORBIDDEN_EXECUTABLE_CHOREOGRAPHY_KEYS = {
    "collisionframe",
    "contactframe",
    "impactframe",
    "collisiontime",
    "contacttime",
    "impactspeedmps",
    "targetimpactspeedmps",
    "targetenergyj",
    "impactenergyj",
    "cutoffdistancem",
    "contactcutoffdistancem",
    "trajectorypoints",
    "pathpoints",
    "waypoints",
    "positionkeyframes",
    "velocitykeyframes",
    "velocityvector",
    "forcedcontactpoint",
}


def _normalized_key(value: Any) -> str:
    return "".join(ch for ch in str(value or "").lower() if ch.isalnum())


def _strip_forbidden(value: Any, removed: list[str], prefix: str = "") -> Any:
    if isinstance(value, dict):
        out: dict[str, Any] = {}
        for key, child in value.items():
            path = f"{prefix}.{key}" if prefix else str(key)
            if _normalized_key(key) in FORBIDDEN_EXECUTABLE_CHOREOGRAPHY_KEYS:
                removed.append(path)
                continue
            out[key] = _strip_forbidden(child, removed, path)
        return out
    if isinstance(value, list):
        return [_strip_forbidden(x, removed, f"{prefix}[]") for x in value]
    return value


def intent_only_compile(request: dict[str, Any], asset_bindings: list[dict[str, Any]]):
    safe = copy.deepcopy(request)
    plan = safe.get("battlePlan") or safe.get("physicsPlan") or {}
    raw_events = plan.get("events") or []
    removed: list[str] = []
    for event in raw_events:
        if not isinstance(event, dict):
            continue
        # Preserve only the high-level semantic meaning of legacy trajectory prose.
        tactic = contract.infer_tactic(event)
        event["tacticalPurpose"] = tactic
        req = event.get("physicsRequirements")
        if isinstance(req, dict):
            req.pop("trajectory", None)
        cleaned = _strip_forbidden(event, removed, str(event.get("eventId") or "event"))
        event.clear()
        event.update(cleaned)

    program = _ORIGINAL_COMPILE(safe, asset_bindings)
    for event in program.events:
        raw = event.original or {}
        bad: list[str] = []
        _strip_forbidden(raw, bad, event.event_id)
        if bad:
            raise BlenderBattleRuntimeError(
                "EXECUTABLE_CHOREOGRAPHY_FIREWALL_FAILED:" + ",".join(sorted(bad))
            )
        req = raw.get("physicsRequirements") or {}
        if isinstance(req, dict) and "trajectory" in req:
            raise BlenderBattleRuntimeError(
                f"EXECUTABLE_TRAJECTORY_FORBIDDEN:{event.event_id}"
            )
    marker(
        "INTENT_ONLY_EXECUTION_CONTRACT_PASS",
        model=INTENT_FIREWALL,
        eventCount=len(program.events),
        strippedExactChoreographyFields=sorted(set(removed)),
        storyContractChanged=False,
    )
    return program


def _active_goal_for_actor(
    entity: str,
    frame: int,
    program: Any,
    states: dict[str, Any],
):
    priorities = {
        "CLIMAX": 0,
        "SPECIAL_ATTACK": 1,
        "COUNTERATTACK": 2,
        "FIRST_ATTACK": 3,
        "ESCALATION": 4,
        "HOOK": 5,
        "PAYOFF": 6,
    }
    rows = []
    for event in program.events:
        if entity not in event.attackers:
            continue
        state = states[event.event_id]
        if state.status in {"SUCCEEDED", "SETTLED", "OBSERVED", "FAILED", "FAILED_DEPENDENCY"}:
            continue
        if frame < event.start_frame:
            continue
        if not hardened._lifecycle.dependencies_ready(event, states):
            continue
        rows.append(event)
    if not rows:
        return None
    rows.sort(
        key=lambda event: (
            priorities.get(event.phase, 50),
            event.start_frame,
            event.event_id,
        )
    )
    return rows[0]


def _support_radius(actor: Any, direction_world: Vector) -> float:
    if direction_world.length < 1.0e-8:
        return 0.0
    direction = direction_world.normalized()
    local = actor.chassis.matrix_world.to_quaternion().inverted() @ direction
    half = actor.chassis.dimensions * 0.5
    return (
        abs(float(local.x)) * float(half.x)
        + abs(float(local.y)) * float(half.y)
        + abs(float(local.z)) * float(half.z)
    )


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


def _wheel_speeds(actor: Any, forward_speed: float, yaw_rate: float) -> tuple[float, float]:
    track_width = max(0.35, float(actor.dimensions.y) * 0.78)
    left = float(forward_speed) - float(yaw_rate) * track_width * 0.5
    right = float(forward_speed) + float(yaw_rate) * track_width * 0.5
    max_forward = max(0.2, actor.profile.max_speed_mps * max(0.15, actor.state.drive_efficiency))
    max_reverse = max(0.2, actor.profile.max_reverse_mps * max(0.15, actor.state.drive_efficiency))
    scale = max(
        1.0,
        left / max_forward if left > 0.0 else abs(left) / max_reverse,
        right / max_forward if right > 0.0 else abs(right) / max_reverse,
    )
    return left / scale, right / scale


def _recovery_bias(event_id: str, actor_id: str) -> float:
    return 1.0 if contract.stable_unit(f"{event_id}:{actor_id}:recovery") >= 0.5 else -1.0


def autonomous_set_controls(
    frame: int,
    program: Any,
    actors: dict[str, Any],
    states: dict[str, Any],
    control_samples: list[dict[str, Any]],
) -> None:
    for entity, actor in actors.items():
        event = _active_goal_for_actor(entity, frame, program, states)
        if event is None:
            actor.rig.coast()
            continue

        wave = runtime.WaveScheduler.active_attackers(event, frame)
        if entity not in wave:
            actor.rig.coast()
            continue

        state = states[event.event_id]
        target_point = runtime.resolve_target_point(actor, event, actors, frame, state)
        position = actor.chassis.matrix_world.translation
        target_vector = target_point - position if target_point is not None else Vector((1.0, 0.0, 0.0))
        target_vector.z = 0.0
        q = actor.chassis.matrix_world.to_quaternion()
        forward = q @ Vector((1.0, 0.0, 0.0))
        heading_error = physics.signed_heading_error(forward, target_vector)
        velocity = actor.velocity.get(frame, Vector((0.0, 0.0, 0.0)))
        forward_speed = velocity.dot(forward.normalized()) if forward.length > 1.0e-8 else 0.0

        if event.target_id and event.target_id in actors:
            target = actors[event.target_id]
            gap, center_distance, normal = _surface_gap(actor, target)
            target_velocity = target.velocity.get(frame, Vector((0.0, 0.0, 0.0)))
            closing = (velocity - target_velocity).dot(normal)
        else:
            gap = max(0.0, float(target_vector.length))
            center_distance = float(target_vector.length)
            closing = 0.0

        key = (event.event_id, entity)
        memory = _memories.setdefault(key, AutonomyMemory())
        previous_mode = memory.mode
        observation = AutonomyObservation(
            frame=int(frame),
            fps=int(program.fps),
            distance_m=float(center_distance),
            surface_gap_m=float(gap),
            heading_error_rad=float(heading_error),
            forward_speed_mps=float(forward_speed),
            closing_speed_mps=float(closing),
            contention=_contention_score(entity, actor, actors, event.target_id),
            contact_count=int(state.contact_count),
            damage_count=int(state.damage_count),
            damage_required=bool(event.damage_required),
            actor_disabled=bool(actor.state.disabled),
            requires_contact=bool(event.requires_contact),
            max_speed_mps=float(actor.profile.max_speed_mps),
            max_reverse_mps=float(actor.profile.max_reverse_mps),
            max_yaw_rate_rad_s=float(actor.profile.max_yaw_rate_rad_s),
            acceleration_mps2=float(actor.profile.acceleration_mps2),
            braking_mps2=float(actor.profile.braking_mps2),
            drive_efficiency=float(actor.state.drive_efficiency),
            characteristic_length_m=max(0.25, float(actor.dimensions.x)),
            speed_intent=str(event.speed_intent),
        )
        command = ClosedLoopGoalController.update(
            memory,
            observation,
            recovery_bias=_recovery_bias(event.event_id, entity),
        )

        if command.replan_triggered:
            state.attempts = max(int(state.attempts), int(memory.attempt))
            state.last_replan_frame = int(frame)
            marker(
                "AUTONOMY_REPLAN_TRIGGERED",
                frame=frame,
                eventId=event.event_id,
                actorId=entity,
                reason=command.reason,
                attempt=state.attempts,
                model=REPLAN_MODEL,
            )

        if command.motor_authority == "COAST":
            actor.rig.coast()
            if command.mode == "CONTACT_HANDOFF":
                hardened._cutoff_frames[(event.event_id, entity)] = int(frame)
        else:
            left, right = _wheel_speeds(
                actor,
                command.forward_speed_mps,
                command.yaw_rate_rad_s,
            )
            actor.rig.command(
                left,
                right,
                impulse_scale=max(0.12, actor.state.drive_efficiency),
            )

        mode_changed = _last_reported_mode.get(key) != command.mode
        if mode_changed:
            _last_reported_mode[key] = command.mode
            marker(
                "AUTONOMY_MODE_CHANGED",
                frame=frame,
                eventId=event.event_id,
                actorId=entity,
                previousMode=previous_mode,
                mode=command.mode,
                reason=command.reason,
                model=AUTONOMY_MODEL,
            )

        if (
            frame == event.start_frame
            or command.replan_triggered
            or mode_changed
            or frame % max(1, program.fps // 4) == 0
        ):
            left = right = 0.0
            if command.motor_authority != "COAST":
                left, right = _wheel_speeds(
                    actor,
                    command.forward_speed_mps,
                    command.yaw_rate_rad_s,
                )
            control_samples.append(
                {
                    "frame": int(frame),
                    "eventId": event.event_id,
                    "actorId": entity,
                    "tactic": event.tactic,
                    "mode": command.mode,
                    "reason": command.reason,
                    "motorAuthority": command.motor_authority,
                    "leftMps": float(left),
                    "rightMps": float(right),
                    "forwardCommandMps": float(command.forward_speed_mps),
                    "yawRateCommandRadS": float(command.yaw_rate_rad_s),
                    "targetRefreshCount": int(memory.target_refreshes),
                    "replanCount": int(memory.replans),
                    "observation": {
                        "distanceM": float(observation.distance_m),
                        "surfaceGapM": float(observation.surface_gap_m),
                        "headingErrorRad": float(observation.heading_error_rad),
                        "forwardSpeedMps": float(observation.forward_speed_mps),
                        "closingSpeedMps": float(observation.closing_speed_mps),
                        "contention": float(observation.contention),
                        "contactCount": int(observation.contact_count),
                        "damageCount": int(observation.damage_count),
                    },
                    "policy": {
                        "progressTimeoutFrames": int(command.progress_timeout_frames),
                        "contactHandoffGapM": float(command.contact_handoff_gap_m),
                    },
                }
            )


def autonomous_update_event_lifecycle(
    frame: int,
    program: Any,
    states: dict[str, Any],
) -> None:
    for event in program.events:
        state = states[event.event_id]
        if state.status in hardened.TERMINAL:
            continue

        deps_ready = hardened._lifecycle.dependencies_ready(event, states)
        if not deps_ready:
            if frame >= program.total_frames and hardened._lifecycle.dependency_failure(event, states):
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

        if hardened._lifecycle.requirements_met(event, state):
            state.status = "SUCCEEDED"
            state.completed_frame = frame
            continue

        if frame >= event.end_frame and event.event_id not in _overtime_marked:
            _overtime_marked.add(event.event_id)
            marker(
                "STORY_WINDOW_EXCEEDED_GOAL_STILL_ACTIVE",
                frame=frame,
                eventId=event.event_id,
                storyEndFrame=event.end_frame,
                finalBattleFrame=program.total_frames,
                timingAuthority="STORY_GUIDANCE_NOT_EXACT_PHYSICS_DEADLINE",
            )

        if frame >= program.total_frames:
            if hardened._lifecycle.requirements_met(event, state):
                state.status = "SUCCEEDED"
            else:
                state.status = "FAILED"
            state.completed_frame = frame


def _reset_candidate_state() -> None:
    _memories.clear()
    _last_reported_mode.clear()
    _overtime_marked.clear()


def main() -> None:
    _reset_candidate_state()
    contract.BattleCompiler.compile = staticmethod(intent_only_compile)
    hardened.set_controls = autonomous_set_controls
    hardened.update_event_lifecycle = autonomous_update_event_lifecycle
    candidate39.CANDIDATE = CANDIDATE

    print(
        json.dumps(
            {
                "marker": "GENERIC_BATTLE_RUNTIME_CANDIDATE40_G04_ENGINEERING_PASS",
                "candidate": CANDIDATE,
                "autonomyModel": AUTONOMY_MODEL,
                "replanModel": REPLAN_MODEL,
                "intentFirewall": INTENT_FIREWALL,
                "assetSpecificBattleCode": False,
                "scenarioTrajectoryHardcode": False,
                "exactImpactEnergyTarget": False,
                "exactCollisionFrameTarget": False,
                "damageThresholdChanged": False,
                "contactThresholdChanged": False,
                "actorPoseOrVelocityMutation": False,
                "nativeContactTruthClaimed": False,
                "damageGateClaimed": False,
                "productionReadyClaimed": False,
            },
            sort_keys=True,
        ),
        flush=True,
    )
    candidate39.main()


if __name__ == "__main__":
    main()
