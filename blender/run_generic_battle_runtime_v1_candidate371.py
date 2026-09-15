from __future__ import annotations

import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from blender import iss_battle_runtime_consequences as consequences
from blender import iss_blender_battle_runtime_v1 as runtime
from blender import iss_blender_battle_runtime_v1_hardened as hardened
from blender import run_generic_battle_runtime_v1_candidate35 as candidate35
from blender import run_generic_battle_runtime_v1_candidate36 as candidate36
from blender import run_generic_battle_runtime_v1_candidate37 as candidate37
from blender.iss_battle_runtime_assets import marker

CANDIDATE = "ISS_GENERIC_BATTLE_RUNTIME_V1_CANDIDATE_3_7_1"
_original_consequence_apply = consequences.ConsequenceEngine.apply


def truthful_consequence_apply(actor, evidence):
    contact_frame = int(evidence.frame)
    visual_evidence = candidate37._remapped_visual_evidence(actor, evidence)
    receipt = _original_consequence_apply(actor, visual_evidence)
    marker(
        "CONSEQUENCE_CONTACT_TO_REALIZATION_BINDING_PASS",
        entityId=actor.profile.entity_id,
        contactFrame=contact_frame,
        realizationFrame=int(visual_evidence.frame),
        delayFrames=int(visual_evidence.frame) - contact_frame,
        actorPoseOrVelocityMutation=False,
    )
    return receipt


def main() -> None:
    candidate35.assets.centroid_for_terms = candidate35.candidate34.ambiguity_safe_centroid_for_terms
    candidate35.physics.DriveRig.command = candidate35.candidate34.calibrated_command
    candidate35.physics.create_drive_rig = candidate35.calibrated_create_drive_rig

    hardened._mirrored_impact = candidate36.mirrored_impact_at_same_contact
    consequences._copy_on_damage = candidate37.fidelity_copy_on_damage
    consequences._deform_source_geometry = candidate37.surface_aware_deform_source_geometry
    consequences._spawn_debris = candidate37.causal_spawn_debris
    consequences.ConsequenceEngine.apply = staticmethod(truthful_consequence_apply)
    consequences.CONSEQUENCE_MODEL = candidate37.CONSEQUENCE_MODEL
    runtime.CONSEQUENCE_MODEL = candidate37.CONSEQUENCE_MODEL
    hardened.RUNTIME_VERSION = CANDIDATE

    print(json.dumps({
        "marker": "GENERIC_BATTLE_RUNTIME_CANDIDATE371_ENGINE_HARDENING_PASS",
        "candidate": CANDIDATE,
        "damageBindingModel": candidate37.DAMAGE_BINDING_MODEL,
        "consequenceModel": candidate37.CONSEQUENCE_MODEL,
        "driveAuthorityModel": candidate35.DRIVE_AUTHORITY_MODEL,
        "semanticLocator": candidate35.candidate34.SEMANTIC_LOCATOR,
        "truthfulVisualReceiptFrame": True,
        "damageThresholdChanged": False,
        "contactThresholdChanged": False,
        "scenarioTrajectoryHardcode": False,
        "actorPoseOrVelocityMutation": False,
    }, sort_keys=True), flush=True)
    hardened.main()


if __name__ == "__main__":
    main()
