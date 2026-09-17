from __future__ import annotations

from dataclasses import dataclass

import bpy
from mathutils import Vector

from blender.iss_battle_runtime_assets import BlenderBattleRuntimeError, add_rigid_body, marker
from blender.iss_battle_runtime_contract import clamp, norm, stable_unit
from blender.iss_battle_runtime_physics import RuntimeActor
from blender import iss_battle_runtime_consequences as base

CONSEQUENCE_MODEL_V2 = "ISS_CAUSAL_VISIBLE_IMPACT_CONSEQUENCE_V2"
DEBRIS_MODEL_V2 = "ENERGY_SCALED_IRREGULAR_RIGID_SHARDS_V2"
VISUAL_RESPONSE_MODEL = "PHYSICALLY_EARNED_VIEWER_VISIBLE_RESPONSE_V1"
CONTACT_LOCALIZATION_MODEL = "VERIFIED_PAIR_NEAREST_RECIPIENT_MESH_VERTEX_V1"


@dataclass(slots=True)
class ConsequenceReceiptV2:
    actor_id: str
    frame: int
    zone: str
    severity: float
    affected_vertices: int
    affected_vertex_fraction: float
    max_deformation_m: float
    normalized_deformation: float
    debris_count: int
    realization: str
    visual_response_model: str
    contact_localization_model: str
    localization_distance_m: float


@dataclass(slots=True)
class RecipientContactAnchor:
    original_contact_point: Vector
    visual_anchor_point: Vector
    visual_normal: Vector
    localization_distance_m: float
    visual_normal_flipped: bool
    source_object: str
    source_vertex_index: int


def _recipient_contact_anchor(
    actor: RuntimeActor,
    evidence,
    meshes: list[bpy.types.Object],
) -> RecipientContactAnchor:
    """Localize a verified pair contact to the current damage recipient geometry.

    G05 owns contact truth and its contact point is never replaced or rewritten.
    A reciprocal/mirrored damage record can legitimately inherit the same verified
    pair receipt even though that receipt's point lies on the opposite member's
    surface. Visual consequences therefore need a recipient-local presentation
    anchor. We derive it only from the verified point plus realized recipient mesh
    geometry; no asset identity, scripted collision coordinate, or trajectory is
    accepted as input.
    """

    original = Vector(evidence.contact_point)
    normal = Vector(evidence.contact_normal)
    if normal.length < 1.0e-7:
        raise BlenderBattleRuntimeError("DAMAGE_CONTACT_NORMAL_DEGENERATE")
    normal.normalize()

    best_distance: float | None = None
    best_point: Vector | None = None
    best_object = ""
    best_vertex_index = -1
    for obj in meshes:
        world = obj.matrix_world
        for vertex in obj.data.vertices:
            point = world @ vertex.co
            distance = float((point - original).length)
            if best_distance is None or distance < best_distance:
                best_distance = distance
                best_point = point.copy()
                best_object = str(obj.name)
                best_vertex_index = int(vertex.index)

    if best_point is None or best_distance is None:
        raise BlenderBattleRuntimeError(
            f"DAMAGE_RECIPIENT_SURFACE_UNRESOLVED:{actor.profile.entity_id}"
        )

    max_dim = max(
        0.25,
        float(actor.dimensions.x),
        float(actor.dimensions.y),
        float(actor.dimensions.z),
    )
    # Fail closed if a supposedly reciprocal physical pair receipt is nowhere
    # near the recipient. This protects G05 authority instead of papering over
    # an unrelated/distant point with an arbitrarily huge deformation radius.
    max_localization_distance = max(0.50, max_dim * 1.35)
    if best_distance > max_localization_distance:
        raise BlenderBattleRuntimeError(
            f"DAMAGE_RECIPIENT_LOCALIZATION_TOO_DISTANT:{actor.profile.entity_id}:"
            f"{best_distance:.6f}:{max_localization_distance:.6f}"
        )

    center = actor.chassis.matrix_world.translation.copy()
    toward_center = center - best_point
    visual_normal_flipped = False
    if toward_center.length > 1.0e-7 and float(toward_center.dot(normal)) < 0.0:
        normal = -normal
        visual_normal_flipped = True

    return RecipientContactAnchor(
        original_contact_point=original,
        visual_anchor_point=best_point,
        visual_normal=normal,
        localization_distance_m=float(best_distance),
        visual_normal_flipped=visual_normal_flipped,
        source_object=best_object,
        source_vertex_index=best_vertex_index,
    )


def _deform_adaptive(
    actor: RuntimeActor,
    evidence,
    anchor: RecipientContactAnchor,
    meshes: list[bpy.types.Object],
) -> tuple[int, int, float]:
    point_world = anchor.visual_anchor_point
    normal_world = anchor.visual_normal
    min_dim = max(
        0.20,
        min(float(actor.dimensions.x), float(actor.dimensions.y), float(actor.dimensions.z)),
    )
    severity = clamp(float(evidence.severity), 0.0, 1.0)
    total_vertices = sum(len(obj.data.vertices) for obj in meshes)
    if total_vertices <= 0:
        raise BlenderBattleRuntimeError(
            f"DAMAGE_SOURCE_VERTICES_EMPTY:{actor.profile.entity_id}"
        )

    target_vertices = max(
        8,
        min(240, int(round(total_vertices * (0.0035 + 0.008 * severity)))),
    )
    radius = clamp(
        min_dim * (0.14 + 0.28 * severity),
        0.10,
        min_dim * 0.42,
    )
    radius_cap = max(radius, min_dim * 0.72)

    def count_vertices(test_radius: float) -> int:
        count = 0
        for obj in meshes:
            inv = obj.matrix_world.inverted_safe()
            local_point = inv @ point_world
            count += sum(
                1
                for vertex in obj.data.vertices
                if (vertex.co - local_point).length <= test_radius
            )
        return count

    support = count_vertices(radius)
    while support < target_vertices and radius < radius_cap:
        radius = min(radius_cap, radius * 1.22)
        support = count_vertices(radius)

    max_depth = clamp(
        min_dim * (0.026 + 0.17 * severity),
        min_dim * 0.025,
        min_dim * 0.24,
    )

    affected = 0
    max_move = 0.0
    for obj in meshes:
        inv = obj.matrix_world.inverted_safe()
        local_point = inv @ point_world
        local_normal = inv.to_3x3() @ normal_world
        if local_normal.length < 1.0e-7:
            continue
        local_normal.normalize()
        base._ensure_basis(obj)
        key = obj.shape_key_add(
            name=f"ISS_DAMAGE_V2_F{int(evidence.frame):05d}",
            from_mix=False,
        )
        touched = False
        for vertex in obj.data.vertices:
            delta = vertex.co - local_point
            distance = delta.length
            if distance > radius:
                continue
            falloff = (1.0 - distance / radius) ** 1.65
            if falloff <= 0.0:
                continue
            jitter = 0.88 + 0.24 * stable_unit(
                f"{actor.profile.entity_id}:{evidence.frame}:{obj.name}:{vertex.index}:v2"
            )
            displacement = max_depth * falloff * jitter
            displaced = key.data[vertex.index].co + local_normal * displacement
            tangent = delta - local_normal * delta.dot(local_normal)
            if tangent.length > 1.0e-6:
                tangent.normalize()
                displaced -= tangent * displacement * (0.08 + 0.08 * severity)
            key.data[vertex.index].co = displaced
            affected += 1
            max_move = max(max_move, displacement)
            touched = True
        if touched:
            before = max(1, int(evidence.frame) - 1)
            key.value = 0.0
            key.keyframe_insert(data_path="value", frame=before)
            key.value = 1.0
            key.keyframe_insert(data_path="value", frame=int(evidence.frame))
            if (
                obj.data.shape_keys
                and obj.data.shape_keys.animation_data
                and obj.data.shape_keys.animation_data.action
            ):
                for curve in obj.data.shape_keys.animation_data.action.fcurves:
                    for point in curve.keyframe_points:
                        point.interpolation = "LINEAR"
        else:
            obj.shape_key_remove(key)

    if affected <= 0:
        raise BlenderBattleRuntimeError(
            f"DAMAGE_NO_SOURCE_VERTICES_WITHIN_ADAPTIVE_RADIUS:{actor.profile.entity_id}"
        )
    return affected, total_vertices, max_move


def _spawn_energy_scaled_debris(
    actor: RuntimeActor,
    evidence,
    meshes: list[bpy.types.Object],
    anchor: RecipientContactAnchor,
) -> list[bpy.types.Object]:
    severity = clamp(float(evidence.severity), 0.0, 1.0)
    fracture_index = clamp((severity - 0.07) / 0.45, 0.0, 1.0)
    if fracture_index <= 0.0:
        return []
    point = anchor.visual_anchor_point
    normal = anchor.visual_normal.copy()
    if normal.length < 1.0e-7:
        return []
    normal.normalize()
    t1, t2 = base._orthonormal_basis(normal)
    min_dim = max(
        0.20,
        min(float(actor.dimensions.x), float(actor.dimensions.y), float(actor.dimensions.z)),
    )
    count = max(2, min(16, 2 + int(round(fracture_index * 14.0))))
    material = base._closest_material(meshes, point)
    shards: list[bpy.types.Object] = []
    for index in range(count):
        key = f"{actor.profile.entity_id}:{evidence.frame}:{index}:v2"
        u = stable_unit(key + ":u")
        v = stable_unit(key + ":v")
        w = stable_unit(key + ":w")
        scale = min_dim * (0.035 + 0.070 * u) * (0.78 + 0.65 * fracture_index)
        lateral = (u - 0.5) * min_dim * (0.16 + 0.20 * fracture_index)
        vertical = (v - 0.5) * min_dim * (0.10 + 0.14 * fracture_index)
        outward = min_dim * (0.018 + 0.055 * w)
        location = point - normal * outward + t1 * lateral + t2 * vertical
        shard = base._make_irregular_shard(
            f"ISS_DEBRIS_V2_{norm(actor.profile.entity_id)}_{int(evidence.frame):05d}_{index:02d}",
            location,
            scale,
            u,
        )
        if material is not None:
            shard.data.materials.append(material)
        volume_proxy = max(1.0e-6, scale**3)
        mass = clamp(
            volume_proxy * 650.0,
            0.10,
            max(0.20, float(actor.profile.mass_kg) * 0.0012),
        )
        add_rigid_body(
            shard,
            mass=mass,
            shape="CONVEX_HULL",
            friction=0.72,
            restitution=clamp(0.035 + severity * 0.09, 0.03, 0.16),
        )
        base._key_debris_birth(shard, int(evidence.frame))
        shard["iss_debris_origin_event_frame"] = int(evidence.frame)
        shard["iss_debris_source_actor"] = actor.profile.entity_id
        shard["iss_debris_impact_severity"] = float(severity)
        shard["iss_debris_fracture_index"] = float(fracture_index)
        shard["iss_debris_trajectory_injection"] = False
        shard["iss_debris_model"] = DEBRIS_MODEL_V2
        shard["iss_debris_contact_localization_model"] = CONTACT_LOCALIZATION_MODEL
        shards.append(shard)
    return shards


class VisibleCausalConsequenceEngineV2:
    @staticmethod
    def apply(actor: RuntimeActor, evidence) -> ConsequenceReceiptV2:
        if evidence.target_id != actor.profile.entity_id:
            raise BlenderBattleRuntimeError(
                f"CONSEQUENCE_TARGET_MISMATCH:{evidence.target_id}:{actor.profile.entity_id}"
            )
        if evidence.severity <= 0.0 or evidence.impact_energy_j <= 0.0:
            raise BlenderBattleRuntimeError("CONSEQUENCE_REQUIRES_POSITIVE_IMPACT")

        meshes = base._copy_on_damage(actor)
        anchor = _recipient_contact_anchor(actor, evidence, meshes)
        affected, total, max_move = _deform_adaptive(
            actor,
            evidence,
            anchor,
            meshes,
        )
        shards = _spawn_energy_scaled_debris(actor, evidence, meshes, anchor)
        characteristic = max(
            0.20,
            min(float(actor.dimensions.x), float(actor.dimensions.y), float(actor.dimensions.z)),
        )
        receipt = ConsequenceReceiptV2(
            actor_id=actor.profile.entity_id,
            frame=int(evidence.frame),
            zone=norm(evidence.target_zone) or "body",
            severity=float(evidence.severity),
            affected_vertices=int(affected),
            affected_vertex_fraction=float(affected) / max(1, int(total)),
            max_deformation_m=float(max_move),
            normalized_deformation=float(max_move) / characteristic,
            debris_count=len(shards),
            realization=CONSEQUENCE_MODEL_V2,
            visual_response_model=VISUAL_RESPONSE_MODEL,
            contact_localization_model=CONTACT_LOCALIZATION_MODEL,
            localization_distance_m=float(anchor.localization_distance_m),
        )
        actor.damage_visual_evidence.append(
            {
                "frame": receipt.frame,
                "zone": receipt.zone,
                "severity": receipt.severity,
                "affectedVertices": receipt.affected_vertices,
                "affectedVertexFraction": receipt.affected_vertex_fraction,
                "maxDeformationM": receipt.max_deformation_m,
                "normalizedDeformation": receipt.normalized_deformation,
                "debrisCount": receipt.debris_count,
                "model": CONSEQUENCE_MODEL_V2,
                "visualResponseModel": VISUAL_RESPONSE_MODEL,
                "debrisModel": DEBRIS_MODEL_V2,
                "contactLocalizationModel": CONTACT_LOCALIZATION_MODEL,
                "originalVerifiedContactPoint": [
                    float(x) for x in anchor.original_contact_point
                ],
                "visualRecipientAnchorPoint": [
                    float(x) for x in anchor.visual_anchor_point
                ],
                "localizationDistanceM": receipt.localization_distance_m,
                "visualNormalFlippedForRecipient": bool(anchor.visual_normal_flipped),
                "localizationSourceObject": anchor.source_object,
                "localizationSourceVertexIndex": int(anchor.source_vertex_index),
                "g05ContactTruthRewritten": False,
                "physicalDamageGateChanged": False,
                "contactGateChanged": False,
            }
        )
        marker(
            "CAUSAL_VISIBLE_IMPACT_CONSEQUENCE_APPLIED",
            entityId=receipt.actor_id,
            frame=receipt.frame,
            zone=receipt.zone,
            severity=round(receipt.severity, 6),
            affectedVertices=receipt.affected_vertices,
            affectedVertexFraction=round(receipt.affected_vertex_fraction, 6),
            maxDeformationM=round(receipt.max_deformation_m, 6),
            normalizedDeformation=round(receipt.normalized_deformation, 6),
            debrisCount=receipt.debris_count,
            localizationDistanceM=round(receipt.localization_distance_m, 6),
            visualNormalFlippedForRecipient=bool(anchor.visual_normal_flipped),
            contactLocalizationModel=CONTACT_LOCALIZATION_MODEL,
            g05ContactTruthRewritten=False,
            model=CONSEQUENCE_MODEL_V2,
        )
        return receipt
