#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import validate_generic_battle_runtime_v1_candidate443_result as candidate443

EXPECTED_RUNTIME = "ISS_GENERIC_BATTLE_RUNTIME_V1_CANDIDATE_4_4_4_G07"
EXPECTED_HANDOFF_MODEL = "STATE_DERIVED_SOLVER_HANDOFF_LIFECYCLE_V1"
_ORIGINAL_VALIDATE_DRAMA_443 = candidate443.validate_drama_443

candidate443.EXPECTED_RUNTIME = EXPECTED_RUNTIME
candidate443.base.EXPECTED_RUNTIME = EXPECTED_RUNTIME


def require(condition: bool, code: str) -> None:
    if not condition:
        raise candidate443.base.ValidationError(code)


def validate_drama_444(drama: dict[str, Any], label: str) -> dict[str, Any]:
    result = _ORIGINAL_VALIDATE_DRAMA_443(drama, label)

    require(drama.get("handoffLifecycleModel") == EXPECTED_HANDOFF_MODEL, f"{label}:HANDOFF_MODEL_MISMATCH:{drama.get('handoffLifecycleModel')}")
    require(drama.get("handoffLifecycleStateDerived") is True, f"{label}:HANDOFF_NOT_STATE_DERIVED")
    require(drama.get("handoffControllerPolicyDerived") is True, f"{label}:HANDOFF_POLICY_NOT_CONTROLLER_DERIVED")
    require(drama.get("handoffReleaseOnVerifiedG05") is True, f"{label}:HANDOFF_G05_RELEASE_NOT_ENABLED")
    require(drama.get("handoffReleaseOnLiveSeparationOrMiss") is True, f"{label}:HANDOFF_LIVE_MISS_RELEASE_NOT_ENABLED")
    require(drama.get("handoffReleaseOnGenericProgressTimeout") is True, f"{label}:HANDOFF_GENERIC_TIMEOUT_RELEASE_NOT_ENABLED")
    require(drama.get("handoffUsesExistingG05SolverWindow") is True, f"{label}:HANDOFF_EXISTING_SOLVER_WINDOW_NOT_PROVEN")
    require(drama.get("perAssetHandoffTuning") is False, f"{label}:PER_ASSET_HANDOFF_TUNING")
    require(drama.get("storyHandoffChoreography") is False, f"{label}:STORY_HANDOFF_CHOREOGRAPHY")
    require(drama.get("g04SourceChangedForHandoff") is False, f"{label}:G04_CHANGED_FOR_HANDOFF")
    require(drama.get("g05SourceChangedForHandoff") is False, f"{label}:G05_CHANGED_FOR_HANDOFF")
    require(drama.get("g06SourceChangedForHandoff") is False, f"{label}:G06_CHANGED_FOR_HANDOFF")
    require(drama.get("issR043ScopePreflightPassed") is True, f"{label}:R043_PREFLIGHT_NOT_PROVEN")
    require(drama.get("issR043ScopePostflightRequired") is True, f"{label}:R043_POSTFLIGHT_REQUIREMENT_MISSING")
    require(int(drama.get("unreleasedHandoffCountAtFinalEvidence") or 0) == 0, f"{label}:UNRELEASED_HANDOFF_AT_FINAL")

    history = drama.get("handoffHistory") or []
    require(bool(history), f"{label}:HANDOFF_HISTORY_EMPTY")
    opens = [row for row in history if isinstance(row, dict) and row.get("stage") == "OPENED"]
    releases = [row for row in history if isinstance(row, dict) and row.get("stage") == "RELEASED"]
    verified = [row for row in releases if row.get("reason") == "VERIFIED_G05_TRANSACTION"]
    require(len(opens) >= 3, f"{label}:HANDOFF_OPEN_COVERAGE_LOW:{len(opens)}")
    require(len(verified) >= 3, f"{label}:VERIFIED_G05_HANDOFF_RELEASE_COVERAGE_LOW:{len(verified)}")

    for row in opens:
        require(row.get("model") == EXPECTED_HANDOFF_MODEL, f"{label}:HANDOFF_OPEN_MODEL_MISMATCH")
        require(row.get("controllerPolicyDerived") is True, f"{label}:HANDOFF_OPEN_NOT_POLICY_DERIVED")
        require(float(row.get("contactHandoffGapM")) >= 0.0, f"{label}:HANDOFF_GAP_INVALID")
        require(int(row.get("progressTimeoutFrames")) >= 1, f"{label}:HANDOFF_TIMEOUT_INVALID")
    for row in verified:
        require(row.get("model") == EXPECTED_HANDOFF_MODEL, f"{label}:HANDOFF_RELEASE_MODEL_MISMATCH")
        require(row.get("contactAuthorityModel") == candidate443.base.EXPECTED_CONTACT_AUTHORITY, f"{label}:HANDOFF_RELEASE_G05_AUTHORITY_MISMATCH")

    reasons = drama.get("handoffReleaseReasons") or {}
    require(int(reasons.get("VERIFIED_G05_TRANSACTION") or 0) >= 3, f"{label}:VERIFIED_G05_RELEASE_REASON_COUNT_LOW")

    result.update({
        "handoffOpenCount": len(opens),
        "handoffReleaseCount": len(releases),
        "verifiedG05HandoffReleaseCount": len(verified),
        "handoffLifecycleStateDerived": True,
        "handoffControllerPolicyDerived": True,
        "perAssetHandoffTuning": False,
    })
    return result


candidate443.base.validate_drama = validate_drama_444


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--bugatti-evidence", required=True)
    parser.add_argument("--bugatti-drama", required=True)
    parser.add_argument("--generic-evidence", required=True)
    parser.add_argument("--generic-drama", required=True)
    args = parser.parse_args()

    bugatti = candidate443.base.validate_one(
        candidate443.base.load(Path(args.bugatti_evidence)),
        candidate443.base.load(Path(args.bugatti_drama)),
        candidate443.base.EXPECTED_BUGATTI_SHA,
        "EXACT_BUGATTI",
    )
    generic = candidate443.base.validate_one(
        candidate443.base.load(Path(args.generic_evidence)),
        candidate443.base.load(Path(args.generic_drama)),
        candidate443.base.EXPECTED_GENERIC_SHA,
        "GENERIC_HYPERCAR",
    )

    print(json.dumps({
        "marker": "GENERIC_BATTLE_RUNTIME_CANDIDATE444_G07_MACHINE_ACCEPTANCE",
        "status": "PASS",
        "runtime": EXPECTED_RUNTIME,
        "dramaModel": candidate443.base.EXPECTED_DRAMA_MODEL,
        "dominanceModel": candidate443.base.EXPECTED_DOMINANCE_MODEL,
        "collisionPlanningAuthority": candidate443.base.EXPECTED_COLLISION_AUTHORITY,
        "engagementTargetingModel": candidate443.EXPECTED_ENGAGEMENT_MODEL,
        "handoffLifecycleModel": EXPECTED_HANDOFF_MODEL,
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
        "handoffLifecycleStateDerived": True,
        "handoffControllerPolicyDerived": True,
        "g07DamageThresholdDependency": False,
        "perAssetCollisionEngineering": False,
        "perAssetHandoffTuning": False,
        "issR041ScopePreserved": True,
        "issR042ScopePreserved": True,
        "issR043ScopePreflightPassed": True,
        "issR043ScopePostflightRequired": True,
        "scopePostflightPassedClaimed": False,
        "exactBugatti": bugatti,
        "genericHypercar": generic,
        "productionReadyClaimed": False,
    }, sort_keys=True))


if __name__ == "__main__":
    main()
