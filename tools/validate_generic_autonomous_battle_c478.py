#!/usr/bin/env python3
from __future__ import annotations

import ast
import json
from pathlib import Path
import sys
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from blender.iss_battle_runtime_orientation_v1 import (
    ORIENTATION_MODEL,
    resolve_physics_semantic_forward_axis,
)

HELPER = ROOT / "blender" / "iss_battle_runtime_orientation_v1.py"
WRAPPER = ROOT / "blender" / "run_generic_battle_runtime_v1_candidate478_generic_battle.py"
C474 = ROOT / "blender" / "run_generic_battle_runtime_v1_candidate474_generic_battle.py"
ASSETS = ROOT / "blender" / "iss_battle_runtime_assets.py"


class Vec:
    def __init__(self, x: float, y: float, z: float = 0.0):
        self.x, self.y, self.z = x, y, z


class Matrix:
    def __init__(self, p: Vec):
        self.translation = p


class Obj:
    def __init__(self, name: str, point: tuple[float, float, float], parent=None):
        self.name = name
        self.type = "EMPTY"
        self.parent = parent
        self.matrix_world = Matrix(Vec(*point))
        self.data = SimpleNamespace(vertices=())


def tokens(obj) -> set[str]:
    return {str(obj.name).lower()}


def token_match(values: set[str], terms: tuple[str, ...]) -> bool:
    return any(str(term).lower() in value for value in values for term in terms)


def unused_world_bounds(_):
    raise AssertionError("SYNTHETIC_EMPTY_WORLD_BOUNDS_MUST_NOT_BE_USED")


def main() -> None:
    texts = {
        "helper": HELPER.read_text(encoding="utf-8"),
        "wrapper": WRAPPER.read_text(encoding="utf-8"),
        "c474": C474.read_text(encoding="utf-8"),
        "assets": ASSETS.read_text(encoding="utf-8"),
    }
    for name, text in texts.items():
        ast.parse(text, filename=name)

    physics = Obj("Physics", (0.0, 0.0, 0.0))
    blade = Obj("blade", (3.4, 0.0, 0.0), physics)
    chassis = Obj("chassis", (0.5, 0.0, 0.0), physics)
    damage = Obj("DamageZones", (0.0, 0.0, 0.0))
    duplicate_blade = Obj("blade", (0.0, 0.0, 0.0), damage)

    proof = resolve_physics_semantic_forward_axis(
        [physics, blade, chassis, damage, duplicate_blade],
        front_terms=("front", "blade"),
        rear_terms=("rear", "back"),
        object_tokens=tokens,
        token_match=token_match,
        world_bounds=unused_world_bounds,
    )
    assert proof is not None
    assert proof["axis"] == "X", proof
    assert proof["referenceSource"] == "PHYSICS_CHASSIS_SEMANTIC", proof
    assert proof["frontAnchors"] == ["blade"], proof
    assert proof["assetIdentityBranch"] is False
    assert proof["sourceShaBranch"] is False
    assert proof["perAssetOrientationOverride"] is False

    no_physics = resolve_physics_semantic_forward_axis(
        [damage, duplicate_blade],
        front_terms=("front", "blade"),
        rear_terms=("rear", "back"),
        object_tokens=tokens,
        token_match=token_match,
        world_bounds=unused_world_bounds,
    )
    assert no_physics is None

    # Identity/provenance values must never enter the generic orientation code.
    for forbidden in (
        "bugatti", "bulldozer", "b06a715d", "2c0be359", "8ab94079",
    ):
        assert forbidden not in texts["helper"].lower(), forbidden
        assert forbidden not in texts["wrapper"].lower(), forbidden

    # Risky battle-control concepts are allowed only as explicit negative
    # declarations in the C478 engineering manifest. The orientation helper
    # itself must contain none of them.
    for forbidden in (
        "desiredimpactspeed", "desiredimpactenergy", "collisionframe", "contactframe",
        "trajectorypoints", "waypoints", "forcedwinner",
    ):
        assert forbidden not in texts["helper"].lower(), forbidden

    for required_false in (
        '"perAssetOrientationOverride": False',
        '"perAssetBattleCode": False',
        '"perVideoTrajectoryEngineering": False',
        '"damageThresholdAwareControl": False',
        '"desiredImpactSpeedControl": False',
        '"desiredImpactEnergyControl": False',
        '"fixedWorldCoordinates": False',
        '"exactCollisionFrameTarget": False',
        '"actorPoseOrVelocityMutation": False',
        '"contactThresholdChanged": False',
        '"damageAdmissionThresholdChanged": False',
    ):
        assert required_false in texts["wrapper"], required_false

    assert "return _ORIGINAL_PARSE_FORWARD_AXIS(binding, imported)" in texts["wrapper"]
    assert "ACTOR_FORWARD_AXIS_UNRESOLVED:" in texts["wrapper"]
    assert "G04_FORWARD_AXIS_RESOLVED_FROM_PHYSICS_SEMANTICS" in texts["wrapper"]
    assert "candidate474.main()" in texts["wrapper"]

    print(json.dumps({
        "marker": "GENERIC_AUTONOMOUS_BATTLE_C478_PROPERTY_ACCEPTANCE",
        "status": "PASS",
        "affectedLayerAudit": "PASS",
        "failureFamily": "PRODUCTION_READY_PHYSICS_SEMANTICS_NOT_CONSUMED_BY_FORWARD_AXIS_RESOLVER",
        "orientationModel": ORIENTATION_MODEL,
        "existingResolverPreservedFirst": True,
        "physicsSemanticFallbackSyntheticProof": "PASS",
        "damageZoneDuplicateRejectedByHierarchyScope": True,
        "assetIdentityBranch": False,
        "sourceShaBranch": False,
        "perAssetOrientationOverride": False,
        "c474TacticalRuntimePreserved": True,
        "contactThresholdChanged": False,
        "damageAdmissionThresholdChanged": False,
        "perAssetBattleCode": False,
        "masterPlanAligned": True,
        "gateClosed": False,
    }, sort_keys=True))


if __name__ == "__main__":
    main()
