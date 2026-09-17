from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any

import bpy

from blender import iss_blender_battle_runtime_v1_hardened as hardened
from blender import run_generic_battle_runtime_v1_candidate44 as candidate44
from blender.iss_battle_runtime_assets import BlenderBattleRuntimeError, marker
from blender.iss_battle_runtime_camera_g08 import EventDrivenCinematicCameraDirector
from blender.iss_battle_runtime_camera_g08_v3 import EventDrivenCinematicCameraDirectorV3

CINEMATIC_SALIENCE_MODEL = "CUE_AWARE_VERTICAL_CINEMATIC_SALIENCE_V2"
CAMERA_G08_V4_MODEL = "ISS_EVENT_DRIVEN_CINEMATIC_CAMERA_DIRECTOR_V4"
PAYOFF_FOCUS_MODEL = "REALIZED_G07_DOMINANCE_LEADER_FOCUS_V1"
SALIENCE_ANCHOR_MODEL = "REALIZED_CUE_ANCHOR_ONLY_V1"
_REQUIRED_SALIENCE_CUES = ("CLIMAX", "PAYOFF")
_SALIENCE_THRESHOLDS = {
    "CLIMAX": {"minActorHeight": 0.10, "minCombinedArea": 0.026},
    "PAYOFF": {"minActorHeight": 0.085, "minCombinedArea": 0.020},
}
_ANCHOR_TRANSITIONS = {
    "CLIMAX": "CLIMAX_PHYSICALLY_EARNED",
    "PAYOFF": "PAYOFF_RESOLVED",
}
_MAX_SALIENCE_ITERATIONS = 14
_MIN_SALIENCE_DISTANCE = 2.5
_SALIENCE_STEP = 0.90


class EventDrivenCinematicCameraDirectorV4(EventDrivenCinematicCameraDirectorV3):
    """Master-Plan G08 successor with generic cinematic salience.

    V3 guarantees portrait full-bounds safety. V4 adds a second, independent
    readability requirement for the *cinematic anchor shots* of climax/payoff.

    Climax remains a relationship shot. Payoff becomes a generic hero/focus
    shot derived from the latest physically realized G07 dominance transition,
    never from asset identity or prescribed Story choreography.

    The director reads realized actor geometry, camera projection and G07 event
    state only. It never writes actor/physics/contact/damage/drama state.
    """

    def __init__(self, fps: int) -> None:
        super().__init__(fps)
        self._salience_rows: list[dict[str, Any]] = []
        self._salience_anchor_seen: set[str] = set()

    @staticmethod
    def _latest_dominance_actor_id(actors: dict[str, Any]) -> str | None:
        transitions = list(getattr(candidate44._tracker, "transitions", []) or [])
        for row in reversed(transitions):
            stage = str(row.get("stage") or "")
            if stage == "DOMINANCE_REVERSAL_COMEBACK_PHYSICALLY_EARNED":
                actor_id = str(row.get("toActorId") or "")
                if actor_id in actors:
                    return actor_id
            if stage == "INITIAL_PHYSICAL_DOMINANCE_ESTABLISHED":
                actor_id = str(row.get("actorId") or "")
                if actor_id in actors:
                    return actor_id
        return None

    @staticmethod
    def _event_actor_ids(event: Any | None, actors: dict[str, Any]) -> list[str]:
        phase = str(getattr(event, "phase", "") or "").upper() if event is not None else ""
        if phase == "PAYOFF":
            leader = EventDrivenCinematicCameraDirectorV4._latest_dominance_actor_id(actors)
            if leader is not None:
                return [leader]
        return EventDrivenCinematicCameraDirector._event_actor_ids(event, actors)

    @staticmethod
    def _transition_actor_ids(row: dict[str, Any], actors: dict[str, Any]) -> list[str]:
        stage = str(row.get("stage") or "")
        if stage == "PAYOFF_RESOLVED":
            leader = EventDrivenCinematicCameraDirectorV4._latest_dominance_actor_id(actors)
            if leader is not None:
                return [leader]
        return EventDrivenCinematicCameraDirector._transition_actor_ids(row, actors)

    @staticmethod
    def _style(cue: str, event_id: str) -> dict[str, float]:
        base = EventDrivenCinematicCameraDirector._style(cue, event_id)
        if cue == "CLIMAX":
            base["lens"] = 46.0
            base["distance"] = 1.95
            base["elevation"] = 0.40
            base["side"] = math.copysign(0.34, float(base.get("side", 1.0)) or 1.0)
            base["back"] = 0.92
        elif cue == "PAYOFF":
            base["lens"] = 48.0
            base["distance"] = 1.72
            base["elevation"] = 0.46
            base["side"] = math.copysign(0.38, float(base.get("side", -1.0)) or -1.0)
            base["back"] = 0.88
        return base

    def _salience_anchor_reason(
        self,
        cue: str,
        transition: dict[str, Any] | None,
    ) -> str | None:
        if cue not in _REQUIRED_SALIENCE_CUES:
            return None
        if cue not in self._salience_anchor_seen:
            self._salience_anchor_seen.add(cue)
            return "FIRST_REALIZED_CUE_ENTRY"
        expected = _ANCHOR_TRANSITIONS.get(cue)
        if expected and str((transition or {}).get("stage") or "") == expected:
            return "REALIZED_G07_STAGE_TRANSITION"
        return None

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
        *,
        required: bool,
        anchor_reason: str | None,
    ) -> dict[str, Any]:
        camera, target = self._ensure()
        readability = self._readability(actor_ids, actors)
        metrics = self._salience_metrics(readability)
        thresholds = self._thresholds(cue) if required else None
        initial_distance = max(1e-6, float((camera.location - target.location).length))
        current_distance = initial_distance
        iterations = 0

        if required and thresholds is not None and not self._salience_pass(cue, readability, metrics):
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

        observed_pass = self._salience_pass(cue, readability, metrics)
        payoff_focus = bool(cue == "PAYOFF" and len(actor_ids) == 1)
        result = {
            "model": CINEMATIC_SALIENCE_MODEL,
            "anchorModel": SALIENCE_ANCHOR_MODEL,
            "cue": cue,
            "required": bool(required),
            "anchorReason": anchor_reason,
            "thresholds": thresholds,
            "iterations": iterations,
            "initialDistance": initial_distance,
            "finalDistance": max(1e-6, float((camera.location - target.location).length)),
            "fullBoundsReadable": bool(readability.get("fullBoundsReadable")),
            "metrics": metrics,
            "observedPass": observed_pass,
            "pass": observed_pass if required else None,
            "focusActorIds": list(actor_ids),
            "focusAuthority": PAYOFF_FOCUS_MODEL if payoff_focus else "REALIZED_RELATIONSHIP_GROUP",
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
        autoframe = self._autoframe(actor_ids, actors)
        anchor_reason = self._salience_anchor_reason(cue, transition)
        salience = self._salience_adjust(
            cue,
            actor_ids,
            actors,
            required=anchor_reason is not None,
            anchor_reason=anchor_reason,
        )

        camera, _ = self._ensure()
        camera.keyframe_insert(
            data_path="location",
            frame=int(bpy.context.scene.frame_current),
        )

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

        required_rows = [row for row in self._salience_rows if bool(row.get("required"))]
        failures = [row for row in required_rows if row.get("pass") is not True]
        per_cue: dict[str, dict[str, Any]] = {}
        for cue in _REQUIRED_SALIENCE_CUES:
            rows = [row for row in required_rows if row.get("cue") == cue]
            per_cue[cue] = {
                "anchorShotCount": len(rows),
                "pass": bool(rows) and all(row.get("pass") is True for row in rows),
                "minActorHeightObserved": min(
                    (float((row.get("metrics") or {}).get("minActorHeight") or 0.0) for row in rows),
                    default=0.0,
                ),
                "minCombinedAreaObserved": min(
                    (float((row.get("metrics") or {}).get("combinedArea") or 0.0) for row in rows),
                    default=0.0,
                ),
                "thresholds": dict(_SALIENCE_THRESHOLDS[cue]),
                "focusAuthorities": sorted({str(row.get("focusAuthority") or "") for row in rows}),
            }

        payoff_rows = [row for row in required_rows if row.get("cue") == "PAYOFF"]
        payoff_focus_valid = bool(payoff_rows) and all(
            row.get("focusAuthority") == PAYOFF_FOCUS_MODEL
            and len(row.get("focusActorIds") or []) == 1
            for row in payoff_rows
        )
        climax_rows = [row for row in required_rows if row.get("cue") == "CLIMAX"]
        climax_relationship_valid = bool(climax_rows) and all(
            len(row.get("focusActorIds") or []) >= 2 for row in climax_rows
        )

        evidence.update(
            {
                "cameraModelV4": CAMERA_G08_V4_MODEL,
                "cinematicSalienceModel": CINEMATIC_SALIENCE_MODEL,
                "salienceAnchorModel": SALIENCE_ANCHOR_MODEL,
                "payoffFocusModel": PAYOFF_FOCUS_MODEL,
                "cinematicSalienceRequiredCues": list(_REQUIRED_SALIENCE_CUES),
                "cinematicSalienceThresholds": _SALIENCE_THRESHOLDS,
                "cinematicSaliencePass": bool(required_rows)
                and not failures
                and all(per_cue[cue]["pass"] for cue in _REQUIRED_SALIENCE_CUES)
                and payoff_focus_valid
                and climax_relationship_valid,
                "cinematicSalienceFailureCount": len(failures),
                "cinematicSalienceRequiredShotCount": len(required_rows),
                "cinematicSaliencePerCue": per_cue,
                "cinematicSalienceRows": self._salience_rows,
                "payoffFocusFromRealizedDominancePass": payoff_focus_valid,
                "climaxRelationshipAnchorPass": climax_relationship_valid,
                "perAssetFocusBranch": False,
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
            payoffFocusFromRealizedDominancePass=payoff_focus_valid,
            climaxRelationshipAnchorPass=climax_relationship_valid,
            model=CINEMATIC_SALIENCE_MODEL,
        )
