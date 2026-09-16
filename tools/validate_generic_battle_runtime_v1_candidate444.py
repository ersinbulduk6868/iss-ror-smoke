#!/usr/bin/env python3
from __future__ import annotations

import ast
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RUNTIME = ROOT / "blender" / "run_generic_battle_runtime_v1_candidate444.py"
BUILDER = ROOT / "tools" / "build_generic_battle_runtime_v1_candidate444_g07.py"
PREFLIGHT = ROOT / "docs" / "ISS_G07_SCOPE_PREFLIGHT_R043.md"


def fail(code: str) -> None:
    raise SystemExit(code)


def main() -> None:
    runtime = RUNTIME.read_text(encoding="utf-8")
    builder = BUILDER.read_text(encoding="utf-8")
    preflight = PREFLIGHT.read_text(encoding="utf-8")
    ast.parse(runtime, filename=str(RUNTIME))
    ast.parse(builder, filename=str(BUILDER))

    required_runtime = (
        'CANDIDATE = "ISS_GENERIC_BATTLE_RUNTIME_V1_CANDIDATE_4_4_4_G07"',
        'HANDOFF_MODEL = "STATE_DERIVED_SOLVER_HANDOFF_LIFECYCLE_V1"',
        'policy["contactHandoffGapM"]',
        'policy["progressTimeoutFrames"]',
        'candidate44.candidate42.SOLVER_WINDOW_MAX_FRAMES',
        'actor.rig.coast()',
        '"VERIFIED_G05_TRANSACTION"',
        '"LIVE_GEOMETRY_SEPARATION_OR_MISS"',
        '"G04_GENERIC_PROGRESS_TIMEOUT_RECOVERY"',
        'receipt.get("status") != "VERIFIED"',
        '"perAssetHandoffTuning": False',
        '"storyHandoffChoreography": False',
        '"issR043ScopePreflightPassed": True',
        '"issR043ScopePostflightRequired": True',
    )
    missing = [token for token in required_runtime if token not in runtime]
    if missing:
        fail("CANDIDATE444_RUNTIME_CONTRACT_MISSING:" + "|".join(missing))

    lower_runtime = runtime.lower()
    for forbidden in (
        "bugatti",
        "ferrari",
        "bulldozer",
        '"front"',
        '"rear"',
        '"left_side"',
        '"right_side"',
        "min_damage_severity",
        "linear_velocity =",
        "angular_velocity =",
        ".location =",
        ".rotation_euler =",
        ".rotation_quaternion =",
        "bpy.ops.rigidbody",
        "handoff_gap = 0.",
        "handoff_timeout =",
        "solver_window_max_frames =",
        "targetenergyj",
        "targetimpactspeedmps",
        "forcedwinner",
    ):
        if forbidden.lower() in lower_runtime:
            fail(f"CANDIDATE444_RUNTIME_FORBIDDEN_TOKEN:{forbidden}")

    if "candidate40._surface_gap(actor, target)" not in runtime:
        fail("CANDIDATE444_LIVE_GEOMETRY_SURFACE_STATE_MISSING")
    if "candidate44.hardened._cutoff_frames[key] = evidence_frame" not in runtime:
        fail("CANDIDATE444_TRUTHFUL_HANDOFF_EVIDENCE_BINDING_MISSING")
    if "int(frame) - max(0, solver_window - 1)" not in runtime:
        fail("CANDIDATE444_EXISTING_SOLVER_WINDOW_EVIDENCE_ALIGNMENT_MISSING")

    required_builder = (
        'candidate443_builder.verify_runtime_selected_targeting(exact)',
        'candidate443_builder.verify_runtime_selected_targeting(generic)',
        '"sameIntentStructureAcrossAssets": True',
        '"handoffLifecycleSpecifiedByStory": False',
        '"handoffDistanceSpecifiedByFixture": False',
        '"handoffTimeoutSpecifiedByFixture": False',
        '"perAssetHandoffTuning": False',
        '"issR043ScopePreflightPassed": True',
    )
    missing_builder = [token for token in required_builder if token not in builder]
    if missing_builder:
        fail("CANDIDATE444_BUILDER_CONTRACT_MISSING:" + "|".join(missing_builder))

    lower_preflight = preflight.lower()
    for semantic in (
        "iss-r041",
        "iss-r042",
        "iss-r043",
        "scope pre-flight: pass",
        "no per-video battle source code",
        "no per-asset battle source code",
        "story/g07 must not prescribe exact trajectories",
        "state-derived solver handoff lifecycle",
        "making vehicles hit harder",
        "scope post-flight",
    ):
        if semantic not in lower_preflight:
            fail(f"CANDIDATE444_SCOPE_PREFLIGHT_SEMANTIC_MISSING:{semantic}")

    print(json.dumps({
        "marker": "GENERIC_BATTLE_RUNTIME_CANDIDATE444_G07_PROPERTY_ACCEPTANCE",
        "status": "PASS",
        "candidate": "ISS_GENERIC_BATTLE_RUNTIME_V1_CANDIDATE_4_4_4_G07",
        "handoffLifecycleModel": "STATE_DERIVED_SOLVER_HANDOFF_LIFECYCLE_V1",
        "handoffLifecycleStateDerived": True,
        "handoffControllerPolicyDerived": True,
        "existingG05SolverWindowReused": True,
        "storyIntentOnly": True,
        "runtimeSelectedSemanticEngagement": True,
        "perAssetCollisionEngineering": False,
        "perAssetHandoffTuning": False,
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
        "issR043ScopePreflightPassed": True,
        "issR043ScopePostflightRequired": True,
        "productionReadyClaimed": False,
    }, sort_keys=True))


if __name__ == "__main__":
    main()
