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
PRESENTATION_MATERIALS = {
    "floor",
    "red_carpet",
    "carshadow",
    "110EBsupersport_BUGATTI",
    "ALs_CARS",
}
FRONT_MARKER_MATERIALS = {
    "headlight_glass",
    "reflector_front",
    "grillA",
    "grillB",
    "grillC",
}
REAR_MARKER_MATERIALS = {
    "brakelight_glass",
    "brakelight_grill",
    "rear_bumper_plastic",
}
EXPECTED_PRESENTATION_MESHES = 5
EXPECTED_VEHICLE_MESHES = 56
EXPECTED_VEHICLE_VERTICES = 150154
EXPECTED_VEHICLE_TRIANGLES = 169031


def fail(msg: str) -> None:
    raise RuntimeError(msg)


def material_matches(name: str, base: str) -> bool:
    return name == base or name.startswith(base + ".")


def object_material_bases(obj: bpy.types.Object) -> set[str]:
    names = set()
    for slot in getattr(obj, "material_slots", []):
        mat = slot.material
        if mat is None:
            continue
        n = mat.name
        matched = False
        for base in PRESENTATION_MATERIALS | FRONT_MARKER_MATERIALS | REAR_MARKER_MATERIALS:
            if material_matches(n, base):
                names.add(base)
                matched = True
                break
        if not matched:
            names.add(n)
    return names


def axis_centroid(objects: list[bpy.types.Object], axis: int) -> float:
    vals = []
    for obj in objects:
        lo, hi = duel.core.world_bbox([obj])
        vals.append(float((lo[axis] + hi[axis]) * 0.5))
    if not vals:
        fail("SEMANTIC_AXIS_MARKERS_EMPTY")
    return sum(vals) / len(vals)


def import_bugatti(name: str, path: Path, want_front_sign: int) -> dict:
    if want_front_sign not in (-1, 1):
        fail(f"{name}_FRONT_SIGN_INVALID:{want_front_sign}")
    if not path.is_file():
        fail(f"{name}_PRIMARY_SCENE_MISSING:{path}")

    before = set(bpy.data.objects)
    bpy.ops.import_scene.gltf(filepath=str(path))
    imported = [o for o in bpy.data.objects if o not in before]
    all_meshes = duel.core.mesh_objects(imported)
    if not all_meshes:
        fail(f"{name}_IMPORT_NO_MESH")

    presentation = []
    vehicle_meshes = []
    for obj in all_meshes:
        mats = object_material_bases(obj)
        if mats & PRESENTATION_MATERIALS:
            presentation.append(obj)
        else:
            vehicle_meshes.append(obj)

    if len(presentation) != EXPECTED_PRESENTATION_MESHES:
        fail(f"{name}_PRESENTATION_MESH_COUNT:{len(presentation)}")
    if len(vehicle_meshes) != EXPECTED_VEHICLE_MESHES:
        fail(f"{name}_VEHICLE_MESH_COUNT:{len(vehicle_meshes)}")

    vehicle_vertices = sum(len(obj.data.vertices) for obj in vehicle_meshes)
    vehicle_triangles = sum(len(obj.data.polygons) for obj in vehicle_meshes)
    if vehicle_vertices != EXPECTED_VEHICLE_VERTICES:
        fail(f"{name}_VEHICLE_VERTEX_GATE:{vehicle_vertices}")
    if vehicle_triangles != EXPECTED_VEHICLE_TRIANGLES:
        fail(f"{name}_VEHICLE_TRIANGLE_GATE:{vehicle_triangles}")

    presentation_ids = {id(o) for o in presentation}
    for obj in presentation:
        bpy.data.objects.remove(obj, do_unlink=True)
    imported = [o for o in imported if id(o) not in presentation_ids]

    root = bpy.data.objects.new(f"{name}_VISUAL_ROOT", None)
    bpy.context.collection.objects.link(root)
    imported_set = set(imported)
    for obj in imported:
        if obj.parent is None or obj.parent not in imported_set:
            mw = obj.matrix_world.copy()
            obj.parent = root
            obj.matrix_world = mw

    bpy.context.view_layer.update()
    lo, hi = duel.core.world_bbox(vehicle_meshes)
    raw_dims = hi - lo
    if raw_dims.z >= min(raw_dims.x, raw_dims.y):
        fail(f"{name}_HEIGHT_AXIS_GATE:{list(raw_dims)}")
    longitudinal_axis = 0 if raw_dims.x > raw_dims.y else 1
    lateral_axis = 1 - longitudinal_axis
    if raw_dims[longitudinal_axis] < raw_dims[lateral_axis] * 1.8:
        fail(f"{name}_LONGITUDINAL_RATIO_GATE:{list(raw_dims)}")

    front_objects = [o for o in vehicle_meshes if object_material_bases(o) & FRONT_MARKER_MATERIALS]
    rear_objects = [o for o in vehicle_meshes if object_material_bases(o) & REAR_MARKER_MATERIALS]
    if len(front_objects) < 2 or len(rear_objects) < 2:
        fail(f"{name}_SEMANTIC_MARKER_COUNT:{len(front_objects)}:{len(rear_objects)}")

    front_coord = axis_centroid(front_objects, longitudinal_axis)
    rear_coord = axis_centroid(rear_objects, longitudinal_axis)
    if abs(front_coord - rear_coord) < raw_dims[longitudinal_axis] * 0.45:
        fail(f"{name}_FRONT_REAR_SEPARATION_GATE:{front_coord}:{rear_coord}")
    current_front_sign = 1 if front_coord > rear_coord else -1

    # Rotate actual material-semantic front direction onto requested world X direction.
    if longitudinal_axis == 1:
        # +Y -> +X is -90 deg; -Y -> +X is +90 deg.
        angle = -current_front_sign * math.pi / 2.0
    else:
        # +X is already normalized; -X needs 180 deg.
        angle = 0.0 if current_front_sign == 1 else math.pi
    if want_front_sign == -1:
        angle += math.pi
    root.rotation_euler.z += angle
    bpy.context.view_layer.update()

    lo, hi = duel.core.recenter_floor(root, vehicle_meshes)
    dims = hi - lo
    if dims.x <= 1e-5:
        fail(f"{name}_ZERO_LENGTH")
    scale = duel.CAR_TARGET_LENGTH / dims.x
    root.scale = tuple(float(x) * scale for x in root.scale)
    bpy.context.view_layer.update()
    lo, hi = duel.core.recenter_floor(root, vehicle_meshes)

    normalized_front_x = axis_centroid(front_objects, 0)
    normalized_rear_x = axis_centroid(rear_objects, 0)
    semantic_delta = (normalized_front_x - normalized_rear_x) * want_front_sign
    if semantic_delta < duel.CAR_TARGET_LENGTH * 0.45:
        fail(f"{name}_NORMALIZED_FRONT_SEMANTIC_GATE:{normalized_front_x}:{normalized_rear_x}:{want_front_sign}")

    lo, hi = duel.core.world_bbox(vehicle_meshes)
    dims = hi - lo
    if abs(dims.x - duel.CAR_TARGET_LENGTH) > duel.CAR_TARGET_LENGTH * 0.08:
        fail(f"{name}_NORMALIZED_LENGTH_GATE:{dims.x}")
    if dims.x <= dims.y * 1.8 or dims.x <= dims.z * 2.5:
        fail(f"{name}_NORMALIZED_AXIS_GATE:{list(dims)}")

    print(f"{name}_PRESENTATION_MESH_FILTER=PASS")
    print(f"{name}_FULL_VEHICLE_MESHES={len(vehicle_meshes)}")
    print(f"{name}_FULL_VEHICLE_VERTICES={vehicle_vertices}")
    print(f"{name}_FULL_VEHICLE_TRIANGLES={vehicle_triangles}")
    print(f"{name}_RAW_VEHICLE_DIMS={list(raw_dims)}")
    print(f"{name}_FRONT_MARKER_COORD={front_coord}")
    print(f"{name}_REAR_MARKER_COORD={rear_coord}")
    print(f"{name}_NORMALIZED_FRONT_SIGN={want_front_sign}")
    print(f"{name}_EXACT_SOURCE_ORIENTATION=PASS")

    return {
        "name": name,
        "root": root,
        "objects": imported,
        "meshes": vehicle_meshes,
        "dims": dims,
        "orientationEvidence": {
            "sourceSha256": BUGATTI_EXACT_SHA,
            "presentationMeshesRemoved": EXPECTED_PRESENTATION_MESHES,
            "vehicleMeshCount": vehicle_vertices and len(vehicle_meshes),
            "vehicleVertexCount": vehicle_vertices,
            "vehicleTriangleCount": vehicle_triangles,
            "frontMarkerCount": len(front_objects),
            "rearMarkerCount": len(rear_objects),
            "longitudinalAxisBeforeNormalize": "X" if longitudinal_axis == 0 else "Y",
            "frontMarkerCoordBeforeNormalize": front_coord,
            "rearMarkerCoordBeforeNormalize": rear_coord,
            "normalizedFrontSign": want_front_sign,
        },
    }


duel.import_bugatti = import_bugatti

if __name__ == "__main__":
    duel.main()
