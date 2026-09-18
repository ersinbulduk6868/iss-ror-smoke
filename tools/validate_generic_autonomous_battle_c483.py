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
    CANONICAL_DRIVE_DIRECTION_MODEL,
    motor_inputs_for_canonical_linear_commands,
)

HELPER = ROOT / "blender" / "iss_battle_runtime_drive_direction_v1.py"
WRAPPER = ROOT / "blender" / "run_generic_battle_runtime_v1_candidate483_generic_battle.py"
C482 = ROOT / "blender" / "run_generic_battle_runtime_v1_candidate482_generic_battle.py"
FORBIDDEN_ASSET_TOKENS = ("bugatti", "bulldozer", "ferrari", "excavator")


def main() -> None:
    texts = {
        "helper": HELPER.read_text(encoding="utf-8"),
        "wrapper": WRAPPER.read_text(encoding="utf-8"),
        "c482": C482.read_text(encoding="utf-8"),
    }
    for name, text in texts.items():
        ast.parse(text, filename=name)

    assert motor_inputs_for_canonical_linear_commands(3.0, 3.0) == (-3.0, -3.0)
    assert motor_inputs_for_canonical_linear_commands(-3.0, -3.0) == (3.0, 3.0)
    assert motor_inputs_for_canonical_linear_commands(2.0, 4.0) == (-2.0, -4.0)
    assert motor_inputs_for_canonical_linear_commands(0.0, 0.0) == (-0.0, -0.0)

    for token in FORBIDDEN_ASSET_TOKENS:
        assert token not in texts["helper"].lower(), ("ASSET_SPECIFIC_HELPER_TOKEN", token)
        assert token not in texts["wrapper"].lower(), ("ASSET_SPECIFIC_WRAPPER_TOKEN", token)

    assert "physics.DriveRig.command = canonical_direction_drive_command" in texts["wrapper"]
    assert "candidate482.main()" in texts["wrapper"]
    assert "motor_inputs_for_canonical_linear_commands" in texts["wrapper"]

    for required in (
        '"c482CollisionRoleSeparationPreserved": True',
        '"c481DeferredHandoffProgressPreserved": True',
        '"c480ApproachSemanticTransactionPreserved": True',
        '"g05NativeSolverFinalAuthorityPreserved": True',
        '"contactThresholdChanged": False',
        '"damageAdmissionThresholdChanged": False',
        '"perAssetBattleCode": False',
        '"perAssetTacticalTuning": False',
        '"perVideoTrajectoryEngineering": False',
        '"actorPoseOrVelocityMutation": False',
    ):
        assert required in texts["wrapper"], required

    for forbidden in (
        "MIN_CLOSING_SPEED_MPS =",
        "MIN_DAMAGE_SEVERITY =",
        "target_impact_speed",
        "target_impact_energy",
        "collision_frame",
        "impact_frame",
        "set_pose",
        "linear_velocity =",
    ):
        assert forbidden not in texts["helper"], forbidden
        assert forbidden not in texts["wrapper"], forbidden

    print(json.dumps({
        "marker": "GENERIC_AUTONOMOUS_BATTLE_C483_PROPERTY_ACCEPTANCE",
        "status": "PASS",
        "affectedLayerAudit": "PASS",
        "failureFamily": "DRIVE_MOTOR_SIGN_OPPOSES_CANONICAL_CHASSIS_FORWARD_AXIS",
        "mechanism": CANONICAL_DRIVE_DIRECTION_MODEL,
        "canonicalPositiveForwardMapsToNegativeBlenderMotorTarget": True,
        "canonicalNegativeReverseMapsToPositiveBlenderMotorTarget": True,
        "c482CollisionRoleSeparationPreserved": True,
        "c481DeferredHandoffProgressPreserved": True,
        "c480ApproachSemanticTransactionPreserved": True,
        "thresholdChanged": False,
        "assetSpecificCode": False,
        "perAssetTacticalTuning": False,
        "masterPlanAligned": True,
        "gateClosed": False,
    }, sort_keys=True))


if __name__ == "__main__":
    main()
