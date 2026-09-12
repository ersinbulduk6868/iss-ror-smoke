import argparse
import json
import math
from pathlib import Path

import bpy
from mathutils import Vector

FPS = 24
SIM_START = 1
SIM_END = 144
HANDOFF_FRAME = 5
CAR_MASS_KG = 1450.0
BULLDOZER_MASS_KG = 27614.189525707065
CAR_EXPECTED_SHA = "8cc074c40fe9ced7271cbeddf223cd9a520dee868977ffcbd439cec1c2b62cb4"
BULLDOZER_EXPECTED_SHA = "187f81c3c4638180fb8d82c5b2bbc7510f01bc970ee149713b2de993089f1e18"


def args():
    p = argparse.ArgumentParser()
    p.add_argument("--hypercar-quant", required=True)
    p.add_argument("--bulldozer-quant", required=True)
    p.add_argument("--output", required=True)
    p.add_argument("--result", required=True)
    return p.parse_args()


def activate(obj):
    bpy.ops.object.select_all(action="DESELECT")
    obj.select_set(True)
    bpy.context.view_layer.objects.active = obj


def load_quant(path, expected_source_sha):
    d = json.loads(Path(path).read_text(encoding="utf-8"))
    if d.get("source_sha256") != expected_source_sha:
        raise RuntimeError(f"SOURCE_SHA_MISMATCH {path}: {d.get('source_sha256')}")
    if d.get("transport") != "exact-upload-derived-quantized-surface-v1":
        raise RuntimeError(f"TRANSPORT_CONTRACT_MISMATCH {path}")
    qv = d["qv"]
    faces_flat = d["f"]
    if len(qv) % 3 or len(faces_flat) % 3:
        raise RuntimeError(f"QUANT_ARRAY_ALIGNMENT_INVALID {path}")
    mn = d["min"]
    mx = d["max"]
    src = []
    for i in range(0, len(qv), 3):
        v = []
        for a in range(3):
            t = (float(qv[i+a]) + 32768.0) / 65535.0
            v.append(float(mn[a]) + t * (float(mx[a]) - float(mn[a])))
        src.append(v)
    faces = [tuple(faces_flat[i:i+3]) for i in range(0, len(faces_flat), 3)]
    return d, src, faces


def orient_and_scale(src, target_length):
    xs = [v[0] for v in src]
    ys = [v[1] for v in src]
    zs = [v[2] for v in src]
    rx = max(xs)-min(xs)
    rz = max(zs)-min(zs)
    if rz >= rx:
        raw = [(v[2], v[0], v[1]) for v in src]
    else:
        raw = [(v[0], v[2], v[1]) for v in src]
    minx = min(v[0] for v in raw); maxx = max(v[0] for v in raw)
    miny = min(v[1] for v in raw); maxy = max(v[1] for v in raw)
    minz = min(v[2] for v in raw); maxz = max(v[2] for v in raw)
    length = maxx-minx
    scale = target_length / length
    cx = (minx+maxx)*0.5
    cy = (miny+maxy)*0.5
    verts = [((v[0]-cx)*scale, (v[1]-cy)*scale, (v[2]-minz)*scale) for v in raw]
    dims = Vector((target_length, (maxy-miny)*scale, (maxz-minz)*scale))
    return verts, dims, scale


def material(name, rgba):
    m = bpy.data.materials.new(name)
    m.diffuse_color = rgba
    return m


def add_rigid_body(obj, mass, friction, restitution=0.03):
    activate(obj)
    bpy.ops.rigidbody.object_add()
    rb = obj.rigid_body
    rb.type = "ACTIVE"
    rb.collision_shape = "BOX"
    rb.mass = mass
    rb.friction = friction
    rb.restitution = restitution
    rb.linear_damping = 0.035
    rb.angular_damping = 0.09
    rb.use_deactivation = False


def build_actor(name, quant_path, expected_sha, target_length, mass, friction, x, rgba):
    meta, src, faces = load_quant(quant_path, expected_sha)
    verts, dims, scale = orient_and_scale(src, target_length)
    mesh = bpy.data.meshes.new(name + "_VISIBLE_MESH")
    mesh.from_pydata(verts, [], faces)
    mesh.update()
    visible = bpy.data.objects.new(name + "_VISIBLE", mesh)
    bpy.context.collection.objects.link(visible)
    visible.data.materials.append(material(name + "_MAT", rgba))

    zc = dims.z * 0.5 + 0.035
    bpy.ops.mesh.primitive_cube_add(size=1.0, location=(x, 0.0, zc))
    proxy = bpy.context.object
    proxy.name = "PHYSICS_" + name
    proxy.dimensions = dims
    activate(proxy)
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    proxy.hide_render = True
    add_rigid_body(proxy, mass, friction)

    visible.parent = proxy
    visible.location = (0.0, 0.0, -dims.z * 0.5)
    return {
        "name": name,
        "proxy": proxy,
        "visible": visible,
        "dims": dims,
        "scale": scale,
        "sourceSha256": meta["source_sha256"],
        "sourceTriangles": int(meta["source_triangles"]),
        "transportTriangles": int(meta["kept_triangles"]),
    }


def look_at(obj, point):
    obj.rotation_euler = (Vector(point) - obj.location).to_track_quat("-Z", "Y").to_euler()


def overlap(a, b):
    pa = a["proxy"].matrix_world.translation
    pb = b["proxy"].matrix_world.translation
    da = a["dims"] * 0.5
    db = b["dims"] * 0.5
    return (abs(pa.x-pb.x) <= da.x+db.x+0.08 and
            abs(pa.y-pb.y) <= da.y+db.y+0.08 and
            abs(pa.z-pb.z) <= da.z+db.z+0.08)


a = args()
out = Path(a.output)
out.parent.mkdir(parents=True, exist_ok=True)
result_path = Path(a.result)
result_path.parent.mkdir(parents=True, exist_ok=True)

bpy.ops.object.select_all(action="SELECT")
bpy.ops.object.delete(use_global=False)
scene = bpy.context.scene
scene.frame_start = SIM_START
scene.frame_end = SIM_END
scene.render.fps = FPS
scene.render.engine = "BLENDER_WORKBENCH"
scene.render.resolution_x = 512
scene.render.resolution_y = 288
scene.render.resolution_percentage = 100
scene.render.image_settings.file_format = "FFMPEG"
scene.render.ffmpeg.format = "MPEG4"
scene.render.ffmpeg.codec = "H264"
scene.render.ffmpeg.constant_rate_factor = "MEDIUM"
scene.render.filepath = str(out)
scene.world.color = (0.025, 0.028, 0.035)
scene.gravity = (0.0, 0.0, -9.81)
scene.display.shading.light = "STUDIO"
scene.display.shading.color_type = "MATERIAL"
scene.display.shading.show_shadows = True
scene.display.shading.show_cavity = True

bpy.ops.mesh.primitive_cube_add(size=1.0, location=(-1.5, 0.0, -0.25))
ground = bpy.context.object
ground.name = "GROUND"
ground.dimensions = (34.0, 16.0, 0.5)
activate(ground)
bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
ground.data.materials.append(material("GROUND_MAT", (0.11,0.12,0.14,1.0)))
activate(ground)
bpy.ops.rigidbody.object_add()
ground.rigid_body.type = "PASSIVE"
ground.rigid_body.collision_shape = "BOX"
ground.rigid_body.friction = 0.9

car = build_actor("BUGATTI_EB110", a.hypercar_quant, CAR_EXPECTED_SHA, 4.40, CAR_MASS_KG, 0.38, -9.0, (0.72,0.76,0.82,1.0))
bulldozer = build_actor("BULLDOZER", a.bulldozer_quant, BULLDOZER_EXPECTED_SHA, 6.10, BULLDOZER_MASS_KG, 0.80, 0.0, (0.55,0.38,0.08,1.0))

p = car["proxy"]
p.rigid_body.kinematic = True
p.rigid_body.keyframe_insert(data_path="kinematic", frame=1)
p.location.x = -9.0
p.keyframe_insert(data_path="location", frame=1)
p.location.x = -7.5
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
            post_handoff_keys += [float(kp.co.x) for kp in fc.keyframe_points if kp.co.x >= HANDOFF_FRAME]
if post_handoff_keys:
    raise RuntimeError(f"POST_HANDOFF_LOCATION_KEYS_FORBIDDEN {post_handoff_keys}")

bpy.ops.object.camera_add(location=(-1.5, -17.5, 7.0))
cam = bpy.context.object
cam.data.lens = 47
look_at(cam, (-2.0, 0.0, 1.25))
scene.camera = cam
bpy.ops.object.light_add(type="SUN", location=(0,0,10))
sun = bpy.context.object
sun.data.energy = 3.0
sun.rotation_euler = (math.radians(28), math.radians(-18), math.radians(24))

if scene.rigidbody_world is None:
    activate(p)
    bpy.ops.rigidbody.world_add()
world = scene.rigidbody_world
world.point_cache.frame_start = SIM_START
world.point_cache.frame_end = SIM_END
world.substeps_per_frame = 20
world.solver_iterations = 30

scene.frame_set(SIM_START)
bpy.context.view_layer.update()
prev_c = car["proxy"].matrix_world.translation.copy()
prev_b = bulldozer["proxy"].matrix_world.translation.copy()
b_start = prev_b.copy()
impact_frame = None
impact_car_speed = None
impact_b_speed = None
pre_car_max = 0.0
post_car_min = None
b_max_speed = 0.0
b_max_disp = 0.0
samples = []

for frame in range(SIM_START, SIM_END+1):
    scene.frame_set(frame)
    bpy.context.view_layer.update()
    pc = car["proxy"].matrix_world.translation.copy()
    pb = bulldozer["proxy"].matrix_world.translation.copy()
    vc = Vector((0,0,0)) if frame == SIM_START else (pc-prev_c)*FPS
    vb = Vector((0,0,0)) if frame == SIM_START else (pb-prev_b)*FPS
    cs = vc.length; bs = vb.length; bd = (pb-b_start).length
    b_max_speed = max(b_max_speed, bs)
    b_max_disp = max(b_max_disp, bd)
    if frame >= HANDOFF_FRAME and car["proxy"].rigid_body.kinematic:
        raise RuntimeError(f"CAR_STILL_KINEMATIC frame={frame}")
    if impact_frame is None:
        if frame >= HANDOFF_FRAME:
            pre_car_max = max(pre_car_max, cs)
        if frame >= HANDOFF_FRAME+2 and overlap(car, bulldozer) and bs > 0.03:
            impact_frame = frame
            impact_car_speed = cs
            impact_b_speed = bs
    else:
        post_car_min = cs if post_car_min is None else min(post_car_min, cs)
    if frame in (1,4,5,8,12,18,24,36,48,72,96,120,144) or frame == impact_frame:
        samples.append({
            "frame": frame,
            "carPos": [round(x,4) for x in pc],
            "bulldozerPos": [round(x,4) for x in pb],
            "carSpeedMps": round(cs,4),
            "bulldozerSpeedMps": round(bs,4),
            "bulldozerDisplacementM": round(bd,4),
            "carDynamic": not bool(car["proxy"].rigid_body.kinematic),
        })
    prev_c = pc; prev_b = pb

scene.frame_set(SIM_END)
bpy.context.view_layer.update()
final_c = car["proxy"].matrix_world.translation.copy()
final_b = bulldozer["proxy"].matrix_world.translation.copy()
final_b_disp = (final_b-b_start).length
collision = impact_frame is not None
momentum = b_max_speed > 0.03 and b_max_disp > 0.01
mass_plausible = b_max_speed < max(pre_car_max*0.35, 0.12)
car_lost = post_car_min is not None and post_car_min < pre_car_max*0.80
persistent = final_b_disp > 0.01
if not collision:
    raise RuntimeError("REAL_MODEL_COLLISION_NOT_OBSERVED")
if not momentum:
    raise RuntimeError(f"MOMENTUM_TRANSFER_NOT_OBSERVED vmax={b_max_speed:.5f} disp={b_max_disp:.5f}")
if not mass_plausible:
    raise RuntimeError(f"MASS_RESPONSE_IMPLAUSIBLE carPre={pre_car_max:.5f} bulldozerMax={b_max_speed:.5f}")
if not car_lost:
    raise RuntimeError(f"CAR_DID_NOT_LOSE_SPEED carPre={pre_car_max:.5f} postMin={post_car_min}")
if not persistent:
    raise RuntimeError(f"OUTCOME_NOT_PERSISTENT finalBulldozerDisp={final_b_disp:.5f}")

scene.frame_start = SIM_START
scene.frame_end = SIM_END
scene.frame_set(SIM_START)
bpy.ops.render.render(animation=True)
if not out.is_file() or out.stat().st_size < 4096:
    raise RuntimeError("REAL_MODEL_VIDEO_MISSING")

result = {
    "scope": "ISS_REAL_MODEL_COLLISION_OUTCOME_TEST",
    "engine": "BLENDER",
    "engineVersion": "4.5.13",
    "physicsBackend": "BLENDER_RIGID_BODY",
    "renderEngine": "BLENDER_WORKBENCH",
    "productionAcceptance": False,
    "continuousWorld": True,
    "simulationSeconds": 6.0,
    "collisionObserved": collision,
    "momentumTransferObserved": momentum,
    "massAsymmetryPlausible": mass_plausible,
    "carLostSpeedAfterImpact": car_lost,
    "persistentOutcome": persistent,
    "scriptedDamageUsed": False,
    "dynamicBeforeImpact": bool(impact_frame and impact_frame > HANDOFF_FRAME),
    "postHandoffLocationKeyframeCount": len(post_handoff_keys),
    "impactFrame": impact_frame,
    "impactTimeSeconds": round(impact_frame/FPS,4),
    "preImpactCarMaxSpeedMps": round(pre_car_max,6),
    "impactCarSpeedMps": round(float(impact_car_speed),6),
    "impactBulldozerSpeedMps": round(float(impact_b_speed),6),
    "bulldozerMaxSpeedMps": round(b_max_speed,6),
    "bulldozerMaxDisplacementMeters": round(b_max_disp,6),
    "finalBulldozerDisplacementMeters": round(final_b_disp,6),
    "finalCarPosition": [round(x,6) for x in final_c],
    "finalBulldozerPosition": [round(x,6) for x in final_b],
    "carMassKg": CAR_MASS_KG,
    "bulldozerMassKg": BULLDOZER_MASS_KG,
    "massRatioBulldozerToCar": round(BULLDOZER_MASS_KG/CAR_MASS_KG,6),
    "carSourceSha256": car["sourceSha256"],
    "bulldozerSourceSha256": bulldozer["sourceSha256"],
    "carSourceTriangles": car["sourceTriangles"],
    "bulldozerSourceTriangles": bulldozer["sourceTriangles"],
    "carTransportTriangles": car["transportTriangles"],
    "bulldozerTransportTriangles": bulldozer["transportTriangles"],
    "geometryTransport": "exact-upload-derived-quantized-surface-v1",
    "carDimensionsMeters": [round(x,4) for x in car["dims"]],
    "bulldozerDimensionsMeters": [round(x,4) for x in bulldozer["dims"]],
    "samples": samples,
}
result_path.write_text(json.dumps(result, indent=2, sort_keys=True), encoding="utf-8")
print(json.dumps(result, sort_keys=True))
print("ISS_REAL_MODEL_COLLISION_OUTCOME=PASS")
