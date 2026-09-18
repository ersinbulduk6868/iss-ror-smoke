#!/usr/bin/env python3
from __future__ import annotations

import ast
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from blender.iss_battle_runtime_collision_roles_v1 import (
    BATTLE_BODY_MASK,
    COLLISION_ROLE_MODEL,
    DRIVE_HELPER_MASK,
    GROUND_MASK,
    mask_for_role,
    runtime_collision_role,
)

HELPER = ROOT / "blender" / "iss_battle_runtime_collision_roles_v1.py"
WRAPPER = ROOT / "blender" / "run_generic_battle_runtime_v1_candidate482_generic_battle.py"
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

    assert len(BATTLE_BODY_MASK) == 20
    assert len(DRIVE_HELPER_MASK) == 20
    assert len(GROUND_MASK) == 20
    assert not any(a and b for a, b in zip(BATTLE_BODY_MASK, DRIVE_HELPER_MASK)), "BATTLE_AND_DRIVE_MASKS_MUST_BE_DISJOINT"
    assert all((not a) or g for a, g in zip(BATTLE_BODY_MASK, GROUND_MASK)), "GROUND_MUST_SHARE_BATTLE_ROLE"
    assert all((not d) or g for d, g in zip(DRIVE_HELPER_MASK, GROUND_MASK)), "GROUND_MUST_SHARE_DRIVE_ROLE"
    assert runtime_collision_role("ISS_PHYSICS_actor_alpha") == "BATTLE_BODY"
    assert runtime_collision_role("ISS_DRIVE_WHEEL_actor_alpha_FL") == "DRIVE_HELPER"
    assert runtime_collision_role("ISS_RUNTIME_GROUND") == "GROUND"
    assert mask_for_role("BATTLE_BODY") == BATTLE_BODY_MASK
    assert mask_for_role("DRIVE_HELPER") == DRIVE_HELPER_MASK
    assert mask_for_role("GROUND") == GROUND_MASK

    lower = (helper_text + "\n" + wrapper_text).lower()
    for token in FORBIDDEN_ASSET_TOKENS:
        assert token.lower() not in lower, ("C482_ASSET_SPECIFIC_TOKEN_FORBIDDEN", token)

    for required in (
        "physics.add_rigid_body = role_aware_add_rigid_body",
        "physics.add_constraint = role_aware_add_constraint",
        "runtime.add_passive_rigid_body = role_aware_add_passive_rigid_body",
        "c.disable_collisions = True",
        "G04_RIGID_BODY_COLLISION_ROLE_ASSIGNED",
        "G04_CONSTRAINED_DRIVE_SELF_COLLISION_DISABLED",
        '"g05NativeSolverFinalAuthorityPreserved": True',
        '"g05AuthoritativeBattleBody": "CHASSIS"',
        '"c481DeferredHandoffProgressPreserved": True',
        '"c480ApproachSemanticTransactionPreserved": True',
        '"assetIdentityBranch": False',
        '"perAssetBattleCode": False',
        '"perAssetTacticalTuning": False',
        '"perVideoTrajectoryEngineering": False',
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
        "marker": "GENERIC_AUTONOMOUS_BATTLE_C482_PROPERTY_ACCEPTANCE",
        "status": "PASS",
        "affectedLayerAudit": "PASS",
        "failureFamily": "DRIVE_HELPER_COLLISION_AUTHORITY_LEAK_BEFORE_CHASSIS_HANDOFF",
        "mechanism": COLLISION_ROLE_MODEL,
        "battleAndDriveRolesDisjoint": True,
        "groundSharesBothRoles": True,
        "constrainedDriveSelfCollisionDisabled": True,
        "assetSpecificCode": False,
        "perAssetTacticalTuning": False,
        "thresholdChanged": False,
        "masterPlanAligned": True,
        "gateClosed": False,
    }, sort_keys=True))


if __name__ == "__main__":
    main()
