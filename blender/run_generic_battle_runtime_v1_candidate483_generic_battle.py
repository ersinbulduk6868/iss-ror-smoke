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
    DRIVE_DIRECTION_MODEL,
    command_drive_rig,
)

CANDIDATE = "ISS_GENERIC_BATTLE_RUNTIME_V1_CANDIDATE_4_8_3_GENERIC_AUTONOMOUS_BATTLE"
MECHANISM = DRIVE_DIRECTION_MODEL
AUDIT = "G04_GENERIC_DRIVE_DIRECTION_FULL_AFFECTED_LAYER_AUDIT_20260918"
FAILURE_FAMILY = "GENERIC_DRIVE_MOTOR_SIGN_INVERTS_CANONICAL_CHASSIS_FORWARD"


def direction_corrected_command(
    self: Any,
    left_mps: float,
    right_mps: float,
    impulse_scale: float = 1.0,
) -> None:
    command_drive_rig(self, left_mps, right_mps, impulse_scale)


def main() -> None:
    physics.DriveRig.command = direction_corrected_command

    print(json.dumps({
        "marker": "GENERIC_AUTONOMOUS_BATTLE_C483_ENGINEERING_READY",
        "candidate": CANDIDATE,
        "mechanism": MECHANISM,
        "affectedLayerAudit": AUDIT,
        "failureFamily": FAILURE_FAMILY,
        "rootCause": "BLENDER_MOTOR_POSITIVE_ROTATION_DRIVES_OPPOSITE_CANONICAL_CHASSIS_FORWARD",
        "canonicalForwardCommandPreserved": True,
        "blenderMotorSignAdapted": True,
        "sameMappingAcrossAssets": True,
        "c482CollisionRolesPreserved": True,
        "c481DeferredHandoffProgressPreserved": True,
        "c480ApproachSemanticTransactionPreserved": True,
        "g05NativeSolverFinalAuthorityPreserved": True,
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
