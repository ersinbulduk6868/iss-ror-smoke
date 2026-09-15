from __future__ import annotations

import json
import math
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

import bpy
from mathutils import Matrix, Vector, geometry

from blender import iss_battle_runtime_consequences as consequences
from blender import iss_blender_battle_runtime_v1 as runtime
from blender import iss_blender_battle_runtime_v1_hardened as hardened
from blender import run_generic_battle_runtime_v1_candidate35 as candidate35
from blender import run_generic_battle_runtime_v1_candidate36 as candidate36
from blender.iss_battle_runtime_core import ImpactEvidence, clamp, norm, stable_unit
from blender.iss_battle_runtime_assets import BlenderBattleRuntimeError, marker

CANDIDATE = "ISS_GENERIC_BATTLE_RUNTIME_V1_CANDIDATE_3_7"
DAMAGE_BINDING_MODEL = "ACTOR_LOCAL_SURFACE_AWARE_CAUSAL_DAMAGE_V1"
CONSEQUENCE_MODEL = "ISS_IMPACT_CONSEQUENCE_V1_1_SURFACE_AWARE"
_original_spawn_debris = consequences._spawn_debris


def _matrix_delta(a: Matrix, b: Matrix) -> float:
    return max(abs(float(a[r][c]) - float(b[r][c])) for r in range(4) for c in range(4))


def fidelity_copy_on_damage(actor):
    if actor.realized_meshes:
        return actor.realized_meshes

    root = bpy.data.objects.new(f"ISS_DAMAGED_VISUAL_{norm(actor.profile.entity_id)}", None)
    bpy.context.scene.collection.objects.link(root)
    root.parent = actor.chassis
    root.matrix_parent_inverse = Matrix.Identity(4)
    root.location = actor.visual_offset.copy()
    root.rotation_mode = "QUATERNION"
    root.rotation_quaternion = (1.0, 0.0, 0.0, 0.0)
    root.scale = (1.0, 1.0, 1.0)
    bpy.context.view_layer.update()

    root_delta = _matrix_delta(root.matrix_world, actor.visual_instance.matrix_world)
    if root_delta > 1.0e-5:
        bpy.data.objects.remove(root, do_unlink=True)
        raise BlenderBattleRuntimeError(
            f"DAMAGE_REALIZATION_ROOT_TRANSFORM_MISMATCH:{actor.profile.entity_id}:{root_delta}"
        )

    realized = []
    expected_world = {}
    for src in actor.prototype.meshes:
        dst = src.copy()
        dst.data = src.data.copy()
        bpy.context.scene.collection.objects.link(dst)
        dst.parent = root
        dst.matrix_parent_inverse = Matrix.Identity(4)
        expected = actor.visual_instance.matrix_world @ src.matrix_world
        dst.matrix_world = expected
        dst.name = f"ISS_DAMAGE_{norm(actor.profile.entity_id)}_{norm(src.name)}"
        expected_world[dst.name] = expected.copy()
        realized.append(dst)

    if not realized:
        bpy.data.objects.remove(root, do_unlink=True)
        raise BlenderBattleRuntimeError(
            f"DAMAGE_REALIZATION_WITHOUT_SOURCE_MESH:{actor.profile.entity_id}"
        )

    bpy.context.view_layer.update()
    max_delta = max(_matrix_delta(obj.matrix_world, expected_world[obj.name]) for obj in realized)
    if max_delta > 1.0e-5:
        for obj in realized:
            bpy.data.objects.remove(obj, do_unlink=True)
        bpy.data.objects.remove(root, do_unlink=True)
        raise BlenderBattleRuntimeError(
            f"DAMAGE_REALIZATION_CHILD_TRANSFORM_MISMATCH:{actor.profile.entity_id}:{max_delta}"
        )

    actor.visual_instance.hide_render = True
    actor.visual_instance.hide_viewport = True
    actor.realized_root = root
    actor.realized_meshes = realized
    marker(
        "DAMAGE_REALIZATION_TRANSFORM_PASS",
        entityId=actor.profile.entity_id,
        meshCount=len(realized),
        rootMatrixDelta=round(float(root_delta), 9),
        childMatrixDelta=round(float(max_delta), 9),
    )
    return realized


def _current_contact_binding(actor, evidence: ImpactEvidence):
    historical = candidate36._historical_chassis_matrix(actor, int(evidence.frame))
    current = actor.chassis.matrix_world.copy()
    historical_point = Vector(evidence.contact_point)
    historical_normal = Vector(evidence.contact_normal)
    if historical_normal.length < 1.0e-7:
        raise BlenderBattleRuntimeError("DAMAGE_CONTACT_NORMAL_DEGENERATE")
    historical_normal.normalize()

    actor_local_point = historical.inverted_safe() @ historical_point
    actor_local_normal = historical.to_quaternion().inverted() @ historical_normal
    current_point = current @ actor_local_point
    current_normal = current.to_quaternion() @ actor_local_normal
    if current_normal.length < 1.0e-7:
        raise BlenderBattleRuntimeError("DAMAGE_CURRENT_CONTACT_NORMAL_DEGENERATE")
    current_normal.normalize()
    return actor_local_point, current_point, current_normal


def _surface_influences(obj, point_world: Vector, radius: float):
    mesh = obj.data
    matrix = obj.matrix_world
    world_vertices = [matrix @ vertex.co for vertex in mesh.vertices]
    influences = {}
    nearest_vertex = float("inf")
    for vertex in mesh.vertices:
        distance = (world_vertices[vertex.index] - point_world).length
        nearest_vertex = min(nearest_vertex, float(distance))
        if distance <= radius:
            influences[vertex.index] = max(
                influences.get(vertex.index, 0.0),
                (1.0 - float(distance) / radius) ** 2,
            )

    mesh.calc_loop_triangles()
    nearest_surface = float("inf")
    for tri in mesh.loop_triangles:
        indices = [int(i) for i in tri.vertices]
        a, b, c = (world_vertices[i] for i in indices)
        closest = geometry.closest_point_on_tri(point_world, a, b, c)
        surface_distance = float((closest - point_world).length)
        nearest_surface = min(nearest_surface, surface_distance)
        if surface_distance > radius:
            continue
        surface_weight = (1.0 - surface_distance / radius) ** 2
        for index in indices:
            support_distance = float((world_vertices[index] - closest).length)
            support_weight = surface_weight / (1.0 + support_distance / max(radius, 0.05))
            influences[index] = max(influences.get(index, 0.0), support_weight)

    return influences, nearest_vertex, nearest_surface


def surface_aware_deform_source_geometry(actor, evidence: ImpactEvidence):
    meshes = fidelity_copy_on_damage(actor)
    _, point_world, normal_world = _current_contact_binding(actor, evidence)
    realization_frame = int(bpy.context.scene.frame_current)

    min_dim = max(
        0.20,
        min(float(actor.dimensions.x), float(actor.dimensions.y), float(actor.dimensions.z)),
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
    nearest_vertex_global = float("inf")
    nearest_surface_global = float("inf")
    surface_fallback_used = False

    for obj in meshes:
        influences, nearest_vertex, nearest_surface = _surface_influences(obj, point_world, radius)
        nearest_vertex_global = min(nearest_vertex_global, nearest_vertex)
        nearest_surface_global = min(nearest_surface_global, nearest_surface)
        if nearest_surface <= radius and nearest_vertex > radius:
            surface_fallback_used = True
        if not influences:
            continue
        if nearest_surface > radius:
            continue

        inv = obj.matrix_world.inverted_safe()
        local_world_normal = inv.to_3x3() @ normal_world
        if local_world_normal.length < 1.0e-9:
            continue

        consequences._ensure_basis(obj)
        key = obj.shape_key_add(
            name=f"ISS_DAMAGE_F{int(evidence.frame):05d}_R{realization_frame:05d}",
            from_mix=False,
        )
        for index, weight in influences.items():
            if weight <= 0.0:
                continue
            jitter = 0.86 + 0.28 * stable_unit(
                f"{actor.profile.entity_id}:{evidence.frame}:{obj.name}:{index}"
            )
            world_move = max_depth * float(weight) * jitter
            local_displacement = local_world_normal * world_move
            key.data[index].co = key.data[index].co + local_displacement
            affected += 1
            max_move = max(max_move, world_move)

        before = max(1, realization_frame - 1)
        key.value = 0.0
        key.keyframe_insert(data_path="value", frame=before)
        key.value = 1.0
        key.keyframe_insert(data_path="value", frame=realization_frame)
        if obj.data.shape_keys and obj.data.shape_keys.animation_data:
            action = obj.data.shape_keys.animation_data.action
            if action:
                for curve in action.fcurves:
                    for point in curve.keyframe_points:
                        point.interpolation = "LINEAR"

    if not math.isfinite(nearest_surface_global) or nearest_surface_global > radius:
        raise BlenderBattleRuntimeError(
            f"DAMAGE_CONTACT_SURFACE_OUTSIDE_RADIUS:{actor.profile.entity_id}:"
            f"surface={nearest_surface_global}:radius={radius}"
        )
    if affected <= 0:
        raise BlenderBattleRuntimeError(
            f"DAMAGE_SURFACE_REGION_WITHOUT_DEFORMABLE_VERTICES:{actor.profile.entity_id}"
        )

    marker(
        "DAMAGE_SURFACE_LOCALIZATION_PASS",
        entityId=actor.profile.entity_id,
        contactFrame=int(evidence.frame),
        realizationFrame=realization_frame,
        radiusM=round(float(radius), 6),
        nearestVertexDistanceM=round(float(nearest_vertex_global), 6),
        nearestSurfaceDistanceM=round(float(nearest_surface_global), 6),
        surfaceFallbackUsed=bool(surface_fallback_used),
        affectedVertices=int(affected),
        maxDeformationM=round(float(max_move), 6),
    )
    marker(
        "DAMAGE_VISUAL_TEMPORAL_BINDING_PASS",
        entityId=actor.profile.entity_id,
        contactFrame=int(evidence.frame),
        realizationFrame=realization_frame,
        actorPoseOrVelocityMutation=False,
    )
    return affected, max_move


def _remapped_visual_evidence(actor, evidence: ImpactEvidence) -> ImpactEvidence:
    _, current_point, current_normal = _current_contact_binding(actor, evidence)
    realization_frame = int(bpy.context.scene.frame_current)
    return ImpactEvidence(
        frame=realization_frame,
        attacker_id=evidence.attacker_id,
        target_id=evidence.target_id,
        target_zone=evidence.target_zone,
        relative_speed_mps=evidence.relative_speed_mps,
        normal_closing_speed_mps=evidence.normal_closing_speed_mps,
        reduced_mass_kg=evidence.reduced_mass_kg,
        impact_energy_j=evidence.impact_energy_j,
        target_specific_energy_j_per_kg=evidence.target_specific_energy_j_per_kg,
        severity=evidence.severity,
        contact_point=tuple(float(x) for x in current_point),
        contact_normal=tuple(float(x) for x in current_normal),
        response_delta_attacker_mps=evidence.response_delta_attacker_mps,
        response_delta_target_mps=evidence.response_delta_target_mps,
        detector=evidence.detector,
    )


def causal_spawn_debris(actor, evidence: ImpactEvidence, meshes):
    mapped = _remapped_visual_evidence(actor, evidence)
    shards = _original_spawn_debris(actor, mapped, meshes)
    marker(
        "DEBRIS_CAUSAL_REALIZATION_PASS",
        entityId=actor.profile.entity_id,
        contactFrame=int(evidence.frame),
        realizationFrame=int(mapped.frame),
        debrisCount=len(shards),
        actorPoseOrVelocityMutation=False,
    )
    return shards


def main() -> None:
    # Preserve Candidate 3.4 semantic correctness and Candidate 3.5 physical drive authority.
    candidate35.assets.centroid_for_terms = candidate35.candidate34.ambiguity_safe_centroid_for_terms
    candidate35.physics.DriveRig.command = candidate35.candidate34.calibrated_command
    candidate35.physics.create_drive_rig = candidate35.calibrated_create_drive_rig

    # Preserve Candidate 3.6 Newton-pair contact-point coherence, but replace the incomplete
    # deformation patch with full transform-fidelity + surface-aware causal realization.
    hardened._mirrored_impact = candidate36.mirrored_impact_at_same_contact
    consequences._copy_on_damage = fidelity_copy_on_damage
    consequences._deform_source_geometry = surface_aware_deform_source_geometry
    consequences._spawn_debris = causal_spawn_debris
    consequences.CONSEQUENCE_MODEL = CONSEQUENCE_MODEL
    runtime.CONSEQUENCE_MODEL = CONSEQUENCE_MODEL
    hardened.RUNTIME_VERSION = CANDIDATE

    print(json.dumps({
        "marker": "GENERIC_BATTLE_RUNTIME_CANDIDATE37_ENGINE_HARDENING_PASS",
        "candidate": CANDIDATE,
        "damageBindingModel": DAMAGE_BINDING_MODEL,
        "consequenceModel": CONSEQUENCE_MODEL,
        "driveAuthorityModel": candidate35.DRIVE_AUTHORITY_MODEL,
        "semanticLocator": candidate35.candidate34.SEMANTIC_LOCATOR,
        "damageThresholdChanged": False,
        "contactThresholdChanged": False,
        "scenarioTrajectoryHardcode": False,
        "actorPoseOrVelocityMutation": False,
        "historicalBackdatingOfDebris": False,
    }, sort_keys=True), flush=True)
    hardened.main()


if __name__ == "__main__":
    main()
