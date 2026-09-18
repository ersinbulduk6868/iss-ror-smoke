from __future__ import annotations

import json
import sys
from typing import Any

from mathutils import Vector

REPO_ROOT = __import__("pathlib").Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from blender import iss_battle_runtime_generic_battle_v2 as control_v2
from blender import iss_battle_runtime_generic_battle_v6 as battle_v6
from blender import iss_battle_runtime_physics as physics
from blender import run_generic_battle_runtime_v1_candidate465_generic_battle as candidate465
from blender import run_generic_battle_runtime_v1_candidate474_generic_battle as candidate474
from blender import run_generic_battle_runtime_v1_candidate481_generic_battle as candidate481
from blender import run_generic_battle_runtime_v1_candidate485_generic_battle as candidate485
from blender import run_generic_battle_runtime_v1_candidate486_generic_battle as candidate486
from blender.iss_battle_runtime_assets import marker
from blender.iss_battle_runtime_autonomy import ClosedLoopGoalController
from blender.iss_battle_runtime_contact_commit_v2 import live_contact_commit_ready
from blender.iss_battle_runtime_engagement_lifecycle_v1 import (
    ALLOW_CONTACT,
    DEFER_TO_TACTIC,
    ENGAGEMENT_LIFECYCLE_MODEL,
    HOLD_STANDOFF,
    PHASE_ALIGN_STANDOFF,
    PHASE_APPROACH,
    PHASE_HANDOFF_READY,
    PHASE_RECOVERING,
    PHASE_RUNWAY_REOPEN,
    REOPEN_DISTANCE,
    SUSPEND_FOR_RECOVERY,
    EngagementLifecycleMemory,
    is_recovery_mode,
    note_recovery_transition,
    precontact_action,
    transaction_key,
)
from blender.iss_battle_runtime_handoff_progress_v1 import deferred_handoff_stalled
from blender.iss_battle_runtime_tactics_v5 import (
    GenericBattleTacticalPlanner,
    TacticalMemory,
    motion_heading_error,
)

CANDIDATE = "ISS_GENERIC_BATTLE_RUNTIME_V1_CANDIDATE_4_8_7_GENERIC_AUTONOMOUS_BATTLE"
MECHANISM = ENGAGEMENT_LIFECYCLE_MODEL
AUDIT = "G04_FULL_EVENT_SCOPED_RECOVERY_AUTHORITY_LIFECYCLE_AUDIT_AFTER_C486_20260918"
FAILURE_FAMILY = "G04_FRAGMENTED_PRECONTACT_RECOVERY_AND_SOLVER_AUTHORITY_TRANSFER_LIFECYCLE"

_BASE_GOAL_FOR_TACTICAL = battle_v6._goal_for_tactical
_BASE_ACTIVE_GOAL = candidate465.candidate446.g07_v7_active_goal_for_actor

_event_tactical_memories: dict[tuple[str, str, str], TacticalMemory] = {}
_event_last_tactical_mode: dict[tuple[str, str, str], str] = {}
_active_transaction_by_actor: dict[str, tuple[str, str, str]] = {}
_lifecycle_memories: dict[tuple[str, str, str], EngagementLifecycleMemory] = {}
_lifecycle_rows: list[dict[str, Any]] = []
_actual_readiness_deferred: set[tuple[str, str, str]] = set()


def _current_frame(event: Any | None = None) -> int:
    context = candidate474._pending_tactical_context or {}
    if context.get("frame") is not None:
        return int(context["frame"])
    return int(getattr(event, "start_frame", 0) or 0)


def _sync_pending_tactical_context(tactical: Any) -> None:
    context = candidate474._pending_tactical_context
    if context is None:
        return
    context["currentTacticalMode"] = str(tactical.mode)
    context["tacticalTransition"] = bool(tactical.transition)
    context["speedIntent"] = str(tactical.speed_intent)
    context["tacticalReason"] = str(tactical.reason)
    context["cycle"] = int(tactical.cycle)


def _copy_tactical_goal(dst: Any, src: Any) -> None:
    for name in (
        "mode",
        "reason",
        "speed_intent",
        "speed_scale",
        "forward_offset_scale",
        "lateral_offset_scale",
        "contact_commit",
        "brake_strength",
        "transition",
        "cycle",
        "stand_off_surface_gap_m",
    ):
        setattr(dst, name, getattr(src, name))
    _sync_pending_tactical_context(dst)


def _pair_from_key(key: tuple[str, str, str]) -> tuple[str, str]:
    return key[1], key[2]


def _clear_legacy_pair_state(pair_key: tuple[str, str]) -> None:
    """Remove historical pair-only caches when a transaction ends or recovers."""
    candidate474._previous_effective_gap.pop(pair_key, None)
    candidate474._defer_active.discard(pair_key)
    candidate474._progress_refresh_counts.pop(pair_key, None)
    candidate485._commit_defer_active.discard(pair_key)
    candidate485._realization_defer_active.discard(pair_key)
    candidate485._alignment_defer_active.discard(pair_key)
    candidate486._corridor_active.discard(pair_key)


def _mark_transition(
    key: tuple[str, str, str],
    *,
    frame: int,
    previous_phase: str,
    current_phase: str,
    reason: str,
    **extra: Any,
) -> None:
    if previous_phase == current_phase:
        return
    row = {
        "frame": int(frame),
        "eventId": key[0],
        "attackerId": key[1],
        "targetId": key[2] or None,
        "previousPhase": str(previous_phase),
        "phase": str(current_phase),
        "reason": str(reason),
        "model": MECHANISM,
        **extra,
    }
    _lifecycle_rows.append(row)
    marker("G04_ENGAGEMENT_LIFECYCLE_TRANSITION", **row)


def _set_phase(
    key: tuple[str, str, str],
    *,
    frame: int,
    phase: str,
    reason: str,
    **extra: Any,
) -> None:
    memory = _lifecycle_memories.setdefault(key, EngagementLifecycleMemory())
    previous = str(memory.phase)
    memory.transition(str(phase), int(frame))
    _mark_transition(
        key,
        frame=int(frame),
        previous_phase=previous,
        current_phase=str(memory.phase),
        reason=reason,
        **extra,
    )


def _end_transaction(entity: str, key: tuple[str, str, str], frame: int) -> None:
    _clear_legacy_pair_state(_pair_from_key(key))
    _actual_readiness_deferred.discard(key)
    battle_v6._last_tactical_mode.pop(entity, None)
    battle_v6._tactical_memories.pop(entity, None)
    marker(
        "G04_EVENT_TRANSACTION_ENDED",
        frame=int(frame),
        eventId=key[0],
        attackerId=key[1],
        targetId=key[2] or None,
        model=MECHANISM,
    )


def _scoped_active_goal(
    entity: str,
    frame: int,
    program: Any,
    states: dict[str, Any],
) -> Any | None:
    entity = str(entity)
    previous_key = _active_transaction_by_actor.get(entity)
    if previous_key is not None:
        previous_mode = battle_v6._last_tactical_mode.get(entity)
        if previous_mode is not None:
            _event_last_tactical_mode[previous_key] = str(previous_mode)

    event = _BASE_ACTIVE_GOAL(entity, frame, program, states)
    if event is None:
        if previous_key is not None:
            _end_transaction(entity, previous_key, int(frame))
            _active_transaction_by_actor.pop(entity, None)
        return None

    key = transaction_key(event.event_id, entity, event.target_id)
    if previous_key is not None and previous_key != key:
        _end_transaction(entity, previous_key, int(frame))
        marker(
            "G04_EVENT_TRANSACTION_CHANGED",
            frame=int(frame),
            previousEventId=previous_key[0],
            eventId=key[0],
            attackerId=key[1],
            targetId=key[2] or None,
            model=MECHANISM,
        )

    tactical_memory = _event_tactical_memories.setdefault(key, TacticalMemory())
    battle_v6._tactical_memories[entity] = tactical_memory
    if key in _event_last_tactical_mode:
        battle_v6._last_tactical_mode[entity] = _event_last_tactical_mode[key]
    else:
        battle_v6._last_tactical_mode.pop(entity, None)
    _active_transaction_by_actor[entity] = key
    _lifecycle_memories.setdefault(key, EngagementLifecycleMemory())
    return event


def event_scoped_generic_battle_set_controls(
    frame: int,
    program: Any,
    actors: dict[str, Any],
    states: dict[str, Any],
    control_samples: list[dict[str, Any]],
) -> None:
    battle_v6.set_controls(
        frame,
        program,
        actors,
        states,
        control_samples,
        active_goal_resolver=_scoped_active_goal,
    )

    for entity, key in tuple(_active_transaction_by_actor.items()):
        mode = battle_v6._last_tactical_mode.get(entity)
        if mode is not None:
            _event_last_tactical_mode[key] = str(mode)
        if (key[0], entity) in battle_v6._handoff_latches:
            _set_phase(
                key,
                frame=int(frame),
                phase=PHASE_HANDOFF_READY,
                reason="SOLVER_HANDOFF_LATCH_ACTIVE",
            )

    changes = candidate465.stabilize_active_handoff_cutoff_frames(
        candidate465.hardened._cutoff_frames,
        battle_v6._handoff_latches,
    )
    for change in changes:
        marker_key = (
            str(change["eventId"]),
            str(change["actorId"]),
            int(change["authoritativeCutoffFrame"]),
        )
        if marker_key in candidate465._cutoff_stabilization_announced:
            continue
        candidate465._cutoff_stabilization_announced.add(marker_key)
        marker(
            "GENERIC_SOLVER_HANDOFF_CUTOFF_FRAME_STABILIZED",
            frame=int(frame),
            eventId=change["eventId"],
            actorId=change["actorId"],
            previousCutoffFrame=change["previousCutoffFrame"],
            authoritativeCutoffFrame=change["authoritativeCutoffFrame"],
            model=candidate465.CUTOFF_FRAME_AUTHORITY_MODEL,
        )


def actual_goal_lifecycle_goal_for_tactical(
    actor: Any,
    target: Any,
    event: Any,
    tactical: Any,
    actors: dict[str, Any],
) -> Vector:
    actor_id = str(actor.profile.entity_id)
    target_id = str(target.profile.entity_id)
    key = transaction_key(event.event_id, actor_id, target_id)
    tactical_memory = _event_tactical_memories.setdefault(key, TacticalMemory())
    frame = _current_frame(event)

    goal_point = _BASE_GOAL_FOR_TACTICAL(actor, target, event, tactical, actors)
    position = actor.chassis.matrix_world.translation.copy()
    q = actor.chassis.matrix_world.to_quaternion()
    forward = q @ Vector((1.0, 0.0, 0.0))
    forward.z = 0.0
    if forward.length <= 1.0e-8:
        forward = Vector((1.0, 0.0, 0.0))
    else:
        forward.normalize()
    target_vector = goal_point - position
    target_vector.z = 0.0
    raw_heading = physics.signed_heading_error(forward, target_vector)
    actual_heading = motion_heading_error(raw_heading, tactical.speed_intent)
    contention = float(
        control_v2._contention_score(actor_id, actor, actors, event.target_id)
    )

    autonomy_memory = battle_v6._autonomy_memories.get((event.event_id, actor_id))
    recovery_active = bool(
        autonomy_memory is not None and is_recovery_mode(autonomy_memory.mode)
    )

    pair = candidate474._active_pair_context or {}
    if str(pair.get("attackerId") or "") != actor_id or str(pair.get("targetId") or "") != target_id:
        raise RuntimeError("G04_EVENT_SCOPED_PAIR_CONTEXT_MISMATCH")
    surface_gap = float(pair.get("radialGapM", 0.0))

    actual_ready = live_contact_commit_ready(
        requires_contact=bool(event.requires_contact),
        engagement_runway_armed=bool(tactical_memory.engagement_runway_armed),
        heading_error_rad=float(actual_heading),
        contention=float(contention),
    )
    action = precontact_action(
        tactical_mode=str(tactical.mode),
        requires_contact=bool(event.requires_contact),
        recovery_active=recovery_active,
        runway_armed=bool(tactical_memory.engagement_runway_armed),
        contact_ready=bool(actual_ready),
        surface_gap_m=float(surface_gap),
        runway_required_m=float(tactical_memory.engagement_runway_required_m),
    )

    if action == DEFER_TO_TACTIC:
        return goal_point

    if action == SUSPEND_FOR_RECOVERY:
        tactical.contact_commit = False
        _set_phase(
            key,
            frame=frame,
            phase=PHASE_RECOVERING,
            reason="LOW_LEVEL_RECOVERY_OWNS_MOTOR_AUTHORITY",
        )
        return goal_point

    if action == REOPEN_DISTANCE:
        tactical_memory.engagement_runway_armed = False
        replacement = GenericBattleTacticalPlanner._open_distance(
            tactical_memory,
            max(0.20, min(1.0, float(tactical.speed_scale))),
            bool(tactical.transition),
            "ACTUAL_GOAL_READINESS_RUNWAY_REOPEN",
        )
        _copy_tactical_goal(tactical, replacement)
        _actual_readiness_deferred.add(key)
        _set_phase(
            key,
            frame=frame,
            phase=PHASE_RUNWAY_REOPEN,
            reason="ACTUAL_NAVIGATION_GOAL_NOT_READY_INSIDE_RUNWAY",
            actualHeadingErrorRad=float(actual_heading),
            contention=float(contention),
            surfaceGapM=float(surface_gap),
            runwayRequiredM=float(tactical_memory.engagement_runway_required_m),
        )
        return _BASE_GOAL_FOR_TACTICAL(actor, target, event, tactical, actors)

    if action == HOLD_STANDOFF:
        transition = GenericBattleTacticalPlanner._set_mode(
            tactical_memory,
            "REPOSITION",
            "ACTUAL_GOAL_READINESS_STANDOFF_ALIGN",
        ) or bool(tactical.transition)
        tactical.mode = "REPOSITION"
        tactical.reason = tactical_memory.reason
        tactical.speed_intent = "ACCELERATE"
        tactical.speed_scale = min(max(0.18, float(tactical.speed_scale)), 0.68)
        tactical.forward_offset_scale = 0.0
        tactical.lateral_offset_scale = 0.0
        tactical.contact_commit = False
        tactical.brake_strength = 0.0
        tactical.transition = bool(transition)
        tactical.stand_off_surface_gap_m = max(
            0.0, float(tactical_memory.engagement_runway_required_m)
        )
        _sync_pending_tactical_context(tactical)
        _actual_readiness_deferred.add(key)
        _set_phase(
            key,
            frame=frame,
            phase=PHASE_ALIGN_STANDOFF,
            reason="ACTUAL_NAVIGATION_GOAL_ALIGNMENT_AT_SAFE_RUNWAY",
            actualHeadingErrorRad=float(actual_heading),
            contention=float(contention),
            surfaceGapM=float(surface_gap),
            runwayRequiredM=float(tactical_memory.engagement_runway_required_m),
        )
        return _BASE_GOAL_FOR_TACTICAL(actor, target, event, tactical, actors)

    if action == ALLOW_CONTACT:
        tactical.contact_commit = True
        if key in _actual_readiness_deferred:
            _actual_readiness_deferred.discard(key)
            marker(
                "G04_ACTUAL_GOAL_CONTACT_READINESS_RECOVERED",
                frame=frame,
                eventId=key[0],
                attackerId=key[1],
                targetId=key[2] or None,
                actualHeadingErrorRad=round(float(actual_heading), 6),
                contention=round(float(contention), 6),
                surfaceGapM=round(float(surface_gap), 6),
                runwayRequiredM=round(
                    float(tactical_memory.engagement_runway_required_m), 6
                ),
                model=MECHANISM,
            )
        _set_phase(
            key,
            frame=frame,
            phase=PHASE_APPROACH,
            reason="ACTUAL_NAVIGATION_GOAL_READY_FOR_CONTACT_APPROACH",
        )
    return goal_point


def event_scoped_recovery_autonomy_update(
    memory: Any,
    obs: Any,
    *,
    recovery_bias: float = 1.0,
) -> Any:
    pair = candidate474._active_pair_context or {}
    attacker_id = str(pair.get("attackerId") or "")
    target_id = str(pair.get("targetId") or "")
    key = _active_transaction_by_actor.get(attacker_id)
    if key is None:
        raise RuntimeError("G04_EVENT_SCOPED_TRANSACTION_CONTEXT_MISSING")
    if key[2] != target_id:
        raise RuntimeError("G04_EVENT_SCOPED_TRANSACTION_TARGET_MISMATCH")
    lifecycle = _lifecycle_memories.setdefault(key, EngagementLifecycleMemory())

    pair_key = (attacker_id, target_id)
    deferred = bool(
        pair_key[0]
        and pair_key[1]
        and pair_key in candidate474._defer_active
    )
    effective_gap = pair.get("effectiveCollisionProxyGapM")
    handoff_gap = ClosedLoopGoalController.contact_handoff_gap(obs)
    timeout = ClosedLoopGoalController.progress_timeout_frames(obs)
    previous_progress_frame = int(memory.last_progress_frame)
    previous_mode = str(memory.mode or "")

    if deferred_handoff_stalled(
        handoff_deferred=deferred,
        effective_collision_proxy_gap_m=(
            float(effective_gap) if effective_gap is not None else None
        ),
        existing_handoff_gap_m=float(handoff_gap),
        last_command_speed_mps=float(memory.last_command_speed_mps),
        frame=int(obs.frame),
        last_progress_frame=previous_progress_frame,
        progress_timeout_frames=int(timeout),
        controller_mode=previous_mode,
    ):
        ClosedLoopGoalController._begin_recovery(
            memory,
            obs,
            "COLLISION_PROXY_STALL_NO_PROGRESS",
            recovery_bias,
        )
        marker(
            "G04_EVENT_SCOPED_STALL_RECOVERY_TRIGGERED",
            frame=int(obs.frame),
            eventId=key[0],
            attackerId=key[1],
            targetId=key[2] or None,
            effectiveCollisionProxyGapM=float(effective_gap),
            existingHandoffGapM=float(handoff_gap),
            previousLastProgressFrame=previous_progress_frame,
            progressTimeoutFrames=int(timeout),
            model=MECHANISM,
        )

    command = candidate481._BASE_AUTONOMY_UPDATE(
        memory,
        obs,
        recovery_bias=recovery_bias,
    )
    current_mode = str(memory.mode or command.mode or "")
    started, completed = note_recovery_transition(
        lifecycle,
        frame=int(obs.frame),
        previous_controller_mode=previous_mode,
        current_controller_mode=current_mode,
    )

    if started:
        tactical_memory = _event_tactical_memories.get(key)
        if tactical_memory is not None:
            tactical_memory.engagement_runway_armed = False
        command.replan_triggered = True
        lifecycle.recovery_replan_reported = True
        marker(
            "G04_EVENT_SCOPED_RECOVERY_REPLAN_PROPAGATED",
            frame=int(obs.frame),
            eventId=key[0],
            attackerId=key[1],
            targetId=key[2] or None,
            controllerMode=current_mode,
            controllerReason=str(command.reason),
            recoveryEpoch=int(lifecycle.recovery_epoch),
            model=MECHANISM,
        )
    elif is_recovery_mode(current_mode):
        if lifecycle.recovery_replan_reported:
            command.replan_triggered = False
        else:
            command.replan_triggered = True
            lifecycle.recovery_replan_reported = True
            marker(
                "G04_EVENT_SCOPED_RECOVERY_REPLAN_PROPAGATED",
                frame=int(obs.frame),
                eventId=key[0],
                attackerId=key[1],
                targetId=key[2] or None,
                controllerMode=current_mode,
                controllerReason=str(command.reason),
                recoveryEpoch=int(lifecycle.recovery_epoch),
                model=MECHANISM,
            )

    if completed:
        tactical_memory = _event_tactical_memories.get(key)
        if tactical_memory is not None:
            tactical_memory.engagement_runway_armed = False
        _clear_legacy_pair_state(pair_key)
        _actual_readiness_deferred.add(key)
        marker(
            "G04_EVENT_SCOPED_RECOVERY_COMPLETED_RUNWAY_INVALIDATED",
            frame=int(obs.frame),
            eventId=key[0],
            attackerId=key[1],
            targetId=key[2] or None,
            recoveryEpoch=int(lifecycle.recovery_epoch),
            model=MECHANISM,
        )
    return command


def main() -> None:
    _event_tactical_memories.clear()
    _event_last_tactical_mode.clear()
    _active_transaction_by_actor.clear()
    _lifecycle_memories.clear()
    _lifecycle_rows.clear()
    _actual_readiness_deferred.clear()

    # Supersede only C486's incomplete, mode-blind G04 corridor composition.
    # Historical source remains immutable. G05/G06/G07/G08 code and thresholds
    # remain untouched; existing C485 realized-motion and C484 alignment gates stay
    # in the controller chain.
    candidate486.corridor_aware_tactical_decide = candidate486._C485_TACTICAL_DECIDE
    battle_v6._goal_for_tactical = actual_goal_lifecycle_goal_for_tactical
    candidate481.defer_progress_aware_base_autonomy_update = (
        event_scoped_recovery_autonomy_update
    )
    candidate465.generic_battle_set_controls = event_scoped_generic_battle_set_controls

    print(
        json.dumps(
            {
                "marker": "GENERIC_AUTONOMOUS_BATTLE_C487_ENGINEERING_READY",
                "candidate": CANDIDATE,
                "mechanism": MECHANISM,
                "affectedLayerAudit": AUDIT,
                "affectedLayerAuditStatus": "PASS",
                "failureFamily": FAILURE_FAMILY,
                "rootCausesClosedByDesign": [
                    "TACTICAL_AND_AUTONOMY_RECOVERY_OWNERSHIP_FRAGMENTED",
                    "C481_STALL_RECOVERY_DID_NOT_PROPAGATE_REPLAN_TO_EVENT_STATE",
                    "RECOVER_STATE_COULD_PERSIST_WHILE_TACTICAL_MODE_REMAINED_ENGAGE",
                    "C486_CORRIDOR_OVERRULED_NON_CONTACT_TACTICAL_MODES",
                    "CONTACT_READINESS_USED_TARGET_CENTER_HEADING_NOT_ACTUAL_NAVIGATION_GOAL",
                    "PAIR_ONLY_G04_CACHES_COULD_LEAK_ACROSS_SEQUENTIAL_EVENTS",
                    "TACTICAL_MUTATION_COULD_LEAVE_C474_PROGRESS_CONTEXT_STALE",
                ],
                "eventActorTargetTransactionScope": True,
                "eventScopedTacticalMemory": True,
                "actualNavigationGoalReadiness": True,
                "tacticalMutationProgressContextSynchronized": True,
                "modeAwareContactCorridor": True,
                "recoveryOwnsMotorAuthorityUntilCompletion": True,
                "recoveryReplanPropagatedExactlyOncePerEpoch": True,
                "runwayInvalidatedAfterRecovery": True,
                "legacyPairStateClearedOnEventTransition": True,
                "flankBrakeEvadeOwnershipPreserved": True,
                "c486ModeBlindCorridorSuperseded": True,
                "c485RealizedMotionHandoffPreserved": True,
                "c484AlignmentSemanticsPreserved": True,
                "c483DriveDirectionPreserved": True,
                "c482CollisionRolesPreserved": True,
                "c480SemanticTransactionPreserved": True,
                "g05NativeSolverFinalAuthorityPreserved": True,
                "g05SourceChanged": False,
                "g06SourceChanged": False,
                "g07SourceChanged": False,
                "g08SourceChanged": False,
                "g05ThresholdImported": False,
                "contactThresholdChanged": False,
                "semanticToleranceChanged": False,
                "localityToleranceChanged": False,
                "damageAdmissionThresholdChanged": False,
                "damageThresholdAwareControl": False,
                "targetToughnessAwareControl": False,
                "desiredImpactSpeedControl": False,
                "desiredImpactEnergyControl": False,
                "assetIdentityBranch": False,
                "perAssetBattleCode": False,
                "perAssetTacticalTuning": False,
                "perVideoTrajectoryEngineering": False,
                "fixedWorldCoordinates": False,
                "exactCollisionFrameTarget": False,
                "exactImpactEnergyTarget": False,
                "actorPoseOrVelocityMutation": False,
                "fixtureBattlePlanChanged": False,
                "frozenNineServiceArchitectureChanged": False,
                "gateClosed": False,
                "productionReadyClaimed": False,
            },
            sort_keys=True,
        ),
        flush=True,
    )

    candidate486.main()


if __name__ == "__main__":
    main()
