from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

import bpy
from mathutils import Matrix, Vector

from blender import iss_battle_runtime_assets as assets
from blender import run_generic_battle_runtime_v1_candidate34 as candidate34


def args() -> argparse.Namespace:
    argv = sys.argv
    argv = argv[argv.index("--") + 1:] if "--" in argv else []
    p = argparse.ArgumentParser()
    p.add_argument("--bugatti", required=True)
    return p.parse_args(argv)


def matrix_delta(a: Matrix, b: Matrix) -> float:
    return max(abs(float(a[r][c]) - float(b[r][c])) for r in range(4) for c in range(4))


def bounds_payload(objects):
    lo, hi = assets.world_bounds(objects)
    dims = hi - lo
    return {
        "lo": [round(float(x), 6) for x in lo],
        "hi": [round(float(x), 6) for x in hi],
        "dims": [round(float(x), 6) for x in dims],
    }


def object_row(obj):
    lo, hi = assets.world_bounds([obj])
    dims = hi - lo
    return {
        "name": obj.name,
        "materials": [slot.material.name for slot in obj.material_slots if slot.material],
        "vertexCount": len(obj.data.vertices),
        "polygonCount": len(obj.data.polygons),
        "parent": obj.parent.name if obj.parent else None,
        "lo": [round(float(x), 6) for x in lo],
        "hi": [round(float(x), 6) for x in hi],
        "dims": [round(float(x), 6) for x in dims],
    }


def front_evidence_rows(objects):
    rows = []
    for obj in assets.mesh_objects(objects):
        name_tokens = candidate34._name_tokens_with_ancestry(obj)
        dedicated = [
            token for token in sorted(name_tokens)
            if candidate34._dedicated_object_match(token, assets.FRONT_TERMS)
        ]
        material_matches = []
        for index, slot in enumerate(getattr(obj, "material_slots", [])):
            material = getattr(slot, "material", None)
            if material is None:
                continue
            token = assets.norm(material.name)
            if token and candidate34._has(token, assets.FRONT_TERMS):
                indices = sorted({
                    int(i)
                    for polygon in obj.data.polygons
                    if int(polygon.material_index) == index
                    for i in polygon.vertices
                })
                points = [obj.matrix_world @ obj.data.vertices[i].co for i in indices]
                if points:
                    lo = Vector((min(p.x for p in points), min(p.y for p in points), min(p.z for p in points)))
                    hi = Vector((max(p.x for p in points), max(p.y for p in points), max(p.z for p in points)))
                    material_matches.append({
                        "material": material.name,
                        "vertexCount": len(indices),
                        "lo": [round(float(x), 6) for x in lo],
                        "hi": [round(float(x), 6) for x in hi],
                    })
        if dedicated or material_matches:
            row = object_row(obj)
            row["dedicatedFrontTokens"] = dedicated
            row["frontMaterialMatches"] = material_matches
            rows.append(row)
    return rows


def main() -> None:
    a = args()
    path = Path(a.bugatti).resolve()
    imported = assets.import_asset(path)
    imported_names = [obj.name for obj in imported]
    meshes = assets.mesh_objects(imported)
    before = bounds_payload(meshes)

    presentation = [
        obj for obj in meshes
        if assets.token_match(assets.object_tokens(obj), assets.PRESENTATION_TERMS)
    ]
    presentation_names = {obj.name for obj in presentation}
    child_world_before = {
        child.name: child.matrix_world.copy()
        for obj in presentation
        for child in obj.children_recursive
        if child.name in imported_names
    }
    removed = []
    for obj in presentation:
        row = object_row(obj)
        row["children"] = [child.name for child in obj.children]
        row["recursiveChildCount"] = len([c for c in obj.children_recursive if c.name in imported_names])
        removed.append(row)

    for obj in presentation:
        bpy.data.objects.remove(obj, do_unlink=True)
    bpy.context.view_layer.update()

    imported_after = []
    for name in imported_names:
        if name in presentation_names:
            continue
        obj = bpy.data.objects.get(name)
        if obj is not None:
            imported_after.append(obj)
    meshes_after = assets.mesh_objects(imported_after)
    after = bounds_payload(meshes_after)

    child_deltas = []
    for name, old in child_world_before.items():
        obj = bpy.data.objects.get(name)
        if obj is None:
            child_deltas.append({"name": name, "missing": True})
            continue
        child_deltas.append({
            "name": name,
            "missing": False,
            "matrixWorldDelta": round(matrix_delta(old, obj.matrix_world), 9),
            "parentAfter": obj.parent.name if obj.parent else None,
        })

    base_front = assets.centroid_for_terms(imported_after, assets.FRONT_TERMS)
    base_rear = assets.centroid_for_terms(imported_after, assets.REAR_TERMS)
    safe_front = candidate34.ambiguity_safe_centroid_for_terms(imported_after, assets.FRONT_TERMS)
    safe_rear = candidate34.ambiguity_safe_centroid_for_terms(imported_after, assets.REAR_TERMS)
    global_lo, global_hi = assets.world_bounds(meshes_after)

    mesh_rows = [object_row(obj) for obj in meshes_after]
    width_extreme_rows = sorted(
        mesh_rows,
        key=lambda row: max(abs(float(row["lo"][0])), abs(float(row["hi"][0]))),
        reverse=True,
    )
    width_span_rows = sorted(mesh_rows, key=lambda row: float(row["dims"][0]), reverse=True)

    payload = {
        "marker": "BUGATTI_SEMANTIC_CONTACT_AFFECTED_LAYER_DIAGNOSTIC",
        "meshCountBefore": len(meshes),
        "presentationCount": len(presentation),
        "meshCountAfter": len(meshes_after),
        "boundsBefore": before,
        "boundsAfter": after,
        "removed": removed,
        "childWorldMatrixDeltas": child_deltas,
        "baseFrontCentroid": [round(float(x), 6) for x in base_front] if base_front is not None else None,
        "baseRearCentroid": [round(float(x), 6) for x in base_rear] if base_rear is not None else None,
        "ambiguitySafeFrontCentroid": [round(float(x), 6) for x in safe_front] if safe_front is not None else None,
        "ambiguitySafeRearCentroid": [round(float(x), 6) for x in safe_rear] if safe_rear is not None else None,
        "sourceForwardAxisExpected": "-Y",
        "geometricFrontSurfaceY": round(float(global_lo.y), 6),
        "geometricRearSurfaceY": round(float(global_hi.y), 6),
        "ambiguitySafeFrontDepthFromSurfaceM": (
            round(float(safe_front.y - global_lo.y), 6) if safe_front is not None else None
        ),
        "frontEvidenceRows": front_evidence_rows(imported_after),
        "widthExtremeTop12": width_extreme_rows[:12],
        "widthSpanTop12": width_span_rows[:12],
        "allRemainingMeshes": mesh_rows,
    }
    print(json.dumps(payload, sort_keys=True), flush=True)


if __name__ == "__main__":
    main()
