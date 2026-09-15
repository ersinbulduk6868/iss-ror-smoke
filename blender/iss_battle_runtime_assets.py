from __future__ import annotations

import hashlib
import json
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

import bpy
from mathutils import Vector

from blender.iss_battle_runtime_core import ActorProfile, clamp, norm

CONTACT_DETECTOR = "SOLVER_CORRELATED_OBB_CONTACT"
VISUAL_DAMAGE_MODEL = "IMPACT_LOCALIZED_SOURCE_GEOMETRY_DEFORMATION_V1"
DEBRIS_MODEL = "IMPACT_DERIVED_RIGID_SHARDS_V1"
CONTROL_MODEL = "DIFFERENTIAL_RIGID_BODY_MOTOR_V1"
MIN_DAMAGE_SEVERITY = 0.055

class BlenderBattleRuntimeError(RuntimeError):
    pass


def marker(name: str, **fields: Any) -> None:
    print(json.dumps({"marker": name, **fields}, sort_keys=True), flush=True)


def activate(obj: bpy.types.Object) -> None:
    bpy.ops.object.select_all(action="DESELECT")
    obj.select_set(True)
    bpy.context.view_layer.objects.active = obj


def add_rigid_body(obj: bpy.types.Object, *, mass: float, shape: str, friction: float, restitution: float, kinematic: bool = False) -> None:
    activate(obj)
    bpy.ops.rigidbody.object_add()
    rb = obj.rigid_body
    rb.type = "ACTIVE"
    rb.collision_shape = shape
    rb.mass = max(0.01, float(mass))
    rb.friction = max(0.0, float(friction))
    rb.restitution = clamp(float(restitution), 0.0, 1.0)
    rb.linear_damping = 0.035
    rb.angular_damping = 0.08
    rb.use_deactivation = False
    rb.kinematic = bool(kinematic)


def add_passive_rigid_body(obj: bpy.types.Object, *, shape: str = "BOX", friction: float = 0.9) -> None:
    activate(obj)
    bpy.ops.rigidbody.object_add()
    obj.rigid_body.type = "PASSIVE"
    obj.rigid_body.collision_shape = shape
    obj.rigid_body.friction = friction
    obj.rigid_body.restitution = 0.0


def cube(name: str, location: Vector | tuple[float, float, float], dimensions: Vector | tuple[float, float, float]) -> bpy.types.Object:
    bpy.ops.mesh.primitive_cube_add(size=1.0, location=location)
    obj = bpy.context.object
    obj.name = name
    obj.dimensions = dimensions
    activate(obj)
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    return obj


def mesh_objects(objects: Iterable[bpy.types.Object]) -> list[bpy.types.Object]:
    return [obj for obj in objects if obj.type == "MESH" and len(obj.data.vertices) > 0]


def world_bounds(objects: Iterable[bpy.types.Object]) -> tuple[Vector, Vector]:
    points: list[Vector] = []
    for obj in mesh_objects(objects):
        for corner in obj.bound_box:
            points.append(obj.matrix_world @ Vector(corner))
    if not points:
        raise BlenderBattleRuntimeError("VISIBLE_MESH_BOUNDS_MISSING")
    lo = Vector((min(p.x for p in points), min(p.y for p in points), min(p.z for p in points)))
    hi = Vector((max(p.x for p in points), max(p.y for p in points), max(p.z for p in points)))
    return lo, hi


def object_tokens(obj: bpy.types.Object) -> set[str]:
    values = {norm(obj.name)}
    for slot in getattr(obj, "material_slots", []):
        if slot.material is not None:
            values.add(norm(slot.material.name))
    return {x for x in values if x}


def token_match(tokens: set[str], terms: tuple[str, ...]) -> bool:
    for token in tokens:
        for term in terms:
            n = norm(term)
            if n and (n in token or token in n):
                return True
    return False


FRONT_TERMS = ("front", "hood", "bonnet", "headlight", "grill", "grille", "front_bumper", "blade")
REAR_TERMS = ("rear", "back", "taillight", "brakelight", "rear_bumper")
PRESENTATION_TERMS = ("floor", "ground", "carpet", "shadow", "backdrop", "pedestal", "display_stand", "showroom", "road_plane")
SEMANTIC_TERMS: dict[str, tuple[str, ...]] = {
    "front": FRONT_TERMS,
    "rear": REAR_TERMS,
    "cab": ("cab", "cabin", "cockpit"),
    "cabin": ("cab", "cabin", "cockpit"),
    "blade": ("blade", "dozer_blade", "dozerblade"),
    "left_track": ("left_track", "track_left", "l_track"),
    "right_track": ("right_track", "track_right", "r_track"),
    "track_left": ("left_track", "track_left", "l_track"),
    "track_right": ("right_track", "track_right", "r_track"),
    "front_left_wheel": ("front_left_wheel", "wheel_front_left", "wheel_fl", "fl_wheel"),
    "front_right_wheel": ("front_right_wheel", "wheel_front_right", "wheel_fr", "fr_wheel"),
    "rear_left_wheel": ("rear_left_wheel", "wheel_rear_left", "wheel_rl", "rl_wheel"),
    "rear_right_wheel": ("rear_right_wheel", "wheel_rear_right", "wheel_rr", "rr_wheel"),
    "wheel": ("wheel", "tire", "tyre"),
    "body": ("body", "shell", "hull"),
    "chassis": ("chassis", "frame", "hull"),
}


def centroid_for_terms(objects: list[bpy.types.Object], terms: tuple[str, ...]) -> Vector | None:
    centers: list[Vector] = []
    for obj in mesh_objects(objects):
        if token_match(object_tokens(obj), terms):
            lo, hi = world_bounds([obj])
            centers.append((lo + hi) * 0.5)
    if not centers:
        return None
    out = Vector((0.0, 0.0, 0.0))
    for center in centers:
        out += center
    return out / len(centers)


def parse_forward_axis(binding: dict[str, Any], imported: list[bpy.types.Object]) -> str:
    rp = binding.get("runtimeProfile") or {}
    cf = binding.get("canonicalFrame") or binding.get("canonical_frame") or {}
    explicit = str(rp.get("forwardAxis") or cf.get("forward") or "").upper().replace(" ", "")
    explicit = explicit.replace("+", "")
    if explicit in {"X", "-X", "Y", "-Y"}:
        return explicit
    front = centroid_for_terms(imported, FRONT_TERMS)
    rear = centroid_for_terms(imported, REAR_TERMS)
    lo, hi = world_bounds(imported)
    center = (lo + hi) * 0.5
    if front is None:
        raise BlenderBattleRuntimeError(f"ACTOR_FORWARD_AXIS_UNRESOLVED:{binding.get('entityId')}")
    delta = front - rear if rear is not None else front - center
    if max(abs(delta.x), abs(delta.y)) < 1e-5:
        raise BlenderBattleRuntimeError(f"ACTOR_FORWARD_AXIS_DEGENERATE:{binding.get('entityId')}")
    if abs(delta.x) >= abs(delta.y):
        return "X" if delta.x >= 0 else "-X"
    return "Y" if delta.y >= 0 else "-Y"


def forward_rotation(axis: str) -> float:
    return {"X": 0.0, "-X": math.pi, "Y": -math.pi / 2.0, "-Y": math.pi / 2.0}[axis]


def import_asset(path: Path) -> list[bpy.types.Object]:
    before = set(bpy.data.objects)
    low = path.suffix.lower()
    if low in {".glb", ".gltf"}:
        bpy.ops.import_scene.gltf(filepath=str(path))
    elif low in {".usd", ".usda", ".usdc"}:
        bpy.ops.wm.usd_import(filepath=str(path))
    else:
        raise BlenderBattleRuntimeError(f"UNSUPPORTED_BLENDER_ASSET_FORMAT:{path}")
    imported = [obj for obj in bpy.data.objects if obj not in before]
    if not mesh_objects(imported):
        raise BlenderBattleRuntimeError(f"PRODUCTION_ASSET_IMPORTED_WITHOUT_MESH:{path}")
    return imported


def move_objects_to_unlinked_collection(objects: list[bpy.types.Object], collection: bpy.types.Collection) -> None:
    for obj in objects:
        for existing in list(obj.users_collection):
            existing.objects.unlink(obj)
        collection.objects.link(obj)


def normalize_prototype(binding: dict[str, Any], imported: list[bpy.types.Object]) -> tuple[Vector, dict[str, Vector], dict[str, str], str]:
    presentation = [obj for obj in mesh_objects(imported) if token_match(object_tokens(obj), PRESENTATION_TERMS)]
    presentation_ids = {id(obj) for obj in presentation}
    if presentation and len(presentation) < len(mesh_objects(imported)):
        for obj in presentation:
            bpy.data.objects.remove(obj, do_unlink=True)
        imported[:] = [obj for obj in imported if id(obj) not in presentation_ids]
        marker("PRESENTATION_GEOMETRY_FILTERED", entityId=binding.get("entityId"), removedMeshes=len(presentation))
    if not mesh_objects(imported):
        raise BlenderBattleRuntimeError(f"ACTOR_GEOMETRY_EMPTY_AFTER_PRESENTATION_FILTER:{binding.get('entityId')}")
    root = bpy.data.objects.new("ISS_NORMALIZE_ROOT", None)
    bpy.context.scene.collection.objects.link(root)
    imported_set = set(imported)
    for obj in imported:
        if obj.parent is None or obj.parent not in imported_set:
            mw = obj.matrix_world.copy(); obj.parent = root; obj.matrix_world = mw
    bpy.context.view_layer.update()
    axis = parse_forward_axis(binding, imported)
    root.rotation_euler.z = forward_rotation(axis)
    bpy.context.view_layer.update()
    lo, hi = world_bounds(imported); center = (lo + hi) * 0.5
    root.location += Vector((-center.x, -center.y, -lo.z))
    rp = binding.get("runtimeProfile") or {}
    scale_multiplier = float(rp.get("scaleMultiplier") or 1.0)
    if not math.isfinite(scale_multiplier) or not (0.01 <= scale_multiplier <= 100.0):
        raise BlenderBattleRuntimeError(f"ACTOR_SCALE_MULTIPLIER_INVALID:{binding.get('entityId')}:{scale_multiplier}")
    root.scale = (scale_multiplier, scale_multiplier, scale_multiplier)
    bpy.context.view_layer.update()
    lo, hi = world_bounds(imported); center = (lo + hi) * 0.5
    root.location += Vector((-center.x, -center.y, -lo.z))
    bpy.context.view_layer.update()
    lo, hi = world_bounds(imported); dims = hi - lo
    if dims.x < 0.45 or dims.x > 60.0 or dims.y < 0.25 or dims.y > 25.0 or dims.z < 0.2 or dims.z > 20.0:
        raise BlenderBattleRuntimeError(f"ACTOR_NORMALIZED_DIMENSIONS_IMPLAUSIBLE:{binding.get('entityId')}:{list(dims)}")
    top = [obj for obj in imported if obj.parent is root]
    for obj in top:
        mw = obj.matrix_world.copy(); obj.parent = None; obj.matrix_world = mw
    bpy.data.objects.remove(root, do_unlink=True)
    bpy.context.view_layer.update()
    lo, hi = world_bounds(imported); dims = hi - lo
    zones: dict[str, Vector] = {}; evidence: dict[str, str] = {}
    for zone, terms in SEMANTIC_TERMS.items():
        point = centroid_for_terms(imported, terms)
        if point is not None:
            zones[zone] = point.copy(); evidence[zone] = "MESH_OR_MATERIAL_SEMANTIC"
    generic = {
        "front": Vector((hi.x, 0.0, max(dims.z * 0.45, 0.25))),
        "rear": Vector((lo.x, 0.0, max(dims.z * 0.45, 0.25))),
        "left_side": Vector((0.0, hi.y, max(dims.z * 0.45, 0.25))),
        "right_side": Vector((0.0, lo.y, max(dims.z * 0.45, 0.25))),
        "body": Vector((0.0, 0.0, max(dims.z * 0.55, 0.25))),
        "chassis": Vector((0.0, 0.0, max(dims.z * 0.30, 0.18))),
        "front_left_wheel": Vector((dims.x * 0.31, dims.y * 0.47, max(dims.z * 0.22, 0.22))),
        "front_right_wheel": Vector((dims.x * 0.31, -dims.y * 0.47, max(dims.z * 0.22, 0.22))),
        "rear_left_wheel": Vector((-dims.x * 0.31, dims.y * 0.47, max(dims.z * 0.22, 0.22))),
        "rear_right_wheel": Vector((-dims.x * 0.31, -dims.y * 0.47, max(dims.z * 0.22, 0.22))),
    }
    for zone, point in generic.items():
        if zone not in zones:
            zones[zone] = point; evidence[zone] = "CANONICAL_GEOMETRIC_ZONE"
    declared = set()
    sem_manifest = binding.get("semanticManifest") or binding.get("semantic_manifest") or {}
    declared.update(norm(x) for x in (binding.get("semanticBodies") or []) if norm(x))
    declared.update(norm(x) for x in (sem_manifest.get("majorSemanticBodies") or []) if norm(x))
    for label in declared:
        if label in zones: continue
        point = centroid_for_terms(imported, (label,))
        if point is not None:
            zones[label] = point; evidence[label] = "DECLARED_SEMANTIC_MATCH"
    return dims, zones, evidence, axis


@dataclass
class AssetPrototype:
    key: str
    collection: bpy.types.Collection
    objects: list[bpy.types.Object]
    meshes: list[bpy.types.Object]
    dimensions: Vector
    zones: dict[str, Vector]
    semantic_evidence: dict[str, str]
    forward_axis_source: str


class AssetPrototypeCache:
    def __init__(self) -> None:
        self._items: dict[str, AssetPrototype] = {}

    def load(self, binding: dict[str, Any], local_path: Path) -> AssetPrototype:
        key = str(binding.get("downloadedSha256") or binding.get("readySha256") or local_path.resolve())
        if key in self._items:
            return self._items[key]
        imported = import_asset(local_path)
        dims, zones, evidence, axis = normalize_prototype(binding, imported)
        collection = bpy.data.collections.new(f"ISS_PROTO_{hashlib.sha256(key.encode()).hexdigest()[:12]}")
        move_objects_to_unlinked_collection(imported, collection)
        proto = AssetPrototype(key, collection, imported, mesh_objects(imported), dims, zones, evidence, axis)
        self._items[key] = proto
        marker("ASSET_PROTOTYPE_READY", sourceKey=key, dimensions=[round(float(x), 4) for x in dims], semanticZones=sorted(zones), forwardAxisSource=axis, visibleMeshCount=len(proto.meshes))
        return proto
