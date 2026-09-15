from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

import bpy
from mathutils import Vector

from blender import iss_blender_battle_runtime_v1 as runtime
from blender import iss_blender_battle_runtime_v1_hardened as hardened
from blender import run_generic_battle_runtime_v1_candidate39 as candidate39
from blender import run_generic_battle_runtime_v1_candidate40 as candidate40
from blender.iss_battle_runtime_assets import BlenderBattleRuntimeError, marker
from blender.iss_battle_runtime_physics import PendingContact

CANDIDATE = "ISS_GENERIC_BATTLE_RUNTIME_V1_CANDIDATE_4_1_G05"
NATIVE_CONTACT_MODEL = "BLENDER_NATIVE_ACTUAL_STEP_SWEEP_PLUS_SOLVER_RESPONSE_V1"
NATIVE_API = "RigidBodyWorld.convex_sweep_test"
PATH_AUTHORITY = "ACTUAL_SOLVER_STEP_ONLY"

_ORIGINAL_HARDENED_RESOLVE = candidate39._original_hardened_resolve_pending_contacts
_ORIGINAL_C39_COALESCING_RESOLVE = candidate39.coalescing_resolve_pending_contacts


def _v3(value: Vector) -> list[float]:
    return [round(float(x), 6) for x in value]


def _world() -> Any:
    world = bpy.context.scene.rigidbody_world
    if world is None:
        raise BlenderBattleRuntimeError("G05_NATIVE_RIGIDBODY_WORLD_MISSING")
    if not hasattr(world, "convex_sweep_test"):
        raise BlenderBattleRuntimeError("G05_NATIVE_CONVEX_SWEEP_API_MISSING")
    return world


def _identity_margin(actor: Any) -> float:
    dims = actor.chassis.dimensions
    smallest = min(float(dims.x), float(dims.y), float(dims.z))
    return max(0.02, min(0.12, smallest * 0.05))


def _point_inside_actor(actor: Any, point_world: Vector) -> bool:
    local = actor.chassis.matrix_world.inverted_safe() @ point_world
    half = actor.chassis.dimensions * 0.5
    margin = _identity_margin(actor)
    return bool(
        abs(float(local.x)) <= float(half.x) + margin
        and abs(float(local.y)) <= float(half.y) + margin
        and abs(float(local.z)) <= float(half.z) + margin
    )


def _controller_handoff(
    event_id: str,
    attacker_id: str,
    attacker: Any,
    frame: int,
    fps: int,
) -> tuple[bool, int | None, bool]:
    motors = attacker.rig.motors_left + attacker.rig.motors_right
    motor_authority_zero = all(
        float(m.rigid_body_constraint.motor_ang_max_impulse) <= 1.0e-9
        for m in motors
    )
    cutoff_frame = hardened._cutoff_frames.get((event_id, attacker_id))
    recent_cutoff = bool(
        cutoff_frame is not None
        and cutoff_frame <= frame
        and frame - cutoff_frame <= max(2, int(fps))
    )
    return bool(motor_authority_zero and recent_cutoff), cutoff_frame, motor_authority_zero


def _native_receipt(
    *,
    frame: int,
    event: Any,
    attacker_id: str,
    attacker: Any,
    target: Any,
    actors: dict[str, Any],
    program: Any,
) -> dict[str, Any] | None:
    previous = attacker.motion.get(frame - 1)
    current = attacker.motion.get(frame)
    if previous is None or current is None:
        return None

    start = previous[0].copy()
    end = current[0].copy()
    displacement = end - start
    if displacement.length <= 1.0e-6:
        return None

    world = _world()
    try:
        object_location, hitpoint_raw, normal_raw, has_hit = world.convex_sweep_test(
            attacker.chassis,
            start,
            end,
        )
    except RuntimeError as exc:
        raise BlenderBattleRuntimeError(
            f"G05_NATIVE_CONTACT_QUERY_FAILED:{event.event_id}:{attacker_id}:{exc}"
        ) from exc

    if int(has_hit) != 1:
        return None

    hitpoint = Vector(hitpoint_raw)
    native_outward_normal = Vector(normal_raw)
    if native_outward_normal.length <= 1.0e-7:
        marker(
            "G05_NATIVE_HIT_REJECTED_ZERO_NORMAL",
            frame=frame,
            eventId=event.event_id,
            attackerId=attacker_id,
            targetId=event.target_id,
        )
        return None
    native_outward_normal.normalize()

    # Ground contacts report a predominantly vertical normal.  G05 contact truth is
    # actor-to-actor authority; vertical environment contacts are not battle hits.
    horizontal_normal = Vector((native_outward_normal.x, native_outward_normal.y, 0.0))
    if horizontal_normal.length <= 0.35:
        marker(
            "G05_NATIVE_HIT_REJECTED_ENVIRONMENT_NORMAL",
            frame=frame,
            eventId=event.event_id,
            attackerId=attacker_id,
            targetId=event.target_id,
            hitpoint=_v3(hitpoint),
            normal=_v3(native_outward_normal),
        )
        return None

    matching_actor_ids = sorted(
        actor_id
        for actor_id, actor in actors.items()
        if actor_id != attacker_id and _point_inside_actor(actor, hitpoint)
    )
    if matching_actor_ids != [str(event.target_id)]:
        marker(
            "G05_NATIVE_HIT_REJECTED_TARGET_IDENTITY",
            frame=frame,
            eventId=event.event_id,
            attackerId=attacker_id,
            intendedTargetId=event.target_id,
            matchingActorIds=matching_actor_ids,
            hitpoint=_v3(hitpoint),
        )
        return None

    zone_point = target.zone_world(event.target_zone)
    semantic_distance = float((hitpoint - zone_point).length)
    semantic_tolerance = float(runtime._semantic_tolerance(target, event.target_zone))
    if semantic_distance > semantic_tolerance:
        marker(
            "G05_NATIVE_HIT_REJECTED_SEMANTIC_ZONE",
            frame=frame,
            eventId=event.event_id,
            attackerId=attacker_id,
            targetId=event.target_id,
            targetZone=event.target_zone,
            semanticDistance=round(semantic_distance, 6),
            semanticTolerance=round(semantic_tolerance, 6),
        )
        return None

    controller_handoff, cutoff_frame, motor_authority_zero = _controller_handoff(
        event.event_id,
        attacker_id,
        attacker,
        frame,
        program.fps,
    )
    if not controller_handoff:
        marker(
            "G05_NATIVE_HIT_REJECTED_CONTROLLER_AUTHORITY",
            frame=frame,
            eventId=event.event_id,
            attackerId=attacker_id,
            targetId=event.target_id,
            cutoffFrame=cutoff_frame,
            motorAuthorityZero=motor_authority_zero,
        )
        return None

    # Blender returns the outward normal of the hit object.  ImpactModel expects the
    # contact normal pointing from attacker toward target, so invert it once.
    contact_normal = -native_outward_normal
    receipt = {
        "status": "VERIFIED",
        "model": NATIVE_CONTACT_MODEL,
        "api": NATIVE_API,
        "pathAuthority": PATH_AUTHORITY,
        "frame": int(frame),
        "eventId": str(event.event_id),
        "attackerId": str(attacker_id),
        "targetId": str(event.target_id),
        "targetZone": event.target_zone,
        "sweepStart": _v3(start),
        "sweepEnd": _v3(end),
        "sweepDistanceM": round(float(displacement.length), 6),
        "objectLocation": _v3(Vector(object_location)),
        "hitpoint": _v3(hitpoint),
        "nativeOutwardNormal": _v3(native_outward_normal),
        "contactNormalTowardTarget": _v3(contact_normal),
        "targetIdentityUnique": True,
        "matchingActorIds": matching_actor_ids,
        "semanticDistance": round(semantic_distance, 6),
        "semanticTolerance": round(semantic_tolerance, 6),
        "semanticPass": True,
        "controllerCutoffObserved": True,
        "cutoffFrame": int(cutoff_frame) if cutoff_frame is not None else None,
        "motorAuthorityZero": bool(motor_authority_zero),
        "obbUsed": False,
        "predictiveExtensionUsed": False,
        "actorPoseOrVelocityMutation": False,
    }
    marker(
        "BLENDER_NATIVE_ACTUAL_STEP_CONTACT_VERIFIED",
        frame=frame,
        eventId=event.event_id,
        attackerId=attacker_id,
        targetId=event.target_id,
        targetZone=event.target_zone,
        hitpoint=receipt["hitpoint"],
        semanticDistance=receipt["semanticDistance"],
        model=NATIVE_CONTACT_MODEL,
    )
    return receipt


def native_detect_contacts(
    frame: int,
    program: Any,
    actors: dict[str, Any],
    states: dict[str, Any],
    pending: list[PendingContact],
    cooldown: dict[tuple[str, str, str], int],
) -> None:
    pending_keys = {
        (item.event_id, item.attacker_id, item.target_id)
        for item in pending
    }
    for event in program.events:
        state = states[event.event_id]
        if not event.requires_contact or state.status in hardened.TERMINAL:
            continue
        if not event.target_id or event.target_id not in actors:
            continue
        if not hardened._lifecycle.dependencies_ready(event, states):
            continue
        grace = program.fps if program.policies.get("replanOnPhysicalImpossibility", True) else 0
        if not (
            event.start_frame
            <= frame
            <= min(program.total_frames, event.end_frame + grace)
        ):
            continue

        target = actors[event.target_id]
        for attacker_id in runtime.WaveScheduler.active_attackers(event, frame):
            if attacker_id not in actors:
                continue
            attacker = actors[attacker_id]
            if attacker.state.disabled:
                continue
            key = (event.event_id, attacker_id, event.target_id)
            if key in pending_keys or cooldown.get(key, 0) > frame:
                continue

            receipt = _native_receipt(
                frame=frame,
                event=event,
                attacker_id=attacker_id,
                attacker=attacker,
                target=target,
                actors=actors,
                program=program,
            )
            if receipt is None:
                continue

            contact_point = Vector(receipt["hitpoint"])
            contact_normal = Vector(receipt["contactNormalTowardTarget"])
            item = PendingContact(
                event_id=event.event_id,
                attacker_id=attacker_id,
                target_id=event.target_id,
                target_zone=event.target_zone,
                frame=int(frame),
                resolve_frame=min(program.total_frames, frame + 2),
                pre_attacker_velocity=attacker.velocity.get(frame, Vector()).copy(),
                pre_target_velocity=target.velocity.get(frame, Vector()).copy(),
                contact_point=contact_point,
                contact_normal=contact_normal,
                semantic_distance=float(receipt["semanticDistance"]),
                controller_cutoff_observed=True,
            )
            setattr(item, "native_contact_verified", True)
            setattr(item, "native_contact_receipt", receipt)
            pending.append(item)
            pending_keys.add(key)
            cooldown[key] = frame + max(3, program.fps // 4)


def native_resolve_pending_contacts(
    frame: int,
    actors: dict[str, Any],
    states: dict[str, Any],
    events_by_id: dict[str, Any],
    pending: list[PendingContact],
    camera: Any,
    impact_log: list[dict[str, Any]],
) -> None:
    due_receipts: dict[tuple[str, int], dict[str, Any]] = {}
    for item in pending:
        if frame < item.resolve_frame:
            continue
        receipt = getattr(item, "native_contact_receipt", None)
        verified = bool(getattr(item, "native_contact_verified", False))
        if not verified or not isinstance(receipt, dict) or receipt.get("status") != "VERIFIED":
            raise BlenderBattleRuntimeError(
                f"G05_PENDING_CONTACT_WITHOUT_NATIVE_AUTHORITY:{item.event_id}:{item.frame}"
            )
        due_receipts[(item.event_id, int(item.frame))] = receipt

    start = len(impact_log)
    _ORIGINAL_HARDENED_RESOLVE(
        frame,
        actors,
        states,
        events_by_id,
        pending,
        camera,
        impact_log,
    )
    for row in impact_log[start:]:
        evidence = row.get("evidence") or {}
        key = (str(row.get("eventId") or ""), int(evidence.get("frame") or -1))
        receipt = due_receipts.get(key)
        if receipt is None:
            raise BlenderBattleRuntimeError(
                f"G05_QUALIFIED_IMPACT_WITHOUT_NATIVE_RECEIPT:{key[0]}:{key[1]}"
            )
        row["nativeContactReceipt"] = receipt
        row["nativeContactAuthority"] = True
        marker(
            "G05_NATIVE_CONTACT_BOUND_TO_SOLVER_RESPONSE",
            frame=key[1],
            eventId=key[0],
            api=NATIVE_API,
            pathAuthority=PATH_AUTHORITY,
        )


def native_coalescing_resolve_pending_contacts(
    frame: int,
    actors: dict[str, Any],
    states: dict[str, Any],
    events_by_id: dict[str, Any],
    pending: list[Any],
    camera: Any,
    impact_log: list[dict[str, Any]],
) -> None:
    start = len(impact_log)
    _ORIGINAL_C39_COALESCING_RESOLVE(
        frame,
        actors,
        states,
        events_by_id,
        pending,
        camera,
        impact_log,
    )
    new_rows = impact_log[start:]
    physical_by_event = {
        str(row.get("eventId")): row
        for row in new_rows
        if row.get("nativeContactAuthority") is True
        and isinstance(row.get("nativeContactReceipt"), dict)
    }
    for row in new_rows:
        if row.get("coalescedPhysicalImpact") is not True:
            continue
        physical_id = str(row.get("physicalTransactionEventId") or "")
        physical = physical_by_event.get(physical_id)
        if physical is None:
            raise BlenderBattleRuntimeError(
                f"G05_COALESCED_EVENT_WITHOUT_NATIVE_PHYSICAL_TRANSACTION:{row.get('eventId')}:{physical_id}"
            )
        row["nativeContactReceipt"] = dict(physical["nativeContactReceipt"])
        row["nativeContactAuthority"] = True
        row["nativeContactInheritedFromPhysicalTransaction"] = True
        marker(
            "G05_RECIPROCAL_EVENT_INHERITS_NATIVE_PHYSICAL_TRANSACTION",
            frame=(row.get("evidence") or {}).get("frame"),
            eventId=row.get("eventId"),
            physicalTransactionEventId=physical_id,
            model=candidate39.RECIPROCAL_CONTACT_MODEL,
        )


def main() -> None:
    candidate39._original_hardened_detect_contacts = native_detect_contacts
    candidate39._original_hardened_resolve_pending_contacts = native_resolve_pending_contacts
    candidate39.coalescing_resolve_pending_contacts = native_coalescing_resolve_pending_contacts
    candidate40.CANDIDATE = CANDIDATE
    runtime.CONTACT_MODEL = NATIVE_CONTACT_MODEL

    print(
        json.dumps(
            {
                "marker": "GENERIC_BATTLE_RUNTIME_CANDIDATE41_G05_ENGINEERING_PASS",
                "candidate": CANDIDATE,
                "nativeContactModel": NATIVE_CONTACT_MODEL,
                "nativeApi": NATIVE_API,
                "pathAuthority": PATH_AUTHORITY,
                "g04AutonomySourceChanged": False,
                "candidate39AssetSemanticSourceChanged": False,
                "obbFinalContactAuthority": False,
                "predictiveSweepExtension": False,
                "assetSpecificBattleCode": False,
                "exactCollisionFrameTarget": False,
                "exactImpactEnergyTarget": False,
                "damageThresholdChanged": False,
                "contactThresholdChanged": False,
                "actorPoseOrVelocityMutation": False,
                "damageGateClaimed": False,
                "productionReadyClaimed": False,
            },
            sort_keys=True,
        ),
        flush=True,
    )
    candidate40.main()


if __name__ == "__main__":
    main()
