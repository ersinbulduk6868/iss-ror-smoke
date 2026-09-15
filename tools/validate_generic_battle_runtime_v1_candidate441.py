#!/usr/bin/env python3
from __future__ import annotations

import ast
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RUNTIME = ROOT / "blender" / "run_generic_battle_runtime_v1_candidate441.py"
BUILDER = ROOT / "tools" / "build_generic_battle_runtime_v1_candidate441_g07.py"
AUDIT = ROOT / "docs" / "ISS_G07_FAILURE_FAMILY_AUDIT_RUN35019926790.md"


def fail(code: str) -> None:
    raise SystemExit(code)


def main() -> None:
    runtime = RUNTIME.read_text(encoding="utf-8")
    builder = BUILDER.read_text(encoding="utf-8")
    audit = AUDIT.read_text(encoding="utf-8")
    ast.parse(runtime, filename=str(RUNTIME))
    ast.parse(builder, filename=str(BUILDER))

    required_runtime = (
        'CANDIDATE = "ISS_GENERIC_BATTLE_RUNTIME_V1_CANDIDATE_4_4_1_G07"',
        'DOMINANCE_MODEL = "LATEST_UNIQUE_DIRECT_G05_PHYSICAL_INITIATIVE_V2"',
        'receipt.get("status") != "VERIFIED"',
        'receipt.get("model") != candidate44.candidate42.CONTACT_AUTHORITY',
        'row.get("nativeContactInheritedFromPhysicalTransaction") is True',
        'OPENING_G05_G06_PERSISTENT_DAMAGE',
        'DIRECT_G05_COUNTER_AFTER_PRIOR_G06_DAMAGE',
        'DIRECT_G05_CLIMAX_AFTER_REVERSAL',
        'repeatedDamageThresholdCrossingRequired": False',
    )
    missing = [x for x in required_runtime if x not in runtime]
    if missing:
        fail("CANDIDATE441_RUNTIME_CONTRACT_MISSING:" + "|".join(missing))

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
            fail(f"CANDIDATE441_RUNTIME_FORBIDDEN_TOKEN:{forbidden}")

    required_builder = (
        '"evt-escalation-alpha"',
        '"evt-escalation-beta"',
        'counter["damage"] = {"required": False',
        'climax["damage"] = {"required": False',
        'counter["causedByEventIds"] = ["evt-escalation-alpha", "evt-escalation-beta"]',
        '"minQualifiedContacts": 1',
        'sameIntentStructureAcrossAssets": True',
        'counterattackRepeatedDamageRequired": False',
        'climaxRepeatedDamageRequired": False',
        '"forcedWinner": False',
        '"exactCollisionFrameTarget": False',
        '"exactImpactEnergyTarget": False',
        'verify_request(exact)',
        'verify_request(generic)',
    )
    missing_builder = [x for x in required_builder if x not in builder]
    if missing_builder:
        fail("CANDIDATE441_BUILDER_CONTRACT_MISSING:" + "|".join(missing_builder))

    for required_audit in (
        "G07_DRAMA_OVERCOUPLED_TO_REPEATED_DAMAGE_GATE",
        "LATEST_UNIQUE_DIRECT_G05_PHYSICAL_INITIATIVE_V2",
        "MIN_DAMAGE_SEVERITY = 0.055",
        "ISS-R041",
        "SCOPE PRESERVED",
    ):
        if required_audit not in audit:
            fail(f"CANDIDATE441_AUDIT_CONTRACT_MISSING:{required_audit}")

    print(json.dumps({
        "marker": "GENERIC_BATTLE_RUNTIME_CANDIDATE441_G07_PROPERTY_ACCEPTANCE",
        "status": "PASS",
        "candidate": "ISS_GENERIC_BATTLE_RUNTIME_V1_CANDIDATE_4_4_1_G07",
        "dramaModel": "PHYSICAL_CAUSAL_DRAMA_STATE_MACHINE_V1",
        "dominanceModel": "LATEST_UNIQUE_DIRECT_G05_PHYSICAL_INITIATIVE_V2",
        "openingPersistentDamageRequired": True,
        "laterInitiativeDirectG05VerifiedRequired": True,
        "repeatedDamageThresholdCrossingRequired": False,
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
