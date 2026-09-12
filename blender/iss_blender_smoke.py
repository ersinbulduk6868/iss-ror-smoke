import bpy
import json
import os
from mathutils import Vector

BLENDER_VERSION = "4.5.13"
FPS = 24
SIM_FRAME_START = 1
SIM_FRAME_END = 96
HANDOFF_FRAME = 5
ROOT = os.path.abspath(os.getcwd())
ARTIFACTS = os.path.join(ROOT, "artifacts")
VIDEO = os.path.join(ARTIFACTS, "blender_smoke.mp4")
RESULT = os.path.join(ARTIFACTS, "blender_smoke_result.json")
os.makedirs(ARTIFACTS, exist_ok=True)


def activate(obj):
    bpy.ops.object.select_all(action="DESELECT")
    obj.select_set(True)
    bpy.context.view_layer.objects.active = obj


def add_box(name, location, dimensions):
    bpy.ops.mesh.primitive_cube_add(size=1.0, location=location)
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
    if body_type == "ACTIVE":
        obj.rigid_body.linear_damping = 0.02
        obj.rigid_body.angular_damping = 0.05
        obj.rigid_body.use_deactivation = False


def look_at(obj, point):
    obj.rotation_euler = (Vector(point) - obj.location).to_track_quat("-Z", "Y").to_euler()


def add_material(obj, name, color):
    mat = bpy.data.materials.new(name)
    mat.diffuse_color = (*color, 1.0)
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
scene.render.resolution_percentage = 25
scene.render.image_settings.file_format = "FFMPEG"
scene.render.ffmpeg.format = "MPEG4"
scene.render.ffmpeg.codec = "H264"
scene.render.ffmpeg.constant_rate_factor = "MEDIUM"
scene.render.filepath = VIDEO
scene.world.color = (0.025, 0.028, 0.035)
scene.gravity = (0.0, 0.0, -9.81)

ground = add_box("ground", (0.0, 0.0, -0.25), (20.0, 8.0, 0.5))
add_rigid_body(ground, body_type="PASSIVE", friction=0.92, restitution=0.01)

attacker = add_box("attacker_vehicle", (-5.5, 0.0, 0.55), (2.2, 1.2, 1.1))
add_rigid_body(attacker, body_type="ACTIVE", mass=1450.0, friction=0.18, restitution=0.04)
add_material(attacker, "attacker_material", (0.10, 0.22, 0.62))

target = add_box("target_vehicle", (1.5, 0.0, 0.55), (2.2, 1.2, 1.1))
add_rigid_body(target, body_type="ACTIVE", mass=1800.0, friction=0.72, restitution=0.04)
add_material(target, "target_material", (0.62, 0.16, 0.08))

# Blender-documented Animated -> Dynamic handoff only seeds initial velocity.
attacker.rigid_body.kinematic = True
attacker.rigid_body.keyframe_insert(data_path="kinematic", frame=1)
attacker.location = (-5.5, 0.0, 0.55)
attacker.keyframe_insert(data_path="location", frame=1)
attacker.location = (-4.6, 0.0, 0.55)
attacker.keyframe_insert(data_path="location", frame=4)
attacker.rigid_body.kinematic = True
attacker.rigid_body.keyframe_insert(data_path="kinematic", frame=4)
attacker.rigid_body.kinematic = False
attacker.rigid_body.keyframe_insert(data_path="kinematic", frame=HANDOFF_FRAME)

if attacker.animation_data and attacker.animation_data.action:
    for fc in attacker.animation_data.action.fcurves:
        for kp in fc.keyframe_points:
            kp.interpolation = "LINEAR"
if target.animation_data is not None:
    raise RuntimeError("TARGET_ANIMATION_FORBIDDEN")

bpy.ops.object.camera_add(location=(7.5, -12.0, 5.5))
camera = bpy.context.object
look_at(camera, (-0.5, 0.0, 0.8))
scene.camera = camera
bpy.ops.object.light_add(type="AREA", location=(0.0, -2.0, 8.0))
key = bpy.context.object
key.data.energy = 1700.0
key.data.shape = "DISK"
key.data.size = 7.0

if scene.rigidbody_world is None:
    activate(attacker)
    bpy.ops.rigidbody.world_add()
scene.rigidbody_world.point_cache.frame_start = SIM_FRAME_START
scene.rigidbody_world.point_cache.frame_end = SIM_FRAME_END
scene.rigidbody_world.substeps_per_frame = 20
scene.rigidbody_world.solver_iterations = 30

post_handoff_location_keys = []
location_curve_count = 0
if attacker.animation_data and attacker.animation_data.action:
    for fc in attacker.animation_data.action.fcurves:
        if fc.data_path == "location":
            location_curve_count += 1
            for kp in fc.keyframe_points:
                if kp.co.x >= HANDOFF_FRAME:
                    post_handoff_location_keys.append(float(kp.co.x))
if post_handoff_location_keys:
    raise RuntimeError(f"POST_HANDOFF_LOCATION_KEYFRAME_FORBIDDEN frames={post_handoff_location_keys}")

scene.frame_set(1)
bpy.context.view_layer.update()
target_start = target.matrix_world.translation.copy()
prev_attacker = attacker.matrix_world.translation.copy()
prev_target = target.matrix_world.translation.copy()
telemetry = []
impact_frame = None
impact_center_distance = None
impact_attacker_speed = None
impact_target_speed = None
attacker_max_speed_after_handoff = 0.0
target_max_speed = 0.0
target_max_displacement = 0.0
preimpact_target_max_speed = 0.0
handoff_dynamic_verified = False
minimum_center_distance = 999.0

for frame in range(1, SIM_FRAME_END + 1):
    scene.frame_set(frame)
    bpy.context.view_layer.update()
    pa = attacker.matrix_world.translation.copy()
    pt = target.matrix_world.translation.copy()
    if frame == 1:
        va = Vector((0.0, 0.0, 0.0))
        vt = Vector((0.0, 0.0, 0.0))
    else:
        va = (pa - prev_attacker) * FPS
        vt = (pt - prev_target) * FPS
    attacker_speed = va.length
    target_speed = vt.length
    target_disp = (pt - target_start).length
    center_distance = (pa - pt).length
    minimum_center_distance = min(minimum_center_distance, center_distance)

    if frame >= HANDOFF_FRAME:
        if attacker.rigid_body.kinematic:
            raise RuntimeError(f"ATTACKER_STILL_KINEMATIC_AFTER_HANDOFF frame={frame}")
        handoff_dynamic_verified = True
        attacker_max_speed_after_handoff = max(attacker_max_speed_after_handoff, attacker_speed)

    target_max_speed = max(target_max_speed, target_speed)
    target_max_displacement = max(target_max_displacement, target_disp)
    if impact_frame is None:
        preimpact_target_max_speed = max(preimpact_target_max_speed, target_speed)
        if frame >= HANDOFF_FRAME + 4 and center_distance <= 2.35 and target_speed > 0.30:
            impact_frame = frame
            impact_center_distance = center_distance
            impact_attacker_speed = attacker_speed
            impact_target_speed = target_speed

    if frame in (1, 4, 5, 12, 24, 48, 72, 96) or frame == impact_frame:
        telemetry.append({
            "frame": frame,
            "attacker": [round(pa.x, 6), round(pa.y, 6), round(pa.z, 6)],
            "target": [round(pt.x, 6), round(pt.y, 6), round(pt.z, 6)],
            "attackerSpeedMps": round(attacker_speed, 6),
            "targetSpeedMps": round(target_speed, 6),
            "targetDisplacementM": round(target_disp, 6),
            "attackerKinematic": bool(attacker.rigid_body.kinematic),
        })
    prev_attacker = pa
    prev_target = pt

scene.frame_set(SIM_FRAME_END)
bpy.context.view_layer.update()
target_final = target.matrix_world.translation.copy()
persistent_target_displacement = (target_final - target_start).length
collision_observed = (
    impact_frame is not None
    and minimum_center_distance <= 2.35
    and target_max_displacement > 0.15
    and target_max_speed > 0.30
    and attacker_max_speed_after_handoff > 0.80
)
momentum_transfer_observed = collision_observed and target_max_speed > 0.30
persistent_world_state = persistent_target_displacement > 0.10

if not handoff_dynamic_verified:
    raise RuntimeError("DYNAMIC_HANDOFF_NOT_VERIFIED")
if not collision_observed:
    raise RuntimeError(
        "BLENDER_REAL_COLLISION_NOT_OBSERVED "
        f"impact_frame={impact_frame} min_center={minimum_center_distance:.6f} "
        f"target_disp={target_max_displacement:.6f} target_vmax={target_max_speed:.6f} "
        f"attacker_vmax_after_handoff={attacker_max_speed_after_handoff:.6f}"
    )
if not momentum_transfer_observed:
    raise RuntimeError("BLENDER_MOMENTUM_TRANSFER_GATE_FAILED")
if not persistent_world_state:
    raise RuntimeError(f"BLENDER_PERSISTENCE_GATE_FAILED final_target_disp={persistent_target_displacement:.6f}")

# Render only a compact evidence window around the already-proven impact.
render_start = max(SIM_FRAME_START, impact_frame - 2)
render_end = min(SIM_FRAME_END, impact_frame + 3)
rendered_frames = render_end - render_start + 1
scene.frame_start = render_start
scene.frame_end = render_end
scene.frame_set(render_start)
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
    "initialVelocitySeedMethod": "BLENDER_ANIMATED_TO_DYNAMIC_HANDOFF",
    "handoffFrame": HANDOFF_FRAME,
    "dynamicBeforeImpact": bool(impact_frame and impact_frame > HANDOFF_FRAME + 3),
    "postHandoffLocationKeyframeCount": len(post_handoff_location_keys),
    "attackerLocationCurveCount": location_curve_count,
    "attackerMassKg": 1450.0,
    "targetMassKg": 1800.0,
    "attackerMaxSpeedAfterHandoffMps": round(attacker_max_speed_after_handoff, 6),
    "targetMaxSpeedMps": round(target_max_speed, 6),
    "maxTargetDisplacementMeters": round(target_max_displacement, 6),
    "finalTargetDisplacementMeters": round(persistent_target_displacement, 6),
    "minimumCenterDistanceMeters": round(minimum_center_distance, 6),
    "impactFrame": impact_frame,
    "impactCenterDistanceMeters": round(float(impact_center_distance), 6),
    "impactAttackerSpeedMps": round(float(impact_attacker_speed), 6),
    "impactTargetSpeedMps": round(float(impact_target_speed), 6),
    "preimpactTargetMaxSpeedMps": round(preimpact_target_max_speed, 6),
    "simulationFrames": SIM_FRAME_END,
    "renderStartFrame": render_start,
    "renderEndFrame": render_end,
    "renderedFrames": rendered_frames,
    "fps": FPS,
    "samples": telemetry,
}
with open(RESULT, "w", encoding="utf-8") as f:
    json.dump(result, f, indent=2, sort_keys=True)
print(json.dumps(result, sort_keys=True))
print("ISS_BLENDER_SMOKE=PASS")
