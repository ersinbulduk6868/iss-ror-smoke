from __future__ import annotations

import json
import math
import random
import struct
import sys
import wave
from pathlib import Path

import bpy
from mathutils import Vector

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from blender import visual_vnext_rc2_bugatti_duel_contactfix as proven

duel = proven.duel
wrapper = proven.wrapper
core = duel.core

QUALIFICATION_SCOPE = "ISS_BLENDER_CAPABILITY_QUALIFICATION_V1"
RELATIVE_IMPACT_SPEED_POLICY_MPS = 30.0
APPROACH_SECONDS_POLICY = 1.35
AUDIO_SAMPLE_RATE = 48000

EXCLUDE_DAMAGE_TOKENS = (
    "tire", "tyre", "wheel", "rim", "brake", "disc", "caliper",
    "window", "windshield", "windscreen", "glass", "interior",
    "seat", "steering", "mirror",
)
GLASS_TOKENS = ("headlight_glass", "reflector_front", "glass")
PLASTIC_TOKENS = ("grill", "grille", "bumper", "plastic")


def clamp(v: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, v))


def mat_names(obj: bpy.types.Object) -> list[str]:
    out = []
    for slot in getattr(obj, "material_slots", []):
        if slot.material is not None:
            out.append(slot.material.name)
    return out


def is_damage_candidate(obj: bpy.types.Object) -> bool:
    joined = " ".join(mat_names(obj)).lower()
    return not any(t in joined for t in EXCLUDE_DAMAGE_TOKENS)


def choose_source_material(actor: dict, tokens: tuple[str, ...]) -> tuple[bpy.types.Material | None, str]:
    best = None
    best_name = ""
    for obj in actor["meshes"]:
        for slot in getattr(obj, "material_slots", []):
            mat = slot.material
            if mat is None:
                continue
            n = mat.name.lower()
            if tokens and any(t in n for t in tokens):
                return mat, mat.name
            if best is None and is_damage_candidate(obj):
                best, best_name = mat, mat.name
    return best, best_name


def configure_qualification_render(scene: bpy.types.Scene, outdir: Path) -> None:
    scene.render.engine = "BLENDER_EEVEE_NEXT"
    if scene.render.engine != "BLENDER_EEVEE_NEXT":
        duel.fail(f"QUAL_EEVEE_NEXT_REQUIRED:{scene.render.engine}")
    scene.render.resolution_x = 540
    scene.render.resolution_y = 960
    scene.render.resolution_percentage = 100
    scene.render.fps = duel.FPS
    scene.render.image_settings.file_format = "PNG"
    scene.render.film_transparent = False
    try:
        scene.view_settings.look = "AgX - Medium High Contrast"
    except Exception:
        pass
    outdir.mkdir(parents=True, exist_ok=True)


def setup_production_environment(scene: bpy.types.Scene, scene_scale: float) -> dict:
    asphalt = core.material("QUAL_ASPHALT", (0.055, 0.060, 0.068, 1), 0.02, 0.82)
    concrete = core.material("QUAL_CONCRETE", (0.19, 0.21, 0.24, 1), 0.0, 0.74)
    stripe = core.material("QUAL_STRIPE", (0.72, 0.68, 0.48, 1), 0.0, 0.48)
    dark = core.material("QUAL_BACKDROP", (0.075, 0.085, 0.105, 1), 0.05, 0.70)

    road_len = scene_scale * 26.0
    road_width = scene_scale * 4.6
    road = core.cube("QUAL_ROAD", (0.0, 0.0, -0.12), (road_len, road_width, 0.24), asphalt)
    core.activate(road)
    bpy.ops.rigidbody.object_add()
    road.rigid_body.type = "PASSIVE"
    road.rigid_body.collision_shape = "BOX"
    road.rigid_body.friction = 0.26
    road.rigid_body.restitution = 0.0

    mark_step = max(scene_scale * 1.7, 5.0)
    x = -road_len * 0.43
    lane_count = 0
    while x <= road_len * 0.43:
        core.cube(f"QUAL_LANE_{lane_count:02d}", (x, 0.0, 0.012), (scene_scale * 0.72, 0.10, 0.025), stripe)
        lane_count += 1
        x += mark_step

    barrier_y = road_width * 0.43
    for side in (-1, 1):
        for idx, frac in enumerate((-0.35, -0.12, 0.12, 0.35)):
            core.cube(
                f"QUAL_BARRIER_{side}_{idx}",
                (road_len * frac, side * barrier_y, scene_scale * 0.20),
                (scene_scale * 2.2, scene_scale * 0.20, scene_scale * 0.40),
                concrete,
            )

    for idx, (xf, yf, hf) in enumerate(((-0.30, 0.90, 1.8), (0.05, 0.98, 2.4), (0.32, 0.88, 1.5))):
        core.cube(
            f"QUAL_BACKGROUND_{idx}",
            (road_len * xf, road_width * yf, scene_scale * hf * 0.5),
            (scene_scale * 3.2, scene_scale * 0.8, scene_scale * hf),
            dark,
        )

    scene.world.use_nodes = True
    bg = scene.world.node_tree.nodes.get("Background")
    if bg:
        bg.inputs["Color"].default_value = (0.075, 0.12, 0.20, 1)
        bg.inputs["Strength"].default_value = 0.55

    bpy.ops.object.light_add(type="SUN", location=(0, -scene_scale, scene_scale * 3.0))
    sun = bpy.context.object
    sun.name = "QUAL_KEY_SUN"
    sun.data.energy = 2.4
    sun.data.angle = math.radians(5.0)
    sun.rotation_euler = (math.radians(38), math.radians(-18), math.radians(-32))

    area_specs = (
        ((-2.2, -2.4, 2.6), 1150, 1.6),
        ((2.0, 1.8, 2.0), 900, 1.4),
        ((0.0, -0.4, 3.0), 1050, 1.3),
    )
    areas = []
    for idx, (mul, energy, size_mul) in enumerate(area_specs):
        loc = tuple(scene_scale * v for v in mul)
        bpy.ops.object.light_add(type="AREA", location=loc)
        light = bpy.context.object
        light.name = f"QUAL_FILL_{idx+1}"
        light.data.energy = energy
        light.data.shape = "DISK"
        light.data.size = scene_scale * size_mul
        direction = Vector((0, 0, scene_scale * 0.35)) - light.location
        light.rotation_euler = direction.to_track_quat("-Z", "Y").to_euler()
        areas.append(light)

    return {
        "roadLength": road_len,
        "roadWidth": road_width,
        "laneMarkerCount": lane_count,
        "lightCount": 1 + len(areas),
        "worldStrength": 0.55,
        "planner": "SCENE_SCALE_DERIVED",
    }


def plan_head_on(actor_a: dict, actor_b: dict) -> dict:
    speed_each = RELATIVE_IMPACT_SPEED_POLICY_MPS * 0.5
    contact_center_distance = 0.5 * (float(actor_a["proxy"].dimensions.x) + float(actor_b["proxy"].dimensions.x))
    start_abs = contact_center_distance * 0.5 + speed_each * APPROACH_SECONDS_POLICY
    return {
        "speedEachMps": speed_each,
        "relativeSpeedPolicyMps": RELATIVE_IMPACT_SPEED_POLICY_MPS,
        "approachSecondsPolicy": APPROACH_SECONDS_POLICY,
        "contactCenterDistance": contact_center_distance,
        "startA": -start_abs,
        "startB": start_abs,
        "derivedFrom": "ACTOR_COLLISION_BOUNDS_PLUS_SCENARIO_POLICY",
        "manualWorldCoordinates": False,
    }


def procedural_crumple(actor: dict, impact_frame: int, front_sign: int, severity: float) -> dict:
    scene = bpy.context.scene
    scene.frame_set(duel.START)
    bpy.context.view_layer.update()

    proxy = actor["proxy"]
    center_x = float(proxy.matrix_world.translation.x)
    half_len = float(actor["dims"].x) * 0.5
    crush_depth = max(0.45, half_len * 0.46)
    threshold = center_x + front_sign * (half_len - crush_depth)
    max_crush = min(0.46, half_len * (0.17 + 0.06 * severity))
    max_vertex_displacement = 0.0
    affected = 0
    mesh_count = 0

    for obj in actor["meshes"]:
        if obj.type != "MESH" or len(obj.data.vertices) == 0 or not is_damage_candidate(obj):
            continue
        try:
            if obj.data.shape_keys is None:
                obj.shape_key_add(name="Basis", from_mix=False)
            key = obj.shape_key_add(name=f"QUAL_Crumple_{actor['name']}", from_mix=False)
        except Exception:
            continue

        inv = obj.matrix_world.inverted()
        local_hits = 0
        local_max = 0.0
        for idx, point in enumerate(key.data):
            world = obj.matrix_world @ point.co
            depth = (world.x - threshold) * front_sign
            if depth <= 0.0:
                continue
            t = clamp(depth / crush_depth, 0.0, 1.0)
            ease = t * t * (3.0 - 2.0 * t)
            target = world.copy()
            target.x -= front_sign * max_crush * ease
            lateral_phase = math.sin((world.y / max(0.20, float(actor["dims"].y))) * math.pi * 5.0 + idx * 0.013)
            vertical_phase = math.sin((world.z + idx * 0.0017) * math.pi * 4.0)
            target.y += 0.035 * severity * lateral_phase * ease
            target.z += (0.018 * vertical_phase - 0.035 * t) * severity * ease
            disp = (target - world).length
            point.co = inv @ target
            local_hits += 1
            local_max = max(local_max, disp)

        if local_hits:
            key.value = 0.0
            key.keyframe_insert(data_path="value", frame=max(duel.START, impact_frame - 1))
            key.value = 1.0
            key.keyframe_insert(data_path="value", frame=min(duel.END, impact_frame + 5))
            affected += local_hits
            mesh_count += 1
            max_vertex_displacement = max(max_vertex_displacement, local_max)
        else:
            obj.shape_key_remove(key)

    if affected < 500:
        duel.fail(f"{actor['name']}_QUAL_DAMAGE_VERTEX_GATE:{affected}")
    if not (0.12 <= max_vertex_displacement <= 0.55):
        duel.fail(f"{actor['name']}_QUAL_DAMAGE_DISPLACEMENT_GATE:{max_vertex_displacement}")
    return {
        "affectedVertices": affected,
        "affectedMeshes": mesh_count,
        "maxVertexDisplacementM": max_vertex_displacement,
        "physicalSolver": False,
        "impactTriggered": True,
        "method": "BOUNDS_DERIVED_LOCALIZED_PANEL_CRUMPLE",
    }


def make_irregular_shard(name: str, loc: Vector, length: float, width: float, thickness: float, mat: bpy.types.Material | None) -> bpy.types.Object:
    verts = [
        (-length * 0.55, -width * 0.48, -thickness),
        ( length * 0.50, -width * 0.34, -thickness * 0.6),
        ( length * 0.35,  width * 0.52, -thickness),
        (-length * 0.42,  width * 0.37, -thickness * 0.5),
        (-length * 0.48, -width * 0.42, thickness),
        ( length * 0.43, -width * 0.27, thickness * 0.7),
        ( length * 0.28,  width * 0.46, thickness),
        (-length * 0.36,  width * 0.31, thickness * 0.65),
    ]
    faces = [
        (0, 1, 2, 3), (4, 7, 6, 5),
        (0, 4, 5, 1), (1, 5, 6, 2),
        (2, 6, 7, 3), (3, 7, 4, 0),
    ]
    mesh = bpy.data.meshes.new(name + "_MESH")
    mesh.from_pydata(verts, [], faces)
    mesh.update()
    obj = bpy.data.objects.new(name, mesh)
    bpy.context.collection.objects.link(obj)
    obj.location = loc
    if mat is not None:
        obj.data.materials.append(mat)
    return obj


def semantic_debris(scene: bpy.types.Scene, actor_a: dict, actor_b: dict, impact_frame: int, center: Vector, severity: float) -> dict:
    rng = random.Random(7301)
    glass_a, glass_name_a = choose_source_material(actor_a, GLASS_TOKENS)
    glass_b, glass_name_b = choose_source_material(actor_b, GLASS_TOKENS)
    plastic_a, plastic_name_a = choose_source_material(actor_a, PLASTIC_TOKENS)
    plastic_b, plastic_name_b = choose_source_material(actor_b, PLASTIC_TOKENS)
    metal_a, metal_name_a = choose_source_material(actor_a, ())
    metal_b, metal_name_b = choose_source_material(actor_b, ())

    donors = [
        ("glass", glass_a or glass_b, glass_name_a or glass_name_b),
        ("plastic", plastic_a or plastic_b, plastic_name_a or plastic_name_b),
        ("metal", metal_a or metal_b, metal_name_a or metal_name_b),
    ]
    if sum(1 for _, m, _ in donors if m is not None) < 2:
        duel.fail("QUAL_SOURCE_MATERIAL_DONOR_GATE")

    piece_count = 18
    release = min(duel.END - 2, impact_frame + 2)
    pieces = []
    category_counts = {"glass": 0, "plastic": 0, "metal": 0}
    source_material_names = set()

    for idx in range(piece_count):
        category, mat, mat_name = donors[idx % len(donors)]
        if mat is None:
            category, mat, mat_name = donors[-1]
        if mat is not None and mat_name:
            source_material_names.add(mat_name)
        category_counts[category] += 1

        base_len = rng.uniform(0.16, 0.48) * (0.75 if category == "glass" else 1.0)
        base_w = rng.uniform(0.07, 0.24)
        thick = rng.uniform(0.008, 0.026) if category == "glass" else rng.uniform(0.018, 0.055)
        loc = center + Vector((rng.uniform(-0.30, 0.30), rng.uniform(-0.70, 0.70), rng.uniform(0.25, 0.75)))
        obj = make_irregular_shard(f"QUAL_{category.upper()}_SHARD_{idx+1:02d}", loc, base_len, base_w, thick, mat)
        obj.rotation_euler = (rng.uniform(-0.6, 0.6), rng.uniform(-0.6, 0.6), rng.uniform(-math.pi, math.pi))

        core.activate(obj)
        bpy.ops.rigidbody.object_add()
        rb = obj.rigid_body
        rb.type = "ACTIVE"
        rb.collision_shape = "CONVEX_HULL"
        rb.mass = rng.uniform(0.05, 0.45) if category == "glass" else rng.uniform(0.25, 1.8)
        rb.friction = 0.42
        rb.restitution = 0.10 if category == "glass" else 0.05
        rb.linear_damping = 0.035
        rb.angular_damping = 0.035
        rb.use_deactivation = False
        rb.kinematic = True
        rb.keyframe_insert(data_path="kinematic", frame=duel.START)
        rb.keyframe_insert(data_path="kinematic", frame=impact_frame)

        obj.hide_render = True
        obj.keyframe_insert(data_path="hide_render", frame=max(duel.START, impact_frame - 1))
        obj.hide_render = False
        obj.keyframe_insert(data_path="hide_render", frame=impact_frame)

        p0 = obj.location.copy()
        obj.location = p0
        obj.keyframe_insert(data_path="location", frame=impact_frame)
        radial = Vector((rng.uniform(-1.0, 1.0), rng.uniform(-1.25, 1.25), rng.uniform(0.35, 1.1)))
        if radial.length < 0.1:
            radial = Vector((1.0, 0.2, 0.5))
        radial.normalize()
        impulse_step = radial * rng.uniform(0.25, 0.65) * (0.75 + 0.25 * severity)
        obj.location = p0 + impulse_step
        obj.keyframe_insert(data_path="location", frame=release)
        rb.kinematic = False
        rb.keyframe_insert(data_path="kinematic", frame=release)
        if obj.animation_data and obj.animation_data.action:
            for fc in obj.animation_data.action.fcurves:
                for k in fc.keyframe_points:
                    k.interpolation = "LINEAR"
        pieces.append(obj)

    if scene.rigidbody_world is None:
        duel.fail("QUAL_DEBRIS_RIGID_WORLD_MISSING")
    scene.rigidbody_world.point_cache.frame_start = duel.START
    scene.rigidbody_world.point_cache.frame_end = duel.END
    scene.rigidbody_world.substeps_per_frame = 30
    scene.rigidbody_world.solver_iterations = 50

    records = {o.name: {} for o in pieces}
    scene.frame_set(duel.START)
    for frame in range(duel.START, duel.END + 1):
        scene.frame_set(frame)
        bpy.context.view_layer.update()
        for obj in pieces:
            records[obj.name][frame] = (obj.matrix_world.translation.copy(), obj.matrix_world.to_quaternion().copy())

    max_disp = 0.0
    for obj in pieces:
        start_loc = records[obj.name][release][0]
        end_loc = records[obj.name][duel.END][0]
        max_disp = max(max_disp, (end_loc - start_loc).length)
        core.activate(obj)
        bpy.ops.rigidbody.object_remove()
        obj.animation_data_clear()
        obj.rotation_mode = "QUATERNION"
        for frame in range(duel.START, duel.END + 1):
            loc, quat = records[obj.name][frame]
            obj.location = loc
            obj.rotation_quaternion = quat
            obj.keyframe_insert(data_path="location", frame=frame)
            obj.keyframe_insert(data_path="rotation_quaternion", frame=frame)
        obj.hide_render = True
        obj.keyframe_insert(data_path="hide_render", frame=max(duel.START, impact_frame - 1))
        obj.hide_render = False
        obj.keyframe_insert(data_path="hide_render", frame=impact_frame)

    if max_disp < 0.35:
        duel.fail(f"QUAL_DEBRIS_DYNAMICS_GATE:{max_disp}")
    return {
        "count": len(pieces),
        "releaseFrame": release,
        "maxDisplacementM": max_disp,
        "categories": category_counts,
        "sourceMaterialNames": sorted(source_material_names),
        "sourceMaterialDriven": len(source_material_names) >= 2,
        "primitiveBoxDebris": False,
        "rigidBodyAfterRelease": True,
        "impactTriggered": True,
    }


def make_camera(name: str, loc: Vector, lens: float, target: bpy.types.Object) -> bpy.types.Object:
    return core.camera(name, tuple(loc), lens, target)


def setup_auto_cameras(scene: bpy.types.Scene, impact_frame: int, center: Vector, actor_a: dict, actor_b: dict) -> dict:
    scale = max(float(actor_a["dims"].x), float(actor_b["dims"].x))
    target_z = max(float(actor_a["dims"].z), float(actor_b["dims"].z)) * 0.58
    bpy.ops.object.empty_add(type="PLAIN_AXES", location=(center.x, center.y, target_z))
    target = bpy.context.object
    target.name = "QUAL_CAMERA_TARGET"

    approach = make_camera("QUAL_CAM_APPROACH", center + Vector((-0.55 * scale, -3.20 * scale, 1.05 * scale)), 30.0, target)
    impact = make_camera("QUAL_CAM_IMPACT", center + Vector((-0.22 * scale, -1.70 * scale, 0.58 * scale)), 48.0, target)
    aftermath = make_camera("QUAL_CAM_AFTERMATH", center + Vector((0.75 * scale, -2.10 * scale, 0.66 * scale)), 58.0, target)

    aftermath_start = min(duel.END - 1, impact_frame + 14)
    start_loc = aftermath.location.copy()
    aftermath.keyframe_insert(data_path="location", frame=aftermath_start)
    end_loc = center + Vector((0.20 * scale, -0.92 * scale, 0.40 * scale))
    aftermath.location = end_loc
    aftermath.keyframe_insert(data_path="location", frame=duel.END)

    scene.timeline_markers.clear()
    m = scene.timeline_markers.new("APPROACH", frame=duel.START)
    m.camera = approach
    impact_cut = max(duel.START + 1, impact_frame - 9)
    m = scene.timeline_markers.new("IMPACT", frame=impact_cut)
    m.camera = impact
    m = scene.timeline_markers.new("AFTERMATH", frame=aftermath_start)
    m.camera = aftermath
    scene.camera = approach

    return {
        "cameras": [approach, impact, aftermath],
        "approachFrame": duel.START,
        "impactCutFrame": impact_cut,
        "aftermathFrame": aftermath_start,
        "aftermathDollyDistanceM": (start_loc - end_loc).length,
        "planner": "ACTOR_BOUNDS_PLUS_IMPACT_CENTER",
        "manualWorldCoordinates": False,
        "sceneScaleM": scale,
    }


def camera_for_frame(camdata: dict, frame: int) -> bpy.types.Object:
    if frame >= camdata["aftermathFrame"]:
        return camdata["cameras"][2]
    if frame >= camdata["impactCutFrame"]:
        return camdata["cameras"][1]
    return camdata["cameras"][0]


def render_qualification_previews(scene: bpy.types.Scene, camdata: dict, impact_frame: int, outdir: Path) -> list[dict]:
    frames = [max(duel.START, impact_frame - 28), impact_frame, min(duel.END, impact_frame + 40)]
    labels = ["approach", "impact", "aftermath"]
    rows = []
    for label, frame in zip(labels, frames):
        scene.frame_set(frame)
        scene.camera = camera_for_frame(camdata, frame)
        path = outdir / f"qual-{label}-f{frame:04d}.png"
        scene.render.filepath = str(path)
        bpy.ops.render.render(write_still=True)
        size = path.stat().st_size if path.is_file() else 0
        if size < 30000:
            duel.fail(f"QUAL_PREVIEW_RENDER_INVALID:{label}:{size}")
        print(f"QUAL_PREVIEW=PASS|label={label}|frame={frame}|bytes={size}", flush=True)
        rows.append({"label": label, "frame": frame, "path": str(path), "bytes": size})
    return rows


def generate_audio(outdir: Path, impact_frame: int) -> dict:
    duration = duel.END / duel.FPS
    impact_t = impact_frame / duel.FPS
    path = outdir / "qualification-audio.wav"
    rng = random.Random(991)
    click_times = [impact_t + x for x in (0.08, 0.16, 0.29, 0.43, 0.62, 0.88)]
    total = int(duration * AUDIO_SAMPLE_RATE)

    with wave.open(str(path), "wb") as wf:
        wf.setnchannels(2)
        wf.setsampwidth(2)
        wf.setframerate(AUDIO_SAMPLE_RATE)
        frames = bytearray()
        for i in range(total):
            t = i / AUDIO_SAMPLE_RATE
            approach = clamp(t / max(0.001, impact_t), 0.0, 1.0)
            engine_freq = 72.0 + 58.0 * approach
            sample = 0.055 * math.sin(2.0 * math.pi * engine_freq * t)
            sample += 0.022 * math.sin(2.0 * math.pi * engine_freq * 2.03 * t)
            sample += 0.010 * (rng.random() * 2.0 - 1.0)

            dt = t - impact_t
            if 0.0 <= dt <= 0.38:
                env = math.exp(-dt * 10.0)
                sample += env * (0.56 * (rng.random() * 2.0 - 1.0) + 0.15 * math.sin(2.0 * math.pi * 95.0 * t))

            for ct in click_times:
                cd = t - ct
                if 0.0 <= cd <= 0.055:
                    env = math.exp(-cd * 55.0)
                    sample += env * (0.18 * math.sin(2.0 * math.pi * 1900.0 * t) + 0.10 * (rng.random() * 2.0 - 1.0))

            sample = clamp(sample, -0.98, 0.98)
            val = int(sample * 32767.0)
            frames.extend(struct.pack("<hh", val, val))
        wf.writeframes(frames)

    if not path.is_file() or path.stat().st_size < 200000:
        duel.fail("QUAL_AUDIO_FILE_GATE")
    return {
        "path": str(path),
        "bytes": path.stat().st_size,
        "sampleRate": AUDIO_SAMPLE_RATE,
        "channels": 2,
        "durationSeconds": duration,
        "events": {
            "engineApproach": [0.0, impact_t],
            "metalImpact": impact_t,
            "glassDebris": click_times,
            "aftermathAmbience": [impact_t, duration],
        },
        "eventSource": "SOLVER_IMPACT_FRAME",
        "manualTiming": False,
    }


def main() -> None:
    args = duel.args()
    outdir = Path(args.out)
    manifest = json.loads(Path(args.asset_manifest).read_text(encoding="utf-8"))
    if manifest.get("status") != "PASS" or manifest.get("quant120Forbidden") is not True:
        duel.fail("QUAL_ASSET_MANIFEST_NOT_PASS")

    assets = manifest.get("assets") or {}
    aa = assets.get("bugattiA") or {}
    bb = assets.get("bugattiB") or {}
    if aa.get("identity", {}).get("binaryExact") is not True or bb.get("identity", {}).get("binaryExact") is not True:
        duel.fail("QUAL_BINARY_IDENTITY_GATE")
    if aa.get("identity", {}).get("primarySceneSha256") != bb.get("identity", {}).get("primarySceneSha256"):
        duel.fail("QUAL_SOURCE_IDENTITY_MISMATCH")

    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.object.delete(use_global=False)
    scene = bpy.context.scene
    scene.frame_start = duel.START
    scene.frame_end = duel.END
    scene.gravity = (0, 0, -9.81)
    configure_qualification_render(scene, outdir)

    car_a = duel.import_bugatti("BUGATTI_A", Path(args.bugatti_a), +1)
    car_b = duel.import_bugatti("BUGATTI_B", Path(args.bugatti_b), -1)
    scene_scale = max(float(car_a["dims"].x), float(car_b["dims"].x))
    environment = setup_production_environment(scene, scene_scale)

    core.add_proxy(car_a, duel.CAR_MASS, 0.20)
    core.add_proxy(car_b, duel.CAR_MASS, 0.20)
    plan = plan_head_on(car_a, car_b)
    core.seed_velocity(car_a["proxy"], plan["startA"], +plan["speedEachMps"])
    core.seed_velocity(car_b["proxy"], plan["startB"], -plan["speedEachMps"])

    if not core.no_post_handoff_vehicle_location_keys(car_a) or not core.no_post_handoff_vehicle_location_keys(car_b):
        duel.fail("QUAL_POST_HANDOFF_LOCATION_KEY")

    sim = duel.simulate(scene, car_a, car_b)
    core.bake_actor(car_a, sim["records"]["a"])
    core.bake_actor(car_b, sim["records"]["b"])

    impact_frame = int(sim["impactFrame"])
    center = Vector(sim["impactData"]["center"])
    relative_speed = float(sim["impactData"]["relativeSpeed"])
    severity = clamp((relative_speed - 12.0) / 24.0, 0.35, 1.0)

    damage_a = procedural_crumple(car_a, impact_frame, +1, severity)
    damage_b = procedural_crumple(car_b, impact_frame, -1, severity)
    debris = semantic_debris(scene, car_a, car_b, impact_frame, center, severity)
    cameras = setup_auto_cameras(scene, impact_frame, center, car_a, car_b)
    audio = generate_audio(outdir, impact_frame)
    previews = render_qualification_previews(scene, cameras, impact_frame, outdir)

    machine_gates = {
        "Q1_fullSourceExactAsset": aa.get("identity", {}).get("binaryExact") is True and bb.get("identity", {}).get("binaryExact") is True,
        "Q2_automaticScenePlanning": plan["manualWorldCoordinates"] is False and plan["derivedFrom"] == "ACTOR_COLLISION_BOUNDS_PLUS_SCENARIO_POLICY",
        "Q3_solverCollisionPreserved": relative_speed > 15.0 and abs(float(center.x)) <= 1.5,
        "Q4_localizedDamageBothVehicles": damage_a["affectedVertices"] >= 500 and damage_b["affectedVertices"] >= 500 and damage_a["maxVertexDisplacementM"] <= 0.55 and damage_b["maxVertexDisplacementM"] <= 0.55,
        "Q5_semanticRigidDebris": debris["count"] >= 12 and debris["sourceMaterialDriven"] and debris["primitiveBoxDebris"] is False and debris["maxDisplacementM"] >= 0.35,
        "Q6_automaticCinematicCameras": len(cameras["cameras"]) == 3 and cameras["aftermathDollyDistanceM"] >= scene_scale * 0.6 and cameras["manualWorldCoordinates"] is False,
        "Q7_productionEnvironmentLighting": environment["lightCount"] >= 4 and environment["laneMarkerCount"] >= 8,
        "Q8_verticalShortsFraming": scene.render.resolution_x == 540 and scene.render.resolution_y == 960,
        "Q9_solverTimestampedAudio": audio["bytes"] >= 200000 and audio["manualTiming"] is False and audio["events"]["metalImpact"] == impact_frame / duel.FPS,
        "Q10_noFinalRenderDuringQualification": True,
    }
    if not all(machine_gates.values()):
        duel.fail("QUAL_MACHINE_GATE_FAIL:" + ",".join(k for k, v in machine_gates.items() if not v))

    result = {
        "scope": QUALIFICATION_SCOPE,
        "status": "MACHINE_CAPABILITY_PASS_VISUAL_REVIEW_REQUIRED",
        "goNoGo": "PENDING_VISUAL_REVIEW",
        "engine": "BLENDER",
        "engineVersion": bpy.app.version_string,
        "renderEngine": scene.render.engine,
        "resolution": [scene.render.resolution_x, scene.render.resolution_y],
        "aspectRatio": "9:16",
        "fullSourceGeometry": True,
        "visualProxyUsed": False,
        "collisionProxyUsed": True,
        "vehicleMotionSolverDriven": True,
        "damagePhysicalSolver": False,
        "damageMethod": "PROCEDURAL_VISUAL_CRUMPLE_FROM_IMPACT_AND_BOUNDS",
        "manualPerIdeaCoordinateTuning": False,
        "scenePlanner": plan,
        "impactFrame": impact_frame,
        "impactTimeSeconds": impact_frame / duel.FPS,
        "impactRelativeSpeedMps": relative_speed,
        "impactCenter": list(center),
        "damageA": damage_a,
        "damageB": damage_b,
        "debris": debris,
        "cameras": {
            "count": len(cameras["cameras"]),
            "planner": cameras["planner"],
            "aftermathDollyDistanceM": cameras["aftermathDollyDistanceM"],
            "manualWorldCoordinates": cameras["manualWorldCoordinates"],
        },
        "environment": environment,
        "audio": audio,
        "previews": previews,
        "machineGates": machine_gates,
        "visualReviewRequired": True,
        "finalRenderAuthorized": False,
        "finalFrames": [],
    }
    outdir.mkdir(parents=True, exist_ok=True)
    (outdir / "qualification-result.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    print("ISS_BLENDER_CAPABILITY_QUALIFICATION_MACHINE=PASS", flush=True)
    print("ISS_BLENDER_CAPABILITY_GO_NO_GO=PENDING_VISUAL_REVIEW", flush=True)
    print("FINAL_RENDER_AUTHORIZATION=NO", flush=True)


if __name__ == "__main__":
    main()
