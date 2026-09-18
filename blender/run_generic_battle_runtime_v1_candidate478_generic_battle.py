from __future__ import annotations

import json
from pathlib import Path
import sys

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from blender import iss_battle_runtime_assets as assets
from blender.iss_battle_runtime_orientation_v1 import (
    ORIENTATION_MODEL,
    resolve_physics_semantic_forward_axis,
)
from blender import run_generic_battle_runtime_v1_candidate474_generic_battle as candidate474

CANDIDATE = "ISS_GENERIC_BATTLE_RUNTIME_V1_CANDIDATE_4_7_8_PHYSICS_SEMANTIC_ORIENTATION"
MECHANISM = ORIENTATION_MODEL
AUDIT = "G04_ASSET_TO_RUNTIME_ORIENTATION_FULL_AFFECTED_LAYER_AUDIT_20260918"

_ORIGINAL_PARSE_FORWARD_AXIS = assets.parse_forward_axis


def c478_parse_forward_axis(binding: dict, imported: list) -> str:
    try:
        return _ORIGINAL_PARSE_FORWARD_AXIS(binding, imported)
    except assets.BlenderBattleRuntimeError as exc:
        if not str(exc).startswith("ACTOR_FORWARD_AXIS_UNRESOLVED:"):
            raise

        proof = resolve_physics_semantic_forward_axis(
            imported,
            front_terms=assets.FRONT_TERMS,
            rear_terms=assets.REAR_TERMS,
            object_tokens=assets.object_tokens,
            token_match=assets.token_match,
            world_bounds=assets.world_bounds,
        )
        if proof is None:
            raise

        print(json.dumps({
            "marker": "G04_FORWARD_AXIS_RESOLVED_FROM_PHYSICS_SEMANTICS",
            "entityId": binding.get("entityId"),
            "model": proof["model"],
            "axis": proof["axis"],
            "referenceSource": proof["referenceSource"],
            "delta": proof["delta"],
            "frontAnchors": proof["frontAnchors"],
            "rearAnchors": proof["rearAnchors"],
            "chassisAnchors": proof["chassisAnchors"],
            "assetIdentityBranch": False,
            "sourceShaBranch": False,
            "perAssetOrientationOverride": False,
        }, sort_keys=True), flush=True)
        return str(proof["axis"])


def main() -> None:
    assets.parse_forward_axis = c478_parse_forward_axis
    print(json.dumps({
        "marker": "GENERIC_AUTONOMOUS_BATTLE_C478_ENGINEERING_READY",
        "candidate": CANDIDATE,
        "mechanism": MECHANISM,
        "affectedLayerAudit": AUDIT,
        "c474TacticalRuntimePreserved": True,
        "existingOrientationAuthorityPreservedFirst": True,
        "physicsSemanticFallbackOnlyAfterUnresolved": True,
        "physicsSemanticHierarchyRequired": True,
        "assetIdentityBranch": False,
        "sourceShaBranch": False,
        "perAssetOrientationOverride": False,
        "perAssetBattleCode": False,
        "perVideoTrajectoryEngineering": False,
        "damageThresholdAwareControl": False,
        "desiredImpactSpeedControl": False,
        "desiredImpactEnergyControl": False,
        "fixedWorldCoordinates": False,
        "exactCollisionFrameTarget": False,
        "actorPoseOrVelocityMutation": False,
        "g05NativeSolverFinalAuthorityPreserved": True,
        "pairwiseSolverOraclePreserved": True,
        "contactThresholdChanged": False,
        "damageAdmissionThresholdChanged": False,
        "g01ToG03Changed": False,
        "frozenNineServiceArchitectureChanged": False,
        "gateClosed": False,
        "productionReadyClaimed": False,
    }, sort_keys=True), flush=True)
    candidate474.main()


if __name__ == "__main__":
    main()
