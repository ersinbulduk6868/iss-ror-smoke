from __future__ import annotations

import argparse
import json
import math
import random
import sys
from pathlib import Path
from typing import Iterable

import bpy
from mathutils import Vector

FPS = 24
START = 1
END = 144
HANDOFF = 5
CAR_MASS = 1570.0
DOZER_MASS = 27614.189525707065
CAR_TARGET_LENGTH = 4.4
DOZER_TARGET_LENGTH = 6.1


def args() -> argparse.Namespace:
    argv = sys.argv
    argv = argv[argv.index("--") + 1:] if "--" in argv else []
    p = argparse.ArgumentParser()
    p.add_argument("--bugatti", required=True)
    p.add_argument("--bulldozer", required=True)
    p.add_argument("--asset-manifest", required=True)
    p.add_argument("--out", default="artifacts/visual-v4-preflight")
    p.add_argument("--mode", choices=("preflight", "final"), default="preflight")
    return p.parse_args(argv)


def fail(msg: str) -> None:
    raise RuntimeError(msg)


def activate(obj: bpy.types.Object) -> None:
    bpy.ops.object.select_all(action="DESELECT")
    obj.select_set(True)
    bpy.context.view_layer.objects.active = obj


def material(name: str, color: tuple[float, float, float, float], metallic: float = 0.0, roughness: float = 0.5) -> bpy.types.Material:
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    bsdf = m.node_tree.nodes.get("Principled BSDF")
    if bsdf:
        bsdf.inputs["Base Color"].default_value = color
        bsdf.inputs["Metallic"].default_value = metallic
        bsdf.inputs["Roughness"].default_value = roughness
    return m


def cube(name: str, loc: tuple[float, float, float], dims: tuple[float, float, float], mat: bpy.types.Material | None = None) -> bpy.types.Object:
    bpy.ops.mesh.primitive_cube_add(size=1.0, location=loc)
    o = bpy.context.object
    o.name = name
    o.dimensions = dims
    activate(o)
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    if mat:
        o.data.materials.append(mat)
    return o


def mesh_objects(objects: Iterable[bpy.types.Object]) -> list[bpy.types.Object]:
    return [o for o in objects if o.type == "MESH" and len(o.data.vertices) > 0]


def world_bbox(objects: Iterable[bpy.types.Object]) -> tuple[Vector, Vector]:
    pts: list[Vector] = []
    for o in mesh_objects(objects):
        for c in o.bound_box:
            pts.append(o.matrix_world @ Vector(c))
    if not pts:
        fail("VISIBLE_MESH_BOUNDS_MISSING")
    lo = Vector((min(p.x for p in pts), min(p.y for p in pts), min(p.z for p in pts)))
    hi = Vector((max(p.x for p in pts), max(p.y for p in pts), max(p.z for p in pts)))
    return lo, hi


def recenter_floor(root: bpy.types.Object, objects: list[bpy.types.Object]) -> tuple[Vector, Vector]:
    lo, hi = world_bbox(objects)
    center = (lo + hi) * 0.5
    root.location += Vector((-center.x, -center.y, -lo.z))
    bpy.context.view_layer.update()
    return world_bbox(objects)


def semantic_centroid_x(objects: list[bpy.types.Object], terms: tuple[str, ...]) -> float | None:
    xs: list[float] = []
    for o in mesh_objects(objects):
        n = o.name.lower()
        if not any(t in n for t in terms):
            continue
        lo, hi = world_bbox([o])
        xs.append((lo.x + hi.x) * 0.5)
    return sum(xs) / len(xs) if xs else None


def import_actor(name: str, path: Path, target_length: float, want_front_sign: int) -> dict:
    if not path.is_file():
        fail(f"{name}_PRIMARY_SCENE_MISSING:{path}")
    before = set(bpy.data.objects)
    bpy.ops.import_scene.gltf(filepath=str(path))
    new = [o for o in bpy.data.objects if o not in before]
    meshes = mesh_objects(new)
    if not meshes:
        fail(f"{name}_IMPORT_NO_MESH")

    root = bpy.data.objects.new(f"{name}_VISUAL_ROOT", None)
    bpy.context.collection.objects.link(root)
    new_set = set(new)
    for o in new:
        if o.parent is None or o.parent not in new_set:
            mw = o.matrix_world.copy()
            o.parent = root
            o.matrix_world = mw

    bpy.context.view_layer.update()
    lo, hi = world_bbox(meshes)
    dims = hi - lo
    if dims.y > dims.x:
        root.rotation_euler.z -= math.pi / 2.0
        bpy.context.view_layer.update()
    lo, hi = recenter_floor(root, meshes)
    dims = hi - lo
    if dims.x <= 1e-5:
        fail(f"{name}_ZERO_LENGTH")
    scale = target_length / dims.x
    root.scale = tuple(float(x) * scale for x in root.scale)
    bpy.context.view_layer.update()
    lo, hi = recenter_floor(root, meshes)

    if name == "BUGATTI":
        front_x = semantic_centroid_x(meshes, ("front", "hood", "bonnet", "bumper", "headlight", "grill", "grille"))
        if front_x is None:
            fail("BUGATTI_FRONT_SEMANTIC_UNRESOLVED")
    else:
        front_x = semantic_centroid_x(meshes, ("blade", "dozerblade", "dozer_blade"))
        if front_x is None:
            fail("BULLDOZER_BLADE_SEMANTIC_UNRESOLVED")

    current_sign = 1 if front_x >= 0.0 else -1
    if current_sign != want_front_sign:
        root.rotation_euler.z += math.pi
        bpy.context.view_layer.update()
        lo, hi = recenter_floor(root, meshes)

    lo, hi = world_bbox(meshes)
    dims = hi - lo
    if abs(dims.x - target_length) > target_length * 0.08:
        fail(f"{name}_NORMALIZED_LENGTH_GATE:{dims.x}")

    return {"name": name, "root": root, "objects": new, "meshes": meshes, "dims": dims}


def add_proxy(actor: dict, mass: float, friction: float) -> bpy.types.Object:
    d: Vector = actor["dims"]
    p = cube(
        f"PHYSICS_{actor['name']}",
        (0.0, 0.0, d.z * 0.5),
        (d.x * 0.96, d.y * 0.92, max(0.35, d.z * 0.88)),
        None,
    )
    p.display_type = "WIRE"
    p.hide_render = True
    activate(p)
    bpy.ops.rigidbody.object_add()
    rb = p.rigid_body
    rb.type = "ACTIVE"
    rb.collision_shape = "BOX"
    rb.mass = mass
    rb.friction = friction
    rb.restitution = 0.02
    rb.linear_damping = 0.015
    rb.angular_damping = 0.06
    rb.use_deactivation = False

    root = actor["root"]
    mw = root.matrix_world.copy()
    root.parent = p
    root.matrix_world = mw
    actor["proxy"] = p
    return p


def seed_velocity(proxy: bpy.types.Object, x1: float, velocity_x: float) -> None:
    rb = proxy.rigid_body
    dt = (4 - 1) / FPS
    x4 = x1 + velocity_x * dt
    rb.kinematic = True
    rb.keyframe_insert(data_path="kinematic", frame=1)
    proxy.location.x = x1
    proxy.keyframe_insert(data_path="location", frame=1)
    proxy.location.x = x4
    proxy.keyframe_insert(data_path="location", frame=4)
    rb.keyframe_insert(data_path="kinematic", frame=4)
    rb.kinematic = False
    rb.keyframe_insert(data_path="kinematic", frame=HANDOFF)
    if proxy.animation_data and proxy.animation_data.action:
        for fc in proxy.animation_data.action.fcurves:
            for k in fc.keyframe_points:
                k.interpolation = "LINEAR"


def no_post_handoff_vehicle_location_keys(actor: dict) -> bool:
    p = actor["proxy"]
    if not p.animation_data or not p.animation_data.action:
        return True
    for fc in p.animation_data.action.fcurves:
        if fc.data_path == "location":
            for k in fc.keyframe_points:
                if k.co.x >= HANDOFF:
                    return False
    return True


def setup_environment(scene: bpy.types.Scene) -> dict:
    road_mat = material("ROAD_MAT", (0.17, 0.19, 0.21, 1), 0.0, 0.72)
    line_mat = material("LINE_MAT", (0.72, 0.74, 0.76, 1), 0.0, 0.55)
    concrete = material("CONCRETE_MAT", (0.28, 0.30, 0.32, 1), 0.0, 0.72)
    road = cube("ROAD", (0, 0, -0.14), (110, 18, 0.28), road_mat)
    activate(road)
    bpy.ops.rigidbody.object_add()
    road.rigid_body.type = "PASSIVE"
    road.rigid_body.collision_shape = "BOX"
    road.rigid_body.friction = 0.04
    road.rigid_body.restitution = 0.0
    for x in range(-48, 49, 6):
        cube(f"LANE_{x}", (x, 0, 0.015), (2.8, 0.12, 0.03), line_mat)
    for y in (-7.2, 7.2):
        for x in (-36, -24, -12, 0, 12, 24, 36):
            cube(f"BARRIER_{x}_{y}", (x, y, 0.5), (3.0, 0.45, 1.0), concrete)

    scene.world.use_nodes = True
    bg = scene.world.node_tree.nodes.get("Background")
    bg.inputs["Color"].default_value = (0.32, 0.48, 0.72, 1)
    bg.inputs["Strength"].default_value = 0.85

    bpy.ops.object.light_add(type="SUN", location=(0, -6, 14))
    sun = bpy.context.object
    sun.name = "KEY_SUN"
    sun.data.energy = 3.0
    sun.data.angle = math.radians(6)
    sun.rotation_euler = (math.radians(35), math.radians(-20), math.radians(-35))

    areas = []
    for i, (loc, energy, size) in enumerate([
        ((-10, -12, 10), 1450, 7.0),
        ((12, 8, 8), 1100, 6.0),
        ((0, -2, 12), 1200, 5.0),
    ]):
        bpy.ops.object.light_add(type="AREA", location=loc)
        light = bpy.context.object
        light.name = f"FILL_AREA_{i+1}"
        light.data.energy = energy
        light.data.shape = "DISK"
        light.data.size = size
        light.rotation_euler = (0.0, 0.0, 0.0)
        direction = Vector((0, 0, 1.0)) - light.location
        light.rotation_euler = direction.to_track_quat("-Z", "Y").to_euler()
        areas.append(light)
    return {"worldStrength": 0.85, "sunEnergy": 3.0, "areaEnergies": [x.data.energy for x in areas], "lightCount": 1 + len(areas)}


def proxy_overlap(car: dict, dozer: dict) -> bool:
    a = car["proxy"]
    b = dozer["proxy"]
    da = Vector(a.dimensions) * 0.5
    db = Vector(b.dimensions) * 0.5
    pa = a.matrix_world.translation
    pb = b.matrix_world.translation
    return abs(pa.x - pb.x) <= da.x + db.x + 0.08 and abs(pa.y - pb.y) <= da.y + db.y + 0.08


def simulate_vehicles(scene: bpy.types.Scene, car: dict, dozer: dict) -> dict:
    if scene.rigidbody_world is None:
        fail("RIGID_BODY_WORLD_MISSING")
    scene.rigidbody_world.point_cache.frame_start = START
    scene.rigidbody_world.point_cache.frame_end = END
    scene.rigidbody_world.substeps_per_frame = 30
    scene.rigidbody_world.solver_iterations = 50

    records = {"car": {}, "dozer": {}}
    prev_c = prev_d = None
    impact = None
    impact_data = None
    car_pre_max = 0.0
    dozer_pre_max = 0.0
    dozer_post_max = 0.0
    car_approach = False
    dozer_approach = False
    dozer_pre_vx = None
    dozer_post_vx = None

    scene.frame_set(START)
    for f in range(START, END + 1):
        scene.frame_set(f)
        bpy.context.view_layer.update()
        pc = car["proxy"].matrix_world.translation.copy()
        pd = dozer["proxy"].matrix_world.translation.copy()
        qc = car["proxy"].matrix_world.to_quaternion().copy()
        qd = dozer["proxy"].matrix_world.to_quaternion().copy()
        records["car"][f] = (pc.copy(), qc)
        records["dozer"][f] = (pd.copy(), qd)
        vc = Vector((0, 0, 0)) if prev_c is None else (pc - prev_c) * FPS
        vd = Vector((0, 0, 0)) if prev_d is None else (pd - prev_d) * FPS

        if f >= HANDOFF and impact is None:
            car_pre_max = max(car_pre_max, vc.length)
            dozer_pre_max = max(dozer_pre_max, vd.length)
            car_approach = car_approach or vc.x > 5.0
            dozer_approach = dozer_approach or vd.x < -1.5
            if f >= HANDOFF + 2 and proxy_overlap(car, dozer) and (vc - vd).length > 2.0:
                impact = f
                dozer_pre_vx = vd.x
                impact_data = {
                    "carPosition": list(pc),
                    "dozerPosition": list(pd),
                    "carVelocity": list(vc),
                    "dozerVelocity": list(vd),
                    "relativeSpeed": (vc - vd).length,
                    "center": list((pc + pd) * 0.5),
                }
        elif impact is not None:
            dozer_post_max = max(dozer_post_max, vd.length)
            if f >= impact + 6 and dozer_post_vx is None:
                dozer_post_vx = vd.x

        prev_c, prev_d = pc, pd

    if impact is None or impact_data is None:
        fail("HEAD_ON_IMPACT_NOT_OBSERVED")
    center_x = float(impact_data["center"][0])
    if abs(center_x) > 2.5:
        fail(f"IMPACT_NOT_CENTERED:{center_x}")
    if not (car_approach and dozer_approach):
        fail("TWO_SIDED_APPROACH_GATE_FAIL")
    if car_pre_max < 10.0 or dozer_pre_max < 2.5:
        fail(f"APPROACH_SPEED_GATE_FAIL:{car_pre_max}:{dozer_pre_max}")
    if dozer_post_vx is None:
        fail("BULLDOZER_POST_IMPACT_SAMPLE_MISSING")
    dozer_response_delta = abs(float(dozer_post_vx) - float(dozer_pre_vx))
    if dozer_response_delta < 0.03:
        fail(f"BULLDOZER_IMPACT_RESPONSE_TOO_SMALL:{dozer_response_delta}")

    return {
        "records": records,
        "impactFrame": impact,
        "impactData": impact_data,
        "carApproach": car_approach,
        "dozerApproach": dozer_approach,
        "carPreImpactMaxSpeed": car_pre_max,
        "dozerPreImpactMaxSpeed": dozer_pre_max,
        "dozerPostImpactMaxSpeed": dozer_post_max,
        "dozerResponseDeltaVx": dozer_response_delta,
    }


def bake_actor(actor: dict, record: dict[int, tuple[Vector, object]]) -> None:
    p = actor["proxy"]
    activate(p)
    bpy.ops.rigidbody.object_remove()
    p.animation_data_clear()
    p.rotation_mode = "QUATERNION"
    for f in range(START, END + 1):
        loc, quat = record[f]
        p.location = loc
        p.rotation_quaternion = quat
        p.keyframe_insert(data_path="location", frame=f)
        p.keyframe_insert(data_path="rotation_quaternion", frame=f)


def impact_damage(car: dict, impact_frame: int) -> int:
    scene = bpy.context.scene
    scene.frame_set(START)
    bpy.context.view_layer.update()
    proxy = car["proxy"]
    car_center_x = proxy.matrix_world.translation.x
    half_len = float(car["dims"].x) * 0.5
    threshold = car_center_x + half_len * 0.42
    affected = 0
    for obj in car["meshes"]:
        if obj.type != "MESH" or len(obj.data.vertices) == 0:
            continue
        try:
            if obj.data.shape_keys is None:
                obj.shape_key_add(name="Basis", from_mix=False)
            key = obj.shape_key_add(name="ImpactCrumple", from_mix=False)
        except Exception:
            continue
        inv = obj.matrix_world.inverted()
        local_hits = 0
        for i, point in enumerate(key.data):
            world = obj.matrix_world @ point.co
            if world.x <= threshold:
                continue
            t = min(1.0, max(0.0, (world.x - threshold) / max(0.20, half_len * 0.58)))
            target = world.copy()
            target.x -= 0.72 * t
            target.z -= 0.16 * t
            target.y += (0.08 if (i % 2) else -0.08) * t
            point.co = inv @ target
            local_hits += 1
        if local_hits:
            key.value = 0.0
            key.keyframe_insert(data_path="value", frame=max(START, impact_frame - 1))
            key.value = 1.0
            key.keyframe_insert(data_path="value", frame=min(END, impact_frame + 5))
            affected += local_hits
        else:
            obj.shape_key_remove(key)
    if affected < 500:
        fail(f"DAMAGE_VERTEX_GATE_TOO_LOW:{affected}")
    return affected


def make_debris(scene: bpy.types.Scene, impact_frame: int, impact_center: Vector) -> dict:
    metal = material("DEBRIS_METAL", (0.08, 0.12, 0.20, 1), 0.75, 0.28)
    glass = material("DEBRIS_GLASS", (0.10, 0.32, 0.50, 1), 0.15, 0.18)
    rng = random.Random(42)
    pieces: list[bpy.types.Object] = []
    release = min(END - 2, impact_frame + 1)
    for i in range(16):
        size = rng.uniform(0.08, 0.20)
        o = cube(f"IMPACT_DEBRIS_{i+1:02d}", tuple(impact_center + Vector((rng.uniform(-0.25, 0.25), rng.uniform(-0.5, 0.5), rng.uniform(0.25, 0.65)))), (size * rng.uniform(1.0, 2.3), size * rng.uniform(0.5, 1.4), size * rng.uniform(0.35, 1.0)), glass if i % 5 == 0 else metal)
        activate(o)
        bpy.ops.rigidbody.object_add()
        rb = o.rigid_body
        rb.type = "ACTIVE"
        rb.collision_shape = "BOX"
        rb.mass = rng.uniform(0.3, 2.0)
        rb.friction = 0.38
        rb.restitution = 0.14
        rb.linear_damping = 0.05
        rb.angular_damping = 0.04
        rb.use_deactivation = False
        rb.kinematic = True
        rb.keyframe_insert(data_path="kinematic", frame=1)
        o.hide_render = True
        o.keyframe_insert(data_path="hide_render", frame=max(1, impact_frame - 1))
        o.hide_render = False
        o.keyframe_insert(data_path="hide_render", frame=impact_frame)

        base = o.location.copy()
        o.location = base - Vector((0.08, 0, 0.02))
        o.keyframe_insert(data_path="location", frame=max(1, impact_frame - 1))
        o.location = base + Vector((rng.uniform(0.06, 0.22), rng.uniform(-0.12, 0.12), rng.uniform(0.05, 0.18)))
        o.keyframe_insert(data_path="location", frame=impact_frame)
        rb.keyframe_insert(data_path="kinematic", frame=impact_frame)
        rb.kinematic = False
        rb.keyframe_insert(data_path="kinematic", frame=release)
        if o.animation_data and o.animation_data.action:
            for fc in o.animation_data.action.fcurves:
                for k in fc.keyframe_points:
                    k.interpolation = "LINEAR"
        pieces.append(o)

    if scene.rigidbody_world is None:
        fail("DEBRIS_RIGID_WORLD_MISSING")
    scene.rigidbody_world.point_cache.frame_start = START
    scene.rigidbody_world.point_cache.frame_end = END
    scene.rigidbody_world.substeps_per_frame = 30
    scene.rigidbody_world.solver_iterations = 50

    records: dict[str, dict[int, tuple[Vector, object]]] = {o.name: {} for o in pieces}
    scene.frame_set(START)
    for f in range(START, END + 1):
        scene.frame_set(f)
        bpy.context.view_layer.update()
        for o in pieces:
            records[o.name][f] = (o.matrix_world.translation.copy(), o.matrix_world.to_quaternion().copy())

    max_disp = 0.0
    for o in pieces:
        start_loc = records[o.name][release][0]
        end_loc = records[o.name][END][0]
        max_disp = max(max_disp, (end_loc - start_loc).length)
        activate(o)
        bpy.ops.rigidbody.object_remove()
        o.animation_data_clear()
        o.rotation_mode = "QUATERNION"
        for f in range(START, END + 1):
            loc, quat = records[o.name][f]
            o.location = loc
            o.rotation_quaternion = quat
            o.keyframe_insert(data_path="location", frame=f)
            o.keyframe_insert(data_path="rotation_quaternion", frame=f)
        o.hide_render = True
        o.keyframe_insert(data_path="hide_render", frame=max(1, impact_frame - 1))
        o.hide_render = False
        o.keyframe_insert(data_path="hide_render", frame=impact_frame)

    if max_disp < 0.35:
        fail(f"DEBRIS_DYNAMICS_DISPLACEMENT_TOO_LOW:{max_disp}")
    return {"count": len(pieces), "releaseFrame": release, "maxDisplacement": max_disp, "rigidBodyAfterRelease": True, "impactTriggered": True}


def camera(name: str, loc: tuple[float, float, float], lens: float, target: bpy.types.Object) -> bpy.types.Object:
    bpy.ops.object.camera_add(location=loc)
    cam = bpy.context.object
    cam.name = name
    cam.data.lens = lens
    cam.data.clip_end = 1000.0
    c = cam.constraints.new(type="TRACK_TO")
    c.target = target
    c.track_axis = "TRACK_NEGATIVE_Z"
    c.up_axis = "UP_Y"
    return cam


def setup_cameras(scene: bpy.types.Scene, impact_frame: int, center: Vector) -> dict:
    bpy.ops.object.empty_add(type="PLAIN_AXES", location=(center.x, center.y, 1.3))
    target = bpy.context.object
    target.name = "CAMERA_TARGET"
    wide = camera("CAM_APPROACH_WIDE", (center.x - 4, -46, 10.5), 34, target)
    impact = camera("CAM_IMPACT_LOW", (center.x - 2.5, -13, 3.1), 54, target)
    aftermath = camera("CAM_AFTERMATH_DOLLY", (center.x + 4.5, -11.5, 3.4), 62, target)
    aft_start = min(END - 1, impact_frame + 14)
    aftermath.keyframe_insert(data_path="location", frame=aft_start)
    aftermath.location = (center.x + 1.4, -5.7, 2.25)
    aftermath.keyframe_insert(data_path="location", frame=END)

    scene.timeline_markers.clear()
    m = scene.timeline_markers.new("APPROACH", frame=START)
    m.camera = wide
    impact_cut = max(START + 1, impact_frame - 10)
    m = scene.timeline_markers.new("IMPACT", frame=impact_cut)
    m.camera = impact
    m = scene.timeline_markers.new("AFTERMATH", frame=aft_start)
    m.camera = aftermath
    scene.camera = wide
    return {
        "cameras": [wide, impact, aftermath],
        "approachFrame": START,
        "impactCutFrame": impact_cut,
        "aftermathFrame": aft_start,
        "aftermathDollyDistance": (Vector((center.x + 4.5, -11.5, 3.4)) - Vector((center.x + 1.4, -5.7, 2.25))).length,
    }


def camera_for_frame(camdata: dict, frame: int) -> bpy.types.Object:
    if frame >= camdata["aftermathFrame"]:
        return camdata["cameras"][2]
    if frame >= camdata["impactCutFrame"]:
        return camdata["cameras"][1]
    return camdata["cameras"][0]


def configure_render(scene: bpy.types.Scene, mode: str, outdir: Path) -> None:
    scene.render.engine = "BLENDER_EEVEE_NEXT"
    if scene.render.engine != "BLENDER_EEVEE_NEXT":
        fail(f"EEVEE_NEXT_REQUIRED:{scene.render.engine}")
    if mode == "preflight":
        scene.render.resolution_x = 960
        scene.render.resolution_y = 540
    else:
        scene.render.resolution_x = 1920
        scene.render.resolution_y = 1080
    scene.render.resolution_percentage = 100
    scene.render.fps = FPS
    scene.render.image_settings.file_format = "PNG"
    scene.render.film_transparent = False
    try:
        scene.view_settings.look = "AgX - Medium High Contrast"
    except Exception:
        pass
    outdir.mkdir(parents=True, exist_ok=True)


def render_preflight(scene: bpy.types.Scene, camdata: dict, impact_frame: int, outdir: Path) -> list[dict]:
    frames = [max(START, impact_frame - 28), impact_frame, min(END, impact_frame + 40)]
    labels = ["approach", "impact", "aftermath"]
    rows = []
    for label, frame in zip(labels, frames):
        scene.frame_set(frame)
        scene.camera = camera_for_frame(camdata, frame)
        path = outdir / f"preview-{label}-f{frame:04d}.png"
        scene.render.filepath = str(path)
        bpy.ops.render.render(write_still=True)
        if not path.is_file() or path.stat().st_size < 20000:
            fail(f"PREVIEW_RENDER_INVALID:{path}")
        print(f"PREVIEW_FRAME=PASS|label={label}|frame={frame}|bytes={path.stat().st_size}", flush=True)
        rows.append({"label": label, "frame": frame, "path": str(path), "bytes": path.stat().st_size})
    return rows


def render_final(scene: bpy.types.Scene, camdata: dict, outdir: Path) -> list[str]:
    frames_dir = outdir / "frames"
    frames_dir.mkdir(parents=True, exist_ok=True)
    paths = []
    for frame in range(START, END + 1):
        scene.frame_set(frame)
        scene.camera = camera_for_frame(camdata, frame)
        path = frames_dir / f"frame_{frame:04d}.png"
        scene.render.filepath = str(path)
        bpy.ops.render.render(write_still=True)
        if not path.is_file() or path.stat().st_size < 20000:
            fail(f"FINAL_FRAME_INVALID:{frame}")
        print(f"RENDER_FRAME={frame}/{END}|bytes={path.stat().st_size}", flush=True)
        paths.append(str(path))
    return paths


def main() -> None:
    a = args()
    outdir = Path(a.out)
    manifest_path = Path(a.asset_manifest)
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if manifest.get("status") != "PASS" or manifest.get("quant120Forbidden") is not True:
        fail("ASSET_MANIFEST_NOT_PASS")

    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.object.delete(use_global=False)
    scene = bpy.context.scene
    scene.frame_start = START
    scene.frame_end = END
    scene.gravity = (0, 0, -9.81)
    configure_render(scene, a.mode, outdir)
    lighting = setup_environment(scene)

    # Car starts left and must face +X; bulldozer starts right and blade must face -X.
    car = import_actor("BUGATTI", Path(a.bugatti), CAR_TARGET_LENGTH, +1)
    dozer = import_actor("BULLDOZER", Path(a.bulldozer), DOZER_TARGET_LENGTH, -1)
    add_proxy(car, CAR_MASS, 0.20)
    add_proxy(dozer, DOZER_MASS, 0.44)
    seed_velocity(car["proxy"], -36.0, +16.0)
    seed_velocity(dozer["proxy"], +14.0, -5.0)

    if not no_post_handoff_vehicle_location_keys(car) or not no_post_handoff_vehicle_location_keys(dozer):
        fail("POST_HANDOFF_VEHICLE_LOCATION_KEY_DETECTED")

    sim = simulate_vehicles(scene, car, dozer)
    bake_actor(car, sim["records"]["car"])
    bake_actor(dozer, sim["records"]["dozer"])

    impact_frame = int(sim["impactFrame"])
    center = Vector(sim["impactData"]["center"])
    damage_vertices = impact_damage(car, impact_frame)
    debris = make_debris(scene, impact_frame, center)
    camdata = setup_cameras(scene, impact_frame, center)

    if lighting["lightCount"] < 4 or lighting["worldStrength"] < 0.7:
        fail("LIGHTING_STRUCTURE_GATE_FAIL")
    if len(camdata["cameras"]) < 3 or camdata["aftermathDollyDistance"] < 2.0:
        fail("CAMERA_STORY_STRUCTURE_GATE_FAIL")

    previews = render_preflight(scene, camdata, impact_frame, outdir) if a.mode == "preflight" else []
    final_frames = render_final(scene, camdata, outdir) if a.mode == "final" else []

    machine_gates = {
        "A1_twoSidedApproach": bool(sim["carApproach"] and sim["dozerApproach"]),
        "A2_headOnCenterImpact": abs(float(center.x)) <= 2.5,
        "A3_bulldozerActiveMotionAndResponse": sim["dozerPreImpactMaxSpeed"] >= 2.5 and sim["dozerResponseDeltaVx"] >= 0.03,
        "A4_damageGeometryCreated": damage_vertices >= 500,
        "A5_debrisRigidBodyAndImpactTriggered": debris["count"] >= 12 and debris["rigidBodyAfterRelease"] and debris["impactTriggered"] and debris["maxDisplacement"] >= 0.35,
        "A6_renderStructureImproved": scene.render.engine == "BLENDER_EEVEE_NEXT" and scene.render.resolution_x >= (960 if a.mode == "preflight" else 1920),
        "A7_threeCameraStructure": len(camdata["cameras"]) >= 3,
        "A8_aftermathDollyStructure": camdata["aftermathDollyDistance"] >= 2.0,
        "A9_storyShotStructure": camdata["impactCutFrame"] < camdata["aftermathFrame"] < END,
        "A11_lightingStructure": lighting["lightCount"] >= 4 and lighting["worldStrength"] >= 0.7,
    }
    if not all(machine_gates.values()):
        fail("MACHINE_GATE_FAIL:" + ",".join(k for k, v in machine_gates.items() if not v))

    result = {
        "scope": "ISS_BATTLE_VIDEO_VISUAL_ACCEPTANCE_V4",
        "mode": a.mode,
        "status": "MACHINE_PREFLIGHT_PASS_VISUAL_REVIEW_REQUIRED" if a.mode == "preflight" else "FINAL_RENDER_FRAMES_COMPLETE_VISUAL_REVIEW_REQUIRED",
        "engine": "BLENDER",
        "engineVersion": bpy.app.version_string,
        "renderEngine": scene.render.engine,
        "resolution": [scene.render.resolution_x, scene.render.resolution_y],
        "fps": FPS,
        "frameCount": END,
        "visualGeometry": "FULL_SOURCE_GLTF",
        "visualProxyUsed": False,
        "collisionProxyUsed": True,
        "vehicleMotionSolverDriven": True,
        "postHandoffVehicleLocationKeys": False,
        "damagePhysicalSolver": False,
        "damageImpactTriggered": True,
        "damageAffectedVertices": damage_vertices,
        "debrisRigidBody": True,
        "debrisReleaseImpactTriggered": True,
        "debrisCount": debris["count"],
        "debrisMaxDisplacement": debris["maxDisplacement"],
        "impactFrame": impact_frame,
        "impactTimeSeconds": impact_frame / FPS,
        "impactCenter": list(center),
        "carPreImpactMaxSpeedMps": sim["carPreImpactMaxSpeed"],
        "bulldozerPreImpactMaxSpeedMps": sim["dozerPreImpactMaxSpeed"],
        "bulldozerResponseDeltaVx": sim["dozerResponseDeltaVx"],
        "cameraShotCount": len(camdata["cameras"]),
        "aftermathDollyDistance": camdata["aftermathDollyDistance"],
        "lighting": lighting,
        "machineGates": machine_gates,
        "visualReviewRequired": ["A4_damage_readability", "A6_image_quality", "A11_scene_brightness", "overall_cinematic_readability"],
        "previews": previews,
        "finalFrames": final_frames,
        "assetManifest": str(manifest_path),
    }
    result_path = outdir / ("preflight-result.json" if a.mode == "preflight" else "final-result.json")
    result_path.write_text(json.dumps(result, indent=2), encoding="utf-8")
    print("ISS_VISUAL_V4_MACHINE_PREFLIGHT=PASS" if a.mode == "preflight" else "ISS_VISUAL_V4_FINAL_FRAMES=PASS", flush=True)


if __name__ == "__main__":
    main()
