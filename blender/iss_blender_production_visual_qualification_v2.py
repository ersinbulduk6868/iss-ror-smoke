from __future__ import annotations

import math
import random
import sys
from pathlib import Path

import bpy
from bpy_extras.object_utils import world_to_camera_view
from mathutils import Vector

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from blender import iss_blender_capability_qualification_v1 as q1

# v1 machine-PASS collision/runtime is intentionally reused unchanged.
q1.QUALIFICATION_SCOPE = "ISS_BLENDER_PRODUCTION_VISUAL_QUALIFICATION_V2"

BREAK_TOKENS = (
    "headlight", "reflector_front", "grill", "grille", "bumper", "plastic",
    "splitter", "trim", "lamp", "light", "glass",
)
BODY_EXCLUDE_TOKENS = (
    "tire", "tyre", "wheel", "rim", "brake", "disc", "caliper",
    "window", "windshield", "windscreen", "glass", "interior", "seat",
    "steering", "mirror", "headlight", "reflector", "grill", "grille",
    "bumper", "plastic", "lamp", "light",
)


def _joined_materials(obj: bpy.types.Object) -> str:
    return " ".join(q1.mat_names(obj)).lower()


def _bbox(obj: bpy.types.Object) -> tuple[Vector, Vector]:
    return q1.core.world_bbox([obj])


def _bbox_points(objects: list[bpy.types.Object]) -> list[Vector]:
    pts: list[Vector] = []
    for obj in objects:
        if obj.type != "MESH":
            continue
        for corner in obj.bound_box:
            pts.append(obj.matrix_world @ Vector(corner))
    if not pts:
        q1.duel.fail("V2_CAMERA_BOUNDS_EMPTY")
    return pts


def _actor_points(actor_a: dict, actor_b: dict, frame: int) -> list[Vector]:
    scene = bpy.context.scene
    scene.frame_set(frame)
    bpy.context.view_layer.update()
    return _bbox_points(actor_a["meshes"] + actor_b["meshes"])


def _target_from_points(points: list[Vector]) -> Vector:
    lo = Vector((min(p.x for p in points), min(p.y for p in points), min(p.z for p in points)))
    hi = Vector((max(p.x for p in points), max(p.y for p in points), max(p.z for p in points)))
    c = (lo + hi) * 0.5
    c.z = lo.z + (hi.z - lo.z) * 0.48
    return c


def _orient_camera(cam: bpy.types.Object, target: Vector) -> None:
    direction = target - cam.location
    cam.rotation_euler = direction.to_track_quat("-Z", "Y").to_euler()


def _framing_stats(scene: bpy.types.Scene, cam: bpy.types.Object, points: list[Vector]) -> dict:
    coords = [world_to_camera_view(scene, cam, p) for p in points]
    front = [c for c in coords if c.z > 0]
    if not front:
        return {"insideFraction": 0.0, "minX": -99.0, "maxX": 99.0, "minY": -99.0, "maxY": 99.0}
    inside = [c for c in front if 0.055 <= c.x <= 0.945 and 0.055 <= c.y <= 0.945]
    return {
        "insideFraction": len(inside) / len(front),
        "minX": min(c.x for c in front),
        "maxX": max(c.x for c in front),
        "minY": min(c.y for c in front),
        "maxY": max(c.y for c in front),
    }


def _fit_static_camera(name: str, points: list[Vector], lens: float, side_x: float, height: float, min_dist: float) -> tuple[bpy.types.Object, Vector, dict]:
    scene = bpy.context.scene
    target = _target_from_points(points)
    bpy.ops.object.camera_add(location=(target.x + side_x, target.y - min_dist, target.z + height))
    cam = bpy.context.object
    cam.name = name
    cam.data.lens = lens
    cam.data.clip_end = 1000.0

    dist = min_dist
    stats = None
    for _ in range(24):
        cam.location = Vector((target.x + side_x, target.y - dist, target.z + height))
        _orient_camera(cam, target)
        bpy.context.view_layer.update()
        stats = _framing_stats(scene, cam, points)
        if stats["insideFraction"] >= 0.985 and stats["minX"] >= 0.035 and stats["maxX"] <= 0.965 and stats["minY"] >= 0.035 and stats["maxY"] <= 0.965:
            break
        dist *= 1.16
    if stats is None or stats["insideFraction"] < 0.985:
        q1.duel.fail(f"V2_CAMERA_AUTOFIT_FAIL:{name}:{stats}")
    return cam, target, stats


def setup_auto_cameras_v2(scene: bpy.types.Scene, impact_frame: int, center: Vector, actor_a: dict, actor_b: dict) -> dict:
    scale = max(float(actor_a["dims"].x), float(actor_b["dims"].x))
    approach_frame = max(q1.duel.START, impact_frame - 28)
    aftermath_frame = min(q1.duel.END, impact_frame + 40)

    approach_pts = _actor_points(actor_a, actor_b, approach_frame)
    approach, approach_target, approach_stats = _fit_static_camera(
        "V2_CAM_APPROACH_AUTOFIT", approach_pts, 42.0, -0.10 * scale, 0.72 * scale, 2.0 * scale
    )

    impact_pts = _actor_points(actor_a, actor_b, impact_frame)
    impact, impact_target, impact_stats = _fit_static_camera(
        "V2_CAM_IMPACT_AUTOFIT", impact_pts, 48.0, -0.18 * scale, 0.50 * scale, 1.35 * scale
    )

    aftermath_pts = _actor_points(actor_a, actor_b, aftermath_frame)
    aft_cam, aft_target, aft_stats = _fit_static_camera(
        "V2_CAM_AFTERMATH_AUTOFIT", aftermath_pts, 58.0, 0.32 * scale, 0.42 * scale, 1.45 * scale
    )
    start_loc = aft_cam.location.copy()
    start_dist = (start_loc - aft_target).length
    end_dist = max(scale * 0.86, start_dist * 0.56)
    direction = (start_loc - aft_target).normalized()
    end_loc = aft_target + direction * end_dist
    aft_start = min(q1.duel.END - 1, impact_frame + 14)
    aft_cam.location = start_loc
    aft_cam.keyframe_insert(data_path="location", frame=aft_start)
    aft_cam.location = end_loc
    aft_cam.keyframe_insert(data_path="location", frame=q1.duel.END)

    # Validate the actual preview frames, not only camera existence.
    scene.frame_set(approach_frame)
    bpy.context.view_layer.update()
    approach_stats = _framing_stats(scene, approach, _bbox_points(actor_a["meshes"] + actor_b["meshes"]))
    if approach_stats["insideFraction"] < 0.985:
        q1.duel.fail(f"V2_APPROACH_VISIBILITY_GATE:{approach_stats}")

    scene.frame_set(impact_frame)
    bpy.context.view_layer.update()
    impact_stats = _framing_stats(scene, impact, _bbox_points(actor_a["meshes"] + actor_b["meshes"]))
    if impact_stats["insideFraction"] < 0.965:
        q1.duel.fail(f"V2_IMPACT_VISIBILITY_GATE:{impact_stats}")

    scene.timeline_markers.clear()
    m = scene.timeline_markers.new("APPROACH", frame=q1.duel.START)
    m.camera = approach
    impact_cut = max(q1.duel.START + 1, impact_frame - 9)
    m = scene.timeline_markers.new("IMPACT", frame=impact_cut)
    m.camera = impact
    m = scene.timeline_markers.new("AFTERMATH", frame=aft_start)
    m.camera = aft_cam
    scene.camera = approach

    return {
        "cameras": [approach, impact, aft_cam],
        "approachFrame": q1.duel.START,
        "impactCutFrame": impact_cut,
        "aftermathFrame": aft_start,
        "aftermathDollyDistanceM": (start_loc - end_loc).length,
        "planner": "FRAME_BOUNDS_PROJECTION_AUTOFIT",
        "manualWorldCoordinates": False,
        "sceneScaleM": scale,
        "projectionValidated": True,
        "approachFraming": approach_stats,
        "impactFraming": impact_stats,
        "aftermathInitialFraming": aft_stats,
    }


def procedural_crumple_v2(actor: dict, impact_frame: int, front_sign: int, severity: float) -> dict:
    scene = bpy.context.scene
    scene.frame_set(q1.duel.START)
    bpy.context.view_layer.update()
    proxy = actor["proxy"]
    center_x = float(proxy.matrix_world.translation.x)
    half_len = float(actor["dims"].x) * 0.5
    crush_depth = max(0.42, half_len * 0.40)
    threshold = center_x + front_sign * (half_len - crush_depth)
    max_crush = min(0.31, half_len * (0.105 + 0.045 * severity))
    affected = 0
    mesh_count = 0
    max_disp = 0.0

    for obj in actor["meshes"]:
        if obj.type != "MESH" or len(obj.data.vertices) == 0:
            continue
        mats = _joined_materials(obj)
        if any(t in mats for t in BODY_EXCLUDE_TOKENS):
            continue
        try:
            if obj.data.shape_keys is None:
                obj.shape_key_add(name="Basis", from_mix=False)
            key = obj.shape_key_add(name=f"V2_Crumple_{actor['name']}", from_mix=False)
        except Exception:
            continue
        inv = obj.matrix_world.inverted()
        local_hits = 0
        local_max = 0.0
        for point in key.data:
            world = obj.matrix_world @ point.co
            depth = (world.x - threshold) * front_sign
            if depth <= 0.0:
                continue
            t = q1.clamp(depth / crush_depth, 0.0, 1.0)
            # Structured compression + two crease bands. No per-vertex noise/melting.
            compression = max_crush * (0.18 * t + 0.82 * t * t)
            crease_a = math.exp(-((t - 0.34) / 0.11) ** 2)
            crease_b = math.exp(-((t - 0.70) / 0.10) ** 2)
            target = world.copy()
            target.x -= front_sign * compression
            lateral_sign = -1.0 if world.y < 0.0 else 1.0
            target.y += lateral_sign * (0.018 * crease_a - 0.012 * crease_b) * severity
            target.z += (-0.045 * crease_a + 0.026 * crease_b - 0.018 * t) * severity
            disp = (target - world).length
            point.co = inv @ target
            local_hits += 1
            local_max = max(local_max, disp)
        if local_hits:
            key.value = 0.0
            key.keyframe_insert(data_path="value", frame=max(q1.duel.START, impact_frame - 1))
            key.value = 1.0
            key.keyframe_insert(data_path="value", frame=min(q1.duel.END, impact_frame + 4))
            affected += local_hits
            mesh_count += 1
            max_disp = max(max_disp, local_max)
        else:
            obj.shape_key_remove(key)

    if affected < 500:
        q1.duel.fail(f"{actor['name']}_V2_DAMAGE_VERTEX_GATE:{affected}")
    if not (0.12 <= max_disp <= 0.34):
        q1.duel.fail(f"{actor['name']}_V2_DAMAGE_DISPLACEMENT_GATE:{max_disp}")
    return {
        "affectedVertices": affected,
        "affectedMeshes": mesh_count,
        "maxVertexDisplacementM": max_disp,
        "physicalSolver": False,
        "impactTriggered": True,
        "method": "STRUCTURED_PANEL_COMPRESSION_WITH_CREASE_BANDS",
        "randomVertexNoise": False,
    }


def _candidate_parts(actor: dict, front_sign: int) -> list[bpy.types.Object]:
    bpy.context.view_layer.update()
    center_x = float(actor["proxy"].matrix_world.translation.x)
    half_len = float(actor["dims"].x) * 0.5
    scored = []
    for obj in actor["meshes"]:
        if obj.type != "MESH" or len(obj.data.vertices) < 8:
            continue
        lo, hi = _bbox(obj)
        c = (lo + hi) * 0.5
        frontness = ((c.x - center_x) * front_sign) / max(half_len, 1e-6)
        if frontness < 0.20:
            continue
        dims = hi - lo
        diag = dims.length
        if diag > float(actor["dims"].x) * 0.62:
            continue
        mats = _joined_materials(obj)
        semantic = 1 if any(t in mats for t in BREAK_TOKENS) else 0
        # Prefer real semantic front components, then small actual front geometry.
        score = semantic * 100.0 + frontness * 10.0 - diag
        scored.append((score, obj))
    scored.sort(key=lambda x: x[0], reverse=True)
    return [o for _, o in scored]


def _part_category(obj: bpy.types.Object) -> str:
    mats = _joined_materials(obj)
    if "glass" in mats or "headlight" in mats or "reflector" in mats:
        return "glass"
    if "plastic" in mats or "grill" in mats or "grille" in mats or "bumper" in mats:
        return "plastic"
    return "metal"


def actual_geometry_debris_v2(scene: bpy.types.Scene, actor_a: dict, actor_b: dict, impact_frame: int, center: Vector, severity: float) -> dict:
    rng = random.Random(92017)
    release = min(q1.duel.END - 2, impact_frame + 2)
    selected: list[tuple[dict, int, bpy.types.Object]] = []
    for actor, sign in ((actor_a, +1), (actor_b, -1)):
        parts = _candidate_parts(actor, sign)
        if len(parts) < 6:
            q1.duel.fail(f"{actor['name']}_V2_BREAKABLE_SOURCE_PARTS_TOO_FEW:{len(parts)}")
        selected.extend((actor, sign, p) for p in parts[:6])

    pieces: list[bpy.types.Object] = []
    source_names = []
    source_materials = set()
    category_counts = {"glass": 0, "plastic": 0, "metal": 0}

    scene.frame_set(impact_frame)
    bpy.context.view_layer.update()
    for idx, (actor, sign, src) in enumerate(selected):
        category = _part_category(src)
        category_counts[category] += 1
        source_names.append(src.name)
        source_materials.update(q1.mat_names(src))

        dup = src.copy()
        dup.data = src.data.copy()
        dup.name = f"V2_ACTUAL_BREAKOFF_{actor['name']}_{idx+1:02d}_{src.name}"
        bpy.context.collection.objects.link(dup)
        mw = src.matrix_world.copy()
        dup.parent = None
        dup.matrix_world = mw

        # The source component remains on the car before impact and disappears only
        # when the exact copied component is released as debris.
        src.hide_render = False
        src.keyframe_insert(data_path="hide_render", frame=max(q1.duel.START, impact_frame - 1))
        src.hide_render = True
        src.keyframe_insert(data_path="hide_render", frame=impact_frame)

        dup.hide_render = True
        dup.keyframe_insert(data_path="hide_render", frame=max(q1.duel.START, impact_frame - 1))
        dup.hide_render = False
        dup.keyframe_insert(data_path="hide_render", frame=impact_frame)

        q1.core.activate(dup)
        bpy.ops.rigidbody.object_add()
        rb = dup.rigid_body
        rb.type = "ACTIVE"
        rb.collision_shape = "CONVEX_HULL"
        rb.mass = rng.uniform(0.08, 0.42) if category == "glass" else rng.uniform(0.35, 2.4)
        rb.friction = 0.40
        rb.restitution = 0.08 if category == "glass" else 0.035
        rb.linear_damping = 0.04
        rb.angular_damping = 0.035
        rb.use_deactivation = False
        rb.kinematic = True
        rb.keyframe_insert(data_path="kinematic", frame=q1.duel.START)
        rb.keyframe_insert(data_path="kinematic", frame=impact_frame)

        p0 = dup.location.copy()
        dup.keyframe_insert(data_path="location", frame=impact_frame)
        radial = Vector((sign * rng.uniform(0.20, 0.75), rng.uniform(-1.0, 1.0), rng.uniform(0.28, 0.95)))
        radial.normalize()
        impulse = radial * rng.uniform(0.22, 0.58) * (0.82 + 0.18 * severity)
        dup.location = p0 + impulse
        dup.keyframe_insert(data_path="location", frame=release)
        rb.kinematic = False
        rb.keyframe_insert(data_path="kinematic", frame=release)
        if dup.animation_data and dup.animation_data.action:
            for fc in dup.animation_data.action.fcurves:
                for k in fc.keyframe_points:
                    k.interpolation = "LINEAR"
        pieces.append(dup)

    if len(pieces) < 12:
        q1.duel.fail(f"V2_ACTUAL_GEOMETRY_DEBRIS_COUNT:{len(pieces)}")

    if scene.rigidbody_world is None:
        q1.duel.fail("V2_DEBRIS_RIGID_WORLD_MISSING")
    scene.rigidbody_world.point_cache.frame_start = q1.duel.START
    scene.rigidbody_world.point_cache.frame_end = q1.duel.END
    scene.rigidbody_world.substeps_per_frame = 30
    scene.rigidbody_world.solver_iterations = 50

    records = {o.name: {} for o in pieces}
    for frame in range(q1.duel.START, q1.duel.END + 1):
        scene.frame_set(frame)
        bpy.context.view_layer.update()
        for obj in pieces:
            records[obj.name][frame] = (obj.matrix_world.translation.copy(), obj.matrix_world.to_quaternion().copy())

    max_disp = 0.0
    for obj in pieces:
        start_loc = records[obj.name][release][0]
        end_loc = records[obj.name][q1.duel.END][0]
        max_disp = max(max_disp, (end_loc - start_loc).length)
        q1.core.activate(obj)
        bpy.ops.rigidbody.object_remove()
        obj.animation_data_clear()
        obj.rotation_mode = "QUATERNION"
        for frame in range(q1.duel.START, q1.duel.END + 1):
            loc, quat = records[obj.name][frame]
            obj.location = loc
            obj.rotation_quaternion = quat
            obj.keyframe_insert(data_path="location", frame=frame)
            obj.keyframe_insert(data_path="rotation_quaternion", frame=frame)
        obj.hide_render = True
        obj.keyframe_insert(data_path="hide_render", frame=max(q1.duel.START, impact_frame - 1))
        obj.hide_render = False
        obj.keyframe_insert(data_path="hide_render", frame=impact_frame)

    if max_disp < 0.35:
        q1.duel.fail(f"V2_ACTUAL_DEBRIS_DYNAMICS_GATE:{max_disp}")
    return {
        "count": len(pieces),
        "releaseFrame": release,
        "maxDisplacementM": max_disp,
        "categories": category_counts,
        "sourceMaterialNames": sorted(source_materials),
        "sourceObjectNames": source_names,
        "sourceMaterialDriven": len(source_materials) >= 2,
        "primitiveBoxDebris": False,
        "rigidBodyAfterRelease": True,
        "impactTriggered": True,
        "geometrySource": "EXACT_IMPORTED_SOURCE_OBJECT_DUPLICATES",
        "syntheticShardGeometry": False,
    }


q1.procedural_crumple = procedural_crumple_v2
q1.semantic_debris = actual_geometry_debris_v2
q1.setup_auto_cameras = setup_auto_cameras_v2

if __name__ == "__main__":
    q1.main()
