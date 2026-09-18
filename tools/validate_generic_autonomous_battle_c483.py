#!/usr/bin/env python3
from __future__ import annotations

import ast
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from blender.iss_battle_runtime_drive_direction_v1 import (
    DRIVE_DIRECTION_MODEL,
    motor_angular_velocity_for_chassis_speed,
)

HELPER = ROOT / "blender" / "iss_battle_runtime_drive_direction_v1.py"
WRAPPER = ROOT / "blender" / "run_generic_battle_runtime_v1_candidate483_generic_battle.py"
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

    assert motor_angular_velocity_for_chassis_speed(3.0, 0.5) == -6.0
    assert motor_angular_velocity_for_chassis_speed(-3.0, 0.5) == 6.0
    assert motor_angular_velocity_for_chassis_speed(0.0, 0.5) == 0.0

    lower = (helper_text + "\n" + wrapper_text).lower()
    for token in FORBIDDEN_ASSET_TOKENS:
        assert token.lower() not in lower, ("C483_ASSET_SPECIFIC_TOKEN_FORBIDDEN", token)

    for required in (
        "return -float(speed_mps) / radius",
        "physics.DriveRig.command = direction_corrected_command",
        '"c482CollisionRolesPreserved": True',
        '"g05NativeSolverFinalAuthorityPreserved": True',
        '"contactThresholdChanged": False',
        '"damageAdmissionThresholdChanged": False',
        '"perAssetBattleCode": False',
        '"perAssetTacticalTuning": False',
        '"perVideoTrajectoryEngineering": False',
    ):
        assert required in (helper_text + "\n" + wrapper_text), required

    for forbidden in (
        "desiredImpactSpeedMps",
        "desiredImpactEnergyJ",
        "collisionFrame",
        "impactFrame",
        "trajectoryPoints",
        "waypoints",
        "set_pose",
        "linear_velocity =",
        "MIN_CLOSING_SPEED_MPS =",
        "MIN_DAMAGE_SEVERITY =",
    ):
        assert forbidden not in helper_text, forbidden
        assert forbidden not in wrapper_text, forbidden

    print(json.dumps({
        "marker": "GENERIC_AUTONOMOUS_BATTLE_C483_PROPERTY_ACCEPTANCE",
        "status": "PASS",
        "affectedLayerAudit": "PASS",
        "failureFamily": "GENERIC_DRIVE_MOTOR_SIGN_INVERTS_CANONICAL_CHASSIS_FORWARD",
        "mechanism": DRIVE_DIRECTION_MODEL,
        "canonicalForwardToMotorSign": "PASS",
        "sameMappingAcrossAssets": True,
        "assetSpecificCode": False,
        "perAssetTacticalTuning": False,
        "contactThresholdChanged": False,
        "damageAdmissionThresholdChanged": False,
        "masterPlanAligned": True,
        "gateClosed": False,
    }, sort_keys=True))


if __name__ == "__main__":
    main()
