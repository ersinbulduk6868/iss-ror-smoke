from __future__ import annotations

import json
import math
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from mathutils import Vector, geometry
from blender import iss_battle_runtime_consequences as consequences
from blender import run_generic_battle_runtime_v1_candidate35 as candidate35

CANDIDATE = "ISS_GENERIC_BATTLE_RUNTIME_V1_CANDIDATE_3_5_1_DAMAGE_DIAGNOSTIC"
_original_deform = consequences._deform_source_geometry


def _bounds_from_matrix(obj, matrix):
    points = [matrix @ Vector(corner) for corner in obj.bound_box]
    lo = Vector((min(p.x for p in points), min(p.y for p in points), min(p.z for p in points)))
    hi = Vector((max(p.x for p in points), max(p.y for p in points), max(p.z for p in points)))
    return lo, hi


def _nearest_vertex_distance(obj, point_world: Vector) -> float:
    if not obj.data.vertices:
        return float("inf")
    return min((obj.matrix_world @ v.co - point_world).length for v in obj.data.vertices)


def _nearest_triangle_distance(obj, point_world: Vector) -> float:
    mesh = obj.data
    mesh.calc_loop_triangles()
    best = float("inf")
    for tri in mesh.loop_triangles:
        a = obj.matrix_world @ mesh.vertices[tri.vertices[0]].co
        b = obj.matrix_world @ mesh.vertices[tri.vertices[1]].co
        c = obj.matrix_world @ mesh.vertices[tri.vertices[2]].co
        closest = geometry.closest_point_on_tri(point_world, a, b, c)
        best = min(best, (closest - point_world).length)
    return best


def diagnostic_deform(actor, evidence):
    meshes = consequences._copy_on_damage(actor)
    point_world = Vector(evidence.contact_point)
    min_dim = max(0.20, min(float(actor.dimensions.x), float(actor.dimensions.y), float(actor.dimensions.z)))
    radius = consequences.clamp(
        min_dim * (0.16 + 0.34 * evidence.severity),
        0.12,
        min_dim * 0.62,
    )
    rows = []
    for index, dst in enumerate(meshes):
        src = actor.prototype.meshes[index] if index < len(actor.prototype.meshes) else None
        actual_lo, actual_hi = _bounds_from_matrix(dst, dst.matrix_world)
        expected_lo = expected_hi = None
        bounds_delta = None
        if src is not None:
            expected_matrix = actor.visual_instance.matrix_world @ src.matrix_world
            expected_lo, expected_hi = _bounds_from_matrix(src, expected_matrix)
            bounds_delta = max(
                (actual_lo - expected_lo).length,
                (actual_hi - expected_hi).length,
            )
        rows.append({
            "mesh": dst.name,
            "actualBoundsMin": [round(float(x), 6) for x in actual_lo],
            "actualBoundsMax": [round(float(x), 6) for x in actual_hi],
            "expectedBoundsMin": [round(float(x), 6) for x in expected_lo] if expected_lo is not None else None,
            "expectedBoundsMax": [round(float(x), 6) for x in expected_hi] if expected_hi is not None else None,
            "boundsDeltaM": round(float(bounds_delta), 6) if bounds_delta is not None else None,
            "nearestVertexDistanceM": round(float(_nearest_vertex_distance(dst, point_world)), 6),
            "nearestTriangleDistanceM": round(float(_nearest_triangle_distance(dst, point_world)), 6),
        })
    print(json.dumps({
        "marker": "DAMAGE_LOCALIZATION_COORDINATE_DIAGNOSTIC",
        "candidate": CANDIDATE,
        "actorId": actor.profile.entity_id,
        "frame": int(evidence.frame),
        "severity": round(float(evidence.severity), 6),
        "radiusM": round(float(radius), 6),
        "contactPoint": [round(float(x), 6) for x in point_world],
        "visualInstanceWorldTranslation": [round(float(x), 6) for x in actor.visual_instance.matrix_world.translation],
        "chassisWorldTranslation": [round(float(x), 6) for x in actor.chassis.matrix_world.translation],
        "meshes": rows,
    }, sort_keys=True), flush=True)
    return _original_deform(actor, evidence)


def main() -> None:
    consequences._deform_source_geometry = diagnostic_deform
    candidate35.main()


if __name__ == "__main__":
    main()
