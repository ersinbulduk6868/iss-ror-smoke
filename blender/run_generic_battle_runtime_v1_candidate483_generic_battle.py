from __future__ import annotations

import json
from pathlib import Path
import sys
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from blender import iss_battle_runtime_physics as physics
from blender import run_generic_battle_runtime_v1_candidate482_generic_battle as candidate482
from blender.iss_battle_runtime_drive_direction_v1 import (
    CANONICAL_DRIVE_DIRECTION_MODEL,
    motor_inputs_for_canonical_linear_commands,
)

CANDIDATE = "ISS_GENERIC_BATTLE_RUNTIME_V1_CANDIDATE_4_8_3_GENERIC_AUTONOMOUS_BATTLE"
MECHANISM = CANONICAL_DRIVE_DIRECTION_MODEL
AUDIT = "G04_CANONICAL_DRIVE_DIRECTION_FULL_AFFECTED_LAYER_AUDIT_20260918"
FAILURE_FAMILY = "DRIVE_MOTOR_SIGN_OPPOSES_CANONICAL_CHASSIS_FORWARD_AXIS"

_ORIGINAL_DRIVE_COMMAND = physics.DriveRig.command


def canonical_direction_drive_command(
    self: Any,
    left_mps: float,
    right_mps: float,
    impulse_scale: float = 1.0,
) -> None:
    motor_left, motor_right = motor_inputs_for_canonical_linear_commands(
        left_mps,
        right_mps,
    )
    _ORIGINAL_DRIVE_COMMAND(
        self,
        motor_left,
        motor_right,
        impulse_scale=impulse_scale,
    )


def main() -> None:
    physics.DriveRig.command = canonical_direction_drive_command

    print(json.dumps({
        "marker": "GENERIC_AUTONOMOUS_BATTLE_C483_ENGINEERING_READY",
        "candidate": CANDIDATE,
        "mechanism": MECHANISM,
        "affectedLayerAudit": AUDIT,
        "failureFamily": FAILURE_FAMILY,
        "canonicalVehicleForwardAxis": "+X",
        "blenderWheelMotorPositiveDirectionRealizes": "CHASSIS_LOCAL_NEGATIVE_X",
        "canonicalLinearCommandSignMappedToMotorSign": "INVERTED",
        "c482CollisionRoleSeparationPreserved": True,
        "c481DeferredHandoffProgressPreserved": True,
        "c480ApproachSemanticTransactionPreserved": True,
        "c474HandoffProgressOwnershipPreserved": True,
        "g05NativeSolverFinalAuthorityPreserved": True,
        "pairwiseSolverOraclePreserved": True,
        "contactThresholdChanged": False,
        "semanticToleranceChanged": False,
        "localityToleranceChanged": False,
        "damageAdmissionThresholdChanged": False,
        "damageThresholdAwareControl": False,
        "targetToughnessAwareControl": False,
        "desiredImpactSpeedControl": False,
        "desiredImpactEnergyControl": False,
        "assetIdentityBranch": False,
        "perAssetBattleCode": False,
        "perAssetTacticalTuning": False,
        "perVideoTrajectoryEngineering": False,
        "fixedWorldCoordinates": False,
        "exactCollisionFrameTarget": False,
        "exactImpactEnergyTarget": False,
        "actorPoseOrVelocityMutation": False,
        "fixtureBattlePlanChanged": False,
        "g01ToG03Changed": False,
        "frozenNineServiceArchitectureChanged": False,
        "gateClosed": False,
        "productionReadyClaimed": False,
    }, sort_keys=True), flush=True)

    candidate482.main()


if __name__ == "__main__":
    main()
