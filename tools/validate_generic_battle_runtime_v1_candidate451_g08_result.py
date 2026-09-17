#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


def load(path: str) -> dict[str, Any]:
    value = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise SystemExit(f"G08_C451_JSON_OBJECT_REQUIRED:{path}")
    return value


def require(condition: bool, code: str) -> None:
    if not condition:
        raise SystemExit(code)


def base_pass(data: dict[str, Any], name: str) -> dict[str, Any]:
    require(data.get("success") is True, f"G08_C451_{name}_BASE_RUNTIME_NOT_SUCCESS")
    program = data.get("program") or {}
    impacts = data.get("impacts") or []
    require(isinstance(program, dict), f"G08_C451_{name}_BASE_PROGRAM_INVALID")
    require(isinstance(impacts, list), f"G08_C451_{name}_BASE_IMPACTS_INVALID")
    actor_count = int(program.get("actorCount") or 0)
    event_count = int(program.get("eventCount") or 0)
    impact_count = len(impacts)
    require(actor_count >= 2, f"G08_C451_{name}_BASE_ACTOR_COUNT_INVALID")
    require(event_count >= 1, f"G08_C451_{name}_BASE_EVENT_COUNT_INVALID")
    require(impact_count >= 1, f"G08_C451_{name}_BASE_IMPACT_MISSING")
    return {"success": True, "actorCount": actor_count, "eventCount": event_count, "impactCount": impact_count}


def drama_pass(data: dict[str, Any], name: str) -> dict[str, Any]:
    require(data.get("status") == "COMPLETE", f"G08_C451_{name}_G07_NOT_COMPLETE")
    direct = data.get("directTransactions") or []
    require(isinstance(direct, list), f"G08_C451_{name}_DIRECT_TRANSACTIONS_INVALID")
    require(len(direct) >= 2, f"G08_C451_{name}_DIRECT_TRANSACTIONS_INSUFFICIENT")
    for key in ("reversal", "climax", "payoff"):
        require(isinstance(data.get(key), dict), f"G08_C451_{name}_{key.upper()}_MISSING")
    require(data.get("g04ControlLawChanged") is False, f"G08_C451_{name}_G04_DRIFT")
    require(data.get("g05ContactAuthorityChanged") is False, f"G08_C451_{name}_G05_DRIFT")
    require(data.get("g06DamagePersistenceChanged") is False, f"G08_C451_{name}_G06_DRIFT")
    return {"status": "PASS", "directTransactionCount": len(direct), "reversalObserved": True, "climaxObserved": True, "payoffObserved": True}


def camera_pass(data: dict[str, Any], name: str) -> dict[str, Any]:
    require(data.get("model") == "ISS_EVENT_DRIVEN_CINEMATIC_CAMERA_DIRECTOR_V2", f"G08_C451_{name}_CAMERA_MODEL_INVALID")
    require(data.get("status") == "COMPLETE", f"G08_C451_{name}_CAMERA_INCOMPLETE")
    require(data.get("verticalShortsFrame") is True, f"G08_C451_{name}_NOT_VERTICAL")
    require(data.get("targetAspect9x16") is True, f"G08_C451_{name}_NOT_9X16")
    require(data.get("allRequiredCuesObserved") is True, f"G08_C451_{name}_CUES_INCOMPLETE")
    require(int(data.get("realImpactShotCount") or 0) >= 1, f"G08_C451_{name}_IMPACT_SHOT_MISSING")
    require(int(data.get("shotCount") or 0) >= 7, f"G08_C451_{name}_SHOT_COUNT_INSUFFICIENT")
    require(data.get("relationshipReadabilityPass") is True, f"G08_C451_{name}_RELATIONSHIP_READABILITY_FAIL")
    require(int(data.get("relationshipReadabilityFailureCount") or 0) == 0, f"G08_C451_{name}_RELATIONSHIP_FAILURE_COUNT_NONZERO")
    require(data.get("autoFrameModel") == "PORTRAIT_FULL_BOUNDS_AUTOFRAME_V1", f"G08_C451_{name}_AUTOFRAME_MODEL_INVALID")
    require(data.get("fullBoundsReadabilityModel") == "VERTICAL_FULL_BOUNDS_READABILITY_ORACLE_V2", f"G08_C451_{name}_FULL_BOUNDS_MODEL_INVALID")
    require(data.get("interpolationModel") == "AUTO_CLAMPED_BEZIER_CAMERA_PATH_V1", f"G08_C451_{name}_INTERPOLATION_MODEL_INVALID")
    require(data.get("portraitSensorFit") == "VERTICAL", f"G08_C451_{name}_SENSOR_FIT_INVALID")
    require(data.get("fullBoundsReadabilityPass") is True, f"G08_C451_{name}_FULL_BOUNDS_FAIL")
    require(int(data.get("fullBoundsReadabilityFailureCount") or 0) == 0, f"G08_C451_{name}_FULL_BOUNDS_FAILURE_COUNT_NONZERO")
    require(int(data.get("autoFrameFailureCount") or 0) == 0, f"G08_C451_{name}_AUTOFRAME_FAILURE")
    require(data.get("cameraInterpolationOvershootGuard") is True, f"G08_C451_{name}_INTERPOLATION_GUARD_MISSING")
    require(data.get("sourceAuthority") == "READ_ONLY_REALIZED_WORLD_AND_G07_EVENT_STATE", f"G08_C451_{name}_SOURCE_AUTHORITY_INVALID")
    require(data.get("cameraOnlyMutation") is True, f"G08_C451_{name}_CAMERA_ONLY_MISSING")
    require(data.get("actorPoseOrVelocityMutation") is False, f"G08_C451_{name}_ACTOR_MUTATION")
    require(data.get("physicsMutation") is False, f"G08_C451_{name}_PHYSICS_MUTATION")
    require(data.get("g04ControlLawChanged") is False, f"G08_C451_{name}_G04_CHANGED")
    require(data.get("g05ContactAuthorityChanged") is False, f"G08_C451_{name}_G05_CHANGED")
    require(data.get("g06DamagePersistenceChanged") is False, f"G08_C451_{name}_G06_CHANGED")
    require(data.get("g07DramaAuthorityChanged") is False, f"G08_C451_{name}_G07_CHANGED")
    require(data.get("perAssetCameraBranch") is False, f"G08_C451_{name}_PER_ASSET_CAMERA")
    require(data.get("cameraFakesPhysics") is False, f"G08_C451_{name}_CAMERA_FAKES_PHYSICS")
    require(data.get("humanCinematicAcceptance") == "PENDING", f"G08_C451_{name}_HUMAN_REVIEW_PRECLAIM")
    require(data.get("gateClosed") is False, f"G08_C451_{name}_GATE_CLOSED_PRECLAIM")
    require(data.get("productionReadyClaimed") is False, f"G08_C451_{name}_PRODUCTION_READY_PRECLAIM")

    coverage = data.get("requiredCueCoverage") or {}
    for cue in ("HOOK", "ESCALATION", "COUNTERATTACK", "REVERSAL", "CLIMAX", "PAYOFF", "IMPACT"):
        require(int(coverage.get(cue) or 0) >= 1, f"G08_C451_{name}_CUE_MISSING:{cue}")

    shots = data.get("shots") or []
    require(isinstance(shots, list) and shots, f"G08_C451_{name}_SHOTS_MISSING")
    multi_actor = 0
    for row in shots:
        require(isinstance(row, dict), f"G08_C451_{name}_SHOT_ROW_INVALID")
        require(row.get("actorPoseOrVelocityMutation") is False, f"G08_C451_{name}_SHOT_ACTOR_MUTATION")
        require(row.get("physicsMutation") is False, f"G08_C451_{name}_SHOT_PHYSICS_MUTATION")
        require(row.get("perAssetCameraBranch") is False, f"G08_C451_{name}_SHOT_ASSET_BRANCH")
        readability = row.get("readability") or {}
        require(readability.get("model") == "VERTICAL_FULL_BOUNDS_READABILITY_ORACLE_V2", f"G08_C451_{name}_SHOT_READABILITY_MODEL_INVALID")
        if int(readability.get("relevantActorCount") or 0) >= 2:
            multi_actor += 1
            require(readability.get("fullBoundsReadable") is True, f"G08_C451_{name}_MULTI_ACTOR_FULL_BOUNDS_FAIL")
            require(readability.get("relationshipReadable") is True, f"G08_C451_{name}_MULTI_ACTOR_RELATIONSHIP_FAIL")
        autoframe = row.get("autoFrame") or {}
        require(autoframe.get("model") == "PORTRAIT_FULL_BOUNDS_AUTOFRAME_V1", f"G08_C451_{name}_SHOT_AUTOFRAME_MISSING")
        require(autoframe.get("fullBoundsReadable") is True, f"G08_C451_{name}_SHOT_AUTOFRAME_UNRESOLVED")

    require(multi_actor >= 1, f"G08_C451_{name}_MULTI_ACTOR_SHOT_MISSING")
    require(int(data.get("multiActorShotCount") or 0) == multi_actor, f"G08_C451_{name}_MULTI_ACTOR_COUNT_MISMATCH")

    return {
        "status": "PASS",
        "model": data.get("model"),
        "autoFrameModel": data.get("autoFrameModel"),
        "shotCount": int(data.get("shotCount") or 0),
        "multiActorShotCount": multi_actor,
        "realImpactShotCount": int(data.get("realImpactShotCount") or 0),
        "autoFrameAdjustedShotCount": int(data.get("autoFrameAdjustedShotCount") or 0),
        "maxAutoFrameIterationsObserved": int(data.get("maxAutoFrameIterationsObserved") or 0),
        "maxAutoFrameDistanceScaleObserved": float(data.get("maxAutoFrameDistanceScaleObserved") or 1.0),
        "fullBoundsReadabilityPass": True,
        "relationshipReadabilityPass": True,
        "verticalShortsFrame": True,
        "targetAspect9x16": True,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--bugatti-evidence", required=True)
    parser.add_argument("--bugatti-drama", required=True)
    parser.add_argument("--bugatti-camera", required=True)
    parser.add_argument("--generic-evidence", required=True)
    parser.add_argument("--generic-drama", required=True)
    parser.add_argument("--generic-camera", required=True)
    args = parser.parse_args()

    bugatti_base = base_pass(load(args.bugatti_evidence), "BUGATTI")
    generic_base = base_pass(load(args.generic_evidence), "GENERIC")
    bugatti_drama = drama_pass(load(args.bugatti_drama), "BUGATTI")
    generic_drama = drama_pass(load(args.generic_drama), "GENERIC")
    bugatti_camera = camera_pass(load(args.bugatti_camera), "BUGATTI")
    generic_camera = camera_pass(load(args.generic_camera), "GENERIC")
    require(bugatti_camera["model"] == generic_camera["model"], "G08_C451_CAMERA_MODEL_DIFFERS_ACROSS_ASSETS")
    require(bugatti_camera["autoFrameModel"] == generic_camera["autoFrameModel"], "G08_C451_AUTOFRAME_MODEL_DIFFERS_ACROSS_ASSETS")

    print(json.dumps({
        "marker": "GENERIC_BATTLE_RUNTIME_CANDIDATE451_G08_MACHINE_ACCEPTANCE",
        "status": "PASS",
        "runtime": "ISS_GENERIC_BATTLE_RUNTIME_V1_CANDIDATE_4_5_1_G08",
        "cameraModel": "ISS_EVENT_DRIVEN_CINEMATIC_CAMERA_DIRECTOR_V2",
        "autoFrameModel": "PORTRAIT_FULL_BOUNDS_AUTOFRAME_V1",
        "gateScope": "G08_EVENT_DRIVEN_CINEMATIC_CAMERA_ONLY",
        "exactBugatti": {"base": bugatti_base, "drama": bugatti_drama, "camera": bugatti_camera, "status": "PASS"},
        "genericHypercar": {"base": generic_base, "drama": generic_drama, "camera": generic_camera, "status": "PASS"},
        "sameCameraSourceAcrossAssets": True,
        "sameAutoFrameSourceAcrossAssets": True,
        "fullBoundsReadabilityRequired": True,
        "g04Preserved": True,
        "g05Preserved": True,
        "g06Preserved": True,
        "g07Preserved": True,
        "actorPoseOrVelocityMutation": False,
        "physicsMutation": False,
        "perAssetCameraBranch": False,
        "perAssetTuning": False,
        "cameraFakesPhysics": False,
        "verticalShortsComposition": True,
        "machineFramingAcceptance": "PASS",
        "humanCinematicAcceptance": "PENDING",
        "issR041ScopePreserved": True,
        "issR042ScopePreserved": True,
        "issR043ScopePreflightPreserved": True,
        "issR044UserPostflightApprovalRequired": True,
        "gateClosed": False,
        "productionReadyClaimed": False,
    }, sort_keys=True))


if __name__ == "__main__":
    main()
