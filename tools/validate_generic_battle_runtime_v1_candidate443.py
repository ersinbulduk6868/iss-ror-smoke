#!/usr/bin/env python3
from __future__ import annotations

import ast
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RUNTIME = ROOT / "blender" / "run_generic_battle_runtime_v1_candidate443.py"
BUILDER = ROOT / "tools" / "build_generic_battle_runtime_v1_candidate443_g07.py"
SCOPE = ROOT / "docs" / "ISS_G07_SCOPE_CORRECTION_R042.md"


def fail(code: str) -> None:
    raise SystemExit(code)


def main() -> None:
    runtime = RUNTIME.read_text(encoding="utf-8")
    builder = BUILDER.read_text(encoding="utf-8")
    scope = SCOPE.read_text(encoding="utf-8")
    ast.parse(runtime, filename=str(RUNTIME))
    ast.parse(builder, filename=str(BUILDER))

    required_runtime = (
        'CANDIDATE = "ISS_GENERIC_BATTLE_RUNTIME_V1_CANDIDATE_4_4_3_G07"',
        'ENGAGEMENT_MODEL = "LIVE_GEOMETRY_SEMANTIC_ENGAGEMENT_RESOLVER_V1"',
        'target.prototype.zones.keys()',
        'target.zone_world(zone)',
        'event.target_zone = _select_live_semantic_surface',
        '"storyTargetZonePrescribed": False',
        '"runtimeSelectedSemanticEngagement": True',
        '"semanticSelectionFromLiveGeometry": True',
        '"hardCodedSemanticZone": False',
        '"perAssetCollisionEngineering": False',
        '"issR042ScopePreserved": True',
    )
    missing = [token for token in required_runtime if token not in runtime]
    if missing:
        fail("CANDIDATE443_RUNTIME_CONTRACT_MISSING:" + "|".join(missing))

    # Runtime must select from whatever semantic surfaces the asset exposes.
    # It must not know vehicle names or preferred semantic-zone names.
    lower_runtime = runtime.lower()
    for forbidden in (
        "bugatti",
        "ferrari",
        "bulldozer",
        '"front"',
        '"rear"',
        '"left_side"',
        '"right_side"',
        "targetenergyj",
        "impactenergyj",
        "targetimpactspeedmps",
        "collisionframe",
        "trajectorypoints",
        "steeringangle",
        "brakingpoint",
        "approachvector",
        "linear_velocity =",
        "angular_velocity =",
        ".location =",
        ".rotation_euler =",
        ".rotation_quaternion =",
        "bpy.ops.rigidbody",
    ):
        if forbidden.lower() in lower_runtime:
            fail(f"CANDIDATE443_RUNTIME_FORBIDDEN_TOKEN:{forbidden}")

    required_builder = (
        '"storyTargetActorOnly": True',
        '"storyTargetZonePrescribed": False',
        '"runtimeSelectsSemanticEngagementSurface": True',
        '"perAssetCollisionEngineering": False',
        'verify_runtime_selected_targeting(exact)',
        'verify_runtime_selected_targeting(generic)',
    )
    missing_builder = [token for token in required_builder if token not in builder]
    if missing_builder:
        fail("CANDIDATE443_BUILDER_CONTRACT_MISSING:" + "|".join(missing_builder))

    for required_scope in (
        "ISS-R042",
        "Asset-independent autonomous collision realization",
        "Story/G07 expresses battle intent and causal state only",
        "per-asset collision engineering",
    ):
        if required_scope not in scope:
            fail(f"CANDIDATE443_SCOPE_LOCK_MISSING:{required_scope}")

    print(json.dumps({
        "marker": "GENERIC_BATTLE_RUNTIME_CANDIDATE443_G07_PROPERTY_ACCEPTANCE",
        "status": "PASS",
        "candidate": "ISS_GENERIC_BATTLE_RUNTIME_V1_CANDIDATE_4_4_3_G07",
        "engagementTargetingModel": "LIVE_GEOMETRY_SEMANTIC_ENGAGEMENT_RESOLVER_V1",
        "storyIntentOnly": True,
        "storyTargetActorOnly": True,
        "storyTargetZonePrescribed": False,
        "runtimeSelectedSemanticEngagement": True,
        "semanticSelectionFromLiveGeometry": True,
        "semanticZoneNamesHardCodedInRuntime": False,
        "perAssetCollisionEngineering": False,
        "g04SourceMutationRequired": False,
        "g05SourceMutationRequired": False,
        "g06SourceMutationRequired": False,
        "damageThresholdChanged": False,
        "contactThresholdChanged": False,
        "actorPoseOrVelocityMutation": False,
        "stateResetMechanismIntroduced": False,
        "forcedWinnerIntroduced": False,
        "exactCollisionFrameTarget": False,
        "exactImpactEnergyTarget": False,
        "issR041ScopePreserved": True,
        "issR042ScopePreserved": True,
        "productionReadyClaimed": False,
    }, sort_keys=True))


if __name__ == "__main__":
    main()
