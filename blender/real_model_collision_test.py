import argparse
import hashlib
import json
import math
from pathlib import Path

import bpy
from mathutils import Vector

FPS = 24
SIM_START = 1
SIM_END = 144  # 6 seconds continuous physics
HANDOFF_FRAME = 5
HYPERCAR_MASS_KG = 1450.0
BULLDOZER_MASS_KG = 27614.189525707065


def parse_args():
    p = argparse.ArgumentParser()
    p.add_argument("--hypercar", required=True)
    p.add_argument("--bulldozer", required=True)
    p.add_argument("--output", required=True)
    p.add_argument("--result", required=True)
    return p.parse_args()


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def activate(obj):
    bpy.ops.object.select_all(action="DESELECT")
    obj.select_set(True)
    bpy.context.view_layer.objects.active = obj


def import_model(path):
    before = set(bpy.data.objects)
    bpy.ops.import_scene.gltf(filepath=str(path))
    imported = [o for o in bpy.data.objects if o not in before]
    meshes = [o for o in imported if o.type == "MESH"]
    if not meshes:
        raise RuntimeError(f"NO_MESHES: {path}")
    return imported, meshes


def bounds(meshes):
    pts = [o.matrix_world @ Vector(c) for o in meshes for c in o.bound_box]
    mn = Vector((min(p.x for p in pts), min(p.y for p in pts), min(p.z for p in pts)))
    mx = Vector((max(p.x for p in pts), max(p.y for p in pts), max(p.z for p in pts)))
    return mn, mx


def add_active_rigid_body(obj, mass, friction, restitution):
    activate(obj)
    bpy.ops.rigidbody.object_add()
    obj.rigid_body.type = "ACTIVE"
    obj.rigid_body.collision_shape = "BOX"
    obj.rigid_body.mass = float(mass)
    obj.rigid_body.friction = friction
    obj.rigid_body.restitution = restitution
    obj.rigid_body.linear_damping = 0.025
    obj.rigid_body.angular_damping = 0.07
    obj.rigid_body.use_deactivation = False


def build_actor(name, path, desired_x, mass, friction):
    imported, meshes = import_model(path)
    mn, mx = bounds(meshes)
    dims = mx - mn
    center = (mn + mx) * 0.5
    if min(dims.x, dims.y, dims.z) <= 0.01:
        raise RuntimeError(f"INVALID_BOUNDS {name}: {tuple(dims)}")

    desired = Vector((desired_x, 0.0, dims.z * 0.5 + 0.03))
    delta = desired - center
    roots = [o for o in imported if o.parent not in imported]
    for root in roots:
        root.matrix_world.translation += delta

    bpy.ops.mesh.primitive_cube_add(size=1.0, location=desired)
    proxy = bpy.context.object
    proxy.name = f"PHYSICS_{name}"
    proxy.dimensions = (dims.x, dims.y, dims.z)
    activate(proxy)
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    proxy.hide_render = True
    add_active_rigid_body(proxy, mass, friction, 0.025)

    for root in roots:
        world = root.matrix_world.copy()
        root.parent = proxy
        root.matrix_world = world

    return {
        "name": name,
        "proxy": proxy,
        "meshes": meshes,
        "dims": Vector(proxy.dimensions),
        "meshCount": len(meshes),
        "path": str(path),
    }


def look_at(obj, point):
    obj.rotation_euler = (Vector(point) - obj.location).to_track_quat("-Z", "Y").to_euler()


def aabb_overlap(a, b):
    pa = a["proxy"].matrix_world.translation
    pb = b["proxy"].matrix_world.translation
    da = a["dims"] * 0.5
    db = b["dims"] * 0.5
    return (
        abs(pa.x - pb.x) <= da.x + db.x + 0.12
        and abs(pa.y - pb.y) <= da.y + db.y + 0.12
        and abs(pa.z - pb.z) <= da.z + db.z + 0.12
    )


a = parse_args()
out = Path(a.output)
out.parent.mkdir(parents=True, exist_ok=True)
result_path = Path(a.result)

bpy.ops.object.select_all(action="SELECT")
bpy.ops.object.delete(use_global=False)
scene = bpy.context.scene
scene.frame_start = SIM_START
scene.frame_end = SIM_END
scene.render.fps = FPS
scene.render.engine = "BLENDER_WORKBENCH"
scene.render.resolution_x = 640
scene.render.resolution_y = 360
scene.render.resolution_percentage = 100
scene.render.image_settings.file_format = "FFMPEG"
scene.render.ffmpeg.format = "MPEG4"
scene.render.ffmpeg.codec = "H264"
scene.render.ffmpeg.constant_rate_factor = "MEDIUM"
scene.render.filepath = str(out)
scene.world.color = (0.035, 0.04, 0.05)
scene.gravity = (0.0, 0.0, -9.81)
scene.display.shading.light = "STUDIO"
scene.display.shading.color_type = "MATERIAL"
scene.display.shading.show_shadows = True
scene.display.shading.show_cavity = True

bpy.ops.mesh.primitive_cube_add(size=1.0, location=(0.0, 0.0, -0.25))
ground = bpy.context.object
ground.name = "GROUND"
ground.dimensions = (40.0, 20.0, 0.5)
activate(ground)
bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
activate(ground)
bpy.ops.rigidbody.object_add()
ground.rigid_body.type = "PASSIVE"
ground.rigid_body.collision_shape = "BOX"
ground.rigid_body.friction = 0.92

hypercar = build_actor("HYPERCAR", Path(a.hypercar), -12.0, HYPERCAR_MASS_KG, 0.22)
bulldozer = build_actor("BULLDOZER", Path(a.bulldozer), 0.0, BULLDOZER_MASS_KG, 0.78)

# Initial velocity seed only. From frame 5 onward the hypercar is fully dynamic.
p = hypercar["proxy"]
p.rigid_body.kinematic = True
p.rigid_body.keyframe_insert(data_path="kinematic", frame=1)
p.location.x = -12.0
p.keyframe_insert(data_path="location", frame=1)
p.location.x = -10.6
p.keyframe_insert(data_path="location", frame=4)
p.rigid_body.kinematic = True
p.rigid_body.keyframe_insert(data_path="kinematic", frame=4)
p.rigid_body.kinematic = False
p.rigid_body.keyframe_insert(data_path="kinematic", frame=HANDOFF_FRAME)
if p.animation_data and p.animation_data.action:
    for fc in p.animation_data.action.fcurves:
        for kp in fc.keyframe_points:
            kp.interpolation = "LINEAR"

post_handoff_keys = []
if p.animation_data and p.animation_data.action:
    for fc in p.animation_data.action.fcurves:
        if fc.data_path == "location":
            for kp in fc.keyframe_points:
                if kp.co.x >= HANDOFF_FRAME:
                    post_handoff_keys.append(float(kp.co.x))
if post_handoff_keys:
    raise RuntimeError(f"POST_HANDOFF_LOCATION_KEYS_FORBIDDEN {post_handoff_keys}")

bpy.ops.object.camera_add(location=(10.0, -20.0, 7.5))
cam = bpy.context.object
look_at(cam, (-2.0, 0.0, 1.3))
scene.camera = cam

bpy.ops.object.light_add(type="SUN", location=(0.0, 0.0, 10.0))
sun = bpy.context.object
sun.data.energy = 3.0
sun.rotation_euler = (math.radians(30), math.radians(-20), math.radians(25))

if scene.rigidbody_world is None:
    activate(p)
    bpy.ops.rigidbody.world_add()
scene.rigidbody_world.point_cache.frame_start = SIM_START
scene.rigidbody_world.point_cache.frame_end = SIM_END
scene.rigidbody_world.substeps_per_frame = 20
scene.rigidbody_world.solver_iterations = 30

scene.frame_set(SIM_START)
bpy.context.view_layer.update()
prev_h = hypercar["proxy"].matrix_world.translation.copy()
prev_b = bulldozer["proxy"].matrix_world.translation.copy()
b_start = prev_b.copy()
impact_frame = None
impact_car_speed = None
impact_bulldozer_speed = None
preimpact_car_speed = 0.0
postimpact_car_speed_min = None
b_max_speed = 0.0
b_max_disp = 0.0
samples = []

for frame in range(SIM_START, SIM_END + 1):
    scene.frame_set(frame)
    bpy.context.view_layer.update()
    ph = hypercar["proxy"].matrix_world.translation.copy()
    pb = bulldozer["proxy"].matrix_world.translation.copy()
    vh = Vector((0, 0, 0)) if frame == SIM_START else (ph - prev_h) * FPS
    vb = Vector((0, 0, 0)) if frame == SIM_START else (pb - prev_b) * FPS

    if frame >= HANDOFF_FRAME and hypercar["proxy"].rigid_body.kinematic:
        raise RuntimeError(f"HYPERCAR_STILL_KINEMATIC frame={frame}")

    car_speed = vh.length
    bulldozer_speed = vb.length
    bulldozer_disp = (pb - b_start).length
    b_max_speed = max(b_max_speed, bulldozer_speed)
    b_max_disp = max(b_max_disp, bulldozer_disp)

    if impact_frame is None:
        if frame >= HANDOFF_FRAME:
            preimpact_car_speed = max(preimpact_car_speed, car_speed)
        if frame >= HANDOFF_FRAME + 3 and aabb_overlap(hypercar, bulldozer) and bulldozer_speed > 0.05:
            impact_frame = frame
            impact_car_speed = car_speed
            impact_bulldozer_speed = bulldozer_speed
    else:
        postimpact_car_speed_min = car_speed if postimpact_car_speed_min is None else min(postimpact_car_speed_min, car_speed)

    if frame in (1, 4, 5, 12, 24, 36, 48, 72, 96, 120, 144) or frame == impact_frame:
        samples.append({
            "frame": frame,
            "hypercarPos": [round(x, 4) for x in ph],
            "bulldozerPos": [round(x, 4) for x in pb],
            "hypercarSpeedMps": round(car_speed, 4),
            "bulldozerSpeedMps": round(bulldozer_speed, 4),
            "bulldozerDisplacementM": round(bulldozer_disp, 4),
            "hypercarDynamic": not bool(hypercar["proxy"].rigid_body.kinematic),
        })

    prev_h = ph
    prev_b = pb

scene.frame_set(SIM_END)
bpy.context.view_layer.update()
final_h = hypercar["proxy"].matrix_world.translation.copy()
final_b = bulldozer["proxy"].matrix_world.translation.copy()
final_b_disp = (final_b - b_start).length

collision_observed = impact_frame is not None
momentum_transfer_observed = b_max_speed > 0.05 and b_max_disp > 0.02
mass_asymmetry_plausible = b_max_speed < max(preimpact_car_speed * 0.35, 0.1)
car_lost_speed = postimpact_car_speed_min is not None and postimpact_car_speed_min < preimpact_car_speed * 0.75
persistent_outcome = final_b_disp > 0.02

if not collision_observed:
    raise RuntimeError("REAL_MODEL_COLLISION_NOT_OBSERVED")
if not momentum_transfer_observed:
    raise RuntimeError(f"MOMENTUM_TRANSFER_NOT_OBSERVED vmax={b_max_speed:.4f} disp={b_max_disp:.4f}")
if not mass_asymmetry_plausible:
    raise RuntimeError(f"MASS_RESPONSE_IMPLAUSIBLE carPre={preimpact_car_speed:.4f} bulldozerMax={b_max_speed:.4f}")
if not car_lost_speed:
    raise RuntimeError(f"CAR_DID_NOT_LOSE_SPEED carPre={preimpact_car_speed:.4f} postMin={postimpact_car_speed_min}")
if not persistent_outcome:
    raise RuntimeError(f"OUTCOME_NOT_PERSISTENT finalBulldozerDisp={final_b_disp:.4f}")

# Full six seconds: approach, impact and aftermath stay visible.
scene.frame_start = SIM_START
scene.frame_end = SIM_END
scene.frame_set(SIM_START)
bpy.ops.render.render(animation=True)
if not out.is_file() or out.stat().st_size < 1024:
    raise RuntimeError("REAL_MODEL_VIDEO_MISSING")

result = {
    "scope": "ISS_REAL_MODEL_COLLISION_OUTCOME_TEST",
    "engine": "BLENDER",
    "engineVersion": "4.5.13",
    "physicsBackend": "BLENDER_RIGID_BODY",
    "renderEngine": "BLENDER_WORKBENCH",
    "productionAcceptance": False,
    "continuousWorld": True,
    "simulationSeconds": SIM_END / FPS,
    "collisionObserved": collision_observed,
    "momentumTransferObserved": momentum_transfer_observed,
    "massAsymmetryPlausible": mass_asymmetry_plausible,
    "carLostSpeedAfterImpact": car_lost_speed,
    "persistentOutcome": persistent_outcome,
    "scriptedDamageUsed": False,
    "dynamicBeforeImpact": impact_frame > HANDOFF_FRAME,
    "postHandoffLocationKeyframeCount": len(post_handoff_keys),
    "impactFrame": impact_frame,
    "impactTimeSeconds": round(impact_frame / FPS, 4),
    "preImpactCarMaxSpeedMps": round(preimpact_car_speed, 6),
    "impactCarSpeedMps": round(float(impact_car_speed), 6),
    "impactBulldozerSpeedMps": round(float(impact_bulldozer_speed), 6),
    "bulldozerMaxSpeedMps": round(b_max_speed, 6),
    "bulldozerMaxDisplacementMeters": round(b_max_disp, 6),
    "finalBulldozerDisplacementMeters": round(final_b_disp, 6),
    "finalHypercarPosition": [round(x, 6) for x in final_h],
    "finalBulldozerPosition": [round(x, 6) for x in final_b],
    "hypercarMassKg": HYPERCAR_MASS_KG,
    "bulldozerMassKg": BULLDOZER_MASS_KG,
    "massRatioBulldozerToCar": round(BULLDOZER_MASS_KG / HYPERCAR_MASS_KG, 6),
    "hypercarMeshCount": hypercar["meshCount"],
    "bulldozerMeshCount": bulldozer["meshCount"],
    "hypercarSha256": sha256(a.hypercar),
    "bulldozerSha256": sha256(a.bulldozer),
    "videoPath": str(out.resolve()),
    "samples": samples,
}
result_path.write_text(json.dumps(result, indent=2, sort_keys=True), encoding="utf-8")
print(json.dumps(result, sort_keys=True))
print("ISS_REAL_MODEL_COLLISION_OUTCOME=PASS")
