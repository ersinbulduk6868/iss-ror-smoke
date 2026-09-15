from __future__ import annotations

import json
import math
import sys
from pathlib import Path
from typing import Iterable

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

import bpy
from mathutils import Vector

from blender import iss_battle_runtime_assets as assets
from blender import run_generic_battle_runtime_v1_candidate34 as candidate34
from blender import run_generic_battle_runtime_v1_candidate371 as candidate371

CANDIDATE = "ISS_GENERIC_BATTLE_RUNTIME_V1_CANDIDATE_3_8_1"
PRESENTATION_CLASSIFIER = "DETACHED_GROUND_PLANE_PLUS_SAFE_TOKEN_V1"
SEMANTIC_LOCATOR = "DIRECTIONALLY_VALIDATED_SURFACE_SEMANTIC_V3"

_original_normalize_prototype = assets.normalize_prototype
_original_token_match = assets.token_match
_original_semantic_locator = candidate34.ambiguity_safe_centroid_for_terms


def _is_presentation_family(terms: tuple[str, ...]) -> bool:
    return tuple(assets.norm(x) for x in terms) == tuple(
        assets.norm(x) for x in assets.PRESENTATION_TERMS
    )


def _safe_presentation_match(tokens: set[str], terms: tuple[str, ...]) -> bool:
    if not _is_presentation_family(terms):
        return _original_token_match(tokens, terms)
    normalized_terms = {assets.norm(x) for x in terms}
    for token in {assets.norm(x) for x in tokens if assets.norm(x)}:
        parts = {part for part in token.split("_") if part}
        for term in normalized_terms:
            if not term:
                continue
            if token == term or term in parts:
                return True
            if term == "shadow" and token.endswith("shadow"):
                return True
            if term in {"display_stand", "road_plane"} and term in token:
                return True
    return False


def _structural_token(token: str) -> bool:
    protected = (
        "body", "chassis", "frame", "bottom", "underbody", "bumper",
        "wheel", "tire", "tyre", "track", "blade", "plate", "axle",
    )
    return any(marker in token for marker in protected)


def _implicit_ground_presentation(obj, all_meshes: list) -> bool:
    if obj.children:
        return False
    if len(obj.data.vertices) > 8 or len(obj.data.polygons) > 4:
        return False
    if _safe_presentation_match(assets.object_tokens(obj), assets.PRESENTATION_TERMS):
        return False
    global_lo, global_hi = assets.world_bounds(all_meshes)
    actor_dims = global_hi - global_lo
    lo, hi = assets.world_bounds([obj])
    dims = hi - lo
    center = (lo + hi) * 0.5
    flat_limit = max(0.006, float(actor_dims.z) * 0.012)
    ground_limit = float(global_lo.z) + max(0.025, float(actor_dims.z) * 0.035)
    if float(dims.z) > flat_limit or float(center.z) > ground_limit:
        return False
    if max(float(dims.x), float(dims.y)) < 0.25:
        return False
    tokens = {assets.norm(obj.name)}
    tokens.update(
        assets.norm(slot.material.name)
        for slot in getattr(obj, "material_slots", [])
        if slot.material is not None
    )
    if any(_structural_token(token) for token in tokens):
        return False
    return True


def hardened_normalize_prototype(binding, imported):
    meshes = assets.mesh_objects(imported)
    implicit = [obj for obj in meshes if _implicit_ground_presentation(obj, meshes)]
    if implicit:
        ids = {id(obj) for obj in implicit}
        names = [obj.name for obj in implicit]
        for obj in implicit:
            bpy.data.objects.remove(obj, do_unlink=True)
        imported[:] = [obj for obj in imported if id(obj) not in ids]
        assets.marker(
            "IMPLICIT_PRESENTATION_GEOMETRY_FILTERED",
            entityId=binding.get("entityId"),
            removedMeshes=len(names),
            classifier=PRESENTATION_CLASSIFIER,
            objectNames=names,
        )

    previous = assets.token_match
    assets.token_match = _safe_presentation_match
    try:
        return _original_normalize_prototype(binding, imported)
    finally:
        assets.token_match = previous


def _bounds_center(points: Iterable[Vector]) -> Vector | None:
    rows = list(points)
    if not rows:
        return None
    lo = Vector((
        min(float(p.x) for p in rows),
        min(float(p.y) for p in rows),
        min(float(p.z) for p in rows),
    ))
    hi = Vector((
        max(float(p.x) for p in rows),
        max(float(p.y) for p in rows),
        max(float(p.z) for p in rows),
    ))
    return (lo + hi) * 0.5


def _strong_direction_token(token: str, family: str) -> bool:
    token = assets.norm(token)
    if not token:
        return False
    wheel_like = any(x in token for x in ("wheel", "tire", "tyre", "track"))
    if family == "front":
        if any(x in token for x in ("rear", "back", "tail", "brake")):
            return False
        if wheel_like:
            return False
        return any(x in token for x in ("front", "headlight", "hood", "bonnet", "blade"))
    if family == "rear":
        if wheel_like:
            return False
        return any(x in token for x in ("rear", "taillight", "brakelight", "back"))
    return False


def _material_points(obj, material_index: int) -> list[Vector]:
    vertex_indices = sorted({
        int(i)
        for polygon in obj.data.polygons
        if int(polygon.material_index) == material_index
        for i in polygon.vertices
    })
    matrix = obj.matrix_world
    return [matrix @ obj.data.vertices[i].co for i in vertex_indices]


def _region_rows(objects, terms: tuple[str, ...]) -> list[tuple[list[Vector], set[str]]]:
    rows: list[tuple[list[Vector], set[str]]] = []
    for obj in assets.mesh_objects(objects):
        matrix = obj.matrix_world
        name_tokens = candidate34._name_tokens_with_ancestry(obj)
        if any(candidate34._dedicated_object_match(token, terms) for token in name_tokens):
            rows.append(([matrix @ vertex.co for vertex in obj.data.vertices], set(name_tokens)))
            continue
        for index, slot in enumerate(getattr(obj, "material_slots", [])):
            material = getattr(slot, "material", None)
            if material is None:
                continue
            token = assets.norm(material.name)
            if token and candidate34._has(token, terms):
                points = _material_points(obj, index)
                if points:
                    rows.append((points, {token}))
    return rows


def _strong_direction_centers(objects, family: str) -> list[Vector]:
    centers: list[Vector] = []
    for obj in assets.mesh_objects(objects):
        name_tokens = candidate34._name_tokens_with_ancestry(obj)
        strong_names = [token for token in name_tokens if _strong_direction_token(token, family)]
        if strong_names:
            points = [obj.matrix_world @ vertex.co for vertex in obj.data.vertices]
            center = _bounds_center(points)
            if center is not None:
                centers.append(center)
        for index, slot in enumerate(getattr(obj, "material_slots", [])):
            material = getattr(slot, "material", None)
            if material is None or not _strong_direction_token(material.name, family):
                continue
            center = _bounds_center(_material_points(obj, index))
            if center is not None:
                centers.append(center)
    return centers


def directionally_validated_semantic_centroid(objects, terms: tuple[str, ...]) -> Vector | None:
    family = candidate34._semantic_family(terms)
    if family not in {"front", "rear"}:
        return _original_semantic_locator(objects, terms)

    meshes = assets.mesh_objects(objects)
    if not meshes:
        return None
    lo, hi = assets.world_bounds(meshes)
    dims = hi - lo
    center = (lo + hi) * 0.5
    axis = 0 if float(dims.x) >= float(dims.y) else 1
    longitudinal = max(float(dims[axis]), 1e-6)
    half = longitudinal * 0.5

    own_strong = _strong_direction_centers(meshes, family)
    opposite = "rear" if family == "front" else "front"
    opposite_strong = _strong_direction_centers(meshes, opposite)
    sign = 0.0
    if own_strong:
        mean = sum(float(p[axis]) for p in own_strong) / len(own_strong)
        sign = 1.0 if mean >= float(center[axis]) else -1.0
    elif opposite_strong:
        mean = sum(float(p[axis]) for p in opposite_strong) / len(opposite_strong)
        sign = -1.0 if mean >= float(center[axis]) else 1.0
    if sign == 0.0:
        return _original_semantic_locator(objects, terms)

    accepted: list[Vector] = []
    for points, tokens in _region_rows(meshes, terms):
        if not points:
            continue
        p_lo = min(float(p[axis]) for p in points)
        p_hi = max(float(p[axis]) for p in points)
        span = p_hi - p_lo
        p_center = 0.5 * (p_lo + p_hi)
        signed_offset = sign * (p_center - float(center[axis]))
        if span > longitudinal * 0.55:
            continue
        if signed_offset < half * 0.12:
            continue
        surface = float(hi[axis]) if sign > 0 else float(lo[axis])
        depth = abs(surface - p_center)
        if depth > longitudinal * 0.45:
            continue
        accepted.extend(points)

    result = _bounds_center(accepted)
    if result is None:
        return None
    return result


def main() -> None:
    assets.normalize_prototype = hardened_normalize_prototype
    candidate34.ambiguity_safe_centroid_for_terms = directionally_validated_semantic_centroid
    candidate371.CANDIDATE = CANDIDATE
    print(json.dumps({
        "marker": "GENERIC_BATTLE_RUNTIME_CANDIDATE381_ENGINE_HARDENING_PASS",
        "candidate": CANDIDATE,
        "presentationClassifier": PRESENTATION_CLASSIFIER,
        "semanticLocator": SEMANTIC_LOCATOR,
        "damageThresholdChanged": False,
        "contactThresholdChanged": False,
        "scenarioTrajectoryHardcode": False,
        "actorPoseOrVelocityMutation": False,
        "bugattiSpecificObjectIds": False,
    }, sort_keys=True), flush=True)
    candidate371.main()


if __name__ == "__main__":
    main()
