from __future__ import annotations

import bpy

from blender import iss_battle_runtime_consequences as base
from blender import iss_battle_runtime_consequences_v2 as v2
from blender.iss_battle_runtime_assets import BlenderBattleRuntimeError, add_rigid_body, marker
from blender.iss_battle_runtime_contract import clamp, norm, stable_unit
from blender.iss_battle_runtime_physics import RuntimeActor

CONSEQUENCE_MODEL_V3 = "ISS_CAUSAL_VISIBLE_IMPACT_CONSEQUENCE_V3"
DEBRIS_MODEL_V3 = "DEFORMATION_EARNED_IRREGULAR_RIGID_SHARDS_V3"
VISUAL_RESPONSE_MODEL_V3 = "PHYSICALLY_EARNED_VIEWER_VISIBLE_RESPONSE_V2"
CONTACT_LOCALIZATION_MODEL = v2.CONTACT_LOCALIZATION_MODEL


def _spawn_physically_earned_debris(
    actor: RuntimeActor,
    evidence,
    meshes: list[bpy.types.Object],
    anchor: v2.RecipientContactAnchor,
    *,
    normalized_deformation: float,
) -> list[bpy.types.Object]:
    """Realize fragments only after the unchanged physical damage gate admitted impact.

    The fracture response is driven by realized deformation or impact severity,
    never by asset identity or a scripted debris count. No trajectory is injected;
    shards are born as native rigid bodies at recipient-local contact geometry.
    """
    severity = clamp(float(evidence.severity), 0.0, 1.0)
    severity_index = clamp((severity - 0.07) / 0.45, 0.0, 1.0)
    deformation_index = clamp((float(normalized_deformation) - 0.025) / 0.20, 0.0, 1.0)
    fracture_index = max(severity_index, deformation_index)
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
        key = f"{actor.profile.entity_id}:{evidence.frame}:{index}:v3"
        u = stable_unit(key + ":u")
        vv = stable_unit(key + ":v")
        w = stable_unit(key + ":w")
        scale = min_dim * (0.030 + 0.060 * u) * (0.76 + 0.60 * fracture_index)
        lateral = (u - 0.5) * min_dim * (0.14 + 0.18 * fracture_index)
        vertical = (vv - 0.5) * min_dim * (0.09 + 0.12 * fracture_index)
        outward = min_dim * (0.016 + 0.050 * w)
        location = point - normal * outward + t1 * lateral + t2 * vertical
        shard = base._make_irregular_shard(
            f"ISS_DEBRIS_V3_{norm(actor.profile.entity_id)}_{int(evidence.frame):05d}_{index:02d}",
            location,
            scale,
            u,
        )
        if material is not None:
            shard.data.materials.append(material)
        volume_proxy = max(1.0e-6, scale**3)
        mass = clamp(
            volume_proxy * 650.0,
            0.08,
            max(0.18, float(actor.profile.mass_kg) * 0.0010),
        )
        add_rigid_body(
            shard,
            mass=mass,
            shape="CONVEX_HULL",
            friction=0.72,
            restitution=clamp(0.03 + severity * 0.09, 0.03, 0.15),
        )
        base._key_debris_birth(shard, int(evidence.frame))
        shard["iss_debris_origin_event_frame"] = int(evidence.frame)
        shard["iss_debris_source_actor"] = actor.profile.entity_id
        shard["iss_debris_impact_severity"] = float(severity)
        shard["iss_debris_normalized_deformation"] = float(normalized_deformation)
        shard["iss_debris_fracture_index"] = float(fracture_index)
        shard["iss_debris_trajectory_injection"] = False
        shard["iss_debris_model"] = DEBRIS_MODEL_V3
        shard["iss_debris_contact_localization_model"] = CONTACT_LOCALIZATION_MODEL
        shards.append(shard)
    return shards


class VisibleCausalConsequenceEngineV3:
    @staticmethod
    def apply(actor: RuntimeActor, evidence) -> v2.ConsequenceReceiptV2:
        if evidence.target_id != actor.profile.entity_id:
            raise BlenderBattleRuntimeError(
                f"CONSEQUENCE_TARGET_MISMATCH:{evidence.target_id}:{actor.profile.entity_id}"
            )
        if evidence.severity <= 0.0 or evidence.impact_energy_j <= 0.0:
            raise BlenderBattleRuntimeError("CONSEQUENCE_REQUIRES_POSITIVE_IMPACT")

        meshes = base._copy_on_damage(actor)
        anchor = v2._recipient_contact_anchor(actor, evidence, meshes)
        affected, total, max_move = v2._deform_adaptive(actor, evidence, anchor, meshes)
        characteristic = max(
            0.20,
            min(float(actor.dimensions.x), float(actor.dimensions.y), float(actor.dimensions.z)),
        )
        normalized_deformation = float(max_move) / characteristic
        shards = _spawn_physically_earned_debris(
            actor,
            evidence,
            meshes,
            anchor,
            normalized_deformation=normalized_deformation,
        )

        receipt = v2.ConsequenceReceiptV2(
            actor_id=actor.profile.entity_id,
            frame=int(evidence.frame),
            zone=norm(evidence.target_zone) or "body",
            severity=float(evidence.severity),
            affected_vertices=int(affected),
            affected_vertex_fraction=float(affected) / max(1, int(total)),
            max_deformation_m=float(max_move),
            normalized_deformation=normalized_deformation,
            debris_count=len(shards),
            realization=CONSEQUENCE_MODEL_V3,
            visual_response_model=VISUAL_RESPONSE_MODEL_V3,
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
                "model": CONSEQUENCE_MODEL_V3,
                "visualResponseModel": VISUAL_RESPONSE_MODEL_V3,
                "debrisModel": DEBRIS_MODEL_V3,
                "debrisEligibility": "UNCHANGED_DAMAGE_GATE_PLUS_REALIZED_DEFORMATION_OR_SEVERITY",
                "contactLocalizationModel": CONTACT_LOCALIZATION_MODEL,
                "originalVerifiedContactPoint": [float(x) for x in anchor.original_contact_point],
                "visualRecipientAnchorPoint": [float(x) for x in anchor.visual_anchor_point],
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
            "CAUSAL_VISIBLE_IMPACT_CONSEQUENCE_V3_APPLIED",
            entityId=receipt.actor_id,
            frame=receipt.frame,
            severity=round(receipt.severity, 6),
            affectedVertices=receipt.affected_vertices,
            maxDeformationM=round(receipt.max_deformation_m, 6),
            normalizedDeformation=round(receipt.normalized_deformation, 6),
            debrisCount=receipt.debris_count,
            contactLocalizationModel=CONTACT_LOCALIZATION_MODEL,
            g05ContactTruthRewritten=False,
            physicalDamageGateChanged=False,
            contactGateChanged=False,
            model=CONSEQUENCE_MODEL_V3,
        )
        return receipt
