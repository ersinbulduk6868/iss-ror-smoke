#!/usr/bin/env python3
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools import validate_generic_battle_runtime_v1 as base  # noqa: E402
from blender.iss_battle_runtime_contract import BattleCompiler, EventState  # noqa: E402
from blender.iss_battle_runtime_lifecycle import BattleLifecycle  # noqa: E402

HARDENED_PATH = "blender/iss_blender_battle_runtime_v1_hardened.py"


def configure_candidate3_static_contract() -> None:
    tokens = list(base.HARDENED_REQUIRED_TOKENS[HARDENED_PATH])
    old = 'RUNTIME_VERSION = "ISS_GENERIC_BATTLE_RUNTIME_V1_CANDIDATE_2_HARDENED"'
    new = 'RUNTIME_VERSION = "ISS_GENERIC_BATTLE_RUNTIME_V1_CANDIDATE_3_HARDENED"'
    tokens = [new if token == old else token for token in tokens]
    for required in (
        "predictiveCutoffMargin",
        "predictiveCutoff",
        "controllerAuthority",
    ):
        if required not in tokens:
            tokens.append(required)
    base.HARDENED_REQUIRED_TOKENS[HARDENED_PATH] = tuple(tokens)


def causal_dependency_properties() -> dict[str, object]:
    request, bindings = base.make_request(5)
    wave = request["battlePlan"]["events"][1]
    wave["physicsRequirements"]["minQualifiedContacts"] = 2
    wave["physicsRequirements"]["minDistinctAttackers"] = 2
    program = BattleCompiler.compile(request, bindings)
    event = next(e for e in program.events if e.event_id == "evt_wave")
    state = EventState(event.event_id, status="ACTIVE")
    lifecycle = BattleLifecycle()

    first, second = event.attackers[:2]
    state.contact_count = 1
    state.damage_count = 1
    lifecycle.note_impact(event, first, damage_earned=True)
    if event.event_id in lifecycle.causally_resolved:
        raise base.ValidationError("CAUSAL_DEPENDENCY_RELEASED_AFTER_FIRST_OF_TWO_CONTACTS")
    if lifecycle.requirements_met(event, state):
        raise base.ValidationError("MULTI_CONTACT_EVENT_FALSE_SUCCESS_AFTER_ONE_CONTACT")

    state.contact_count = 2
    state.damage_count = 2
    lifecycle.note_impact(event, second, damage_earned=True)
    if event.event_id not in lifecycle.causally_resolved:
        raise base.ValidationError("CAUSAL_DEPENDENCY_NOT_RELEASED_AFTER_REQUIRED_EVIDENCE")
    if not lifecycle.requirements_met(event, state):
        raise base.ValidationError("MULTI_CONTACT_EVENT_REQUIREMENTS_NOT_MET")

    snapshot = lifecycle.snapshot()
    return {
        "status": "PASS",
        "minQualifiedContacts": 2,
        "minDistinctAttackers": 2,
        "causallyResolved": event.event_id in snapshot["causallyResolvedEvents"],
        "qualifiedContactCount": snapshot["qualifiedContactCounts"][event.event_id],
        "qualifiedAttackerCount": len(snapshot["qualifiedAttackers"][event.event_id]),
    }


def candidate3_runtime_contract() -> dict[str, object]:
    source = (ROOT / HARDENED_PATH).read_text(encoding="utf-8")
    required = (
        'ISS_GENERIC_BATTLE_RUNTIME_V1_CANDIDATE_3_HARDENED',
        'predictiveCutoffMargin',
        'predictiveCutoff',
        'CONTACT_REJECTED_CONTROLLER_AUTHORITY',
        'MIN_DAMAGE_SEVERITY = 0.055',
        'ForwardPreviewDirector',
    )
    missing = [token for token in required if token not in source]
    if missing:
        raise base.ValidationError("CANDIDATE3_RUNTIME_CONTRACT_MISSING:" + ",".join(missing))
    return {"status": "PASS", "requiredTokens": len(required)}


def main() -> None:
    configure_candidate3_static_contract()
    result = {
        "static": base.static_source_audit(),
        "compilerScale": base.compiler_scale_properties(),
        "failClosed": base.contract_fail_closed_properties(),
        "impactDamage": base.impact_damage_properties(),
        "lifecycle": base.lifecycle_properties(),
        "causalDependency": causal_dependency_properties(),
        "candidate3Runtime": candidate3_runtime_contract(),
    }
    print(
        json.dumps(
            {
                "marker": "GENERIC_BATTLE_RUNTIME_CANDIDATE3_STATIC_VALIDATION",
                "status": "PASS",
                "result": result,
            },
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
