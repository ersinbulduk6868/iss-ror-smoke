#!/usr/bin/env python3
from __future__ import annotations

import ast
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RUNTIME = ROOT / "blender" / "run_generic_battle_runtime_v1_candidate44.py"
BUILDER = ROOT / "tools" / "build_generic_battle_runtime_v1_candidate44_g07.py"
AUDIT = ROOT / "docs" / "ISS_G07_FULL_AFFECTED_LAYER_AUDIT.md"


def fail(code: str) -> None:
    raise SystemExit(code)


def main() -> None:
    runtime = RUNTIME.read_text(encoding="utf-8")
    builder = BUILDER.read_text(encoding="utf-8")
    audit = AUDIT.read_text(encoding="utf-8")
    ast.parse(runtime, filename=str(RUNTIME))
    ast.parse(builder, filename=str(BUILDER))

    required_runtime = (
        'CANDIDATE = "ISS_GENERIC_BATTLE_RUNTIME_V1_CANDIDATE_4_4_G07"',
        'DRAMA_MODEL = "PHYSICAL_CAUSAL_DRAMA_STATE_MACHINE_V1"',
        'DOMINANCE_MODEL = "LATEST_UNIQUE_DIRECT_G05_DAMAGE_INITIATIVE_V1"',
        'receipt.get("status") != "VERIFIED"',
        'receipt.get("model") != candidate42.CONTACT_AUTHORITY',
        'row.get("nativeContactInheritedFromPhysicalTransaction") is True',
        'PRIOR_G05_G06_DAMAGE_FROM_TARGET',
        'CLIMAX_WAITS_FOR_PHYSICAL_DOMINANCE_REVERSAL',
        'PAYOFF_WAITS_FOR_CAUSAL_CLIMAX',
        'DOMINANCE_REVERSAL_COMEBACK_PHYSICALLY_EARNED',
        'G07_CAUSAL_DRAMA_EVIDENCE_WRITTEN',
        'g04AutonomySourceChanged": False',
        'g05ContactAuthoritySourceChanged": False',
        'g06PersistenceSourceChanged": False',
        'actorPoseOrVelocityMutation": False',
        'stateResetMechanismIntroduced": False',
        'forcedWinnerIntroduced": False',
        'productionReadyClaimed": False',
    )
    missing = [token for token in required_runtime if token not in runtime]
    if missing:
        fail("CANDIDATE44_REQUIRED_RUNTIME_CONTRACT_MISSING:" + "|".join(missing))

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
    ):
        if forbidden in runtime:
            fail(f"CANDIDATE44_RUNTIME_FORBIDDEN_TOKEN:{forbidden}")

    required_builder = (
        '"phase": "ESCALATION"',
        '"phase": "COUNTERATTACK"',
        '"phase": "CLIMAX"',
        '"phase": "PAYOFF"',
        '"minQualifiedContacts": 1',
        '"persistent": True',
        '"forcedWinner": False',
        '"exactCollisionFrameTarget": False',
        '"exactImpactEnergyTarget": False',
    )
    missing_builder = [token for token in required_builder if token not in builder]
    if missing_builder:
        fail("CANDIDATE44_FIXTURE_CONTRACT_MISSING:" + "|".join(missing_builder))

    lower_builder = builder.lower()
    for forbidden in (
        "collisionframe",
        "contactframe",
        "impactframe",
        "targetenergyj",
        "targetimpactspeedmps",
        "trajectorypoints",
        "positionkeyframes",
        "velocitykeyframes",
        "winnerid",
    ):
        # Forbidden words are allowed only inside the explicit rejection list.
        occurrences = lower_builder.count(forbidden)
        if occurrences > 1:
            fail(f"CANDIDATE44_FIXTURE_FORBIDDEN_EXECUTABLE_FIELD:{forbidden}:{occurrences}")

    if "G07_CAUSAL_DRAMA_STATE_MACHINE_MISSING" not in audit:
        fail("CANDIDATE44_AFFECTED_LAYER_AUDIT_MISSING_ROOT_GAP")

    print(json.dumps({
        "marker": "GENERIC_BATTLE_RUNTIME_CANDIDATE44_G07_PROPERTY_ACCEPTANCE",
        "status": "PASS",
        "candidate": "ISS_GENERIC_BATTLE_RUNTIME_V1_CANDIDATE_4_4_G07",
        "dramaModel": "PHYSICAL_CAUSAL_DRAMA_STATE_MACHINE_V1",
        "dominanceModel": "LATEST_UNIQUE_DIRECT_G05_DAMAGE_INITIATIVE_V1",
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
        "productionReadyClaimed": False,
    }, sort_keys=True))


if __name__ == "__main__":
    main()
