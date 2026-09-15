from __future__ import annotations

import json
import math

import bpy
from mathutils import Vector

from blender.iss_battle_runtime_assets import add_passive_rigid_body, add_rigid_body, cube
from blender.iss_battle_runtime_contract import ActorProfile
from blender.iss_battle_runtime_physics import create_drive_rig

MODEL = "G05_CONSTRAINED_DRIVE_RIG_SELF_COLLISION_AUDIT_V1"


def reset() -> None:
    bpy.ops.wm.read_factory_settings(use_empty=True)
    scene = bpy.context.scene
    scene.frame_start = 1
    scene.frame_end = 8
    scene.render.fps = 30
    scene.gravity = (0.0, 0.0, -9.81)
    if scene.rigidbody_world is None:
        bpy.ops.rigidbody.world_add()
    world = scene.rigidbody_world
    world.substeps_per_frame = 10
    world.solver_iterations = 30
    world.point_cache.frame_start = 1
    world.point_cache.frame_end = 8


def profile(entity: str) -> ActorProfile:
    return ActorProfile(
        entity_id=entity,
        mass_kg=1450.0,
        friction=1.0,
        restitution=0.03,
        max_speed_mps=18.0,
        max_reverse_mps=5.0,
        max_yaw_rate_rad_s=1.35,
        acceleration_mps2=7.0,
        braking_mps2=10.0,
        toughness_j_per_kg=72.0,
    )


def add_vehicle(entity: str, x: float):
    dims = Vector((4.42, 2.06, 1.36))
    wheel_radius = max(0.26, min(0.90, float(dims.z) * 0.24, float(dims.x) * 0.16))
    chassis_height = max(0.35, float(dims.z) * 0.62)
    center_z = wheel_radius + chassis_height * 0.52
    chassis = cube(
        f"G05_CHASSIS_{entity}",
        (x, 0.0, center_z),
        (dims.x * 0.91, dims.y * 0.84, chassis_height),
    )
    add_rigid_body(
        chassis,
        mass=1450.0,
        shape="BOX",
        friction=0.22,
        restitution=0.03,
    )
    rig = create_drive_rig(entity, chassis, dims, profile(entity), 0.0)
    return chassis, rig


def set_pair_collision_disabled(rig, value: bool) -> None:
    constraints = rig.hinges + rig.motors_left + rig.motors_right
    for obj in constraints:
        obj.rigid_body_constraint.disable_collisions = bool(value)


def initialize() -> None:
    scene = bpy.context.scene
    scene.frame_set(1)
    bpy.context.view_layer.update()
    scene.frame_set(2)
    bpy.context.view_layer.update()


def inside(obj: bpy.types.Object, point: Vector, margin: float = 0.08) -> bool:
    local = obj.matrix_world.inverted_safe() @ point
    half = obj.dimensions * 0.5
    return bool(
        abs(float(local.x)) <= float(half.x) + margin
        and abs(float(local.y)) <= float(half.y) + margin
        and abs(float(local.z)) <= float(half.z) + margin
    )


def classify(point: Vector, attacker_chassis, attacker_rig, target_chassis, target_rig, ground) -> list[str]:
    rows: list[str] = []
    if inside(attacker_chassis, point):
        rows.append("ATTACKER_CHASSIS")
    for idx, wheel in enumerate(attacker_rig.wheels_left + attacker_rig.wheels_right):
        if inside(wheel, point):
            rows.append(f"ATTACKER_WHEEL_{idx}")
    if inside(target_chassis, point):
        rows.append("TARGET_CHASSIS")
    for idx, wheel in enumerate(target_rig.wheels_left + target_rig.wheels_right):
        if inside(wheel, point):
            rows.append(f"TARGET_WHEEL_{idx}")
    if inside(ground, point, margin=0.03):
        rows.append("GROUND")
    return rows


def scenario(*, disable_pair_collisions: bool) -> dict[str, object]:
    reset()
    attacker_chassis, attacker_rig = add_vehicle("alpha", -5.0)
    target_chassis, target_rig = add_vehicle("beta", 3.0)
    set_pair_collision_disabled(attacker_rig, disable_pair_collisions)
    set_pair_collision_disabled(target_rig, disable_pair_collisions)
    ground = cube("G05_GROUND", (0.0, 0.0, -0.5), (40.0, 20.0, 1.0))
    add_passive_rigid_body(ground, shape="BOX", friction=1.15)
    initialize()

    world = bpy.context.scene.rigidbody_world
    assert world is not None
    start = attacker_chassis.matrix_world.translation.copy()
    end = Vector((5.5, float(start.y), float(start.z)))
    result = world.convex_sweep_test(attacker_chassis, start, end)
    object_location, hitpoint_raw, normal_raw, has_hit = result
    hitpoint = Vector(hitpoint_raw)
    normal = Vector(normal_raw)
    labels = classify(
        hitpoint,
        attacker_chassis,
        attacker_rig,
        target_chassis,
        target_rig,
        ground,
    ) if int(has_hit) == 1 else []
    own_hit = any(x.startswith("ATTACKER_") for x in labels)
    target_hit = any(x.startswith("TARGET_") for x in labels)
    return {
        "disableConstrainedPairCollisions": disable_pair_collisions,
        "constraintCount": len(attacker_rig.hinges + attacker_rig.motors_left + attacker_rig.motors_right),
        "constraintDisableStates": sorted({
            bool(x.rigid_body_constraint.disable_collisions)
            for x in attacker_rig.hinges + attacker_rig.motors_left + attacker_rig.motors_right
        }),
        "hasHit": int(has_hit),
        "objectLocation": [round(float(x), 6) for x in object_location],
        "hitpoint": [round(float(x), 6) for x in hitpoint],
        "normal": [round(float(x), 6) for x in normal],
        "classification": labels,
        "ownRigContamination": own_hit,
        "targetActorHit": target_hit,
        "sweepStart": [round(float(x), 6) for x in start],
        "sweepEnd": [round(float(x), 6) for x in end],
        "poseVelocityInjection": False,
        "obbUsed": False,
    }


def main() -> None:
    baseline = scenario(disable_pair_collisions=False)
    isolated = scenario(disable_pair_collisions=True)

    if baseline["hasHit"] != 1:
        raise RuntimeError(f"G05_SELF_COLLISION_BASELINE_NO_HIT:{baseline}")
    if baseline["constraintDisableStates"] != [False]:
        raise RuntimeError(f"G05_SELF_COLLISION_BASELINE_CONSTRAINT_STATE_UNEXPECTED:{baseline}")
    if not baseline["ownRigContamination"]:
        raise RuntimeError(f"G05_SELF_COLLISION_BASELINE_CONTAMINATION_NOT_REPRODUCED:{baseline}")

    if isolated["constraintDisableStates"] != [True]:
        raise RuntimeError(f"G05_SELF_COLLISION_ISOLATION_CONSTRAINT_STATE_UNEXPECTED:{isolated}")
    if isolated["ownRigContamination"]:
        raise RuntimeError(f"G05_SELF_COLLISION_ISOLATION_FAILED:{isolated}")
    if isolated["hasHit"] != 1 or not isolated["targetActorHit"]:
        raise RuntimeError(f"G05_SELF_COLLISION_ISOLATION_DID_NOT_REACH_TARGET:{isolated}")

    print(json.dumps({
        "marker": "G05_DRIVE_RIG_SELF_COLLISION_AUDIT",
        "status": "PASS",
        "model": MODEL,
        "blenderVersion": bpy.app.version_string,
        "baseline": baseline,
        "isolated": isolated,
        "rootCause": "CONSTRAINED_CHASSIS_WHEEL_COLLISIONS_ENABLED",
        "genericFixProven": True,
        "runtimeIntegrationClaimed": False,
        "productionReadyClaimed": False,
    }, sort_keys=True), flush=True)


if __name__ == "__main__":
    main()
