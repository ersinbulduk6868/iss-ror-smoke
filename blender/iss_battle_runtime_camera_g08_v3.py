from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any

import bpy

from blender import iss_blender_battle_runtime_v1_hardened as hardened
from blender.iss_battle_runtime_assets import BlenderBattleRuntimeError, marker
from blender.iss_battle_runtime_camera_g08 import (
    CAMERA_G08_MODEL,
    EventDrivenCinematicCameraDirector,
)

AUTOFRAME_MODEL = "PORTRAIT_FULL_BOUNDS_AUTOFRAME_V1"
FULL_BOUNDS_READABILITY_MODEL = "VERTICAL_FULL_BOUNDS_READABILITY_ORACLE_V2"
INTERPOLATION_MODEL = "AUTO_CLAMPED_BEZIER_CAMERA_PATH_V1"

_SAFE_X_MIN = 0.06
_SAFE_X_MAX = 0.94
_SAFE_Y_MIN = 0.05
_SAFE_Y_MAX = 0.95
_MAX_AUTOFIT_ITERATIONS = 8
_MAX_AUTOFIT_DISTANCE = 600.0
_MIN_AUTOFIT_STEP = 1.10
_MAX_AUTOFIT_STEP = 3.00


class EventDrivenCinematicCameraDirectorV3(EventDrivenCinematicCameraDirector):
    """G08 Candidate 4.5.1 portrait-safe camera successor.

    Keeps V2 event/cue/shot grammar authority. The only added behavior is
    generic, geometry-driven camera auto-framing from realized actor bounds.
    Actors, physics, contact, damage, G07 lifecycle and outcome remain read-only.
    """

    def __init__(self, fps: int) -> None:
        super().__init__(fps)
        self._autoframe_rows: list[dict[str, Any]] = []

    def setup(self) -> None:
        super().setup()
        camera, _ = self._ensure()
        camera.data.sensor_fit = "VERTICAL"
        camera.data.sensor_height = 18.0
        camera.data.clip_start = 0.1
        camera.data.clip_end = 1000.0

    @staticmethod
    def _project_actor(scene: Any, camera: Any, actor: Any) -> dict[str, Any]:
        row = EventDrivenCinematicCameraDirector._project_actor(scene, camera, actor)
        bbox = row.get("bbox")
        bbox_inside = bool(
            bbox is not None
            and float(row["center"][2]) > 0.0
            and bbox["minX"] >= _SAFE_X_MIN
            and bbox["maxX"] <= _SAFE_X_MAX
            and bbox["minY"] >= _SAFE_Y_MIN
            and bbox["maxY"] <= _SAFE_Y_MAX
        )
        row["bboxInsideSafeFrame"] = bbox_inside
        row["safeFrame"] = {
            "minX": _SAFE_X_MIN,
            "maxX": _SAFE_X_MAX,
            "minY": _SAFE_Y_MIN,
            "maxY": _SAFE_Y_MAX,
        }
        return row

    def _readability(
        self,
        actor_ids: list[str],
        actors: dict[str, Any],
    ) -> dict[str, Any]:
        scene = bpy.context.scene
        camera, _ = self._ensure()
        bpy.context.view_layer.update()
        rows = {
            actor_id: self._project_actor(scene, camera, actors[actor_id])
            for actor_id in actor_ids
            if actor_id in actors
        }
        fully_visible_ids = [
            actor_id
            for actor_id, row in rows.items()
            if row["centerInsideSafeFrame"] and row["bboxInsideSafeFrame"]
        ]
        separation = None
        if len(fully_visible_ids) >= 2:
            a = rows[fully_visible_ids[0]]["center"]
            b = rows[fully_visible_ids[1]]["center"]
            separation = math.hypot(
                float(a[0]) - float(b[0]),
                float(a[1]) - float(b[1]),
            )
        all_relevant_full_bounds = bool(
            rows
            and len(fully_visible_ids) == len(rows)
            and len(rows) == len(actor_ids)
        )
        return {
            "model": FULL_BOUNDS_READABILITY_MODEL,
            "actorProjection": rows,
            "relevantActorCount": len(actor_ids),
            "visibleRelevantActorCount": len(fully_visible_ids),
            "visibleRelevantActorIds": fully_visible_ids,
            "relationshipScreenSeparation": separation,
            "fullBoundsReadable": all_relevant_full_bounds,
            "relationshipReadable": bool(
                len(actor_ids) < 2 or all_relevant_full_bounds
            ),
        }

    @staticmethod
    def _projection_required_scale(readability: dict[str, Any]) -> float:
        required = 1.0
        rows = readability.get("actorProjection") or {}
        for row in rows.values():
            bbox = row.get("bbox")
            center = row.get("center") or [0.5, 0.5, -1.0]
            if bbox is None or float(center[2]) <= 0.0:
                required = max(required, 2.0)
                continue
            if bbox["minX"] < _SAFE_X_MIN:
                required = max(
                    required,
                    (0.5 - float(bbox["minX"]))
                    / max(1e-6, 0.5 - _SAFE_X_MIN),
                )
            if bbox["maxX"] > _SAFE_X_MAX:
                required = max(
                    required,
                    (float(bbox["maxX"]) - 0.5)
                    / max(1e-6, _SAFE_X_MAX - 0.5),
                )
            if bbox["minY"] < _SAFE_Y_MIN:
                required = max(
                    required,
                    (0.5 - float(bbox["minY"]))
                    / max(1e-6, 0.5 - _SAFE_Y_MIN),
                )
            if bbox["maxY"] > _SAFE_Y_MAX:
                required = max(
                    required,
                    (float(bbox["maxY"]) - 0.5)
                    / max(1e-6, _SAFE_Y_MAX - 0.5),
                )
        return max(_MIN_AUTOFIT_STEP, min(_MAX_AUTOFIT_STEP, required * 1.08))

    def _autoframe(
        self,
        actor_ids: list[str],
        actors: dict[str, Any],
    ) -> dict[str, Any]:
        camera, target = self._ensure()
        bpy.context.view_layer.update()

        initial_vector = camera.location - target.location
        initial_distance = max(1e-6, float(initial_vector.length))
        current_distance = initial_distance
        readability = self._readability(actor_ids, actors)
        iterations = 0

        while (
            not bool(readability.get("fullBoundsReadable"))
            and iterations < _MAX_AUTOFIT_ITERATIONS
            and current_distance < _MAX_AUTOFIT_DISTANCE
        ):
            direction = camera.location - target.location
            if direction.length < 1e-6:
                direction = initial_vector.copy()
            if direction.length < 1e-6:
                direction.x = 1.0
            direction.normalize()

            scale = self._projection_required_scale(readability)
            next_distance = min(
                _MAX_AUTOFIT_DISTANCE,
                max(current_distance * scale, current_distance + 0.25),
            )
            camera.location = target.location + direction * next_distance
            current_distance = next_distance
            iterations += 1
            bpy.context.view_layer.update()
            readability = self._readability(actor_ids, actors)

        result = {
            "model": AUTOFRAME_MODEL,
            "iterations": iterations,
            "initialDistance": initial_distance,
            "finalDistance": current_distance,
            "distanceScale": current_distance / initial_distance,
            "fullBoundsReadable": bool(readability.get("fullBoundsReadable")),
            "maxIterations": _MAX_AUTOFIT_ITERATIONS,
            "maxDistance": _MAX_AUTOFIT_DISTANCE,
            "safeFrame": {
                "minX": _SAFE_X_MIN,
                "maxX": _SAFE_X_MAX,
                "minY": _SAFE_Y_MIN,
                "maxY": _SAFE_Y_MAX,
            },
        }
        self._autoframe_rows.append(result)
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
        autoframe = self._autoframe(actor_ids, actors)
        camera, _ = self._ensure()
        camera.keyframe_insert(
            data_path="location",
            frame=int(bpy.context.scene.frame_current),
        )
        super()._record_shot(
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

    def _apply_interpolation_safety(self) -> None:
        camera, target = self._ensure()
        for owner in (camera, target, camera.data):
            animation = getattr(owner, "animation_data", None)
            action = animation.action if animation else None
            if action is None:
                continue
            for curve in action.fcurves:
                for point in curve.keyframe_points:
                    point.interpolation = "BEZIER"
                    point.handle_left_type = "AUTO_CLAMPED"
                    point.handle_right_type = "AUTO_CLAMPED"

    def finalize(self, total_frames: int) -> None:
        super().finalize(total_frames)
        self._apply_interpolation_safety()

        output = hardened._capture_output
        if output is None:
            raise BlenderBattleRuntimeError("G08_OUTPUT_DIR_UNAVAILABLE")
        path = Path(output) / "g08-camera-evidence.json"
        evidence = json.loads(path.read_text(encoding="utf-8"))

        multi_actor_shots = [
            row
            for row in self._shot_records
            if int(row["readability"].get("relevantActorCount") or 0) >= 2
        ]
        full_bounds_failures = [
            row
            for row in multi_actor_shots
            if not bool(row["readability"].get("fullBoundsReadable"))
        ]
        adjusted = [
            row
            for row in self._autoframe_rows
            if int(row.get("iterations") or 0) > 0
        ]
        evidence.update(
            {
                "autoFrameModel": AUTOFRAME_MODEL,
                "fullBoundsReadabilityModel": FULL_BOUNDS_READABILITY_MODEL,
                "interpolationModel": INTERPOLATION_MODEL,
                "portraitSensorFit": "VERTICAL",
                "fullBoundsReadabilityPass": len(full_bounds_failures) == 0,
                "fullBoundsReadabilityFailureCount": len(full_bounds_failures),
                "multiActorShotCount": len(multi_actor_shots),
                "autoFrameAdjustedShotCount": len(adjusted),
                "maxAutoFrameIterationsObserved": max(
                    (int(row.get("iterations") or 0) for row in self._autoframe_rows),
                    default=0,
                ),
                "maxAutoFrameDistanceScaleObserved": max(
                    (float(row.get("distanceScale") or 1.0) for row in self._autoframe_rows),
                    default=1.0,
                ),
                "autoFrameFailureCount": sum(
                    1
                    for row in self._autoframe_rows
                    if not bool(row.get("fullBoundsReadable"))
                ),
                "cameraInterpolationOvershootGuard": True,
            }
        )
        path.write_text(
            json.dumps(evidence, indent=2, sort_keys=True),
            encoding="utf-8",
        )
        marker(
            "G08_PORTRAIT_AUTOFRAME_EVIDENCE_WRITTEN",
            path=str(path),
            fullBoundsReadabilityPass=evidence["fullBoundsReadabilityPass"],
            fullBoundsReadabilityFailureCount=evidence[
                "fullBoundsReadabilityFailureCount"
            ],
            autoFrameAdjustedShotCount=evidence["autoFrameAdjustedShotCount"],
            maxAutoFrameIterationsObserved=evidence[
                "maxAutoFrameIterationsObserved"
            ],
            model=AUTOFRAME_MODEL,
        )
