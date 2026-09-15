from __future__ import annotations

import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from mathutils import Matrix, Vector

from blender import iss_battle_runtime_consequences as consequences
from blender import iss_blender_battle_runtime_v1_hardened as hardened
from blender import run_generic_battle_runtime_v1_candidate35 as candidate35
from blender.iss_battle_runtime_core import ImpactEvidence, ImpactModel

CANDIDATE = "ISS_GENERIC_BATTLE_RUNTIME_V1_CANDIDATE_3_6"
CONTACT_SPACE_MODEL = "IMPACT_FRAME_ACTOR_LOCAL_CONTACT_BINDING_V1"

_original_deform_source_geometry = consequences._deform_source_geometry


def _historical_chassis_matrix(actor, frame: int) -> Matrix:
    sample = actor.motion.get(int(frame))
    if sample is None:
        raise RuntimeError(
            f"DAMAGE_IMPACT_FRAME_POSE_MISSING:{actor.profile.entity_id}:{frame}"
        )
    position, quaternion = sample
    return Matrix.Translation(Vector(position)) @ quaternion.to_matrix().to_4x4()


def temporally_coherent_deform_source_geometry(
    actor,
    evidence: ImpactEvidence,
):
    """Apply deformation in the actor pose that owned the recorded contact point.

    Solver response is deliberately observed two frames after contact. The contact point
    is therefore historical world-space data. We temporarily evaluate the realized source
    meshes in the contact-frame actor transform, deform their *local* vertex data, and then
    restore their current solver-driven world transforms. No actor pose, velocity, contact
    tolerance, damage threshold, or scenario trajectory is changed.
    """
    meshes = consequences._copy_on_damage(actor)
    if actor.realized_root is None:
        raise RuntimeError(f"DAMAGE_REALIZED_ROOT_MISSING:{actor.profile.entity_id}")

    historical_chassis = _historical_chassis_matrix(actor, int(evidence.frame))
    current_chassis = actor.chassis.matrix_world.copy()
    historical_from_current = historical_chassis @ current_chassis.inverted_safe()

    saved_world = {obj.name: obj.matrix_world.copy() for obj in meshes}
    try:
        for obj in meshes:
            obj.matrix_world = historical_from_current @ obj.matrix_world
        return _original_deform_source_geometry(actor, evidence)
    finally:
        for obj in meshes:
            matrix = saved_world.get(obj.name)
            if matrix is not None:
                obj.matrix_world = matrix


def mirrored_impact_at_same_contact(
    evidence: ImpactEvidence,
    attacker,
    target,
    frame: int,
    response_attacker: float,
    response_target: float,
) -> ImpactEvidence:
    normal = -Vector(evidence.contact_normal)
    if normal.length < 1e-7:
        raise RuntimeError("MIRRORED_IMPACT_NORMAL_DEGENERATE")
    normal.normalize()
    # Newton-pair consequence uses the same physical contact point at the same impact frame.
    # Recomputing a surface point at the later resolve frame creates a temporal-space error.
    point = Vector(evidence.contact_point)
    return ImpactModel.estimate(
        frame=int(frame),
        attacker_id=target.profile.entity_id,
        target_id=attacker.profile.entity_id,
        target_zone="front",
        attacker_mass_kg=target.profile.mass_kg,
        target_mass_kg=attacker.profile.mass_kg,
        relative_speed_mps=evidence.relative_speed_mps,
        normal_closing_speed_mps=evidence.normal_closing_speed_mps,
        contact_point=tuple(point),
        contact_normal=tuple(normal),
        response_delta_attacker_mps=response_target,
        response_delta_target_mps=response_attacker,
        target_toughness_j_per_kg=attacker.profile.toughness_j_per_kg,
    )


def main() -> None:
    # Preserve all generic engine fixes proven/introduced by Candidate 3.5.
    candidate35.assets.centroid_for_terms = candidate35.candidate34.ambiguity_safe_centroid_for_terms
    candidate35.physics.DriveRig.command = candidate35.candidate34.calibrated_command
    candidate35.physics.create_drive_rig = candidate35.calibrated_create_drive_rig

    # Harden only the temporal contact->source-geometry binding failure family.
    consequences._deform_source_geometry = temporally_coherent_deform_source_geometry
    hardened._mirrored_impact = mirrored_impact_at_same_contact
    hardened.RUNTIME_VERSION = CANDIDATE

    print(
        json.dumps(
            {
                "marker": "GENERIC_BATTLE_RUNTIME_CANDIDATE36_ENGINE_HARDENING_PASS",
                "candidate": CANDIDATE,
                "contactSpaceModel": CONTACT_SPACE_MODEL,
                "driveAuthorityModel": candidate35.DRIVE_AUTHORITY_MODEL,
                "motorRollingSign": candidate35.candidate34.MOTOR_ROLLING_SIGN,
                "semanticLocator": candidate35.candidate34.SEMANTIC_LOCATOR,
                "damageThresholdChanged": False,
                "contactThresholdChanged": False,
                "scenarioTrajectoryHardcode": False,
                "actorPoseOrVelocityMutation": False,
            },
            sort_keys=True,
        ),
        flush=True,
    )
    hardened.main()


if __name__ == "__main__":
    main()
