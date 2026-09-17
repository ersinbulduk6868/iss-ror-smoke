#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


def load(path: str) -> dict[str, Any]:
    value = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise SystemExit(f"G08_C452_JSON_OBJECT_REQUIRED:{path}")
    return value


def require(condition: bool, code: str) -> None:
    if not condition:
        raise SystemExit(code)


def base_pass(data: dict[str, Any], name: str) -> dict[str, Any]:
    require(data.get("success") is True, f"G08_C452_{name}_BASE_RUNTIME_NOT_SUCCESS")
    program = data.get("program") or {}
    impacts = data.get("impacts") or []
    require(int(program.get("actorCount") or 0) >= 2, f"G08_C452_{name}_BASE_ACTOR_COUNT_INVALID")
    require(int(program.get("eventCount") or 0) >= 1, f"G08_C452_{name}_BASE_EVENT_COUNT_INVALID")
    require(len(impacts) >= 1, f"G08_C452_{name}_BASE_IMPACT_MISSING")
    return {"status": "PASS", "actorCount": int(program.get("actorCount") or 0), "eventCount": int(program.get("eventCount") or 0), "impactCount": len(impacts)}


def drama_pass(data: dict[str, Any], name: str) -> dict[str, Any]:
    require(data.get("status") == "COMPLETE", f"G08_C452_{name}_G07_NOT_COMPLETE")
    direct = data.get("directTransactions") or []
    require(len(direct) >= 2, f"G08_C452_{name}_DIRECT_TRANSACTIONS_INSUFFICIENT")
    for key in ("reversal", "climax", "payoff"):
        require(isinstance(data.get(key), dict), f"G08_C452_{name}_{key.upper()}_MISSING")
    require(data.get("g04ControlLawChanged") is False, f"G08_C452_{name}_G04_DRIFT")
    require(data.get("g05ContactAuthorityChanged") is False, f"G08_C452_{name}_G05_DRIFT")
    require(data.get("g06DamagePersistenceChanged") is False, f"G08_C452_{name}_G06_DRIFT")
    return {"status": "PASS", "directTransactionCount": len(direct)}


def camera_pass(data: dict[str, Any], name: str) -> dict[str, Any]:
    require(data.get("cameraModelV4") == "ISS_EVENT_DRIVEN_CINEMATIC_CAMERA_DIRECTOR_V4", f"G08_C452_{name}_CAMERA_MODEL_INVALID")
    require(data.get("status") == "COMPLETE", f"G08_C452_{name}_CAMERA_INCOMPLETE")
    require(data.get("verticalShortsFrame") is True, f"G08_C452_{name}_NOT_VERTICAL")
    require(data.get("targetAspect9x16") is True, f"G08_C452_{name}_NOT_9X16")
    require(data.get("allRequiredCuesObserved") is True, f"G08_C452_{name}_CUES_INCOMPLETE")
    require(int(data.get("realImpactShotCount") or 0) >= 1, f"G08_C452_{name}_IMPACT_SHOT_MISSING")
    require(data.get("relationshipReadabilityPass") is True, f"G08_C452_{name}_RELATIONSHIP_READABILITY_FAIL")
    require(data.get("autoFrameModel") == "PORTRAIT_FULL_BOUNDS_AUTOFRAME_V1", f"G08_C452_{name}_AUTOFRAME_MODEL_INVALID")
    require(data.get("fullBoundsReadabilityPass") is True, f"G08_C452_{name}_FULL_BOUNDS_FAIL")
    require(int(data.get("autoFrameFailureCount") or 0) == 0, f"G08_C452_{name}_AUTOFRAME_FAILURE")
    require(data.get("cinematicSalienceModel") == "CUE_AWARE_VERTICAL_CINEMATIC_SALIENCE_V1", f"G08_C452_{name}_SALIENCE_MODEL_INVALID")
    require(data.get("cinematicSaliencePass") is True, f"G08_C452_{name}_CINEMATIC_SALIENCE_FAIL")
    require(int(data.get("cinematicSalienceFailureCount") or 0) == 0, f"G08_C452_{name}_SALIENCE_FAILURE_COUNT_NONZERO")
    per_cue = data.get("cinematicSaliencePerCue") or {}
    for cue in ("CLIMAX", "PAYOFF"):
        row = per_cue.get(cue) or {}
        require(row.get("pass") is True, f"G08_C452_{name}_{cue}_SALIENCE_FAIL")
        require(int(row.get("shotCount") or 0) >= 1, f"G08_C452_{name}_{cue}_SHOT_MISSING")
    require(data.get("sourceAuthority") == "READ_ONLY_REALIZED_WORLD_AND_G07_EVENT_STATE", f"G08_C452_{name}_SOURCE_AUTHORITY_INVALID")
    require(data.get("cameraOnlyMutation") is True, f"G08_C452_{name}_CAMERA_ONLY_MISSING")
    require(data.get("actorPoseOrVelocityMutation") is False, f"G08_C452_{name}_ACTOR_MUTATION")
    require(data.get("physicsMutation") is False, f"G08_C452_{name}_PHYSICS_MUTATION")
    require(data.get("g04ControlLawChanged") is False, f"G08_C452_{name}_G04_CHANGED")
    require(data.get("g05ContactAuthorityChanged") is False, f"G08_C452_{name}_G05_CHANGED")
    require(data.get("g06DamagePersistenceChanged") is False, f"G08_C452_{name}_G06_CHANGED")
    require(data.get("g07DramaAuthorityChanged") is False, f"G08_C452_{name}_G07_CHANGED")
    require(data.get("perAssetCameraBranch") is False, f"G08_C452_{name}_PER_ASSET_CAMERA")
    require(data.get("cameraFakesPhysics") is False, f"G08_C452_{name}_CAMERA_FAKES_PHYSICS")
    require(data.get("humanCinematicAcceptance") == "PENDING", f"G08_C452_{name}_HUMAN_REVIEW_PRECLAIM")
    require(data.get("gateClosed") is False, f"G08_C452_{name}_GATE_CLOSED_PRECLAIM")
    require(data.get("productionReadyClaimed") is False, f"G08_C452_{name}_PRODUCTION_READY_PRECLAIM")
    return {
        "status": "PASS",
        "cameraModel": data.get("cameraModelV4"),
        "autoFrameModel": data.get("autoFrameModel"),
        "cinematicSalienceModel": data.get("cinematicSalienceModel"),
        "shotCount": int(data.get("shotCount") or 0),
        "cinematicSaliencePass": True,
        "climax": per_cue.get("CLIMAX"),
        "payoff": per_cue.get("PAYOFF"),
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
    require(bugatti_camera["cameraModel"] == generic_camera["cameraModel"], "G08_C452_CAMERA_MODEL_DIFFERS_ACROSS_ASSETS")
    require(bugatti_camera["cinematicSalienceModel"] == generic_camera["cinematicSalienceModel"], "G08_C452_SALIENCE_MODEL_DIFFERS_ACROSS_ASSETS")

    print(json.dumps({
        "marker": "GENERIC_BATTLE_RUNTIME_CANDIDATE452_G08_MACHINE_ACCEPTANCE",
        "status": "PASS",
        "runtime": "ISS_GENERIC_BATTLE_RUNTIME_V1_CANDIDATE_4_5_2_G08",
        "gateScope": "G08_EVENT_DRIVEN_CINEMATIC_CAMERA_ONLY",
        "exactBugatti": {"base": bugatti_base, "drama": bugatti_drama, "camera": bugatti_camera, "status": "PASS"},
        "genericHypercar": {"base": generic_base, "drama": generic_drama, "camera": generic_camera, "status": "PASS"},
        "sameGenericCameraAcrossAssets": True,
        "sameGenericSalienceLogicAcrossAssets": True,
        "climaxPayoffCinematicSalience": "PASS",
        "g04Preserved": True, "g05Preserved": True, "g06Preserved": True, "g07Preserved": True,
        "actorPoseOrVelocityMutation": False, "physicsMutation": False,
        "perAssetCameraBranch": False, "perAssetTuning": False, "cameraFakesPhysics": False,
        "machineFramingAcceptance": "PASS",
        "humanCinematicAcceptance": "PENDING",
        "issR045MasterPlanAlignment": "PASS_MACHINE_LAYER_PENDING_HUMAN_POSTFLIGHT",
        "gateClosed": False,
        "productionReadyClaimed": False,
    }, sort_keys=True))


if __name__ == "__main__":
    main()
