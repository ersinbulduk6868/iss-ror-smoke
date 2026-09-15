from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any

import bpy
from mathutils import Matrix, Vector

from blender.iss_battle_runtime_core import ImpactEvidence, clamp, norm, stable_unit
from blender.iss_battle_runtime_assets import (
    BlenderBattleRuntimeError,
    add_rigid_body,
    marker,
)
from blender.iss_battle_runtime_physics import RuntimeActor

CONSEQUENCE_MODEL = "ISS_IMPACT_CONSEQUENCE_V1"
DEBRIS_REPRESENTATION = "IMPACT_DERIVED_IRREGULAR_RIGID_SHARDS_V1"


@dataclass(slots=True)
class ConsequenceReceipt:
    actor_id: str
    frame: int
    zone: str
    severity: float
    affected_vertices: int
    max_deformation_m: float
    debris_count: int
    realization: str


def _copy_on_damage(actor: RuntimeActor) -> list[bpy.types.Object]:
    if actor.realized_meshes:
        return actor.realized_meshes

    root = bpy.data.objects.new(f"ISS_DAMAGED_VISUAL_{norm(actor.profile.entity_id)}", None)
    bpy.context.scene.collection.objects.link(root)
    root.parent = actor.chassis
    root.location = actor.visual_offset.copy()
    root.rotation_mode = "QUATERNION"
    root.rotation_quaternion = (1.0, 0.0, 0.0, 0.0)

    realized: list[bpy.types.Object] = []
    for src in actor.prototype.meshes:
        dst = src.copy()
        dst.data = src.data.copy()
        bpy.context.scene.collection.objects.link(dst)
        dst.parent = root
        dst.matrix_world = root.matrix_world @ src.matrix_world
        dst.name = f"ISS_DAMAGE_{norm(actor.profile.entity_id)}_{norm(src.name)}"
        realized.append(dst)

    if not realized:
        bpy.data.objects.remove(root, do_unlink=True)
        raise BlenderBattleRuntimeError(
            f"DAMAGE_REALIZATION_WITHOUT_SOURCE_MESH:{actor.profile.entity_id}"
        )

    actor.visual_instance.hide_render = True
    actor.visual_instance.hide_viewport = True
    actor.realized_root = root
    actor.realized_meshes = realized
    marker(
        "COPY_ON_DAMAGE_REALIZED",
        entityId=actor.profile.entity_id,
        meshCount=len(realized),
    )
    return realized


def _closest_material(
    meshes: list[bpy.types.Object], contact_point: Vector
) -> bpy.types.Material | None:
    best: tuple[float, bpy.types.Material] | None = None
    for obj in meshes:
        if not obj.material_slots:
            continue
        material = obj.material_slots[0].material
        if material is None:
            continue
        d = (obj.matrix_world.translation - contact_point).length
        if best is None or d < best[0]:
            best = (d, material)
    return best[1] if best else None


def _deform_source_geometry(
    actor: RuntimeActor,
    evidence: ImpactEvidence,
) -> tuple[int, float]:
    meshes = _copy_on_damage(actor)
    point_world = Vector(evidence.contact_point)
    normal_world = Vector(evidence.contact_normal)
    if normal_world.length < 1e-7:
        raise BlenderBattleRuntimeError("DAMAGE_CONTACT_NORMAL_DEGENERATE")
    normal_world.normalize()

    min_dim = max(
        0.20,
        min(
            float(actor.dimensions.x),
            float(actor.dimensions.y),
            float(actor.dimensions.z),
        ),
    )
    radius = clamp(
        min_dim * (0.16 + 0.34 * evidence.severity),
        0.12,
        min_dim * 0.62,
    )
    max_depth = clamp(
        min_dim * (0.035 + 0.19 * evidence.severity),
        0.015,
        min_dim * 0.30,
    )

    affected = 0
    max_move = 0.0
    for obj in meshes:
        inv = obj.matrix_world.inverted_safe()
        local_point = inv @ point_world
        local_normal = inv.to_3x3() @ normal_world
        if local_normal.length < 1e-7:
            continue
        local_normal.normalize()

        mesh = obj.data
        touched = False
        for vertex in mesh.vertices:
            delta = vertex.co - local_point
            distance = delta.length
            if distance > radius:
                continue
            falloff = (1.0 - distance / radius) ** 2
            if falloff <= 0.0:
                continue

            jitter = 0.86 + 0.28 * stable_unit(
                f"{actor.profile.entity_id}:{evidence.frame}:{obj.name}:{vertex.index}"
            )
            displacement = max_depth * falloff * jitter
            vertex.co += local_normal * displacement

            tangent = delta - local_normal * delta.dot(local_normal)
            if tangent.length > 1e-6:
                tangent.normalize()
                vertex.co -= tangent * displacement * 0.10 * evidence.severity

            affected += 1
            max_move = max(max_move, displacement)
            touched = True

        if touched:
            mesh.update()

    if affected <= 0:
        raise BlenderBattleRuntimeError(
            f"DAMAGE_NO_SOURCE_VERTICES_WITHIN_IMPACT_RADIUS:{actor.profile.entity_id}"
        )
    return affected, max_move


def _orthonormal_basis(normal: Vector) -> tuple[Vector, Vector]:
    n = normal.normalized()
    seed = Vector((0.0, 0.0, 1.0))
    if abs(n.dot(seed)) > 0.92:
        seed = Vector((0.0, 1.0, 0.0))
    t1 = n.cross(seed).normalized()
    t2 = n.cross(t1).normalized()
    return t1, t2


def _make_irregular_shard(
    name: str,
    location: Vector,
    scale: float,
    seed: float,
) -> bpy.types.Object:
    sx = scale * (0.70 + 0.55 * seed)
    sy = scale * (0.55 + 0.35 * ((seed * 1.77) % 1.0))
    sz = scale * (0.32 + 0.42 * ((seed * 2.31) % 1.0))
    verts = [
        (-sx, -sy, -sz * 0.35),
        ( sx, -sy * 0.72, -sz * 0.18),
        ( sx * 0.48, sy, -sz * 0.28),
        (-sx * 0.82, sy * 0.58, -sz * 0.12),
        ( sx * 0.05, sy * 0.05, sz),
    ]
    faces = [
        (0, 1, 2, 3),
        (0, 4, 1),
        (1, 4, 2),
        (2, 4, 3),
        (3, 4, 0),
    ]
    mesh = bpy.data.meshes.new(f"{name}_MESH")
    mesh.from_pydata(verts, [], faces)
    mesh.update()
    obj = bpy.data.objects.new(name, mesh)
    bpy.context.scene.collection.objects.link(obj)
    obj.location = location
    return obj


def _spawn_debris(
    actor: RuntimeActor,
    evidence: ImpactEvidence,
    meshes: list[bpy.types.Object],
) -> list[bpy.types.Object]:
    severity = clamp(evidence.severity, 0.0, 1.0)
    if severity < 0.09:
        return []

    point = Vector(evidence.contact_point)
    normal = Vector(evidence.contact_normal)
    if normal.length < 1e-7:
        return []
    normal.normalize()
    t1, t2 = _orthonormal_basis(normal)
    min_dim = max(
        0.20,
        min(
            float(actor.dimensions.x),
            float(actor.dimensions.y),
            float(actor.dimensions.z),
        ),
    )
    count = max(2, min(14, 2 + int(round(severity * 12.0))))
    material = _closest_material(meshes, point)
    shards: list[bpy.types.Object] = []

    for index in range(count):
        key = f"{actor.profile.entity_id}:{evidence.frame}:{index}"
        u = stable_unit(key + ":u")
        v = stable_unit(key + ":v")
        w = stable_unit(key + ":w")
        scale = min_dim * (0.025 + 0.055 * u) * (0.72 + 0.55 * severity)
        lateral = (u - 0.5) * min_dim * 0.18
        vertical = (v - 0.5) * min_dim * 0.12
        outward = min_dim * (0.015 + 0.040 * w)
        location = point - normal * outward + t1 * lateral + t2 * vertical

        shard = _make_irregular_shard(
            f"ISS_DEBRIS_{norm(actor.profile.entity_id)}_{evidence.frame:05d}_{index:02d}",
            location,
            scale,
            u,
        )
        if material is not None:
            shard.data.materials.append(material)

        volume_proxy = max(1e-6, scale ** 3)
        mass = clamp(volume_proxy * 520.0, 0.08, max(0.15, actor.profile.mass_kg * 0.0009))
        add_rigid_body(
            shard,
            mass=mass,
            shape="CONVEX_HULL",
            friction=0.72,
            restitution=clamp(0.04 + severity * 0.08, 0.03, 0.15),
        )
        shard["iss_debris_origin_event_frame"] = int(evidence.frame)
        shard["iss_debris_source_actor"] = actor.profile.entity_id
        shard["iss_debris_impact_severity"] = float(severity)
        shard["iss_debris_trajectory_injection"] = False
        shards.append(shard)

    return shards


class ConsequenceEngine:
    @staticmethod
    def apply(
        actor: RuntimeActor,
        evidence: ImpactEvidence,
    ) -> ConsequenceReceipt:
        if evidence.target_id != actor.profile.entity_id:
            raise BlenderBattleRuntimeError(
                f"CONSEQUENCE_TARGET_MISMATCH:{evidence.target_id}:{actor.profile.entity_id}"
            )
        if evidence.severity <= 0.0 or evidence.impact_energy_j <= 0.0:
            raise BlenderBattleRuntimeError("CONSEQUENCE_REQUIRES_POSITIVE_IMPACT")

        affected, max_move = _deform_source_geometry(actor, evidence)
        shards = _spawn_debris(actor, evidence, actor.realized_meshes)

        receipt = ConsequenceReceipt(
            actor_id=actor.profile.entity_id,
            frame=evidence.frame,
            zone=norm(evidence.target_zone) or "body",
            severity=float(evidence.severity),
            affected_vertices=affected,
            max_deformation_m=float(max_move),
            debris_count=len(shards),
            realization=CONSEQUENCE_MODEL,
        )
        actor.damage_visual_evidence.append(
            {
                "frame": receipt.frame,
                "zone": receipt.zone,
                "severity": receipt.severity,
                "affectedVertices": receipt.affected_vertices,
                "maxDeformationM": receipt.max_deformation_m,
                "debrisCount": receipt.debris_count,
                "model": CONSEQUENCE_MODEL,
                "debrisModel": DEBRIS_REPRESENTATION,
            }
        )
        marker(
            "IMPACT_CONSEQUENCE_APPLIED",
            entityId=receipt.actor_id,
            frame=receipt.frame,
            zone=receipt.zone,
            severity=round(receipt.severity, 6),
            affectedVertices=receipt.affected_vertices,
            maxDeformationM=round(receipt.max_deformation_m, 6),
            debrisCount=receipt.debris_count,
        )
        return receipt
