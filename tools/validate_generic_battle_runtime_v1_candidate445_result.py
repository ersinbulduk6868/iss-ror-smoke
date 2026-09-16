#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import validate_generic_battle_runtime_v1_candidate443_result as prev

EXPECTED_RUNTIME = "ISS_GENERIC_BATTLE_RUNTIME_V1_CANDIDATE_4_4_5_G07"
EXPECTED_RECEIPT_ADMISSION_MODEL = "G07_AWAITING_G05_PHYSICAL_RECEIPT_V1"

prev.EXPECTED_RUNTIME = EXPECTED_RUNTIME
prev.base.EXPECTED_RUNTIME = EXPECTED_RUNTIME
_ORIGINAL_VALIDATE_DRAMA = prev.validate_drama_443


def require(condition: bool, code: str) -> None:
    if not condition:
        raise prev.base.ValidationError(code)


def validate_drama_445(drama: dict[str, Any], label: str) -> dict[str, Any]:
    result = _ORIGINAL_VALIDATE_DRAMA(drama, label)
    require(drama.get("receiptAdmissionModel") == EXPECTED_RECEIPT_ADMISSION_MODEL, f"{label}:RECEIPT_ADMISSION_MODEL_MISMATCH:{drama.get('receiptAdmissionModel')}")
    require(drama.get("physicalReceiptPendingAdmission") is True, f"{label}:PHYSICAL_RECEIPT_PENDING_ADMISSION_NOT_PROVEN")
    require(int(drama.get("g05SolverWindowFramesConsumed") or 0) > 0, f"{label}:G05_SOLVER_WINDOW_NOT_CONSUMED")
    require(drama.get("g07OwnsOnlyEventAdmission") is True, f"{label}:G07_NOT_EVENT_ADMISSION_ONLY")
    require(drama.get("g04ControlLawChanged") is False, f"{label}:G04_CONTROL_LAW_CHANGED")
    require(drama.get("g04AutonomySourceChangedForReceiptAdmission") is False, f"{label}:G04_SOURCE_CHANGED_FOR_RECEIPT_ADMISSION")
    require(drama.get("g05ContactAuthorityChanged") is False, f"{label}:G05_CONTACT_AUTHORITY_CHANGED")
    require(drama.get("g05SourceChangedForReceiptAdmission") is False, f"{label}:G05_SOURCE_CHANGED_FOR_RECEIPT_ADMISSION")
    require(drama.get("g06DamagePersistenceChanged") is False, f"{label}:G06_DAMAGE_PERSISTENCE_CHANGED")
    require(drama.get("g06SourceChangedForReceiptAdmission") is False, f"{label}:G06_SOURCE_CHANGED_FOR_RECEIPT_ADMISSION")
    require(drama.get("storyCollisionChoreography") is False, f"{label}:STORY_COLLISION_CHOREOGRAPHY")
    require(drama.get("perAssetCollisionEngineering") is False, f"{label}:PER_ASSET_COLLISION_ENGINEERING")
    require(drama.get("issR043ScopePreflightPreserved") is True, f"{label}:ISS_R043_PREFLIGHT_NOT_PRESERVED")
    require(int(drama.get("receiptWaitsOpenAtOutcome") or 0) == 0, f"{label}:RECEIPT_WAIT_LEFT_OPEN_AT_OUTCOME")

    transitions = drama.get("receiptWaitTransitions") or []
    require(bool(transitions), f"{label}:RECEIPT_WAIT_TRANSITIONS_EMPTY")
    started = [row for row in transitions if isinstance(row, dict) and row.get("stage") == "AWAITING_G05_PHYSICAL_RECEIPT"]
    observed = [row for row in transitions if isinstance(row, dict) and row.get("stage") == "G05_RECEIPT_OBSERVED"]
    require(bool(started), f"{label}:RECEIPT_WAIT_NEVER_STARTED")
    require(bool(observed), f"{label}:G05_RECEIPT_NOT_OBSERVED_AFTER_WAIT")
    for row in transitions:
        if not isinstance(row, dict):
            continue
        require(row.get("model") == EXPECTED_RECEIPT_ADMISSION_MODEL, f"{label}:RECEIPT_WAIT_MODEL_MISMATCH")
        require(bool(str(row.get("eventId") or "")), f"{label}:RECEIPT_WAIT_EVENT_EMPTY")
        require(bool(str(row.get("actorId") or "")), f"{label}:RECEIPT_WAIT_ACTOR_EMPTY")

    result.update({
        "receiptWaitStartCount": len(started),
        "receiptObservedCount": len(observed),
        "receiptAdmissionModel": EXPECTED_RECEIPT_ADMISSION_MODEL,
        "g07OwnsOnlyEventAdmission": True,
        "g04ControlLawChanged": False,
        "g05ContactAuthorityChanged": False,
        "g06DamagePersistenceChanged": False,
    })
    return result


prev.base.validate_drama = validate_drama_445


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--bugatti-evidence", required=True)
    parser.add_argument("--bugatti-drama", required=True)
    parser.add_argument("--generic-evidence", required=True)
    parser.add_argument("--generic-drama", required=True)
    args = parser.parse_args()

    bugatti = prev.base.validate_one(
        prev.base.load(Path(args.bugatti_evidence)),
        prev.base.load(Path(args.bugatti_drama)),
        prev.base.EXPECTED_BUGATTI_SHA,
        "EXACT_BUGATTI",
    )
    generic = prev.base.validate_one(
        prev.base.load(Path(args.generic_evidence)),
        prev.base.load(Path(args.generic_drama)),
        prev.base.EXPECTED_GENERIC_SHA,
        "GENERIC_HYPERCAR",
    )

    print(json.dumps({
        "marker": "GENERIC_BATTLE_RUNTIME_CANDIDATE445_G07_MACHINE_ACCEPTANCE",
        "status": "PASS",
        "runtime": EXPECTED_RUNTIME,
        "dramaModel": prev.base.EXPECTED_DRAMA_MODEL,
        "dominanceModel": prev.base.EXPECTED_DOMINANCE_MODEL,
        "collisionPlanningAuthority": prev.base.EXPECTED_COLLISION_AUTHORITY,
        "engagementTargetingModel": prev.EXPECTED_ENGAGEMENT_MODEL,
        "receiptAdmissionModel": EXPECTED_RECEIPT_ADMISSION_MODEL,
        "g04Preserved": True,
        "g05Preserved": True,
        "g06Preserved": True,
        "g07BattleStateMachineDramaticCausalProgression": True,
        "g07OwnsOnlyEventAdmission": True,
        "storyIntentOnly": True,
        "storyTargetActorOnly": True,
        "storyTargetZonePrescribed": False,
        "runtimeChoosesCollisionRealization": True,
        "runtimeSelectedSemanticEngagement": True,
        "perAssetCollisionEngineering": False,
        "g04ControlLawChanged": False,
        "g05ContactAuthorityChanged": False,
        "g06DamagePersistenceChanged": False,
        "issR041ScopePreserved": True,
        "issR042ScopePreserved": True,
        "issR043ScopePreflightPreserved": True,
        "issR044UserPostflightApprovalRequired": True,
        "gateClosed": False,
        "exactBugatti": bugatti,
        "genericHypercar": generic,
        "productionReadyClaimed": False,
    }, sort_keys=True))


if __name__ == "__main__":
    main()
