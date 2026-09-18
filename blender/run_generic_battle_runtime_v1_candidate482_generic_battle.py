from __future__ import annotations

import json
from pathlib import Path
import sys
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from blender import iss_battle_runtime_assets as assets
from blender import iss_battle_runtime_physics as physics
from blender import iss_blender_battle_runtime_v1 as runtime
from blender import run_generic_battle_runtime_v1_candidate481_generic_battle as candidate481
from blender.iss_battle_runtime_assets import marker
from blender.iss_battle_runtime_collision_roles_v1 import (
    COLLISION_ROLE_MODEL,
    mask_for_role,
    runtime_collision_role,
)

CANDIDATE = "ISS_GENERIC_BATTLE_RUNTIME_V1_CANDIDATE_4_8_2_GENERIC_AUTONOMOUS_BATTLE"
MECHANISM = COLLISION_ROLE_MODEL
AUDIT = "G04_DRIVE_HELPER_COLLISION_ROLE_FULL_AFFECTED_LAYER_AUDIT_20260918"
FAILURE_FAMILY = "DRIVE_HELPER_COLLISION_AUTHORITY_LEAK_BEFORE_CHASSIS_HANDOFF"

_ORIGINAL_ADD_RIGID_BODY = physics.add_rigid_body
_ORIGINAL_ADD_CONSTRAINT = physics.add_constraint
_ORIGINAL_ADD_PASSIVE_RIGID_BODY = runtime.add_passive_rigid_body
_role_rows: list[dict[str, Any]] = []
_constraint_rows: list[dict[str, Any]] = []


def _apply_role_mask(obj: Any) -> str:
    role = runtime_collision_role(str(obj.name))
    mask = mask_for_role(role)
    if mask is None:
        return role
    if obj.rigid_body is None:
        raise RuntimeError(f"C482_RIGID_BODY_REQUIRED_FOR_ROLE:{obj.name}:{role}")
    obj.rigid_body.collision_collections = mask
    row = {
        "objectName": str(obj.name),
        "role": role,
        "enabledGroups": [i for i, value in enumerate(mask) if value],
        "model": MECHANISM,
    }
    _role_rows.append(row)
    marker("G04_RIGID_BODY_COLLISION_ROLE_ASSIGNED", **row)
    return role


def role_aware_add_rigid_body(
    obj: Any,
    *,
    mass: float,
    shape: str,
    friction: float,
    restitution: float,
    kinematic: bool = False,
) -> None:
    _ORIGINAL_ADD_RIGID_BODY(
        obj,
        mass=mass,
        shape=shape,
        friction=friction,
        restitution=restitution,
        kinematic=kinematic,
    )
    _apply_role_mask(obj)


def role_aware_add_passive_rigid_body(
    obj: Any,
    *,
    shape: str = "BOX",
    friction: float = 0.9,
) -> None:
    _ORIGINAL_ADD_PASSIVE_RIGID_BODY(obj, shape=shape, friction=friction)
    _apply_role_mask(obj)


def role_aware_add_constraint(
    name: str,
    kind: str,
    location: Any,
    axis: Any,
    object1: Any,
    object2: Any,
) -> Any:
    constraint_obj = _ORIGINAL_ADD_CONSTRAINT(
        name,
        kind,
        location,
        axis,
        object1,
        object2,
    )
    c = constraint_obj.rigid_body_constraint
    c.disable_collisions = True
    row = {
        "constraintName": str(name),
        "constraintType": str(kind),
        "object1": str(object1.name),
        "object2": str(object2.name),
        "disableCollisions": bool(c.disable_collisions),
        "model": MECHANISM,
    }
    _constraint_rows.append(row)
    marker("G04_CONSTRAINED_DRIVE_SELF_COLLISION_DISABLED", **row)
    return constraint_obj


def main() -> None:
    _role_rows.clear()
    _constraint_rows.clear()

    # Physics-role ownership only. No asset identity, mass thresholds, semantic
    # names, trajectory points, target speeds, impact energies or fixture branches.
    physics.add_rigid_body = role_aware_add_rigid_body
    physics.add_constraint = role_aware_add_constraint
    runtime.add_passive_rigid_body = role_aware_add_passive_rigid_body

    print(json.dumps({
        "marker": "GENERIC_AUTONOMOUS_BATTLE_C482_ENGINEERING_READY",
        "candidate": CANDIDATE,
        "mechanism": MECHANISM,
        "affectedLayerAudit": AUDIT,
        "failureFamily": FAILURE_FAMILY,
        "rootCause": "HIDDEN_DRIVE_HELPER_RIGID_BODIES_SHARED_INTERACTOR_COLLISION_AUTHORITY_WITH_BATTLE_CHASSIS",
        "battleBodyCollisionRole": "BATTLE_BODY",
        "driveHelperCollisionRole": "DRIVE_HELPER",
        "groundSharesBothRoles": True,
        "constrainedDriveSelfCollisionDisabled": True,
        "g05NativeSolverFinalAuthorityPreserved": True,
        "g05AuthoritativeBattleBody": "CHASSIS",
        "c481DeferredHandoffProgressPreserved": True,
        "c480ApproachSemanticTransactionPreserved": True,
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

    candidate481.main()


if __name__ == "__main__":
    main()
