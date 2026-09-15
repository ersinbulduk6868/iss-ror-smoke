from __future__ import annotations

import json

import bpy
from mathutils import Vector


def reset() -> None:
    bpy.ops.wm.read_factory_settings(use_empty=True)
    scene = bpy.context.scene
    scene.frame_start = 1
    scene.frame_end = 10


def cube(name: str, location: tuple[float, float, float], scale: tuple[float, float, float]):
    bpy.ops.mesh.primitive_cube_add(size=1.0, location=location)
    obj = bpy.context.object
    obj.name = name
    obj.dimensions = scale
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    return obj


def add_rigid(obj, *, passive: bool) -> None:
    bpy.context.view_layer.objects.active = obj
    obj.select_set(True)
    bpy.ops.rigidbody.object_add()
    obj.rigid_body.type = "PASSIVE" if passive else "ACTIVE"
    obj.rigid_body.collision_shape = "BOX"
    obj.rigid_body.use_margin = True
    obj.rigid_body.collision_margin = 0.02
    obj.select_set(False)


def row(result) -> dict[str, object]:
    object_location, hitpoint, normal, has_hit = result
    return {
        "objectLocation": [round(float(v), 6) for v in object_location],
        "hitpoint": [round(float(v), 6) for v in hitpoint],
        "normal": [round(float(v), 6) for v in normal],
        "hasHit": int(has_hit),
    }


def main() -> None:
    reset()
    mover = cube("G05_SWEEP_MOVER", (-4.0, 0.0, 0.0), (1.0, 1.0, 1.0))
    target = cube("G05_SWEEP_TARGET", (0.0, 0.0, 0.0), (2.0, 2.0, 2.0))
    add_rigid(mover, passive=False)
    add_rigid(target, passive=True)
    scene = bpy.context.scene
    if scene.rigidbody_world is None:
        raise RuntimeError("G05_RIGIDBODY_WORLD_MISSING")
    world = scene.rigidbody_world
    world.substeps_per_frame = 10
    world.solver_iterations = 20
    bpy.context.view_layer.update()

    if not hasattr(world, "convex_sweep_test"):
        raise RuntimeError("G05_CONVEX_SWEEP_API_MISSING")

    positive = row(
        world.convex_sweep_test(
            mover,
            Vector((-4.0, 0.0, 0.0)),
            Vector((4.0, 0.0, 0.0)),
        )
    )
    near_miss = row(
        world.convex_sweep_test(
            mover,
            Vector((-4.0, 2.1, 0.0)),
            Vector((4.0, 2.1, 0.0)),
        )
    )
    empty_path = row(
        world.convex_sweep_test(
            mover,
            Vector((-4.0, -4.0, 0.0)),
            Vector((-4.0, -8.0, 0.0)),
        )
    )

    if positive["hasHit"] != 1:
        raise RuntimeError(f"G05_NATIVE_SWEEP_POSITIVE_MISS:{positive}")
    if near_miss["hasHit"] != 0:
        raise RuntimeError(f"G05_NATIVE_SWEEP_NEAR_MISS_FALSE_POSITIVE:{near_miss}")
    if empty_path["hasHit"] != 0:
        raise RuntimeError(f"G05_NATIVE_SWEEP_SELF_OR_EMPTY_FALSE_POSITIVE:{empty_path}")

    hit_x = float(positive["hitpoint"][0])
    if not (-1.25 <= hit_x <= -0.75):
        raise RuntimeError(f"G05_NATIVE_SWEEP_HITPOINT_UNEXPECTED:{positive}")

    print(
        json.dumps(
            {
                "marker": "G05_BLENDER_NATIVE_CONVEX_SWEEP_PROBE",
                "status": "PASS",
                "blenderVersion": bpy.app.version_string,
                "api": "RigidBodyWorld.convex_sweep_test",
                "positive": positive,
                "nearMiss": near_miss,
                "emptyPath": empty_path,
                "selfHitContamination": False,
                "obbUsed": False,
                "poseVelocityMutation": False,
                "runtimeIntegrationClaimed": False,
            },
            sort_keys=True,
        ),
        flush=True,
    )


if __name__ == "__main__":
    main()
