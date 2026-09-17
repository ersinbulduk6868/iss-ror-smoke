from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any

import bpy

from blender import iss_blender_battle_runtime_v1_hardened as hardened
from blender.iss_battle_runtime_assets import BlenderBattleRuntimeError, marker
from blender.iss_battle_runtime_camera_g08 import EventDrivenCinematicCameraDirector
from blender.iss_battle_runtime_camera_g08_v3 import EventDrivenCinematicCameraDirectorV3

CINEMATIC_SALIENCE_MODEL = "CUE_AWARE_VERTICAL_CINEMATIC_SALIENCE_V1"
CAMERA_G08_V4_MODEL = "ISS_EVENT_DRIVEN_CINEMATIC_CAMERA_DIRECTOR_V4"
_REQUIRED_SALIENCE_CUES = ("CLIMAX", "PAYOFF")
_SALIENCE_THRESHOLDS = {
    "CLIMAX": {"minActorHeight": 0.10, "minCombinedArea": 0.026},
    "PAYOFF": {"minActorHeight": 0.085, "minCombinedArea": 0.020},
}
_MAX_SALIENCE_ITERATIONS = 14
_MIN_SALIENCE_DISTANCE = 2.5
_SALIENCE_STEP = 0.90


class EventDrivenCinematicCameraDirectorV4(EventDrivenCinematicCameraDirectorV3):
    """Master-Plan G08 successor with generic cinematic salience.

    V3 guarantees portrait full-bounds safety. V4 adds a second, independent
    readability requirement for climax/payoff: relevant actors must remain
    fully visible *and* large enough to read in a vertical Shorts frame.

    The adjustment is projection-driven and uses only realized actor geometry,
    camera projection and event cue. It never branches on asset identity and
    never writes actor/physics/contact/damage/drama state.
    """

    def __init__(self, fps: int) -> None:
        super().__init__(fps)
        self._salience_rows: list[dict[str, Any]] = []

    @staticmethod
    def _style(cue: str, event_id: str) -> dict[str, float]:
        base = EventDrivenCinematicCameraDirector._style(cue, event_id)
        # Climax/payoff use a more axial relationship view. This reduces
        # horizontal spread in portrait framing without changing actor state.
        if cue == "CLIMAX":
            base["lens"] = 46.0
            base["distance"] = 1.95
            base["elevation"] = 0.40
            base["side"] = math.copysign(0.34, float(base.get("side", 1.0)) or 1.0)
            base["back"] = 0.92
        elif cue == "PAYOFF":
            base["lens"] = 48.0
            base["distance"] = 2.05
            base["elevation"] = 0.52
            base["side"] = math.copysign(0.30, float(base.get("side", -1.0)) or -1.0)
            base["back"] = 0.96
        return base

    @staticmethod
    def _salience_metrics(readability: dict[str, Any]) -> dict[str, float]:
        rows = readability.get("actorProjection") or {}
        boxes: list[dict[str, float]] = []
        actor_heights: list[float] = []
        actor_areas: list[float] = []
        for row in rows.values():
            bbox = row.get("bbox")
            center = row.get("center") or [0.5, 0.5, -1.0]
            if bbox is None or float(center[2]) <= 0.0:
                continue
            width = max(0.0, float(bbox["maxX"]) - float(bbox["minX"]))
            height = max(0.0, float(bbox["maxY"]) - float(bbox["minY"]))
            boxes.append(bbox)
            actor_heights.append(height)
            actor_areas.append(width * height)

        if not boxes:
            return {
                "minActorHeight": 0.0,
                "maxActorHeight": 0.0,
                "minActorArea": 0.0,
                "combinedWidth": 0.0,
                "combinedHeight": 0.0,
                "combinedArea": 0.0,
            }

        min_x = min(float(b["minX"]) for b in boxes)
        max_x = max(float(b["maxX"]) for b in boxes)
        min_y = min(float(b["minY"]) for b in boxes)
        max_y = max(float(b["maxY"]) for b in boxes)
        combined_width = max(0.0, max_x - min_x)
        combined_height = max(0.0, max_y - min_y)
        return {
            "minActorHeight": min(actor_heights),
            "maxActorHeight": max(actor_heights),
            "minActorArea": min(actor_areas),
            "combinedWidth": combined_width,
            "combinedHeight": combined_height,
            "combinedArea": combined_width * combined_height,
        }

    @staticmethod
    def _thresholds(cue: str) -> dict[str, float] | None:
        row = _SALIENCE_THRESHOLDS.get(cue)
        return dict(row) if row is not None else None

    @classmethod
    def _salience_pass(
        cls,
        cue: str,
        readability: dict[str, Any],
        metrics: dict[str, float],
    ) -> bool:
        thresholds = cls._thresholds(cue)
        if thresholds is None:
            return True
        return bool(
            readability.get("fullBoundsReadable")
            and float(metrics["minActorHeight"]) >= float(thresholds["minActorHeight"])
            and float(metrics["combinedArea"]) >= float(thresholds["minCombinedArea"])
        )

    def _salience_adjust(
        self,
        cue: str,
        actor_ids: list[str],
        actors: dict[str, Any],
    ) -> dict[str, Any]:
        camera, target = self._ensure()
        readability = self._readability(actor_ids, actors)
        metrics = self._salience_metrics(readability)
        thresholds = self._thresholds(cue)
        initial_distance = max(1e-6, float((camera.location - target.location).length))
        current_distance = initial_distance
        iterations = 0

        if thresholds is not None and not self._salience_pass(cue, readability, metrics):
            last_safe_location = camera.location.copy()
            last_safe_readability = readability
            last_safe_metrics = metrics

            while iterations < _MAX_SALIENCE_ITERATIONS and current_distance > _MIN_SALIENCE_DISTANCE:
                direction = camera.location - target.location
                if direction.length < 1e-6:
                    break
                direction.normalize()
                next_distance = max(_MIN_SALIENCE_DISTANCE, current_distance * _SALIENCE_STEP)
                candidate_location = target.location + direction * next_distance
                camera.location = candidate_location
                bpy.context.view_layer.update()

                candidate_readability = self._readability(actor_ids, actors)
                candidate_metrics = self._salience_metrics(candidate_readability)
                iterations += 1

                if not bool(candidate_readability.get("fullBoundsReadable")):
                    camera.location = last_safe_location
                    bpy.context.view_layer.update()
                    readability = last_safe_readability
                    metrics = last_safe_metrics
                    break

                last_safe_location = camera.location.copy()
                last_safe_readability = candidate_readability
                last_safe_metrics = candidate_metrics
                readability = candidate_readability
                metrics = candidate_metrics
                current_distance = next_distance

                if self._salience_pass(cue, readability, metrics):
                    break

        result = {
            "model": CINEMATIC_SALIENCE_MODEL,
            "cue": cue,
            "required": thresholds is not None,
            "thresholds": thresholds,
            "iterations": iterations,
            "initialDistance": initial_distance,
            "finalDistance": max(1e-6, float((camera.location - target.location).length)),
            "fullBoundsReadable": bool(readability.get("fullBoundsReadable")),
            "metrics": metrics,
            "pass": self._salience_pass(cue, readability, metrics),
            "assetIdentityBranch": False,
            "actorPoseOrVelocityMutation": False,
            "physicsMutation": False,
        }
        self._salience_rows.append(result)
        return result

    def _record_shot(
        self,
        frame: int,
        cue: str,
        event: Any | None,
        transition: dict[str, Any] | None,
        actor_ids: list[str],
        actors: dict[str, Any],
        *,
        impact_emphasis: bool,
    ) -> None:
        # Phase 1: preserve V3 full-bounds guarantee.
        autoframe = self._autoframe(actor_ids, actors)
        # Phase 2: move only the camera closer while preserving full bounds.
        salience = self._salience_adjust(cue, actor_ids, actors)

        camera, _ = self._ensure()
        camera.keyframe_insert(
            data_path="location",
            frame=int(bpy.context.scene.frame_current),
        )

        # Call the V2 recorder directly so V3 does not run autoframe twice.
        EventDrivenCinematicCameraDirector._record_shot(
            self,
            frame,
            cue,
            event,
            transition,
            actor_ids,
            actors,
            impact_emphasis=impact_emphasis,
        )
        if self._shot_records:
            self._shot_records[-1]["autoFrame"] = dict(autoframe)
            self._shot_records[-1]["cinematicSalience"] = dict(salience)

    def finalize(self, total_frames: int) -> None:
        super().finalize(total_frames)

        output = hardened._capture_output
        if output is None:
            raise BlenderBattleRuntimeError("G08_OUTPUT_DIR_UNAVAILABLE")
        path = Path(output) / "g08-camera-evidence.json"
        evidence = json.loads(path.read_text(encoding="utf-8"))

        required_rows = [
            row for row in self._salience_rows if bool(row.get("required"))
        ]
        failures = [row for row in required_rows if not bool(row.get("pass"))]
        per_cue: dict[str, dict[str, Any]] = {}
        for cue in _REQUIRED_SALIENCE_CUES:
            rows = [row for row in required_rows if row.get("cue") == cue]
            per_cue[cue] = {
                "shotCount": len(rows),
                "pass": bool(rows) and all(bool(row.get("pass")) for row in rows),
                "minActorHeightObserved": min(
                    (float((row.get("metrics") or {}).get("minActorHeight") or 0.0) for row in rows),
                    default=0.0,
                ),
                "minCombinedAreaObserved": min(
                    (float((row.get("metrics") or {}).get("combinedArea") or 0.0) for row in rows),
                    default=0.0,
                ),
                "thresholds": dict(_SALIENCE_THRESHOLDS[cue]),
            }

        evidence.update(
            {
                "cameraModelV4": CAMERA_G08_V4_MODEL,
                "cinematicSalienceModel": CINEMATIC_SALIENCE_MODEL,
                "cinematicSalienceRequiredCues": list(_REQUIRED_SALIENCE_CUES),
                "cinematicSalienceThresholds": _SALIENCE_THRESHOLDS,
                "cinematicSaliencePass": bool(required_rows) and not failures
                and all(per_cue[cue]["pass"] for cue in _REQUIRED_SALIENCE_CUES),
                "cinematicSalienceFailureCount": len(failures),
                "cinematicSalienceRequiredShotCount": len(required_rows),
                "cinematicSaliencePerCue": per_cue,
                "cinematicSalienceRows": self._salience_rows,
                "humanCinematicAcceptance": "PENDING",
                "gateClosed": False,
                "productionReadyClaimed": False,
            }
        )
        path.write_text(json.dumps(evidence, indent=2, sort_keys=True), encoding="utf-8")
        marker(
            "G08_CINEMATIC_SALIENCE_EVIDENCE_WRITTEN",
            path=str(path),
            cinematicSaliencePass=evidence["cinematicSaliencePass"],
            cinematicSalienceFailureCount=evidence["cinematicSalienceFailureCount"],
            requiredShotCount=evidence["cinematicSalienceRequiredShotCount"],
            model=CINEMATIC_SALIENCE_MODEL,
        )
