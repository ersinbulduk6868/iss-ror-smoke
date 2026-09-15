from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

import bpy
from mathutils import Matrix

from blender import iss_battle_runtime_assets as assets


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


def main() -> None:
    a = args()
    path = Path(a.bugatti).resolve()
    imported = assets.import_asset(path)
    meshes = assets.mesh_objects(imported)
    before = bounds_payload(meshes)

    presentation = [
        obj for obj in meshes
        if assets.token_match(assets.object_tokens(obj), assets.PRESENTATION_TERMS)
    ]
    child_world_before = {
        child.name: child.matrix_world.copy()
        for obj in presentation
        for child in obj.children_recursive
        if child in imported
    }
    removed = []
    for obj in presentation:
        lo, hi = assets.world_bounds([obj])
        removed.append({
            "name": obj.name,
            "materials": [slot.material.name for slot in obj.material_slots if slot.material],
            "parent": obj.parent.name if obj.parent else None,
            "children": [child.name for child in obj.children],
            "recursiveChildCount": len([c for c in obj.children_recursive if c in imported]),
            "bounds": {
                "lo": [round(float(x), 6) for x in lo],
                "hi": [round(float(x), 6) for x in hi],
            },
        })

    for obj in presentation:
        bpy.data.objects.remove(obj, do_unlink=True)
    imported_after = [obj for obj in imported if obj.name in bpy.data.objects]
    bpy.context.view_layer.update()
    after = bounds_payload(assets.mesh_objects(imported_after))

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

    front = assets.centroid_for_terms(imported_after, assets.FRONT_TERMS)
    rear = assets.centroid_for_terms(imported_after, assets.REAR_TERMS)
    payload = {
        "marker": "BUGATTI_PRESENTATION_FILTER_DIAGNOSTIC",
        "meshCountBefore": len(meshes),
        "presentationCount": len(presentation),
        "meshCountAfter": len(assets.mesh_objects(imported_after)),
        "boundsBefore": before,
        "boundsAfter": after,
        "removed": removed,
        "childWorldMatrixDeltas": child_deltas,
        "frontCentroidAfter": [round(float(x), 6) for x in front] if front is not None else None,
        "rearCentroidAfter": [round(float(x), 6) for x in rear] if rear is not None else None,
    }
    print(json.dumps(payload, sort_keys=True), flush=True)


if __name__ == "__main__":
    main()
