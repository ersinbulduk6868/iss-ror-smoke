#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import validate_generic_battle_runtime_v1_candidate442_result as base

EXPECTED_RUNTIME = "ISS_GENERIC_BATTLE_RUNTIME_V1_CANDIDATE_4_4_3_G07"
EXPECTED_ENGAGEMENT_MODEL = "LIVE_GEOMETRY_SEMANTIC_ENGAGEMENT_RESOLVER_V1"
_ORIGINAL_VALIDATE_DRAMA = base.validate_drama

base.EXPECTED_RUNTIME = EXPECTED_RUNTIME


def require(condition: bool, code: str) -> None:
    if not condition:
        raise base.ValidationError(code)


def validate_drama_443(drama: dict[str, Any], label: str) -> dict[str, Any]:
    result = _ORIGINAL_VALIDATE_DRAMA(drama, label)
    require(drama.get("engagementTargetingModel") == EXPECTED_ENGAGEMENT_MODEL, f"{label}:ENGAGEMENT_MODEL_MISMATCH:{drama.get('engagementTargetingModel')}")
    require(drama.get("runtimeSelectedSemanticEngagement") is True, f"{label}:RUNTIME_SEMANTIC_ENGAGEMENT_NOT_PROVEN")
    require(drama.get("storyTargetZonePrescribed") is False, f"{label}:STORY_TARGET_ZONE_PRESCRIBED")
    require(drama.get("hardCodedSemanticZone") is False, f"{label}:HARDCODED_SEMANTIC_ZONE")
    require(drama.get("semanticSelectionFromLiveGeometry") is True, f"{label}:LIVE_GEOMETRY_SELECTION_NOT_PROVEN")
    require(drama.get("perAssetCollisionEngineering") is False, f"{label}:PER_ASSET_COLLISION_ENGINEERING")
    require(drama.get("g04SourceChangedForEngagement") is False, f"{label}:G04_SOURCE_CHANGED_FOR_ENGAGEMENT")
    require(drama.get("g05SourceChangedForEngagement") is False, f"{label}:G05_SOURCE_CHANGED_FOR_ENGAGEMENT")
    require(drama.get("g06SourceChangedForEngagement") is False, f"{label}:G06_SOURCE_CHANGED_FOR_ENGAGEMENT")

    selections = drama.get("engagementSurfaceSelections") or []
    require(bool(selections), f"{label}:ENGAGEMENT_SELECTION_EVIDENCE_EMPTY")
    selected_events = {str(row.get("eventId") or "") for row in selections if isinstance(row, dict)}
    for event_id in ("evt-escalation", "evt-counterattack", "evt-climax"):
        require(event_id in selected_events, f"{label}:ENGAGEMENT_SELECTION_MISSING:{event_id}")
    for row in selections:
        require(row.get("model") == EXPECTED_ENGAGEMENT_MODEL, f"{label}:SELECTION_MODEL_MISMATCH")
        require(row.get("selectionAuthority") == "LIVE_TARGET_GEOMETRY_AND_AVAILABLE_ASSET_SEMANTICS", f"{label}:SELECTION_AUTHORITY_INVALID")
        require(row.get("storyTargetZonePrescribed") is False, f"{label}:SELECTION_STORY_ZONE_PRESCRIBED")
        require(row.get("assetSpecificBranch") is False, f"{label}:SELECTION_ASSET_BRANCH")
        require(bool(str(row.get("selectedSemanticZone") or "")), f"{label}:SELECTED_ZONE_EMPTY")
        require(int(row.get("candidateZoneCount") or 0) >= 1, f"{label}:CANDIDATE_ZONE_COUNT_INVALID")

    result.update({
        "engagementSelectionCount": len(selections),
        "selectedEventCount": len(selected_events),
        "runtimeSelectedSemanticEngagement": True,
        "storyTargetZonePrescribed": False,
        "semanticSelectionFromLiveGeometry": True,
    })
    return result


base.validate_drama = validate_drama_443


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--bugatti-evidence", required=True)
    parser.add_argument("--bugatti-drama", required=True)
    parser.add_argument("--generic-evidence", required=True)
    parser.add_argument("--generic-drama", required=True)
    args = parser.parse_args()

    bugatti = base.validate_one(
        base.load(Path(args.bugatti_evidence)),
        base.load(Path(args.bugatti_drama)),
        base.EXPECTED_BUGATTI_SHA,
        "EXACT_BUGATTI",
    )
    generic = base.validate_one(
        base.load(Path(args.generic_evidence)),
        base.load(Path(args.generic_drama)),
        base.EXPECTED_GENERIC_SHA,
        "GENERIC_HYPERCAR",
    )

    print(json.dumps({
        "marker": "GENERIC_BATTLE_RUNTIME_CANDIDATE443_G07_MACHINE_ACCEPTANCE",
        "status": "PASS",
        "runtime": EXPECTED_RUNTIME,
        "dramaModel": base.EXPECTED_DRAMA_MODEL,
        "dominanceModel": base.EXPECTED_DOMINANCE_MODEL,
        "collisionPlanningAuthority": base.EXPECTED_COLLISION_AUTHORITY,
        "engagementTargetingModel": EXPECTED_ENGAGEMENT_MODEL,
        "g04Preserved": True,
        "g05Preserved": True,
        "g06Preserved": True,
        "g07BattleStateMachineDramaticCausalProgression": True,
        "storyIntentOnly": True,
        "storyTargetActorOnly": True,
        "storyTargetZonePrescribed": False,
        "runtimeChoosesCollisionRealization": True,
        "runtimeSelectedSemanticEngagement": True,
        "semanticSelectionFromLiveGeometry": True,
        "g07DamageThresholdDependency": False,
        "perAssetCollisionEngineering": False,
        "issR041ScopePreserved": True,
        "issR042ScopePreserved": True,
        "exactBugatti": bugatti,
        "genericHypercar": generic,
        "productionReadyClaimed": False,
    }, sort_keys=True))


if __name__ == "__main__":
    main()
