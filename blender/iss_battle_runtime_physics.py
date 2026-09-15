from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any

import bpy
from mathutils import Vector

from blender.iss_battle_runtime_core import (ActorProfile, ActorState, BattleProgram, EventState, RuntimeEvent, TargetingPlanner, clamp, norm)
from blender.iss_battle_runtime_assets import (AssetPrototype, BlenderBattleRuntimeError, add_rigid_body, activate, cube)

CONTROL_MODEL = "DIFFERENTIAL_RIGID_BODY_MOTOR_V1"

@dataclass
class DriveRig:
    chassis: bpy.types.Object
    wheels_left: list[bpy.types.Object]
    wheels_right: list[bpy.types.Object]
    motors_left: list[bpy.types.Object]
    motors_right: list[bpy.types.Object]
    hinges: list[bpy.types.Object]
    wheel_radius: float
    max_motor_impulse: float

    def command(self, left_mps: float, right_mps: float, impulse_scale: float = 1.0) -> None:
        left_w = float(left_mps) / max(self.wheel_radius, 1e-4)
        right_w = float(right_mps) / max(self.wheel_radius, 1e-4)
        for obj in self.motors_left:
            c = obj.rigid_body_constraint
            c.motor_ang_target_velocity = left_w
            c.motor_ang_max_impulse = max(0.0, self.max_motor_impulse * impulse_scale)
        for obj in self.motors_right:
            c = obj.rigid_body_constraint
            c.motor_ang_target_velocity = right_w
            c.motor_ang_max_impulse = max(0.0, self.max_motor_impulse * impulse_scale)

    def brake(self, strength: float = 1.0) -> None:
        self.command(0.0, 0.0, max(1.0, strength * 1.5))


@dataclass
class RuntimeActor:
    binding: dict[str, Any]
    profile: ActorProfile
    state: ActorState
    prototype: AssetPrototype
    chassis: bpy.types.Object
    visual_instance: bpy.types.Object
    visual_offset: Vector
    rig: DriveRig
    dimensions: Vector
    motion: dict[int, tuple[Vector, Any]] = field(default_factory=dict)
    velocity: dict[int, Vector] = field(default_factory=dict)
    realized_root: bpy.types.Object | None = None
    realized_meshes: list[bpy.types.Object] = field(default_factory=list)
    damage_visual_evidence: list[dict[str, Any]] = field(default_factory=list)

    def zone_world(self, zone: str | None) -> Vector:
        key = norm(zone) or "body"
        if key not in self.prototype.zones:
            raise BlenderBattleRuntimeError(f"TARGET_SEMANTIC_ZONE_UNRESOLVED:{self.profile.entity_id}:{key}")
        local = self.prototype.zones[key] + self.visual_offset
        return self.chassis.matrix_world @ local

    def local_point_world(self, local: Vector) -> Vector:
        return self.chassis.matrix_world @ (local + self.visual_offset)


@dataclass
class PendingContact:
    event_id: str
    attacker_id: str
    target_id: str
    target_zone: str | None
    frame: int
    resolve_frame: int
    pre_attacker_velocity: Vector
    pre_target_velocity: Vector
    contact_point: Vector
    contact_normal: Vector
    semantic_distance: float


def add_constraint(name: str, kind: str, location: Vector, axis: Vector, object1: bpy.types.Object, object2: bpy.types.Object) -> bpy.types.Object:
    obj = bpy.data.objects.new(name, None)
    bpy.context.scene.collection.objects.link(obj)
    obj.location = location
    if kind == "HINGE":
        obj.rotation_mode = "QUATERNION"
        obj.rotation_quaternion = axis.normalized().to_track_quat("Z", "X")
    elif kind == "MOTOR":
        obj.rotation_mode = "QUATERNION"
        obj.rotation_quaternion = axis.normalized().to_track_quat("X", "Z")
    activate(obj)
    bpy.ops.rigidbody.constraint_add(type=kind)
    c = obj.rigid_body_constraint
    c.object1 = object1
    c.object2 = object2
    c.use_override_solver_iterations = True
    c.solver_iterations = 50
    if kind == "MOTOR":
        c.use_motor_ang = True
        c.motor_ang_target_velocity = 0.0
    return obj


def create_drive_rig(entity: str, chassis: bpy.types.Object, dimensions: Vector, profile: ActorProfile, yaw: float) -> DriveRig:
    length, width, height = float(dimensions.x), float(dimensions.y), float(dimensions.z)
    wheel_radius = clamp(height * 0.24, 0.26, min(0.90, length * 0.16))
    wheel_width = clamp(width * 0.13, 0.16, 0.55)
    axle_x = length * 0.31
    lateral_y = width * 0.48
    base = chassis.location.copy()
    axis = Vector((-math.sin(yaw), math.cos(yaw), 0.0)).normalized()
    forward = Vector((math.cos(yaw), math.sin(yaw), 0.0))
    lateral = axis
    wheels_left: list[bpy.types.Object] = []
    wheels_right: list[bpy.types.Object] = []
    motors_left: list[bpy.types.Object] = []
    motors_right: list[bpy.types.Object] = []
    hinges: list[bpy.types.Object] = []
    wheel_mass = max(8.0, profile.mass_kg * 0.018)
    impulse = max(8.0, profile.mass_kg * profile.acceleration_mps2 * wheel_radius / 4.0 / 30.0 * 7.0)
    for axle_label, sx in (("F", 1.0), ("R", -1.0)):
        for side_label, sy in (("L", 1.0), ("R", -1.0)):
            center = base + forward * (sx * axle_x) + lateral * (sy * lateral_y)
            center.z = wheel_radius
            bpy.ops.mesh.primitive_cylinder_add(vertices=24, radius=wheel_radius, depth=wheel_width, location=center)
            wheel = bpy.context.object
            wheel.name = f"ISS_DRIVE_WHEEL_{norm(entity)}_{axle_label}{side_label}"
            wheel.rotation_mode = "QUATERNION"
            wheel.rotation_quaternion = axis.to_track_quat("Z", "X")
            wheel.hide_render = True
            add_rigid_body(wheel, mass=wheel_mass, shape="CYLINDER", friction=max(1.1, profile.friction), restitution=0.01)
            hinge = add_constraint(f"ISS_HINGE_{norm(entity)}_{axle_label}{side_label}", "HINGE", center, axis, chassis, wheel)
            motor = add_constraint(f"ISS_MOTOR_{norm(entity)}_{axle_label}{side_label}", "MOTOR", center, axis, chassis, wheel)
            motor.rigid_body_constraint.motor_ang_max_impulse = impulse
            hinges.append(hinge)
            if side_label == "L":
                wheels_left.append(wheel); motors_left.append(motor)
            else:
                wheels_right.append(wheel); motors_right.append(motor)
    return DriveRig(chassis, wheels_left, wheels_right, motors_left, motors_right, hinges, wheel_radius, impulse)


def create_runtime_actor(binding: dict[str, Any], profile: ActorProfile, proto: AssetPrototype, spawn: tuple[float, float, float], yaw: float) -> RuntimeActor:
    dims = proto.dimensions.copy()
    wheel_radius = clamp(float(dims.z) * 0.24, 0.26, min(0.90, float(dims.x) * 0.16))
    chassis_height = max(0.35, float(dims.z) * 0.62)
    chassis_center_z = wheel_radius + chassis_height * 0.52
    chassis = cube(
        f"ISS_PHYSICS_{norm(profile.entity_id)}", (spawn[0], spawn[1], chassis_center_z),
        (max(0.55, dims.x * 0.91), max(0.45, dims.y * 0.84), chassis_height),
    )
    chassis.rotation_euler.z = yaw
    chassis.hide_render = True
    activate(chassis)
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    add_rigid_body(chassis, mass=profile.mass_kg, shape="BOX", friction=max(0.15, profile.friction * 0.22), restitution=profile.restitution)
    instance = bpy.data.objects.new(f"ISS_VISUAL_{norm(profile.entity_id)}", None)
    bpy.context.scene.collection.objects.link(instance)
    instance.instance_type = "COLLECTION"; instance.instance_collection = proto.collection; instance.parent = chassis
    visual_offset = Vector((0.0, 0.0, -chassis_center_z)); instance.location = visual_offset
    rig = create_drive_rig(profile.entity_id, chassis, dims, profile, yaw)
    return RuntimeActor(binding, profile, ActorState(profile.entity_id), proto, chassis, instance, visual_offset, rig, dims)


def obb_axes(actor: RuntimeActor) -> tuple[Vector, Vector]:
    q = actor.chassis.matrix_world.to_quaternion()
    x = q @ Vector((1.0, 0.0, 0.0)); y = q @ Vector((0.0, 1.0, 0.0))
    x.z = 0.0; y.z = 0.0
    if x.length < 1e-6 or y.length < 1e-6: raise BlenderBattleRuntimeError("OBB_AXIS_DEGENERATE")
    return x.normalized(), y.normalized()


def obb_overlap_2d(a: RuntimeActor, b: RuntimeActor) -> bool:
    pa = a.chassis.matrix_world.translation; pb = b.chassis.matrix_world.translation; delta = pb - pa
    ax, ay = obb_axes(a); bx, by = obb_axes(b)
    ha = (float(a.chassis.dimensions.x) * 0.5, float(a.chassis.dimensions.y) * 0.5)
    hb = (float(b.chassis.dimensions.x) * 0.5, float(b.chassis.dimensions.y) * 0.5)
    for axis in (ax, ay, bx, by):
        center_distance = abs(delta.dot(axis))
        ra = ha[0] * abs(ax.dot(axis)) + ha[1] * abs(ay.dot(axis))
        rb = hb[0] * abs(bx.dot(axis)) + hb[1] * abs(by.dot(axis))
        if center_distance > ra + rb + 0.06: return False
    return abs(pa.z - pb.z) <= (float(a.chassis.dimensions.z) + float(b.chassis.dimensions.z)) * 0.55 + 0.12


def signed_heading_error(forward: Vector, desired: Vector) -> float:
    f = Vector((forward.x, forward.y, 0.0)); d = Vector((desired.x, desired.y, 0.0))
    if f.length < 1e-5 or d.length < 1e-5: return 0.0
    f.normalize(); d.normalize()
    return math.atan2(f.x * d.y - f.y * d.x, clamp(f.dot(d), -1.0, 1.0))


def choose_initial_yaw(entity: str, spawn: dict[str, tuple[float, float, float]], program: BattleProgram) -> float:
    pos = Vector(spawn[entity])
    for event in program.events:
        if entity in event.attackers and event.target_id and event.target_id in spawn:
            d = Vector(spawn[event.target_id]) - pos
            if d.length > 0.1: return math.atan2(d.y, d.x)
    return 0.0


def event_dependency_ready(event: RuntimeEvent, states: dict[str, EventState]) -> bool:
    return all(states[d].status in {"SUCCEEDED", "SETTLED", "OBSERVED"} for d in event.dependencies)


def active_event_for_actor(entity: str, frame: int, program: BattleProgram, states: dict[str, EventState]) -> RuntimeEvent | None:
    candidates = []
    for event in program.events:
        if entity not in event.attackers: continue
        state = states[event.event_id]
        grace = program.fps if program.policies.get("replanOnPhysicalImpossibility", True) and event.requires_contact else 0
        if event.start_frame <= frame <= min(program.total_frames, event.end_frame + grace) and state.status not in {"SUCCEEDED", "SETTLED"} and event_dependency_ready(event, states):
            candidates.append(event)
    if not candidates: return None
    candidates.sort(key=lambda e: (0 if e.phase == "CLIMAX" else 1, e.end_frame, e.start_frame, e.event_id))
    return candidates[0]


def event_target_point(event: RuntimeEvent, attacker: RuntimeActor, target: RuntimeActor, attacker_index: int, attacker_count: int, frame: int, state: EventState) -> Vector:
    zone = target.zone_world(event.target_zone)
    dx, dy = TargetingPlanner.approach_offset(event.tactic, attacker_index, attacker_count, float(target.dimensions.x), float(target.dimensions.y))
    if state.attempts % 2: dy *= -1.0
    target_q = target.chassis.matrix_world.to_quaternion(); offset_world = target_q @ Vector((dx, dy, 0.0))
    attacker_pos = attacker.chassis.matrix_world.translation; distance = (zone - attacker_pos).length
    commit_distance = max(3.0, float(target.dimensions.x) * 1.05)
    if event.tactic in {"RAM", "COUNTER"} or distance <= commit_distance: return zone
    return zone + offset_world


def drive_command(actor: RuntimeActor, event: RuntimeEvent | None, target_point: Vector | None, current_velocity: Vector) -> tuple[float, float, dict[str, float]]:
    efficiency = clamp(actor.state.drive_efficiency, 0.0, 1.0)
    if actor.state.disabled or event is None or event.tactic in {"HOLD", "SETTLE"}:
        return 0.0, 0.0, {"headingError": 0.0, "targetSpeed": 0.0, "distance": 0.0}
    profile = actor.profile; q = actor.chassis.matrix_world.to_quaternion(); forward = q @ Vector((1.0, 0.0, 0.0))
    pos = actor.chassis.matrix_world.translation; desired = (target_point - pos) if target_point is not None else forward
    distance = desired.length; error = signed_heading_error(forward, desired)
    if event.tactic == "REVERSE" or event.speed_intent == "REVERSE":
        target_speed = -profile.max_reverse_mps * efficiency
    else:
        factor = {"FLANK": 0.74, "SURROUND": 0.62, "COUNTER": 0.78, "RAM": 0.88}.get(event.tactic, 0.66)
        if event.speed_intent == "SUSTAIN": factor *= 0.82
        target_speed = profile.max_speed_mps * factor * efficiency
    fwd_speed = current_velocity.dot(forward.normalized()) if forward.length > 1e-5 else 0.0
    if event.requires_contact and distance < max(0.8, float(actor.dimensions.x) * 0.22): target_speed *= 0.65
    if abs(error) > 1.20:
        pivot = min(max(1.0, abs(target_speed) * 0.34), profile.max_speed_mps * 0.36) * (1.0 if target_speed >= 0 else -1.0)
        left, right = -pivot, pivot
    else:
        turn = clamp(error / max(0.32, profile.max_yaw_rate_rad_s), -1.0, 1.0)
        left = target_speed * (1.0 - 0.86 * turn); right = target_speed * (1.0 + 0.86 * turn)
    max_abs = profile.max_speed_mps * max(0.15, efficiency)
    left = clamp(left, -profile.max_reverse_mps, max_abs); right = clamp(right, -profile.max_reverse_mps, max_abs)
    if event.speed_intent in {"BRAKE", "STOP", "SETTLE"}: left = right = 0.0
    return left, right, {"headingError": error, "targetSpeed": target_speed, "distance": distance, "forwardSpeed": fwd_speed}
