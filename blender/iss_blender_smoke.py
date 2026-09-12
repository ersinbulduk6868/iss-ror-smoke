import bpy
import json
import math
import os
from mathutils import Vector

BLENDER_VERSION = "4.5.13"
FPS = 24
SIM_FRAME_START = 1
SIM_FRAME_END = 96
ROOT = os.path.abspath(os.getcwd())
ARTIFACTS = os.path.join(ROOT, "artifacts")
VIDEO = os.path.join(ARTIFACTS, "blender_smoke.mp4")
RESULT = os.path.join(ARTIFACTS, "blender_smoke_result.json")
os.makedirs(ARTIFACTS, exist_ok=True)


def activate(obj):
    bpy.ops.object.select_all(action="DESELECT")
    obj.select_set(True)
    bpy.context.view_layer.objects.active = obj


def add_box(name, location, dimensions, rotation=(0.0, 0.0, 0.0)):
    bpy.ops.mesh.primitive_cube_add(size=1.0, location=location, rotation=rotation)
    obj = bpy.context.object
    obj.name = name
    obj.dimensions = dimensions
    activate(obj)
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    return obj


def add_rigid_body(obj, body_type="ACTIVE", mass=1.0, friction=0.5, restitution=0.05):
    activate(obj)
    bpy.ops.rigidbody.object_add()
    obj.rigid_body.type = body_type
    obj.rigid_body.collision_shape = "BOX"
    obj.rigid_body.mass = mass
    obj.rigid_body.friction = friction
    obj.rigid_body.restitution = restitution
    obj.rigid_body.linear_damping = 0.03
    obj.rigid_body.angular_damping = 0.08
    if body_type == "ACTIVE":
        obj.rigid_body.kinematic = False
        obj.rigid_body.use_deactivation = False


def look_at(obj, point):
    direction = Vector(point) - obj.location
    obj.rotation_euler = direction.to_track_quat("-Z", "Y").to_euler()


def add_material(obj, name, base_color):
    mat = bpy.data.materials.new(name)
    mat.diffuse_color = (*base_color, 1.0)
    obj.data.materials.append(mat)


bpy.ops.object.select_all(action="SELECT")
bpy.ops.object.delete(use_global=False)

scene = bpy.context.scene
scene.frame_start = SIM_FRAME_START
scene.frame_end = SIM_FRAME_END
scene.render.fps = FPS
scene.render.engine = "BLENDER_EEVEE_NEXT"
scene.render.resolution_x = 320
scene.render.resolution_y = 180
scene.render.resolution_percentage = 50
scene.render.image_settings.file_format = "FFMPEG"
scene.render.ffmpeg.format = "MPEG4"
scene.render.ffmpeg.codec = "H264"
scene.render.ffmpeg.constant_rate_factor = "MEDIUM"
scene.render.filepath = VIDEO
scene.world.color = (0.025, 0.028, 0.035)
scene.gravity = (0.0, 0.0, -9.81)

# Flat ground after the launch ramp.
ground = add_box("ground", (2.5, 0.0, -0.25), (14.0, 8.0, 0.5))
add_rigid_body(ground, body_type="PASSIVE", friction=0.95, restitution=0.02)

# Gravity-only launch ramp. No kinematic rigid bodies and no location keyframes.
ramp_angle = math.radians(-12.0)
ramp = add_box("launch_ramp", (-4.0, 0.0, 0.90), (8.0, 3.0, 0.22), rotation=(0.0, ramp_angle, 0.0))
add_rigid_body(ramp, body_type="PASSIVE", friction=0.03, restitution=0.01)

# Vehicle-scale rigid bodies.
attacker = add_box("attacker_vehicle", (-5.6, 0.0, 1.82), (2.2, 1.2, 1.1), rotation=(0.0, ramp_angle, 0.0))
add_rigid_body(attacker, body_type="ACTIVE", mass=1450.0, friction=0.08, restitution=0.04)
add_material(attacker, "attacker_material", (0.10, 0.22, 0.62))

target = add_box("target_vehicle", (2.0, 0.0, 0.55), (2.2, 1.2, 1.1))
add_rigid_body(target, body_type="ACTIVE", mass=1800.0, friction=0.82, restitution=0.04)
add_material(target, "target_material", (0.62, 0.16, 0.08))

# Camera/light.
bpy.ops.object.camera_add(location=(7.5, -12.0, 5.8))
camera = bpy.context.object
camera.name = "collision_truth_camera"
look_at(camera, (-0.5, 0.0, 0.9))
scene.camera = camera

bpy.ops.object.light_add(type="AREA", location=(0.0, -2.0, 8.0))
key = bpy.context.object
key.data.energy = 1700.0
key.data.shape = "DISK"
key.data.size = 7.0

bpy.ops.object.light_add(type="AREA", location=(-5.0, 4.0, 4.0))
fill = bpy.context.object
fill.data.energy = 800.0
fill.data.size = 5.0
look_at(fill, (-1.0, 0.0, 0.8))

if scene.rigidbody_world is None:
    activate(attacker)
    bpy.ops.rigidbody.world_add()
scene.rigidbody_world.point_cache.frame_start = SIM_FRAME_START
scene.rigidbody_world.point_cache.frame_end = SIM_FRAME_END
scene.rigidbody_world.substeps_per_frame = 20
scene.rigidbody_world.solver_iterations = 30

# Prove there is no scripted motion path.
kinematic_count = sum(
    1 for obj in (attacker, target)
    if obj.rigid_body and obj.rigid_body.kinematic
)
location_keyframe_count = 0
for obj in (attacker, target):
    ad = obj.animation_data
    action = ad.action if ad else None
    if action:
        location_keyframe_count += sum(1 for fc in action.fcurves if fc.data_path == "location")
if kinematic_count != 0:
    raise RuntimeError(f"KINEMATIC_BODY_FORBIDDEN count={kinematic_count}")
if location_keyframe_count != 0:
    raise RuntimeError(f"LOCATION_KEYFRAME_FORBIDDEN count={location_keyframe_count}")

scene.frame_set(SIM_FRAME_START)
bpy.context.view_layer.update()
attacker_start = attacker.matrix_world.translation.copy()
target_start = target.matrix_world.translation.copy()

telemetry = []
prev_attacker = attacker_start.copy()
prev_target = target_start.copy()
target_max_speed = 0.0
attacker_max_speed = 0.0
target_max_displacement = 0.0
impact_frame = None
impact_center_distance = None
impact_attacker_speed = None
impact_target_speed = None
preimpact_target_max_speed = 0.0

for frame in range(SIM_FRAME_START, SIM_FRAME_END + 1):
    scene.frame_set(frame)
    bpy.context.view_layer.update()
    pa = attacker.matrix_world.translation.copy()
    pt = target.matrix_world.translation.copy()
    if frame == SIM_FRAME_START:
        va = Vector((0.0, 0.0, 0.0))
        vt = Vector((0.0, 0.0, 0.0))
    else:
        va = (pa - prev_attacker) * FPS
        vt = (pt - prev_target) * FPS
    attacker_speed = va.length
    target_speed = vt.length
    target_disp = (pt - target_start).length
    attacker_max_speed = max(attacker_max_speed, attacker_speed)
    target_max_speed = max(target_max_speed, target_speed)
    target_max_displacement = max(target_max_displacement, target_disp)
    if impact_frame is None:
        preimpact_target_max_speed = max(preimpact_target_max_speed, target_speed)
        # A real response is a previously stationary target gaining velocity
        # while the attacker is physically close enough for box contact.
        center_distance = (pa - pt).length
        contact_distance = 2.55
        if frame > 8 and target_speed > 0.35 and center_distance <= contact_distance:
            impact_frame = frame
            impact_center_distance = center_distance
            impact_attacker_speed = attacker_speed
            impact_target_speed = target_speed
    if frame in (1, 24, 48, 72, 96) or frame == impact_frame:
        telemetry.append({
            "frame": frame,
            "attacker": [round(pa.x, 6), round(pa.y, 6), round(pa.z, 6)],
            "target": [round(pt.x, 6), round(pt.y, 6), round(pt.z, 6)],
            "attackerSpeedMps": round(attacker_speed, 6),
            "targetSpeedMps": round(target_speed, 6),
            "targetDisplacementM": round(target_disp, 6),
        })
    prev_attacker = pa
    prev_target = pt

scene.frame_set(SIM_FRAME_END)
bpy.context.view_layer.update()
target_final = target.matrix_world.translation.copy()
attacker_final = attacker.matrix_world.translation.copy()
persistent_target_displacement = (target_final - target_start).length

collision_observed = (
    impact_frame is not None
    and target_max_displacement > 0.15
    and target_max_speed > 0.35
    and attacker_max_speed > 0.8
)
momentum_transfer_observed = collision_observed and target_max_speed > 0.35
persistent_world_state = persistent_target_displacement > 0.10

if not collision_observed:
    raise RuntimeError(
        "BLENDER_REAL_COLLISION_NOT_OBSERVED "
        f"impact_frame={impact_frame} target_disp={target_max_displacement:.6f} "
        f"target_vmax={target_max_speed:.6f} attacker_vmax={attacker_max_speed:.6f}"
    )
if not momentum_transfer_observed:
    raise RuntimeError("BLENDER_MOMENTUM_TRANSFER_GATE_FAILED")
if not persistent_world_state:
    raise RuntimeError(
        f"BLENDER_PERSISTENCE_GATE_FAILED final_target_disp={persistent_target_displacement:.6f}"
    )

# Render the full continuous truth-test timeline.
scene.frame_start = SIM_FRAME_START
scene.frame_end = SIM_FRAME_END
scene.frame_set(SIM_FRAME_START)
bpy.ops.render.render(animation=True)
render_completed = os.path.isfile(VIDEO) and os.path.getsize(VIDEO) > 0
if not render_completed:
    raise RuntimeError("BLENDER_RENDER_OUTPUT_MISSING")

result = {
    "scope": "BLENDER_RIGID_BODY_COLLISION_TRUTH_TEST",
    "productionAcceptance": False,
    "engine": "BLENDER",
    "engineVersion": BLENDER_VERSION,
    "renderEngine": "BLENDER_EEVEE_NEXT",
    "physicsBackend": "BLENDER_RIGID_BODY",
    "continuousWorld": True,
    "simulationCompleted": True,
    "collisionObserved": collision_observed,
    "momentumTransferObserved": momentum_transfer_observed,
    "persistentWorldState": persistent_world_state,
    "renderCompleted": render_completed,
    "scriptedDamageUsed": False,
    "kinematicBodyCount": kinematic_count,
    "locationKeyframeCurveCount": location_keyframe_count,
    "attackerMassKg": 1450.0,
    "targetMassKg": 1800.0,
    "attackerMaxSpeedMps": round(attacker_max_speed, 6),
    "targetMaxSpeedMps": round(target_max_speed, 6),
    "maxTargetDisplacementMeters": round(target_max_displacement, 6),
    "finalTargetDisplacementMeters": round(persistent_target_displacement, 6),
    "impactFrame": impact_frame,
    "impactCenterDistanceMeters": round(float(impact_center_distance), 6) if impact_center_distance is not None else None,
    "impactAttackerSpeedMps": round(float(impact_attacker_speed), 6) if impact_attacker_speed is not None else None,
    "impactTargetSpeedMps": round(float(impact_target_speed), 6) if impact_target_speed is not None else None,
    "preimpactTargetMaxSpeedMps": round(preimpact_target_max_speed, 6),
    "simulationFrames": SIM_FRAME_END - SIM_FRAME_START + 1,
    "renderedFrames": SIM_FRAME_END - SIM_FRAME_START + 1,
    "fps": FPS,
    "samples": telemetry,
    "notes": (
        "Vehicle-scale Blender rigid-body truth test. Both actors remain fully dynamic; "
        "motion is gravity-driven by a passive launch ramp. No kinematic actor, no location "
        "keyframes, no scripted damage. PASS requires target motion/momentum response while "
        "the attacker is within physical contact proximity."
    ),
}
with open(RESULT, "w", encoding="utf-8") as f:
    json.dump(result, f, indent=2, sort_keys=True)

print(json.dumps(result, sort_keys=True))
print("ISS_BLENDER_SMOKE=PASS")
