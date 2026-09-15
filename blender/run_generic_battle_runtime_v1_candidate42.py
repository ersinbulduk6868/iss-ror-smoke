from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from mathutils import Quaternion, Vector

from blender import iss_blender_battle_runtime_v1 as runtime
from blender import iss_blender_battle_runtime_v1_hardened as hardened
from blender import run_generic_battle_runtime_v1_candidate39 as candidate39
from blender import run_generic_battle_runtime_v1_candidate40 as candidate40
from blender.iss_battle_runtime_assets import BlenderBattleRuntimeError, marker
from blender.iss_battle_runtime_contact_truth import (
    PAIRWISE_RESPONSE_MODEL,
    PairwiseSolverResponseOracle,
    PairwiseSolverSample,
)
from blender.iss_battle_runtime_physics import PendingContact

CANDIDATE = "ISS_GENERIC_BATTLE_RUNTIME_V1_CANDIDATE_4_2_G05"
CONTACT_AUTHORITY = PAIRWISE_RESPONSE_MODEL
LOCALITY_MODEL = "AUTHORITATIVE_CHASSIS_LOCALITY_V1"
SEMANTIC_MODEL = "EXISTING_TARGET_ZONE_TOLERANCE_V1"
SOLVER_WINDOW_MAX_FRAMES = 3

_ORIGINAL_HARDENED_RESOLVE = candidate39._original_hardened_resolve_pending_contacts
_ORIGINAL_C39_COALESCING_RESOLVE = candidate39.coalescing_resolve_pending_contacts


def _v3(value: Vector) -> list[float]:
    return [round(float(x), 6) for x in value]


def _support_radius_at(actor: Any, rotation: Quaternion, direction_world: Vector) -> float:
    direction = Vector(direction_world)
    direction.z = 0.0
    if direction.length <= 1.0e-8:
        return 0.0
    direction.normalize()
    local = rotation.inverted() @ direction
    half = actor.chassis.dimensions * 0.5
    return (
        abs(float(local.x)) * float(half.x)
        + abs(float(local.y)) * float(half.y)
        + abs(float(local.z)) * float(half.z)
    )


def _pair_geometry_at(attacker: Any, target: Any, frame: int) -> dict[str, Any] | None:
    a_pose = attacker.motion.get(frame)
    t_pose = target.motion.get(frame)
    if a_pose is None or t_pose is None:
        return None
    a_pos, a_rot = a_pose
    t_pos, t_rot = t_pose
    delta = t_pos - a_pos
    delta.z = 0.0
    center_distance = float(delta.length)
    if center_distance <= 1.0e-8:
        normal = Vector((1.0, 0.0, 0.0))
    else:
        normal = delta.normalized()
    attacker_support = _support_radius_at(attacker, a_rot, normal)
    target_support = _support_radius_at(target, t_rot, -normal)
    gap = center_distance - attacker_support - target_support
    target_surface = t_pos - normal * target_support
    return {
        "frame": int(frame),
        "attackerPosition": a_pos.copy(),
        "targetPosition": t_pos.copy(),
        "targetRotation": t_rot.copy(),
        "normal": normal,
        "centerDistanceM": center_distance,
        "attackerSupportM": attacker_support,
        "targetSupportM": target_support,
        "gapM": float(gap),
        "targetSurface": target_surface,
    }


def _collision_margin(actor: Any) -> float:
    rb = getattr(actor.chassis, "rigid_body", None)
    if rb is None:
        return 0.0
    use_margin = bool(getattr(rb, "use_margin", True))
    return max(0.0, float(getattr(rb, "collision_margin", 0.0))) if use_margin else 0.0


def _locality_tolerance(attacker: Any, target: Any) -> float:
    # This is a numerical locality tolerance derived from the solver collision
    # margins plus a fixed 4 cm frame-sampling allowance.  It is not an impact,
    # damage, semantic, or viewer-facing acceptance threshold.
    return float(_collision_margin(attacker) + _collision_margin(target) + 0.04)


def _historical_zone_world(target: Any, zone: str | None, geometry: dict[str, Any]) -> Vector:
    key = runtime.norm(zone) or "body"
    if key not in target.prototype.zones:
        raise BlenderBattleRuntimeError(
            f"G05_TARGET_SEMANTIC_ZONE_UNRESOLVED:{target.profile.entity_id}:{key}"
        )
    local = target.prototype.zones[key] + target.visual_offset
    return geometry["targetPosition"] + geometry["targetRotation"] @ local


def _controller_handoff(
    event_id: str,
    attacker_id: str,
    attacker: Any,
    contact_frame: int,
    fps: int,
) -> tuple[bool, int | None, bool]:
    motors = attacker.rig.motors_left + attacker.rig.motors_right
    motor_authority_zero = all(
        float(m.rigid_body_constraint.motor_ang_max_impulse) <= 1.0e-9
        for m in motors
    )
    cutoff_frame = hardened._cutoff_frames.get((event_id, attacker_id))
    recent = bool(
        cutoff_frame is not None
        and cutoff_frame <= contact_frame
        and contact_frame - cutoff_frame <= max(2, int(fps))
    )
    return bool(motor_authority_zero and recent), cutoff_frame, motor_authority_zero


def _best_recent_locality(attacker: Any, target: Any, frame: int) -> dict[str, Any] | None:
    start = max(2, int(frame) - SOLVER_WINDOW_MAX_FRAMES + 1)
    rows = [
        row
        for sample_frame in range(start, int(frame) + 1)
        if (row := _pair_geometry_at(attacker, target, sample_frame)) is not None
    ]
    if not rows:
        return None
    return min(rows, key=lambda row: (float(row["gapM"]), int(row["frame"])))


def _pairwise_receipt(
    *,
    frame: int,
    event: Any,
    attacker_id: str,
    attacker: Any,
    target: Any,
) -> tuple[dict[str, Any], dict[str, Any]] | None:
    geometry = _best_recent_locality(attacker, target, frame)
    if geometry is None:
        return None
    contact_frame = int(geometry["frame"])
    pre_frame = max(1, contact_frame - 1)
    if pre_frame not in attacker.velocity or pre_frame not in target.velocity:
        return None
    if frame not in attacker.velocity or frame not in target.velocity:
        return None

    locality_tolerance = _locality_tolerance(attacker, target)
    locality_gap = float(geometry["gapM"])
    if locality_gap > locality_tolerance:
        return None

    handoff, cutoff_frame, motor_authority_zero = _controller_handoff(
        event.event_id,
        attacker_id,
        attacker,
        contact_frame,
        runtime.bpy.context.scene.render.fps,
    )
    if not handoff:
        marker(
            "G05_PAIRWISE_RESPONSE_REJECTED_CONTROLLER_AUTHORITY",
            frame=frame,
            contactFrame=contact_frame,
            eventId=event.event_id,
            attackerId=attacker_id,
            targetId=event.target_id,
            cutoffFrame=cutoff_frame,
            motorAuthorityZero=motor_authority_zero,
        )
        return None

    normal = Vector(geometry["normal"])
    pre_a = attacker.velocity[pre_frame].copy()
    pre_t = target.velocity[pre_frame].copy()
    post_a = attacker.velocity[frame].copy()
    post_t = target.velocity[frame].copy()
    solver = PairwiseSolverResponseOracle.evaluate(
        PairwiseSolverSample.build(
            attacker_mass_kg=attacker.profile.mass_kg,
            target_mass_kg=target.profile.mass_kg,
            pre_attacker_velocity=pre_a,
            pre_target_velocity=pre_t,
            post_attacker_velocity=post_a,
            post_target_velocity=post_t,
            collision_normal_attacker_to_target=normal,
        )
    )
    if not solver.qualified:
        return None

    zone_point = _historical_zone_world(target, event.target_zone, geometry)
    contact_point = Vector(geometry["targetSurface"])
    semantic_distance = float((contact_point - zone_point).length)
    semantic_tolerance = float(runtime._semantic_tolerance(target, event.target_zone))
    if semantic_distance > semantic_tolerance:
        marker(
            "G05_PAIRWISE_RESPONSE_REJECTED_SEMANTIC_ZONE",
            frame=frame,
            contactFrame=contact_frame,
            eventId=event.event_id,
            attackerId=attacker_id,
            targetId=event.target_id,
            targetZone=event.target_zone,
            semanticDistance=round(semantic_distance, 6),
            semanticTolerance=round(semantic_tolerance, 6),
        )
        return None

    receipt = {
        "status": "VERIFIED",
        "model": CONTACT_AUTHORITY,
        "localityModel": LOCALITY_MODEL,
        "semanticModel": SEMANTIC_MODEL,
        "eventId": str(event.event_id),
        "attackerId": str(attacker_id),
        "targetId": str(event.target_id),
        "targetZone": event.target_zone,
        "solverPreFrame": int(pre_frame),
        "contactFrame": int(contact_frame),
        "solverPostFrame": int(frame),
        "preAttackerVelocity": _v3(pre_a),
        "preTargetVelocity": _v3(pre_t),
        "postAttackerVelocity": _v3(post_a),
        "postTargetVelocity": _v3(post_t),
        "contactNormalTowardTarget": _v3(normal),
        "contactPoint": _v3(contact_point),
        "pairwiseLocalityGapM": round(locality_gap, 6),
        "pairwiseLocalityToleranceM": round(locality_tolerance, 6),
        "localityPass": True,
        "semanticDistance": round(semantic_distance, 6),
        "semanticTolerance": round(semantic_tolerance, 6),
        "semanticPass": True,
        "controllerCutoffObserved": True,
        "cutoffFrame": int(cutoff_frame) if cutoff_frame is not None else None,
        "motorAuthorityZero": bool(motor_authority_zero),
        "pairwiseSolverReceipt": solver.as_dict(),
        "obbFinalContactAuthority": False,
        "nativeSweepFinalContactAuthority": False,
        "actorPoseOrVelocityMutation": False,
    }
    context = {
        "preAttackerVelocity": pre_a,
        "preTargetVelocity": pre_t,
        "contactPoint": contact_point,
        "contactNormal": normal,
        "semanticDistance": semantic_distance,
    }
    marker(
        "PAIRWISE_NATIVE_SOLVER_CONTACT_VERIFIED",
        frame=frame,
        contactFrame=contact_frame,
        eventId=event.event_id,
        attackerId=attacker_id,
        targetId=event.target_id,
        targetZone=event.target_zone,
        pairwiseLocalityGapM=receipt["pairwiseLocalityGapM"],
        semanticDistance=receipt["semanticDistance"],
        impulseBalanceRatio=round(float(solver.impulse_balance_ratio), 6),
        impulseOppositionCosine=round(float(solver.impulse_opposition_cosine), 6),
        model=CONTACT_AUTHORITY,
    )
    return receipt, context


def pairwise_detect_contacts(
    frame: int,
    program: Any,
    actors: dict[str, Any],
    states: dict[str, Any],
    pending: list[PendingContact],
    cooldown: dict[tuple[str, str, str], int],
) -> None:
    pending_keys = {(x.event_id, x.attacker_id, x.target_id) for x in pending}
    for event in program.events:
        state = states[event.event_id]
        if not event.requires_contact or state.status in hardened.TERMINAL:
            continue
        if not event.target_id or event.target_id not in actors:
            continue
        if not hardened._lifecycle.dependencies_ready(event, states):
            continue
        if frame < event.start_frame:
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

            verified = _pairwise_receipt(
                frame=frame,
                event=event,
                attacker_id=attacker_id,
                attacker=attacker,
                target=target,
            )
            if verified is None:
                continue
            receipt, context = verified
            contact_frame = int(receipt["contactFrame"])
            item = PendingContact(
                event_id=event.event_id,
                attacker_id=attacker_id,
                target_id=event.target_id,
                target_zone=event.target_zone,
                frame=contact_frame,
                resolve_frame=min(program.total_frames, frame + 1),
                pre_attacker_velocity=context["preAttackerVelocity"].copy(),
                pre_target_velocity=context["preTargetVelocity"].copy(),
                contact_point=context["contactPoint"].copy(),
                contact_normal=context["contactNormal"].copy(),
                semantic_distance=float(context["semanticDistance"]),
                controller_cutoff_observed=True,
            )
            setattr(item, "native_contact_authority", True)
            setattr(item, "native_contact_receipt", receipt)
            pending.append(item)
            pending_keys.add(key)
            cooldown[key] = frame + max(3, program.fps // 4)


def pairwise_resolve_pending_contacts(
    frame: int,
    actors: dict[str, Any],
    states: dict[str, Any],
    events_by_id: dict[str, Any],
    pending: list[PendingContact],
    camera: Any,
    impact_log: list[dict[str, Any]],
) -> None:
    due: dict[tuple[str, int], dict[str, Any]] = {}
    for item in pending:
        if frame < item.resolve_frame:
            continue
        receipt = getattr(item, "native_contact_receipt", None)
        if getattr(item, "native_contact_authority", False) is not True:
            raise BlenderBattleRuntimeError(
                f"G05_PENDING_WITHOUT_PAIRWISE_AUTHORITY:{item.event_id}:{item.frame}"
            )
        if not isinstance(receipt, dict) or receipt.get("status") != "VERIFIED":
            raise BlenderBattleRuntimeError(
                f"G05_PENDING_PAIRWISE_RECEIPT_INVALID:{item.event_id}:{item.frame}"
            )
        due[(item.event_id, int(item.frame))] = receipt

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
    bound: set[tuple[str, int]] = set()
    for row in impact_log[start:]:
        evidence = row.get("evidence") or {}
        key = (str(row.get("eventId") or ""), int(evidence.get("frame") or -1))
        receipt = due.get(key)
        if receipt is None:
            raise BlenderBattleRuntimeError(
                f"G05_QUALIFIED_IMPACT_WITHOUT_PAIRWISE_RECEIPT:{key[0]}:{key[1]}"
            )
        row["nativeContactReceipt"] = receipt
        row["nativeContactAuthority"] = True
        row["contactAuthorityModel"] = CONTACT_AUTHORITY
        bound.add(key)
        marker(
            "G05_PAIRWISE_CONTACT_BOUND_TO_EXISTING_IMPACT_GATE",
            frame=key[1],
            eventId=key[0],
            solverPreFrame=receipt["solverPreFrame"],
            solverPostFrame=receipt["solverPostFrame"],
            model=CONTACT_AUTHORITY,
        )

    for key, receipt in due.items():
        if key not in bound:
            marker(
                "G05_PAIRWISE_CONTACT_REJECTED_BY_EXISTING_IMPACT_GATE",
                frame=key[1],
                eventId=key[0],
                solverPreFrame=receipt["solverPreFrame"],
                solverPostFrame=receipt["solverPostFrame"],
                model=CONTACT_AUTHORITY,
            )


def pairwise_coalescing_resolve_pending_contacts(
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
                f"G05_COALESCED_EVENT_WITHOUT_PAIRWISE_PHYSICAL_TRANSACTION:{row.get('eventId')}:{physical_id}"
            )
        row["nativeContactReceipt"] = dict(physical["nativeContactReceipt"])
        row["nativeContactAuthority"] = True
        row["nativeContactInheritedFromPhysicalTransaction"] = True
        row["contactAuthorityModel"] = CONTACT_AUTHORITY
        marker(
            "G05_RECIPROCAL_EVENT_INHERITS_PAIRWISE_PHYSICAL_TRANSACTION",
            frame=(row.get("evidence") or {}).get("frame"),
            eventId=row.get("eventId"),
            physicalTransactionEventId=physical_id,
            model=CONTACT_AUTHORITY,
        )


def main() -> None:
    candidate39._original_hardened_detect_contacts = pairwise_detect_contacts
    candidate39._original_hardened_resolve_pending_contacts = pairwise_resolve_pending_contacts
    candidate39.coalescing_resolve_pending_contacts = pairwise_coalescing_resolve_pending_contacts
    candidate40.CANDIDATE = CANDIDATE
    runtime.CONTACT_MODEL = CONTACT_AUTHORITY

    print(
        json.dumps(
            {
                "marker": "GENERIC_BATTLE_RUNTIME_CANDIDATE42_G05_ENGINEERING_PASS",
                "candidate": CANDIDATE,
                "contactAuthorityModel": CONTACT_AUTHORITY,
                "pairwiseResponseOracle": "PairwiseSolverResponseOracle",
                "localityModel": LOCALITY_MODEL,
                "semanticModel": SEMANTIC_MODEL,
                "g04AutonomySourceChanged": False,
                "candidate39AssetSemanticSourceChanged": False,
                "obbFinalContactAuthority": False,
                "nativeSweepFinalContactAuthority": False,
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
