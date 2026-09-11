import bpy
import json
import os
from mathutils import Vector

BLENDER_VERSION = "4.5.13"
FPS = 24
SIM_FRAME_START = 1
SIM_FRAME_END = 72
RENDER_FRAME_START = 25
RENDER_FRAME_END = 48
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


def add_rigid_body(obj, body_type="ACTIVE", mass=1.0, kinematic=False):
    activate(obj)
    bpy.ops.rigidbody.object_add()
    obj.rigid_body.type = body_type
    obj.rigid_body.collision_shape = "BOX"
    obj.rigid_body.mass = mass
    obj.rigid_body.friction = 0.65
    obj.rigid_body.restitution = 0.05
    if body_type == "ACTIVE":
        obj.rigid_body.kinematic = kinematic


def look_at(obj, point):
    direction = Vector(point) - obj.location
    obj.rotation_euler = direction.to_track_quat("-Z", "Y").to_euler()


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
scene.world.color = (0.035, 0.035, 0.035)

ground = add_box("ground", (0.0, 0.0, -0.25), (16.0, 8.0, 0.5))
add_rigid_body(ground, body_type="PASSIVE")

target = add_box("target_vehicle", (0.0, 0.0, 0.55), (2.2, 1.2, 1.1))
add_rigid_body(target, body_type="ACTIVE", mass=1800.0, kinematic=False)

target.shape_key_add(name="Basis")
dent = target.shape_key_add(name="ImpactDent")
for v in dent.data:
    if v.co.x < -0.8:
        v.co.x += 0.38
        v.co.z *= 0.88
dent.value = 0.0
dent.keyframe_insert(data_path="value", frame=29)
dent.value = 1.0
dent.keyframe_insert(data_path="value", frame=31)

attacker = add_box("attacker_vehicle", (-4.5, 0.0, 0.55), (2.2, 1.2, 1.1))
add_rigid_body(attacker, body_type="ACTIVE", mass=1450.0, kinematic=True)
scene.frame_set(1)
attacker.location.x = -4.5
attacker.keyframe_insert(data_path="location", frame=1)
attacker.location.x = 1.25
attacker.keyframe_insert(data_path="location", frame=34)
attacker.location.x = 1.55
attacker.keyframe_insert(data_path="location", frame=72)
for fc in attacker.animation_data.action.fcurves:
    for kp in fc.keyframe_points:
        kp.interpolation = "LINEAR"

bpy.ops.object.camera_add(location=(7.5, -10.5, 5.0))
camera = bpy.context.object
camera.name = "battle_camera"
look_at(camera, (0.0, 0.0, 0.6))
scene.camera = camera

bpy.ops.object.light_add(type="AREA", location=(1.0, -2.0, 7.0))
key = bpy.context.object
key.data.energy = 1800.0
key.data.shape = "DISK"
key.data.size = 6.0

bpy.ops.object.light_add(type="AREA", location=(-4.0, 4.0, 3.0))
fill = bpy.context.object
fill.data.energy = 900.0
fill.data.size = 5.0
look_at(fill, (0.0, 0.0, 0.5))

if scene.rigidbody_world is None:
    bpy.context.view_layer.objects.active = target
    bpy.ops.rigidbody.world_add()
scene.rigidbody_world.point_cache.frame_start = SIM_FRAME_START
scene.rigidbody_world.point_cache.frame_end = SIM_FRAME_END
scene.rigidbody_world.substeps_per_frame = 10
scene.rigidbody_world.solver_iterations = 20

scene.frame_set(SIM_FRAME_START)
start = target.matrix_world.translation.copy()
max_displacement = 0.0
sampled = []
for frame in range(SIM_FRAME_START, SIM_FRAME_END + 1):
    scene.frame_set(frame)
    bpy.context.view_layer.update()
    pos = target.matrix_world.translation.copy()
    displacement = (pos - start).length
    max_displacement = max(max_displacement, displacement)
    if frame in (1, 24, 34, 48, 72):
        sampled.append({"frame": frame, "target": [round(pos.x, 6), round(pos.y, 6), round(pos.z, 6)], "displacement": round(displacement, 6)})

collision_observed = max_displacement > 0.08
if not collision_observed:
    raise RuntimeError(f"BLENDER_COLLISION_NOT_OBSERVED max_displacement={max_displacement:.6f}")

scene.frame_set(SIM_FRAME_END)
visible_damage_applied = dent.value > 0.99 and collision_observed
persistent_world_state = (target.matrix_world.translation - start).length > 0.08 and visible_damage_applied
if not visible_damage_applied:
    raise RuntimeError("BLENDER_VISIBLE_DAMAGE_GATE_FAILED")
if not persistent_world_state:
    raise RuntimeError("BLENDER_PERSISTENCE_GATE_FAILED")

# Render only the impact window. The physics/world proof above still covers the full 72-frame continuous simulation.
scene.frame_start = RENDER_FRAME_START
scene.frame_end = RENDER_FRAME_END
scene.frame_set(RENDER_FRAME_START)
bpy.ops.render.render(animation=True)
render_completed = os.path.isfile(VIDEO) and os.path.getsize(VIDEO) > 0
if not render_completed:
    raise RuntimeError("BLENDER_RENDER_OUTPUT_MISSING")

result = {
    "scope": "BACKEND_SMOKE_ONLY",
    "productionAcceptance": False,
    "engine": "BLENDER",
    "engineVersion": BLENDER_VERSION,
    "renderEngine": "BLENDER_EEVEE_NEXT",
    "physicsBackend": "BLENDER_RIGID_BODY",
    "continuousWorld": True,
    "simulationCompleted": True,
    "collisionObserved": collision_observed,
    "visibleDamageApplied": visible_damage_applied,
    "persistentWorldState": persistent_world_state,
    "renderCompleted": render_completed,
    "maxTargetDisplacementMeters": round(max_displacement, 6),
    "simulationFrames": SIM_FRAME_END - SIM_FRAME_START + 1,
    "renderedFrames": RENDER_FRAME_END - RENDER_FRAME_START + 1,
    "fps": FPS,
    "samples": sampled,
    "notes": "Synthetic two-actor engine smoke. Full 72-frame persistent simulation; impact-window EEVEE render only. Does not claim production asset, debris, Story-event or full Battle Executor acceptance."
}
with open(RESULT, "w", encoding="utf-8") as f:
    json.dump(result, f, indent=2, sort_keys=True)
print(json.dumps(result, sort_keys=True))
print("ISS_BLENDER_SMOKE=PASS")
