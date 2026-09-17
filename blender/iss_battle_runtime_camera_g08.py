from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any, Iterable

import bpy
from bpy_extras.object_utils import world_to_camera_view
from mathutils import Vector

from blender import iss_blender_battle_runtime_v1_hardened as hardened
from blender import run_generic_battle_runtime_v1_candidate44 as candidate44
from blender.iss_battle_runtime_assets import BlenderBattleRuntimeError, marker
from blender.iss_battle_runtime_core import clamp, stable_unit

CAMERA_G08_MODEL = "ISS_EVENT_DRIVEN_CINEMATIC_CAMERA_DIRECTOR_V2"
SHOT_GRAMMAR_MODEL = "REALIZED_EVENT_PHASE_SHOT_GRAMMAR_V1"
READABILITY_MODEL = "VERTICAL_RELATIONSHIP_READABILITY_ORACLE_V1"

_STAGE_TO_CUE = {
    "ESCALATION_PHYSICALLY_EARNED": "ESCALATION",
    "INITIAL_PHYSICAL_DOMINANCE_ESTABLISHED": "DOMINANCE",
    "COUNTERATTACK_CAUSALLY_EARNED": "COUNTERATTACK",
    "DOMINANCE_REVERSAL_COMEBACK_PHYSICALLY_EARNED": "REVERSAL",
    "CLIMAX_PHYSICALLY_EARNED": "CLIMAX",
    "PAYOFF_RESOLVED": "PAYOFF",
}

_REQUIRED_CUES = (
    "HOOK",
    "ESCALATION",
    "COUNTERATTACK",
    "REVERSAL",
    "CLIMAX",
    "PAYOFF",
    "IMPACT",
)

_SHOT_GRAMMAR: dict[str, dict[str, float]] = {
    "WORLD": {"lens": 34.0, "distance": 2.90, "elevation": 0.72, "side": 0.78, "back": 0.50},
    "HOOK": {"lens": 32.0, "distance": 3.05, "elevation": 0.78, "side": 0.82, "back": 0.42},
    "ESCALATION": {"lens": 42.0, "distance": 2.55, "elevation": 0.52, "side": 0.92, "back": 0.25},
    "DOMINANCE": {"lens": 46.0, "distance": 2.45, "elevation": 0.48, "side": 0.86, "back": 0.32},
    "COUNTERATTACK": {"lens": 48.0, "distance": 2.42, "elevation": 0.46, "side": -0.92, "back": 0.22},
    "REVERSAL": {"lens": 44.0, "distance": 2.48, "elevation": 0.50, "side": -0.80, "back": -0.30},
    "CLIMAX": {"lens": 38.0, "distance": 2.62, "elevation": 0.42, "side": 0.74, "back": 0.18},
    "PAYOFF": {"lens": 36.0, "distance": 2.95, "elevation": 0.82, "side": -0.72, "back": 0.36},
    "IMPACT": {"lens": 52.0, "distance": 2.18, "elevation": 0.38, "side": 0.76, "back": 0.12},
}


def _phase(event: Any | None) -> str:
    return str(getattr(event, "phase", "") or "").upper()


def _actor_center(actor: Any) -> Vector:
    return actor.chassis.matrix_world.translation.copy()


def _mean_point(rows: Iterable[Any]) -> Vector:
    values = [_actor_center(row) for row in rows]
    if not values:
        return Vector((0.0, 0.0, 1.0))
    return sum(values, Vector((0.0, 0.0, 0.0))) / len(values)


def _horizontal_unit(value: Vector, fallback: Vector) -> Vector:
    result = value.copy()
    result.z = 0.0
    if result.length < 1e-6:
        result = fallback.copy()
        result.z = 0.0
    if result.length < 1e-6:
        result = Vector((1.0, 0.0, 0.0))
    result.normalize()
    return result


class EventDrivenCinematicCameraDirector(hardened.ForwardPreviewDirector):
    """G08 camera-only successor.

    Reads realized world/event state and keys camera/target/lens only. It never
    writes actor transforms, velocity, control, contact, damage, lifecycle, or
    outcome state.
    """

    def __init__(self, fps: int) -> None:
        super().__init__(fps)
        self._shot_records: list[dict[str, Any]] = []
        self._seen_transition_indices: set[int] = set()
        self._seen_phase_cues: set[str] = set()
        self._cue_counts: dict[str, int] = {}
        self._impact_count = 0
        self._last_cue = "WORLD"
        self._last_event_id: str | None = None
        self._last_record_frame = -10**9

    def setup(self) -> None:
        super().setup()
        camera, _ = self._ensure()
        camera.data.lens = 38.0
        camera.data.sensor_width = 32.0
        camera.data.sensor_fit = "AUTO"
        camera.data.dof.use_dof = False

    @staticmethod
    def _event_actor_ids(event: Any | None, actors: dict[str, Any]) -> list[str]:
        if event is None:
            return sorted(actors)
        ids: list[str] = [str(x) for x in getattr(event, "attackers", ()) if str(x) in actors]
        target_id = str(getattr(event, "target_id", "") or "")
        if target_id and target_id in actors and target_id not in ids:
            ids.append(target_id)
        return ids or sorted(actors)

    @staticmethod
    def _transition_actor_ids(row: dict[str, Any], actors: dict[str, Any]) -> list[str]:
        ids: list[str] = []
        for key in ("attackerId", "targetId", "actorId", "fromActorId", "toActorId"):
            value = str(row.get(key) or "")
            if value and value in actors and value not in ids:
                ids.append(value)
        return ids or sorted(actors)

    def _next_transition(self, frame: int) -> tuple[int, dict[str, Any], str] | None:
        transitions = list(getattr(candidate44._tracker, "transitions", []) or [])
        for index, row in enumerate(transitions):
            if index in self._seen_transition_indices:
                continue
            if int(row.get("frame") or -1) > int(frame):
                continue
            cue = _STAGE_TO_CUE.get(str(row.get("stage") or ""))
            if cue:
                self._seen_transition_indices.add(index)
                return index, row, cue
        return None

    def _resolve_cue(
        self,
        frame: int,
        event: Any | None,
        *,
        force_key: bool,
        impact_emphasis: bool,
    ) -> tuple[str, dict[str, Any] | None, bool]:
        if impact_emphasis:
            return "IMPACT", None, True

        transition = self._next_transition(frame)
        if transition is not None:
            _, row, cue = transition
            return cue, row, True

        phase = _phase(event)
        if phase in {"HOOK", "ESCALATION", "COUNTERATTACK", "CLIMAX", "PAYOFF"} and phase not in self._seen_phase_cues:
            self._seen_phase_cues.add(phase)
            return phase, None, True

        if force_key:
            return phase or self._last_cue or "WORLD", None, True
        return phase or self._last_cue or "WORLD", None, False

    @staticmethod
    def _bounds(rows: list[Any]) -> tuple[Vector, float, float]:
        if not rows:
            return Vector((0.0, 0.0, 1.0)), 4.0, 1.5
        centers = [_actor_center(actor) for actor in rows]
        center = sum(centers, Vector((0.0, 0.0, 0.0))) / len(centers)
        radius = 0.5
        height = 0.5
        for actor, position in zip(rows, centers):
            dims = actor.dimensions
            horizontal_half = 0.5 * math.hypot(float(dims.x), float(dims.y))
            radius = max(radius, float((position - center).length) + horizontal_half)
            height = max(height, float(dims.z))
        center.z = max(float(center.z), height * 0.48)
        return center, radius, height

    @staticmethod
    def _action_axis(actor_ids: list[str], actors: dict[str, Any], event: Any | None) -> Vector:
        target_id = str(getattr(event, "target_id", "") or "") if event is not None else ""
        attacker_ids = [str(x) for x in getattr(event, "attackers", ())] if event is not None else []
        if target_id in actors:
            sources = [actors[x] for x in attacker_ids if x in actors]
            if sources:
                source_center = _mean_point(sources)
                return _horizontal_unit(_actor_center(actors[target_id]) - source_center, Vector((1.0, 0.0, 0.0)))
        if len(actor_ids) >= 2:
            return _horizontal_unit(
                _actor_center(actors[actor_ids[1]]) - _actor_center(actors[actor_ids[0]]),
                Vector((1.0, 0.0, 0.0)),
            )
        return Vector((1.0, 0.0, 0.0))

    @staticmethod
    def _style(cue: str, event_id: str) -> dict[str, float]:
        base = dict(_SHOT_GRAMMAR.get(cue, _SHOT_GRAMMAR["WORLD"]))
        jitter = stable_unit(f"G08:{cue}:{event_id}") - 0.5
        base["side"] *= 1.0 + jitter * 0.12
        base["back"] += jitter * 0.08
        base["elevation"] *= 1.0 + jitter * 0.08
        return base

    @staticmethod
    def _project_actor(scene: Any, camera: Any, actor: Any) -> dict[str, Any]:
        center = world_to_camera_view(scene, camera, actor.chassis.matrix_world.translation)
        corners: list[tuple[float, float, float]] = []
        try:
            for corner in actor.chassis.bound_box:
                world = actor.chassis.matrix_world @ Vector(corner)
                p = world_to_camera_view(scene, camera, world)
                corners.append((float(p.x), float(p.y), float(p.z)))
        except Exception:
            corners = []

        if corners:
            xs = [row[0] for row in corners if row[2] > 0.0]
            ys = [row[1] for row in corners if row[2] > 0.0]
        else:
            xs = []
            ys = []
        bbox = None
        if xs and ys:
            bbox = {
                "minX": min(xs),
                "maxX": max(xs),
                "minY": min(ys),
                "maxY": max(ys),
            }
        center_inside = bool(
            float(center.z) > 0.0
            and 0.04 <= float(center.x) <= 0.96
            and 0.05 <= float(center.y) <= 0.95
        )
        bbox_intersects = bool(
            bbox is not None
            and bbox["maxX"] >= 0.0
            and bbox["minX"] <= 1.0
            and bbox["maxY"] >= 0.0
            and bbox["minY"] <= 1.0
        )
        return {
            "center": [float(center.x), float(center.y), float(center.z)],
            "centerInsideSafeFrame": center_inside,
            "bboxIntersectsFrame": bbox_intersects,
            "bbox": bbox,
        }

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
        visible_ids = [
            actor_id
            for actor_id, row in rows.items()
            if row["centerInsideSafeFrame"] and row["bboxIntersectsFrame"]
        ]
        separation = None
        if len(visible_ids) >= 2:
            a = rows[visible_ids[0]]["center"]
            b = rows[visible_ids[1]]["center"]
            separation = math.hypot(float(a[0]) - float(b[0]), float(a[1]) - float(b[1]))
        return {
            "model": READABILITY_MODEL,
            "actorProjection": rows,
            "relevantActorCount": len(actor_ids),
            "visibleRelevantActorCount": len(visible_ids),
            "visibleRelevantActorIds": visible_ids,
            "relationshipScreenSeparation": separation,
            "relationshipReadable": bool(len(actor_ids) < 2 or len(visible_ids) >= 2),
        }

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
        scene = bpy.context.scene
        camera, target = self._ensure()
        readability = self._readability(actor_ids, actors)
        row = {
            "frame": int(scene.frame_current),
            "requestedFrame": int(frame),
            "cue": cue,
            "phase": _phase(event),
            "eventId": str(getattr(event, "event_id", "") or "") or None,
            "transitionStage": str((transition or {}).get("stage") or "") or None,
            "transitionFrame": int((transition or {}).get("frame")) if (transition or {}).get("frame") is not None else None,
            "actorIds": list(actor_ids),
            "cameraLocation": [float(x) for x in camera.location],
            "targetLocation": [float(x) for x in target.location],
            "lensMm": float(camera.data.lens),
            "impactEmphasis": bool(impact_emphasis),
            "renderResolution": [int(scene.render.resolution_x), int(scene.render.resolution_y)],
            "verticalShortsFrame": bool(scene.render.resolution_y > scene.render.resolution_x),
            "readability": readability,
            "sourceAuthority": "READ_ONLY_REALIZED_WORLD_AND_G07_EVENT_STATE",
            "actorPoseOrVelocityMutation": False,
            "physicsMutation": False,
            "perAssetCameraBranch": False,
        }
        self._shot_records.append(row)
        self._cue_counts[cue] = int(self._cue_counts.get(cue, 0)) + 1
        marker(
            "G08_CINEMATIC_SHOT_KEYED",
            frame=int(scene.frame_current),
            cue=cue,
            eventId=row["eventId"],
            transitionStage=row["transitionStage"],
            visibleRelevantActorCount=readability["visibleRelevantActorCount"],
            relevantActorCount=readability["relevantActorCount"],
            relationshipReadable=readability["relationshipReadable"],
            lensMm=round(float(camera.data.lens), 3),
            model=CAMERA_G08_MODEL,
        )

    def _position_for_cue(
        self,
        frame: int,
        cue: str,
        event: Any | None,
        transition: dict[str, Any] | None,
        actors: dict[str, Any],
        *,
        impact_emphasis: bool,
        force_key: bool,
    ) -> None:
        camera, target = self._ensure()
        actor_ids = self._transition_actor_ids(transition, actors) if transition else self._event_actor_ids(event, actors)
        rows = [actors[x] for x in actor_ids if x in actors]
        center, radius, height = self._bounds(rows)
        action = self._action_axis(actor_ids, actors, event)
        side_axis = Vector((-float(action.y), float(action.x), 0.0))
        if side_axis.length < 1e-6:
            side_axis = Vector((0.0, 1.0, 0.0))
        side_axis.normalize()

        event_id = str(getattr(event, "event_id", "") or "world")
        style = self._style(cue, event_id)

        # Vertical 9:16 requires more standoff than a landscape camera for the
        # same horizontal relationship. Radius is measured from realized actor
        # positions/dimensions, not from asset identity.
        distance = clamp(radius * float(style["distance"]) + 3.5, 7.0, 78.0)
        elevation = clamp(height * 1.10 + radius * float(style["elevation"]), 2.4, 22.0)

        desired_camera = (
            center
            + side_axis * (distance * float(style["side"]))
            - action * (distance * float(style["back"]))
            + Vector((0.0, 0.0, elevation))
        )
        desired_target = center.copy()
        desired_target.z = max(float(desired_target.z), height * 0.48)

        stride = max(1, self.fps // 6)
        should_key = bool(force_key or impact_emphasis or frame == 1 or frame % stride == 0)
        if not should_key:
            return

        camera.location = desired_camera
        target.location = desired_target
        camera.data.lens = float(style["lens"])
        camera.keyframe_insert(data_path="location", frame=frame)
        target.keyframe_insert(data_path="location", frame=frame)
        camera.data.keyframe_insert(data_path="lens", frame=frame)
        self.keyed_frames.append(int(frame))
        self._record_shot(
            frame,
            cue,
            event,
            transition,
            actor_ids,
            actors,
            impact_emphasis=impact_emphasis,
        )

        if hardened._capture_enabled and force_key:
            label = "cinematic-" + cue.lower().replace("_", "-")
            self._render(label)

    def observe(
        self,
        frame: int,
        event: Any | None,
        actors: dict[str, Any],
        *,
        force_key: bool = False,
        impact_emphasis: bool = False,
    ) -> None:
        cue, transition, cue_force = self._resolve_cue(
            frame,
            event,
            force_key=force_key,
            impact_emphasis=impact_emphasis,
        )
        force = bool(force_key or cue_force or impact_emphasis)
        self._position_for_cue(
            frame,
            cue,
            event,
            transition,
            actors,
            impact_emphasis=impact_emphasis,
            force_key=force,
        )
        self._last_cue = cue
        self._last_event_id = str(getattr(event, "event_id", "") or "") or None

        if (
            hardened._capture_enabled
            and not self._approach_done
            and self._approach_ready(event, actors)
        ):
            self._render("approach")
            self._approach_done = True
        if (
            hardened._capture_enabled
            and self._impact_scene_frame is not None
            and not self._aftermath_done
            and bpy.context.scene.frame_current
            >= self._impact_scene_frame + max(3, int(round(self.fps * 0.55)))
        ):
            self._render("aftermath")
            self._aftermath_done = True

    def mark_impact(
        self,
        frame: int,
        event: Any | None,
        actors: dict[str, Any],
    ) -> None:
        self._impact_count += 1
        super().mark_impact(frame, event, actors)

    def finalize(self, total_frames: int) -> None:
        super().finalize(total_frames)
        scene = bpy.context.scene
        output = hardened._capture_output
        if output is None:
            raise BlenderBattleRuntimeError("G08_OUTPUT_DIR_UNAVAILABLE")

        coverage = {cue: int(self._cue_counts.get(cue, 0)) for cue in _REQUIRED_CUES}
        relationship_failures = [
            row
            for row in self._shot_records
            if row["cue"] in {"HOOK", "ESCALATION", "COUNTERATTACK", "REVERSAL", "CLIMAX", "PAYOFF"}
            and row["readability"]["relevantActorCount"] >= 2
            and not row["readability"]["relationshipReadable"]
        ]
        aspect = float(scene.render.resolution_x) / max(1.0, float(scene.render.resolution_y))
        evidence = {
            "model": CAMERA_G08_MODEL,
            "shotGrammarModel": SHOT_GRAMMAR_MODEL,
            "readabilityModel": READABILITY_MODEL,
            "status": "COMPLETE",
            "finalFrame": int(total_frames),
            "renderResolution": [int(scene.render.resolution_x), int(scene.render.resolution_y)],
            "renderAspect": aspect,
            "verticalShortsFrame": bool(scene.render.resolution_y > scene.render.resolution_x),
            "targetAspect9x16": bool(abs(aspect - (9.0 / 16.0)) <= 0.035),
            "requiredCueCoverage": coverage,
            "allRequiredCuesObserved": all(coverage[cue] > 0 for cue in _REQUIRED_CUES),
            "realImpactShotCount": int(self._impact_count),
            "shotCount": len(self._shot_records),
            "relationshipReadabilityFailureCount": len(relationship_failures),
            "relationshipReadabilityPass": len(relationship_failures) == 0,
            "shots": self._shot_records,
            "sourceAuthority": "READ_ONLY_REALIZED_WORLD_AND_G07_EVENT_STATE",
            "cameraOnlyMutation": True,
            "actorPoseOrVelocityMutation": False,
            "physicsMutation": False,
            "g04ControlLawChanged": False,
            "g05ContactAuthorityChanged": False,
            "g06DamagePersistenceChanged": False,
            "g07DramaAuthorityChanged": False,
            "perAssetCameraBranch": False,
            "cameraFakesPhysics": False,
            "humanCinematicAcceptance": "PENDING",
            "gateClosed": False,
            "productionReadyClaimed": False,
        }
        path = Path(output) / "g08-camera-evidence.json"
        path.write_text(json.dumps(evidence, indent=2, sort_keys=True), encoding="utf-8")
        marker(
            "G08_CAMERA_EVIDENCE_WRITTEN",
            path=str(path),
            shotCount=len(self._shot_records),
            allRequiredCuesObserved=evidence["allRequiredCuesObserved"],
            relationshipReadabilityPass=evidence["relationshipReadabilityPass"],
            realImpactShotCount=self._impact_count,
            verticalShortsFrame=evidence["verticalShortsFrame"],
            targetAspect9x16=evidence["targetAspect9x16"],
            model=CAMERA_G08_MODEL,
        )
