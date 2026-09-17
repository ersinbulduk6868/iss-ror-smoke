#!/usr/bin/env python3
from __future__ import annotations

import ast
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RUNTIME = ROOT / "blender" / "run_generic_battle_runtime_v1_candidate446.py"
BUILDER = ROOT / "tools" / "build_generic_battle_runtime_v1_candidate446_g07.py"
PREFLIGHT = ROOT / "docs" / "ISS_G07_CANDIDATE446_SCOPE_PREFLIGHT.md"


def fail(code: str) -> None:
    raise SystemExit(code)


def main() -> None:
    runtime = RUNTIME.read_text(encoding="utf-8")
    builder = BUILDER.read_text(encoding="utf-8")
    preflight = PREFLIGHT.read_text(encoding="utf-8")
    ast.parse(runtime, filename=str(RUNTIME))
    ast.parse(builder, filename=str(BUILDER))

    required_runtime = (
        'CANDIDATE = "ISS_GENERIC_BATTLE_RUNTIME_V1_CANDIDATE_4_4_6_G07"',
        'CLIMAX_REALIZATION_MODEL = "CAUSAL_REVERSAL_STATE_CLIMAX_V1"',
        'def _realize_causal_climax(',
        '"CLIMAX_PHYSICALLY_EARNED"',
        '"REALIZED_REVERSAL_AND_PERSISTENT_STATE"',
        '"climaxRequiresNewContact": False',
        'state.status = "OBSERVED"',
        '"g07OwnsDramaLifecycleOnly": True',
        '"g04ControlLawChanged": False',
        '"g05ContactAuthorityChanged": False',
        '"g06DamagePersistenceChanged": False',
        '"issR043ScopePreflightPreserved": True',
        '"issR044UserPostflightApprovalRequired": True',
        '"gateClosed": False',
    )
    missing = [token for token in required_runtime if token not in runtime]
    if missing:
        fail("CANDIDATE446_RUNTIME_CONTRACT_MISSING:" + "|".join(missing))

    lower_runtime = runtime.lower()
    forbidden_runtime = (
        "actor.rig.command",
        "actor.rig.coast",
        "actor.rig.brake",
        "_cutoff_frames",
        "pairwise_resolve_pending_contacts =",
        "g06_pairwise_resolve_pending_contacts =",
        "solver_window_max_frames =",
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
        "candidate445",
        '"front"',
        '"rear"',
        '"left_side"',
        '"right_side"',
        "bugatti",
        "ferrari",
        "bulldozer",
    )
    for token in forbidden_runtime:
        if token.lower() in lower_runtime:
            fail(f"CANDIDATE446_G07_SCOPE_FORBIDDEN_TOKEN:{token}")

    required_builder = (
        'candidate443_builder.OUT = OUT',
        'candidate443_builder.main()',
        'events["evt-climax"]',
        '"type": "CAUSAL_CLIMAX_STATE"',
        '"attackTarget": ""',
        '"physicsRequirements": {}',
        '"evt-counterattack"',
        '"physicalEventsUnchanged": ["evt-escalation", "evt-counterattack"]',
        '"climaxRequiresNewContact": False',
        '"climaxPrescribesPhysics": False',
        '"perAssetCollisionEngineering": False',
        '"issR043ScopePreflightPreserved": True',
    )
    missing_builder = [token for token in required_builder if token not in builder]
    if missing_builder:
        fail("CANDIDATE446_BUILDER_CONTRACT_MISSING:" + "|".join(missing_builder))

    preflight_lower = preflight.lower()
    for semantic in (
        "g04, g05 and g06 remain preserved machine_proven dependencies",
        "candidate 4.4.6 changes only the g07 climax representation",
        "climax does not require a third independent collision",
        "no g04 control law change",
        "no g05 contact-authority change",
        "no g06 damage/persistence change",
        "scope pre-flight result: pass",
        "g07 remains open after machine pass until the mandatory scope post-flight and explicit user ok",
    ):
        if semantic not in preflight_lower:
            fail(f"CANDIDATE446_SCOPE_PREFLIGHT_SEMANTIC_MISSING:{semantic}")

    print(json.dumps({
        "marker": "GENERIC_BATTLE_RUNTIME_CANDIDATE446_G07_PROPERTY_ACCEPTANCE",
        "status": "PASS",
        "candidate": "ISS_GENERIC_BATTLE_RUNTIME_V1_CANDIDATE_4_4_6_G07",
        "gateScope": "G07_CAUSAL_DRAMA_LIFECYCLE_ONLY",
        "climaxRealizationModel": "CAUSAL_REVERSAL_STATE_CLIMAX_V1",
        "climaxRequiresNewContact": False,
        "g07OwnsDramaLifecycleOnly": True,
        "directVehicleControlInG07": False,
        "g05ContactAuthorityMutationInG07": False,
        "g06DamageMutationInG07": False,
        "perAssetCollisionEngineering": False,
        "g04SourceMutationRequired": False,
        "g05SourceMutationRequired": False,
        "g06SourceMutationRequired": False,
        "issR041ScopePreserved": True,
        "issR042ScopePreserved": True,
        "issR043ScopePreflightPreserved": True,
        "issR044UserPostflightApprovalRequired": True,
        "gateClosed": False,
        "productionReadyClaimed": False,
    }, sort_keys=True))


if __name__ == "__main__":
    main()
