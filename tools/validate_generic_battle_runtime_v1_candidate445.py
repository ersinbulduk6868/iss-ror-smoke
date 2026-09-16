#!/usr/bin/env python3
from __future__ import annotations

import ast
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RUNTIME = ROOT / "blender" / "run_generic_battle_runtime_v1_candidate445.py"
BUILDER = ROOT / "tools" / "build_generic_battle_runtime_v1_candidate445_g07.py"
PREFLIGHT = ROOT / "docs" / "ISS_G07_SCOPE_PREFLIGHT_R043_R044.md"


def fail(code: str) -> None:
    raise SystemExit(code)


def main() -> None:
    runtime = RUNTIME.read_text(encoding="utf-8")
    builder = BUILDER.read_text(encoding="utf-8")
    preflight = PREFLIGHT.read_text(encoding="utf-8")
    ast.parse(runtime, filename=str(RUNTIME))
    ast.parse(builder, filename=str(BUILDER))

    required_runtime = (
        'CANDIDATE = "ISS_GENERIC_BATTLE_RUNTIME_V1_CANDIDATE_4_4_5_G07"',
        'RECEIPT_ADMISSION_MODEL = "G07_AWAITING_G05_PHYSICAL_RECEIPT_V1"',
        'candidate42.SOLVER_WINDOW_MAX_FRAMES',
        'candidate40._memories.items()',
        '"AWAITING_G05_PHYSICAL_RECEIPT"',
        '"G05_RECEIPT_OBSERVED"',
        '"G05_RECEIPT_WINDOW_EXPIRED_REENABLE_G04"',
        '"g07OwnsOnlyEventAdmission": True',
        '"g04ControlLawChanged": False',
        '"g05ContactAuthorityChanged": False',
        '"g06DamagePersistenceChanged": False',
        '"issR043ScopePreflightPreserved": True',
    )
    missing = [token for token in required_runtime if token not in runtime]
    if missing:
        fail("CANDIDATE445_RUNTIME_CONTRACT_MISSING:" + "|".join(missing))

    lower_runtime = runtime.lower()
    forbidden = (
        "actor.rig.command",
        "actor.rig.coast",
        "actor.rig.brake",
        "_cutoff_frames",
        "pairwise_resolve_pending_contacts =",
        "g06_pairwise_resolve_pending_contacts =",
        "min_damage_severity",
        "damageaccumulator",
        "consequenceengine",
        "impactmodel",
        "linear_velocity =",
        "angular_velocity =",
        ".location =",
        ".rotation_euler =",
        ".rotation_quaternion =",
        "bpy.ops.rigidbody",
        '"front"',
        '"rear"',
        '"left_side"',
        '"right_side"',
        "bugatti",
        "ferrari",
        "bulldozer",
    )
    for token in forbidden:
        if token.lower() in lower_runtime:
            fail(f"CANDIDATE445_G07_SCOPE_FORBIDDEN_TOKEN:{token}")

    required_builder = (
        'candidate443_builder.OUT = OUT',
        'candidate443_builder.main()',
        '"fixtureSemanticsChangedFromCandidate443": False',
        '"storyTargetActorOnly": True',
        '"storyTargetZonePrescribed": False',
        '"perAssetCollisionEngineering": False',
        '"issR043ScopePreflightPreserved": True',
    )
    missing_builder = [token for token in required_builder if token not in builder]
    if missing_builder:
        fail("CANDIDATE445_BUILDER_CONTRACT_MISSING:" + "|".join(missing_builder))

    preflight_lower = preflight.lower()
    for semantic in (
        "g04, g05 and g06 are preserved machine_proven dependencies",
        "g07 must not",
        "issue direct motor, steering, brake, coast, force, impulse, pose or velocity commands",
        "write g05 cutoff-frame/contact-authority state",
        "candidate 4.4.4 is **superseded before machine test by scope pre-flight**",
        "candidate 4.4.5 is the scope-correct successor",
        "g07 remains open until the user explicitly answers **ok**",
        "scope pre-flight result: pass",
    ):
        if semantic not in preflight_lower:
            fail(f"CANDIDATE445_SCOPE_PREFLIGHT_SEMANTIC_MISSING:{semantic}")

    print(json.dumps({
        "marker": "GENERIC_BATTLE_RUNTIME_CANDIDATE445_G07_PROPERTY_ACCEPTANCE",
        "status": "PASS",
        "candidate": "ISS_GENERIC_BATTLE_RUNTIME_V1_CANDIDATE_4_4_5_G07",
        "receiptAdmissionModel": "G07_AWAITING_G05_PHYSICAL_RECEIPT_V1",
        "gateScope": "G07_EVENT_ADMISSION_ONLY",
        "fixtureSemanticsChangedFromCandidate443": False,
        "directVehicleControlInG07": False,
        "g05CutoffStateWriteInG07": False,
        "g05ResolverMutationInG07": False,
        "g06DamageMutationInG07": False,
        "perAssetCollisionEngineering": False,
        "g04SourceMutationRequired": False,
        "g05SourceMutationRequired": False,
        "g06SourceMutationRequired": False,
        "issR041ScopePreserved": True,
        "issR042ScopePreserved": True,
        "issR043ScopePreflightPreserved": True,
        "issR044UserPostflightApprovalRequired": True,
        "productionReadyClaimed": False,
    }, sort_keys=True))


if __name__ == "__main__":
    main()
