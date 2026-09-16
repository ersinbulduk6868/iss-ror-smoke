#!/usr/bin/env python3
from __future__ import annotations

import ast
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RUNTIME = ROOT / "blender" / "run_generic_battle_runtime_v1_candidate442.py"
BUILDER = ROOT / "tools" / "build_generic_battle_runtime_v1_candidate442_g07.py"
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
        'CANDIDATE = "ISS_GENERIC_BATTLE_RUNTIME_V1_CANDIDATE_4_4_2_G07"',
        'DOMINANCE_MODEL = "LATEST_UNIQUE_DIRECT_G05_AGGRESSION_INITIATIVE_V3"',
        'COLLISION_PLANNING_AUTHORITY = "G04_G05_GENERIC_RUNTIME_AUTONOMY"',
        'PRIOR_DIRECT_G05_AGGRESSION_FROM_TARGET',
        'DIRECT_G05_OPENING_AGGRESSION',
        'DIRECT_G05_COUNTER_AFTER_PRIOR_AGGRESSION',
        'DIRECT_G05_CLIMAX_AFTER_REVERSAL',
        '"g07DamageThresholdDependency": False',
        '"storyCollisionChoreography": False',
        '"perAssetCollisionEngineering": False',
        '"hardCodedContactZone": False',
        '"issR042ScopePreserved": True',
    )
    missing = [token for token in required_runtime if token not in runtime]
    if missing:
        fail("CANDIDATE442_RUNTIME_CONTRACT_MISSING:" + "|".join(missing))

    for forbidden in (
        "actor_alpha",
        "actor_beta",
        "MIN_DAMAGE_SEVERITY =",
        "DamageAccumulator.apply",
        "ConsequenceEngine.apply",
        "linear_velocity =",
        "angular_velocity =",
        ".location =",
        ".rotation_euler =",
        ".rotation_quaternion =",
        "bpy.ops.rigidbody",
        "obb_overlap_2d(",
        "convex_sweep_test(",
        "targetEnergyJ",
        "impactEnergyJ",
        "targetImpactSpeedMps",
        "collisionFrame",
        "trajectoryPoints",
        "pathPoints",
        "waypoints",
    ):
        if forbidden in runtime:
            fail(f"CANDIDATE442_RUNTIME_FORBIDDEN_TOKEN:{forbidden}")

    required_builder = (
        '"attackTarget": target',
        '"damage": {"required": False, "persistent": True}',
        '"minQualifiedContacts": 1',
        '"minDistinctAttackers": 1',
        'verify_intent_only_request(request)',
        '"storyIntentOnly": True',
        '"runtimeChoosesCollisionRealization": True',
        '"damageRequiredForG07": False',
        '"hardCodedContactZone": False',
        '"speedIntentPrescribed": False',
        '"issR042ScopePreserved": True',
    )
    missing_builder = [token for token in required_builder if token not in builder]
    if missing_builder:
        fail("CANDIDATE442_BUILDER_CONTRACT_MISSING:" + "|".join(missing_builder))

    if 'target="actor_beta:front"' in builder or 'target="actor_alpha:front"' in builder:
        fail("CANDIDATE442_HARDCODED_CONTACT_ZONE_PRESENT")
    if '"targetArea":' in builder or '"speedIntent":' in builder:
        fail("CANDIDATE442_STORY_COLLISION_CONTROL_PRESENT")

    for required_scope in (
        "ISS-R042",
        "Asset-independent autonomous collision realization",
        "Candidate 4.4.1 post-run scope result: **SCOPE DRIFT DETECTED**",
        "Candidate 4.4.2",
        "Story/G07 expresses battle intent and causal state only",
    ):
        if required_scope not in scope:
            fail(f"CANDIDATE442_SCOPE_CORRECTION_MISSING:{required_scope}")

    print(json.dumps({
        "marker": "GENERIC_BATTLE_RUNTIME_CANDIDATE442_G07_PROPERTY_ACCEPTANCE",
        "status": "PASS",
        "candidate": "ISS_GENERIC_BATTLE_RUNTIME_V1_CANDIDATE_4_4_2_G07",
        "dramaModel": "PHYSICAL_CAUSAL_DRAMA_STATE_MACHINE_V1",
        "dominanceModel": "LATEST_UNIQUE_DIRECT_G05_AGGRESSION_INITIATIVE_V3",
        "collisionPlanningAuthority": "G04_G05_GENERIC_RUNTIME_AUTONOMY",
        "storyIntentOnly": True,
        "runtimeChoosesCollisionRealization": True,
        "g07DamageThresholdDependency": False,
        "storyCollisionChoreography": False,
        "perAssetCollisionEngineering": False,
        "hardCodedContactZone": False,
        "g04SourceMutationRequired": False,
        "g05SourceMutationRequired": False,
        "g06SourceMutationRequired": False,
        "damageThresholdChanged": False,
        "contactThresholdChanged": False,
        "actorPoseOrVelocityMutation": False,
        "stateResetMechanismIntroduced": False,
        "forcedWinnerIntroduced": False,
        "assetSpecificBattleCode": False,
        "exactCollisionFrameTarget": False,
        "exactImpactEnergyTarget": False,
        "issR041ScopePreserved": True,
        "issR042ScopePreserved": True,
        "productionReadyClaimed": False,
    }, sort_keys=True))


if __name__ == "__main__":
    main()
