from __future__ import annotations

import argparse
import json
import pathlib
import sys
from typing import Any

import bpy

from blender import run_generic_battle_runtime_v1_candidate494_generic_battle as candidate494

ENGINE_VERSION = "4.5.13"
GENERIC_EVIDENCE_FILE = "generic-battle-runtime-v1-evidence.json"
PRODUCTION_ADAPTER_VERSION = "ISS_BLENDER_PRODUCTION_ADAPTER_C494_G04_V1"


def parse_args() -> argparse.Namespace:
    argv = sys.argv
    argv = argv[argv.index("--") + 1 :] if "--" in argv else []
    parser = argparse.ArgumentParser()
    parser.add_argument("--job", required=True)
    parser.add_argument("--assets", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--result", required=True)
    return parser.parse_args(argv)


def marker(name: str, **fields: Any) -> None:
    print(json.dumps({"marker": name, **fields}, sort_keys=True), flush=True)


def load_json(path: pathlib.Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def validate_production_contract(job: dict[str, Any], assets: Any) -> dict[str, Any]:
    request = job.get("request_json") or {}
    if not isinstance(request, dict):
        raise RuntimeError("PRODUCTION_REQUEST_JSON_INVALID")
    if request.get("engine") != "BLENDER":
        raise RuntimeError("ENGINE_CONTRACT_MISMATCH")
    if request.get("engineVersion") != ENGINE_VERSION:
        raise RuntimeError("ENGINE_VERSION_CONTRACT_MISMATCH")
    if (request.get("executionPolicy") or {}).get("continuousWorld") is not True:
        raise RuntimeError("CONTINUOUS_WORLD_REQUIRED")
    if not request.get("assetBindings"):
        raise RuntimeError("ASSET_BINDINGS_REQUIRED")
    if not (request.get("battlePlan") or {}).get("events"):
        raise RuntimeError("STORY_EVENT_CONTRACT_EMPTY")
    if not request.get("scenes"):
        raise RuntimeError("STORY_SCENE_CONTRACT_EMPTY")
    if not isinstance(assets, list) or len(assets) < 2:
        raise RuntimeError("PRODUCTION_ASSETS_LT_2")
    return request


def run_c494_generic_runtime(
    *,
    job_path: pathlib.Path,
    asset_map_path: pathlib.Path,
    output_dir: pathlib.Path,
) -> dict[str, Any]:
    old_argv = list(sys.argv)
    try:
        # The hardened generic runtime intentionally accepts the production job.json
        # wrapper and the production asset-list format. The production worker does
        # not own motion, contact scheduling, damage, or actor transforms.
        sys.argv = [
            old_argv[0],
            "--",
            "--request",
            str(job_path),
            "--asset-map",
            str(asset_map_path),
            "--output-dir",
            str(output_dir),
        ]
        marker(
            "ISS_PRODUCTION_GENERIC_RUNTIME_START",
            candidate=candidate494.CANDIDATE,
            adapter=PRODUCTION_ADAPTER_VERSION,
            secondBattleEngine=False,
            actorPoseKeyframesIntroduced=False,
            exactCollisionFrameTarget=False,
            fixedWorldCoordinates=False,
        )
        candidate494.main()
    finally:
        sys.argv = old_argv

    evidence_path = output_dir / GENERIC_EVIDENCE_FILE
    if not evidence_path.is_file():
        raise RuntimeError("GENERIC_BATTLE_RUNTIME_EVIDENCE_MISSING")
    evidence = load_json(evidence_path)
    if not isinstance(evidence, dict) or evidence.get("success") is not True:
        raise RuntimeError("GENERIC_BATTLE_RUNTIME_ACCEPTANCE_NOT_PASS")
    gates = evidence.get("gates") or {}
    required = (
        "continuousWorld",
        "noActorPoseKeyframes",
        "assetIdentityVerified",
        "massReconciled",
        "solverCorrelatedImpactEvidence",
        "damageCausallyImpactGated",
        "persistentDebrisMaterialized",
        "allRequiredEventsSucceeded",
    )
    failed = [name for name in required if gates.get(name) is not True]
    if failed:
        raise RuntimeError("GENERIC_BATTLE_RUNTIME_GATE_FAIL:" + ",".join(failed))
    marker(
        "ISS_PRODUCTION_GENERIC_RUNTIME_PASS",
        candidate=candidate494.CANDIDATE,
        runtime=evidence.get("runtime"),
        noActorPoseKeyframes=True,
        allRequiredEventsSucceeded=True,
    )
    return evidence


def configure_video_render(scene: bpy.types.Scene) -> None:
    scene.render.engine = "BLENDER_EEVEE_NEXT"
    scene.render.resolution_x = 720
    scene.render.resolution_y = 1280
    scene.render.resolution_percentage = 100
    scene.render.image_settings.file_format = "FFMPEG"
    scene.render.ffmpeg.format = "MPEG4"
    scene.render.ffmpeg.codec = "H264"
    scene.render.ffmpeg.constant_rate_factor = "MEDIUM"


def render_scene_windows(
    *,
    request: dict[str, Any],
    output_dir: pathlib.Path,
) -> list[dict[str, Any]]:
    scene = bpy.context.scene
    if scene.camera is None:
        raise RuntimeError("GENERIC_RUNTIME_CAMERA_MISSING")
    fps = int(scene.render.fps or 30)
    total_frames = int(scene.frame_end)
    original_start = int(scene.frame_start)
    original_end = int(scene.frame_end)
    configure_video_render(scene)

    rows: list[dict[str, Any]] = []
    try:
        for index, item in enumerate(request.get("scenes") or [], 1):
            scene_number = int(item.get("sceneNumber") or index)
            start_second = float(item.get("startSecond", (index - 1) * 5.0))
            end_second = float(item.get("endSecond", index * 5.0))
            start_frame = max(1, min(total_frames, int(round(start_second * fps)) + 1))
            end_frame = max(start_frame, min(total_frames, int(round(end_second * fps))))
            path = output_dir / f"scene-{scene_number:02d}.mp4"
            scene.frame_start = start_frame
            scene.frame_end = end_frame
            scene.render.filepath = str(path)
            marker(
                "SCENE_RENDER_START",
                sceneNumber=scene_number,
                startFrame=start_frame,
                endFrame=end_frame,
                actorPoseOrVelocityMutation=False,
            )
            bpy.ops.render.render(animation=True)
            if not path.is_file() or path.stat().st_size < 1024:
                raise RuntimeError(f"SCENE_RENDER_MISSING scene={scene_number}")
            rows.append(
                {
                    "sceneNumber": scene_number,
                    "path": str(path.resolve()),
                }
            )
            marker(
                "SCENE_RENDER_PASS",
                sceneNumber=scene_number,
                bytes=path.stat().st_size,
                actorPoseOrVelocityMutation=False,
            )
    finally:
        scene.frame_start = original_start
        scene.frame_end = original_end
    return rows


def event_evidence_rows(evidence: dict[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for event_id, state in sorted((evidence.get("events") or {}).items()):
        status = str(state.get("status") or "")
        rows.append(
            {
                "eventId": event_id,
                "status": status,
                "executed": status in {"SUCCEEDED", "SETTLED", "OBSERVED"},
                "physicalContactObserved": int(state.get("contactCount") or 0) > 0,
                "damageCount": int(state.get("damageCount") or 0),
                "completedFrame": state.get("completedFrame"),
            }
        )
    return rows


def build_result(
    *,
    evidence: dict[str, Any],
    videos: list[dict[str, Any]],
) -> dict[str, Any]:
    event_rows = event_evidence_rows(evidence)
    actors = evidence.get("actors") or {}
    damage_count = sum(
        len(((row.get("state") or {}).get("damageEvents") or []))
        for row in actors.values()
    )
    gates = evidence.get("gates") or {}
    result = {
        "engine": "BLENDER",
        "engineVersion": ENGINE_VERSION,
        "renderEngine": "BLENDER_EEVEE_NEXT",
        "physicsBackend": "BLENDER_RIGID_BODY",
        "productionAdapter": PRODUCTION_ADAPTER_VERSION,
        "genericRuntimeCandidate": candidate494.CANDIDATE,
        "genericRuntimeVersion": evidence.get("runtime"),
        "productionAssetsLoaded": gates.get("assetIdentityVerified") is True,
        "storyEventsExecuted": all(row["executed"] for row in event_rows),
        "simulationCompleted": evidence.get("success") is True,
        "collisionObserved": bool(evidence.get("impacts")),
        "visibleDamageApplied": damage_count > 0,
        "persistentWorldState": gates.get("continuousWorld") is True,
        "debrisPersisted": gates.get("persistentDebrisMaterialized") is True,
        "continuousWorld": gates.get("continuousWorld") is True,
        "noActorPoseKeyframes": gates.get("noActorPoseKeyframes") is True,
        "allRequiredEventsSucceeded": gates.get("allRequiredEventsSucceeded") is True,
        "renderCompleted": bool(videos),
        "eventEvidence": event_rows,
        "videoFiles": videos,
        "actorEvidence": [
            {
                "entityId": entity,
                "sha256": row.get("sha256"),
                "visibleMeshCount": row.get("visibleMeshCount"),
                "dimensions": row.get("dimensions"),
                "semanticZones": row.get("semanticZones"),
            }
            for entity, row in sorted((evidence.get("resolvedAssets") or {}).items())
        ],
        "genericBattleRuntimeEvidencePath": GENERIC_EVIDENCE_FILE,
        "secondBattleEngine": False,
        "actorPoseOrVelocityMutationByAdapter": False,
        "fixedWorldCoordinatesByAdapter": False,
        "exactCollisionFrameTargetByAdapter": False,
        "manualTrajectoryByAdapter": False,
        "notes": (
            "Production worker is a transport/render adapter over the C494 generic "
            "battle runtime. Motion, replanning, contact authority, consequences and "
            "world-state evolution are owned by the generic runtime; the adapter "
            "does not choreograph actor transforms."
        ),
    }
    if result["storyEventsExecuted"] is not True:
        raise RuntimeError("PRODUCTION_STORY_EVENTS_NOT_EXECUTED")
    if result["renderCompleted"] is not True:
        raise RuntimeError("PRODUCTION_RENDER_NOT_COMPLETED")
    return result


def main() -> None:
    args = parse_args()
    job_path = pathlib.Path(args.job).expanduser().resolve()
    assets_path = pathlib.Path(args.assets).expanduser().resolve()
    output_dir = pathlib.Path(args.output).expanduser().resolve()
    result_path = pathlib.Path(args.result).expanduser().resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    job = load_json(job_path)
    assets = load_json(assets_path)
    if not isinstance(job, dict):
        raise RuntimeError("PRODUCTION_JOB_NOT_OBJECT")
    request = validate_production_contract(job, assets)

    evidence = run_c494_generic_runtime(
        job_path=job_path,
        asset_map_path=assets_path,
        output_dir=output_dir,
    )
    videos = render_scene_windows(request=request, output_dir=output_dir)
    result = build_result(evidence=evidence, videos=videos)
    result_path.write_text(json.dumps(result, indent=2, sort_keys=True), encoding="utf-8")
    marker(
        "ISS_BLENDER_PRODUCTION_RUNTIME_C494_PASS",
        candidate=candidate494.CANDIDATE,
        adapter=PRODUCTION_ADAPTER_VERSION,
        events=len(result["eventEvidence"]),
        scenes=len(videos),
        secondBattleEngine=False,
        noActorPoseKeyframes=True,
    )


if __name__ == "__main__":
    main()
