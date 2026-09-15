from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

import bpy
from mathutils import Vector

from blender import iss_battle_runtime_assets as assets
from blender import run_generic_battle_runtime_v1_candidate34 as candidate34


def args() -> argparse.Namespace:
    argv = sys.argv
    argv = argv[argv.index("--") + 1:] if "--" in argv else []
    p = argparse.ArgumentParser()
    p.add_argument("--bugatti", required=True)
    p.add_argument("--out", required=True)
    return p.parse_args(argv)


def vec(v: Vector) -> list[float]:
    return [round(float(v.x), 6), round(float(v.y), 6), round(float(v.z), 6)]


def bounds(objects) -> tuple[Vector, Vector, Vector]:
    lo, hi = assets.world_bounds(objects)
    return lo, hi, hi - lo


def parent_chain(obj) -> list[str]:
    out = []
    cur = obj
    for _ in range(8):
        if cur is None:
            break
        out.append(str(getattr(cur, "name", "")))
        cur = getattr(cur, "parent", None)
    return out


def material_names(obj) -> list[str]:
    out = []
    for slot in getattr(obj, "material_slots", []):
        mat = getattr(slot, "material", None)
        if mat is not None:
            out.append(str(mat.name))
    return out


def semantic_match_details(obj, terms: tuple[str, ...]) -> dict:
    name_tokens = sorted(candidate34._name_tokens_with_ancestry(obj))
    dedicated = [t for t in name_tokens if candidate34._dedicated_object_match(t, terms)]
    matching_materials = []
    for slot in getattr(obj, "material_slots", []):
        mat = getattr(slot, "material", None)
        if mat is None:
            continue
        token = assets.norm(mat.name)
        if token and candidate34._has(token, terms):
            matching_materials.append(str(mat.name))
    return {
        "dedicatedNameTokens": dedicated,
        "matchingMaterials": sorted(matching_materials),
    }


def main() -> None:
    a = args()
    path = Path(a.bugatti).expanduser().resolve()
    out = Path(a.out).expanduser().resolve()
    out.parent.mkdir(parents=True, exist_ok=True)

    assets.centroid_for_terms = candidate34.ambiguity_safe_centroid_for_terms
    imported = assets.import_asset(path)
    meshes = assets.mesh_objects(imported)
    raw_lo, raw_hi, raw_dims = bounds(imported)

    rows = []
    presentation_names = []
    front_candidates = []
    rear_candidates = []
    for obj in meshes:
        lo, hi, dims = bounds([obj])
        tokens = sorted(assets.object_tokens(obj))
        presentation = assets.token_match(set(tokens), assets.PRESENTATION_TERMS)
        front = semantic_match_details(obj, assets.FRONT_TERMS)
        rear = semantic_match_details(obj, assets.REAR_TERMS)
        row = {
            "name": str(obj.name),
            "parents": parent_chain(obj),
            "materials": material_names(obj),
            "tokens": tokens,
            "boundsLo": vec(lo),
            "boundsHi": vec(hi),
            "dimensions": vec(dims),
            "vertexCount": len(obj.data.vertices),
            "presentationMatched": bool(presentation),
            "frontMatch": front,
            "rearMatch": rear,
        }
        rows.append(row)
        if presentation:
            presentation_names.append(str(obj.name))
        if front["dedicatedNameTokens"] or front["matchingMaterials"]:
            front_candidates.append(row)
        if rear["dedicatedNameTokens"] or rear["matchingMaterials"]:
            rear_candidates.append(row)

    kept = [obj for obj in meshes if not assets.token_match(assets.object_tokens(obj), assets.PRESENTATION_TERMS)]
    kept_lo, kept_hi, kept_dims = bounds(kept)

    binding = {
        "entityId": "actor_probe",
        "totalMassKg": 1570.0,
        "semanticBodies": ["front", "rear", "body", "chassis"],
        "runtimeProfile": {"locomotionModel": "GROUND_DIFFERENTIAL"},
    }
    axis_pre = assets.parse_forward_axis(binding, imported)
    dims, zones, evidence, axis = assets.normalize_prototype(binding, imported)
    final_lo, final_hi, final_dims = bounds(imported)
    front = zones.get("front")
    rear = zones.get("rear")
    geometric_front = Vector((final_hi.x, 0.0, max(final_dims.z * 0.45, 0.25)))
    geometric_rear = Vector((final_lo.x, 0.0, max(final_dims.z * 0.45, 0.25)))

    result = {
        "marker": "BUGATTI_GENERIC_GEOMETRY_DIAGNOSTIC",
        "status": "PASS",
        "source": str(path),
        "meshCountRaw": len(meshes),
        "presentationMatchedCount": len(presentation_names),
        "presentationMatchedNames": sorted(presentation_names),
        "keptMeshCountPreNormalize": len(kept),
        "rawBounds": {"lo": vec(raw_lo), "hi": vec(raw_hi), "dimensions": vec(raw_dims)},
        "keptBoundsPreNormalize": {"lo": vec(kept_lo), "hi": vec(kept_hi), "dimensions": vec(kept_dims)},
        "resolvedForwardAxisBeforeNormalize": axis_pre,
        "resolvedForwardAxis": axis,
        "finalBounds": {"lo": vec(final_lo), "hi": vec(final_hi), "dimensions": vec(final_dims)},
        "normalizeReturnedDimensions": vec(dims),
        "semanticFront": vec(front) if front is not None else None,
        "semanticRear": vec(rear) if rear is not None else None,
        "semanticFrontEvidence": evidence.get("front"),
        "semanticRearEvidence": evidence.get("rear"),
        "geometricFront": vec(geometric_front),
        "geometricRear": vec(geometric_rear),
        "frontToGeometricFrontDistance": round(float((front - geometric_front).length), 6) if front is not None else None,
        "rearToGeometricRearDistance": round(float((rear - geometric_rear).length), 6) if rear is not None else None,
        "frontCandidates": front_candidates,
        "rearCandidates": rear_candidates,
        "meshes": rows,
    }
    out.write_text(json.dumps(result, indent=2, sort_keys=True), encoding="utf-8")
    print(json.dumps({
        "marker": result["marker"],
        "status": result["status"],
        "meshCountRaw": result["meshCountRaw"],
        "presentationMatchedCount": result["presentationMatchedCount"],
        "presentationMatchedNames": result["presentationMatchedNames"],
        "keptMeshCountPreNormalize": result["keptMeshCountPreNormalize"],
        "rawDimensions": result["rawBounds"]["dimensions"],
        "keptDimensionsPreNormalize": result["keptBoundsPreNormalize"]["dimensions"],
        "resolvedForwardAxis": result["resolvedForwardAxis"],
        "finalDimensions": result["finalBounds"]["dimensions"],
        "semanticFront": result["semanticFront"],
        "semanticFrontEvidence": result["semanticFrontEvidence"],
        "geometricFront": result["geometricFront"],
        "frontToGeometricFrontDistance": result["frontToGeometricFrontDistance"],
        "semanticRear": result["semanticRear"],
        "semanticRearEvidence": result["semanticRearEvidence"],
        "geometricRear": result["geometricRear"],
        "rearToGeometricRearDistance": result["rearToGeometricRearDistance"],
        "frontCandidateCount": len(front_candidates),
        "rearCandidateCount": len(rear_candidates),
        "output": str(out),
    }, sort_keys=True), flush=True)


if __name__ == "__main__":
    main()
