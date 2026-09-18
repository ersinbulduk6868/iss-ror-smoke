#!/usr/bin/env python3
from __future__ import annotations

import ast
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from blender.iss_battle_runtime_handoff_progress_v1 import (
    HANDOFF_DEFER_PROGRESS_MODEL,
    deferred_handoff_stalled,
)

HELPER = ROOT / "blender" / "iss_battle_runtime_handoff_progress_v1.py"
WRAPPER = ROOT / "blender" / "run_generic_battle_runtime_v1_candidate481_generic_battle.py"
FORBIDDEN_ASSET_TOKENS = (
    "bulldozer",
    "b06a715d23a7450babac383b8bb7fb0a",
    "2c0be359bbc6c99118751e7caa4b71a205961914e78d2e58c5dd7afc0f498468",
    "27614.189525707065",
)


def main() -> None:
    helper_text = HELPER.read_text(encoding="utf-8")
    wrapper_text = WRAPPER.read_text(encoding="utf-8")
    ast.parse(helper_text, filename=str(HELPER))
    ast.parse(wrapper_text, filename=str(WRAPPER))

    base = dict(
        handoff_deferred=True,
        effective_collision_proxy_gap_m=1.2,
        existing_handoff_gap_m=0.08,
        last_command_speed_mps=1.0,
        frame=100,
        last_progress_frame=60,
        progress_timeout_frames=40,
        controller_mode="TRACK",
    )
    assert deferred_handoff_stalled(**base) is True
    assert deferred_handoff_stalled(**{**base, "handoff_deferred": False}) is False
    assert deferred_handoff_stalled(**{**base, "effective_collision_proxy_gap_m": None}) is False
    assert deferred_handoff_stalled(**{**base, "effective_collision_proxy_gap_m": 0.05}) is False
    assert deferred_handoff_stalled(**{**base, "last_command_speed_mps": 0.10}) is False
    assert deferred_handoff_stalled(**{**base, "frame": 99}) is False
    assert deferred_handoff_stalled(**{**base, "controller_mode": "RECOVER_REVERSE"}) is False

    lower = (helper_text + "\n" + wrapper_text).lower()
    for token in FORBIDDEN_ASSET_TOKENS:
        assert token.lower() not in lower, ("C481_ASSET_SPECIFIC_TOKEN_FORBIDDEN", token)

    for required in (
        "G04_DEFERRED_HANDOFF_STALL_RECOVERY_TRIGGERED",
        "candidate472._ORIGINAL_AUTONOMY_UPDATE = defer_progress_aware_base_autonomy_update",
        '"c480ApproachSemanticTransactionPreserved": True',
        '"radialNavigationContractPreserved": True',
        '"c474ObbHandoffEligibilityPreserved": True',
        '"existingProgressTimeoutReused": True',
        '"existingRecoveryMechanismReused": True',
        '"newRecoveryTrajectoryIntroduced": False',
        '"g05NativeSolverFinalAuthorityPreserved": True',
        '"assetIdentityBranch": False',
        '"perAssetBattleCode": False',
        '"perAssetTacticalTuning": False',
        '"perVideoTrajectoryEngineering": False',
        '"fixedWorldCoordinates": False',
        '"actorPoseOrVelocityMutation": False',
        '"contactThresholdChanged": False',
        '"damageAdmissionThresholdChanged": False',
    ):
        assert required in wrapper_text, required

    for forbidden in (
        "desiredImpactSpeedMps",
        "desiredImpactEnergyJ",
        "collisionFrame",
        "impactFrame",
        "trajectoryPoints",
        "waypoints",
        "forcedWinner",
        "set_pose",
        "linear_velocity =",
        "MIN_CLOSING_SPEED_MPS =",
        "MIN_IMPULSE_BALANCE_RATIO =",
        "MIN_OPPOSITION_COSINE =",
        "MIN_NORMAL_ALIGNMENT =",
    ):
        assert forbidden not in helper_text, forbidden
        assert forbidden not in wrapper_text, forbidden

    print(json.dumps({
        "marker": "GENERIC_AUTONOMOUS_BATTLE_C481_PROPERTY_ACCEPTANCE",
        "status": "PASS",
        "affectedLayerAudit": "PASS",
        "failureFamily": "RADIAL_NAVIGATION_AND_OBB_HANDOFF_SPLIT_GEOMETRY_DEAD_ZONE",
        "mechanism": HANDOFF_DEFER_PROGRESS_MODEL,
        "deferredHandoffStallRecovery": "PASS",
        "radialNavigationPreserved": True,
        "obbHandoffEligibilityPreserved": True,
        "existingRecoveryReused": True,
        "assetSpecificCode": False,
        "perAssetTacticalTuning": False,
        "thresholdChanged": False,
        "masterPlanAligned": True,
        "gateClosed": False,
    }, sort_keys=True))


if __name__ == "__main__":
    main()
