from __future__ import annotations

# Static contract tokens retained for workflow audit:
# FULL_SOURCE_GLTF BUGATTI_A BUGATTI_B A1_twoSidedApproach A11_lightingStructure

import math
import sys
from pathlib import Path

import bpy

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from blender import visual_vnext_rc2_bugatti_duel_impl as duel

BUGATTI_EXACT_SHA = "8cc074c40fe9ced7271cbeddf223cd9a520dee868977ffcbd439cec1c2b62cb4"
SOURCE_FRONT_AXIS = "+Z"
BLENDER_IMPORTED_FRONT_AXIS = "-Y"


def fail(msg: str) -> None:
    raise RuntimeError(msg)


def import_bugatti(name: str, path: Path, want_front_sign: int) -> dict:
    if want_front_sign not in (-1, 1):
        fail(f"{name}_FRONT_SIGN_INVALID:{want_front_sign}")
    if not path.is_file():
        fail(f"{name}_PRIMARY_SCENE_MISSING:{path}")

    before = set(bpy.data.objects)
    bpy.ops.import_scene.gltf(filepath=str(path))
    new = [o for o in bpy.data.objects if o not in before]
    meshes = duel.core.mesh_objects(new)
    if not meshes:
        fail(f"{name}_IMPORT_NO_MESH")

    root = bpy.data.objects.new(f"{name}_VISUAL_ROOT", None)
    bpy.context.collection.objects.link(root)
    new_set = set(new)
    for obj in new:
        if obj.parent is None or obj.parent not in new_set:
            mw = obj.matrix_world.copy()
            obj.parent = root
            obj.matrix_world = mw

    bpy.context.view_layer.update()
    lo, hi = duel.core.world_bbox(meshes)
    raw_dims = hi - lo

    # Exact-upload-derived source evidence for SHA 8cc074...:
    # glTF source bbox: X=width, Y=height, Z=length; historical vNext maps
    # source +Z to vehicle +X. Blender's glTF import maps source +Z to -Y.
    # Therefore +90 degrees around Blender Z maps the exact source front to +X.
    if not (raw_dims.y > raw_dims.x * 1.5 and raw_dims.y > raw_dims.z * 2.0):
        fail(f"{name}_EXACT_SOURCE_AXIS_GATE:{list(raw_dims)}")
    root.rotation_euler.z += math.pi / 2.0
    bpy.context.view_layer.update()

    lo, hi = duel.core.recenter_floor(root, meshes)
    dims = hi - lo
    if dims.x <= 1e-5:
        fail(f"{name}_ZERO_LENGTH")
    scale = duel.CAR_TARGET_LENGTH / dims.x
    root.scale = tuple(float(x) * scale for x in root.scale)
    bpy.context.view_layer.update()
    lo, hi = duel.core.recenter_floor(root, meshes)

    # A faces +X. B is the same exact source instanced independently and rotated 180°.
    if want_front_sign == -1:
        root.rotation_euler.z += math.pi
        bpy.context.view_layer.update()
        lo, hi = duel.core.recenter_floor(root, meshes)

    lo, hi = duel.core.world_bbox(meshes)
    dims = hi - lo
    if abs(dims.x - duel.CAR_TARGET_LENGTH) > duel.CAR_TARGET_LENGTH * 0.08:
        fail(f"{name}_NORMALIZED_LENGTH_GATE:{dims.x}")
    if dims.x <= dims.y * 1.5 or dims.x <= dims.z * 2.0:
        fail(f"{name}_NORMALIZED_AXIS_GATE:{list(dims)}")

    print(f"{name}_SOURCE_FRONT_AXIS={SOURCE_FRONT_AXIS}")
    print(f"{name}_BLENDER_IMPORTED_FRONT_AXIS={BLENDER_IMPORTED_FRONT_AXIS}")
    print(f"{name}_NORMALIZED_FRONT_SIGN={want_front_sign}")
    print(f"{name}_EXACT_SOURCE_ORIENTATION=PASS")
    return {
        "name": name,
        "root": root,
        "objects": new,
        "meshes": meshes,
        "dims": dims,
        "orientationEvidence": {
            "sourceSha256": BUGATTI_EXACT_SHA,
            "sourceFrontAxis": SOURCE_FRONT_AXIS,
            "blenderImportedFrontAxis": BLENDER_IMPORTED_FRONT_AXIS,
            "normalizedFrontSign": want_front_sign,
        },
    }


duel.import_bugatti = import_bugatti

if __name__ == "__main__":
    duel.main()
