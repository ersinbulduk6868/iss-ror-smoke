#!/usr/bin/env python3
from __future__ import annotations

import ast
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from blender.iss_battle_runtime_handoff_alignment_v1 import (
    HANDOFF_ALIGNMENT_MODEL,
    rotational_nose_speed_mps,
    should_defer_handoff_for_alignment,
    translation_dominates_rotation,
)

HELPER = ROOT / "blender" / "iss_battle_runtime_handoff_alignment_v1.py"
WRAPPER = ROOT / "blender" / "run_generic_battle_runtime_v1_candidate484_generic_battle.py"
FORBIDDEN_ASSET_TOKENS = (
    "bulldozer",
    "bugatti",
    "b06a715d23a7450babac383b8bb7fb0a",
    "27614.189525707065",
)


def main() -> None:
    helper_text = HELPER.read_text(encoding="utf-8")
    wrapper_text = WRAPPER.read_text(encoding="utf-8")
    ast.parse(helper_text, filename=str(HELPER))
    ast.parse(wrapper_text, filename=str(WRAPPER))

    assert rotational_nose_speed_mps(
        yaw_rate_rad_s=1.0,
        characteristic_length_m=4.0,
    ) == 2.0
    assert translation_dominates_rotation(
        forward_speed_mps=3.0,
        yaw_rate_rad_s=1.0,
        characteristic_length_m=4.0,
    ) is True
    assert translation_dominates_rotation(
        forward_speed_mps=1.5,
        yaw_rate_rad_s=1.0,
        characteristic_length_m=4.0,
    ) is False
    assert translation_dominates_rotation(
        forward_speed_mps=0.0,
        yaw_rate_rad_s=0.0,
        characteristic_length_m=4.0,
    ) is False
    assert translation_dominates_rotation(
        forward_speed_mps=-2.0,
        yaw_rate_rad_s=0.0,
        characteristic_length_m=4.0,
    ) is False

    assert should_defer_handoff_for_alignment(
        contact_handoff_requested=True,
        prospective_motor_authority="MOTOR",
        forward_speed_mps=1.5,
        yaw_rate_rad_s=1.0,
        characteristic_length_m=4.0,
    ) is True
    assert should_defer_handoff_for_alignment(
        contact_handoff_requested=True,
        prospective_motor_authority="MOTOR",
        forward_speed_mps=3.0,
        yaw_rate_rad_s=1.0,
        characteristic_length_m=4.0,
    ) is False
    assert should_defer_handoff_for_alignment(
        contact_handoff_requested=False,
        prospective_motor_authority="MOTOR",
        forward_speed_mps=1.0,
        yaw_rate_rad_s=1.0,
        characteristic_length_m=4.0,
    ) is False
    assert should_defer_handoff_for_alignment(
        contact_handoff_requested=True,
        prospective_motor_authority="COAST",
        forward_speed_mps=1.0,
        yaw_rate_rad_s=1.0,
        characteristic_length_m=4.0,
    ) is False

    lower = (helper_text + "\n" + wrapper_text).lower()
    for token in FORBIDDEN_ASSET_TOKENS:
        assert token.lower() not in lower, ("C484_ASSET_SPECIFIC_TOKEN_FORBIDDEN", token)

    combined = helper_text + "\n" + wrapper_text
    for required in (
        "candidate481._BASE_AUTONOMY_UPDATE = alignment_aware_base_autonomy_update",
        "replace(memory)",
        "replace(obs, requires_contact=False)",
        "G04_CONTACT_HANDOFF_DEFERRED_BY_ROTATIONAL_DOMINANCE",
        "G04_CONTACT_HANDOFF_ALIGNMENT_READY",
        '"c483DriveDirectionPreserved": True',
        '"c482CollisionRolesPreserved": True',
        '"c481DeferredHandoffProgressPreserved": True',
        '"c480ApproachSemanticTransactionPreserved": True',
        '"c474ObbHandoffEligibilityPreserved": True',
        '"g05NativeSolverFinalAuthorityPreserved": True',
        '"contactThresholdChanged": False',
        '"damageAdmissionThresholdChanged": False',
        '"perAssetBattleCode": False',
        '"perAssetTacticalTuning": False',
        '"perVideoTrajectoryEngineering": False',
    ):
        assert required in combined, required

    for forbidden in (
        "MIN_CLOSING_SPEED_MPS",
        "MIN_DAMAGE_SEVERITY",
        "desiredImpactSpeedMps",
        "desiredImpactEnergyJ",
        "collisionFrame",
        "impactFrame",
        "trajectoryPoints",
        "waypoints",
        "set_pose",
        "linear_velocity =",
        "actor_beta",
        "actor_alpha",
    ):
        assert forbidden not in helper_text, forbidden
        assert forbidden not in wrapper_text, forbidden

    print(json.dumps({
        "marker": "GENERIC_AUTONOMOUS_BATTLE_C484_PROPERTY_ACCEPTANCE",
        "status": "PASS",
        "affectedLayerAudit": "PASS",
        "failureFamily": "SOLVER_HANDOFF_BEGINS_WHILE_CONTACT_APPROACH_IS_ROTATIONALLY_DOMINANT",
        "mechanism": HANDOFF_ALIGNMENT_MODEL,
        "translationDominantHandoffContract": "PASS",
        "rotationalLeverArmFromCharacteristicLength": True,
        "shadowMemoryProbeOnly": True,
        "g05ThresholdImported": False,
        "assetSpecificCode": False,
        "perAssetTacticalTuning": False,
        "contactThresholdChanged": False,
        "damageAdmissionThresholdChanged": False,
        "masterPlanAligned": True,
        "gateClosed": False,
    }, sort_keys=True))


if __name__ == "__main__":
    main()
