from __future__ import annotations

import json
import math
import sys
from pathlib import Path
from typing import Iterable

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from mathutils import Vector
from blender import iss_battle_runtime_assets as assets
from blender import iss_battle_runtime_physics as physics

CANDIDATE = "ISS_GENERIC_BATTLE_RUNTIME_V1_CANDIDATE_3_4"
MOTOR_ROLLING_SIGN = -1.0
SEMANTIC_LOCATOR = "AMBIGUITY_SAFE_GEOMETRY_AWARE_SEMANTIC_REGION_V2"


def calibrated_command(
    self: physics.DriveRig,
    left_mps: float,
    right_mps: float,
    impulse_scale: float = 1.0,
) -> None:
    radius = max(float(self.wheel_radius), 1e-4)
    left_w = MOTOR_ROLLING_SIGN * float(left_mps) / radius
    right_w = MOTOR_ROLLING_SIGN * float(right_mps) / radius
    impulse = max(0.0, float(self.max_motor_impulse) * float(impulse_scale))
    if not all(math.isfinite(x) for x in (left_w, right_w, impulse)):
        raise RuntimeError("MOTOR_COMMAND_NONFINITE")
    for obj in self.motors_left:
        constraint = obj.rigid_body_constraint
        constraint.motor_ang_target_velocity = left_w
        constraint.motor_ang_max_impulse = impulse
    for obj in self.motors_right:
        constraint = obj.rigid_body_constraint
        constraint.motor_ang_target_velocity = right_w
        constraint.motor_ang_max_impulse = impulse


def _name_tokens_with_ancestry(obj) -> set[str]:
    tokens: set[str] = set()
    current = obj
    depth = 0
    while current is not None and depth < 8:
        token = assets.norm(getattr(current, "name", ""))
        if token:
            tokens.add(token)
        current = getattr(current, "parent", None)
        depth += 1
    return tokens


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


def _has(token: str, terms: tuple[str, ...]) -> bool:
    return assets.token_match({token}, terms)


def _semantic_family(terms: tuple[str, ...]) -> str:
    normalized = tuple(assets.norm(x) for x in terms)
    if normalized == tuple(assets.norm(x) for x in assets.FRONT_TERMS):
        return "front"
    if normalized == tuple(assets.norm(x) for x in assets.REAR_TERMS):
        return "rear"
    for zone, known_terms in assets.SEMANTIC_TERMS.items():
        if normalized == tuple(assets.norm(x) for x in known_terms):
            if zone in {"cab", "cabin"}:
                return "cabin"
            if zone in {"left_track", "track_left"}:
                return "left_track"
            if zone in {"right_track", "track_right"}:
                return "right_track"
            return zone
    return "declared"


def _is_composite_whole_actor_name(token: str) -> bool:
    front = _has(token, assets.FRONT_TERMS)
    rear = _has(token, assets.REAR_TERMS)
    left = any(x in token for x in ("left", "_l_", "_l"))
    right = any(x in token for x in ("right", "_r_", "_r"))
    structural = sum(
        1
        for marker in ("body", "chassis", "wheel", "track", "cabin", "cab", "blade")
        if marker in token
    )
    if front and rear:
        return True
    if left and right:
        return True
    if structural >= 3:
        return True
    return False


def _dedicated_object_match(token: str, terms: tuple[str, ...]) -> bool:
    if not _has(token, terms):
        return False
    family = _semantic_family(terms)
    if _is_composite_whole_actor_name(token):
        return False

    # A wheel/track object is not sufficient evidence for the whole vehicle front/rear.
    if family in {"front", "rear"} and any(x in token for x in ("wheel", "tire", "tyre", "track")):
        return False

    # Generic wheel evidence must be a wheel-like object, not a whole body name that happens
    # to mention wheels among many components.
    if family == "wheel":
        return any(x in token for x in ("wheel", "tire", "tyre")) and not any(
            x in token for x in ("body", "chassis", "cabin", "cab", "blade", "track")
        )

    return True


def ambiguity_safe_centroid_for_terms(objects, terms: tuple[str, ...]) -> Vector | None:
    """Resolve semantic regions from trustworthy geometry only.

    Object/ancestor names are accepted only when they identify a dedicated region. Composite
    whole-actor names (for example a single mesh named with both front and rear) are rejected.
    Material semantics are localized to polygons assigned to matching slots. If neither source
    provides trustworthy evidence, the canonical geometric fallback in normalize_prototype()
    remains authoritative.
    """
    dedicated_points: list[Vector] = []
    material_points: list[Vector] = []

    for obj in assets.mesh_objects(objects):
        matrix = obj.matrix_world
        mesh = obj.data

        name_tokens = _name_tokens_with_ancestry(obj)
        if any(_dedicated_object_match(token, terms) for token in name_tokens):
            dedicated_points.extend(matrix @ vertex.co for vertex in mesh.vertices)
            continue

        matching_material_indices: set[int] = set()
        for index, slot in enumerate(getattr(obj, "material_slots", [])):
            material = getattr(slot, "material", None)
            if material is None:
                continue
            material_token = assets.norm(material.name)
            if material_token and _has(material_token, terms):
                matching_material_indices.add(index)

        if not matching_material_indices:
            continue

        vertex_indices: set[int] = set()
        for polygon in mesh.polygons:
            if int(polygon.material_index) in matching_material_indices:
                vertex_indices.update(int(i) for i in polygon.vertices)

        material_points.extend(
            matrix @ mesh.vertices[index].co
            for index in sorted(vertex_indices)
            if 0 <= index < len(mesh.vertices)
        )

    if dedicated_points:
        return _bounds_center(dedicated_points)
    if material_points:
        return _bounds_center(material_points)
    return None


def main() -> None:
    assets.centroid_for_terms = ambiguity_safe_centroid_for_terms
    physics.DriveRig.command = calibrated_command

    from blender import iss_blender_battle_runtime_v1_hardened as hardened

    hardened.RUNTIME_VERSION = CANDIDATE
    print(
        json.dumps(
            {
                "marker": "GENERIC_BATTLE_RUNTIME_CANDIDATE34_ENGINE_HARDENING_PASS",
                "candidate": CANDIDATE,
                "motorRollingSign": MOTOR_ROLLING_SIGN,
                "semanticLocator": SEMANTIC_LOCATOR,
                "scope": "GENERIC_ENGINE_LEVEL_NO_SCENARIO_TRAJECTORY",
                "compositeSemanticNamesFailClosed": True,
            },
            sort_keys=True,
        ),
        flush=True,
    )
    hardened.main()


if __name__ == "__main__":
    main()
