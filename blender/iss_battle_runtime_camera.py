from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Iterable

import bpy
from mathutils import Vector

from blender.iss_battle_runtime_core import RuntimeEvent, clamp, stable_unit
from blender.iss_battle_runtime_physics import RuntimeActor

CAMERA_MODEL = "ISS_EVENT_DRIVEN_CAMERA_DIRECTOR_V1"


@dataclass
class CameraDirector:
    fps: int
    camera: bpy.types.Object | None = None
    target: bpy.types.Object | None = None
    impact_frames: list[int] = field(default_factory=list)
    keyed_frames: list[int] = field(default_factory=list)

    def setup(self) -> None:
        scene = bpy.context.scene
        camera_data = bpy.data.cameras.new("ISS_BATTLE_CAMERA_DATA")
        camera = bpy.data.objects.new("ISS_BATTLE_CAMERA", camera_data)
        scene.collection.objects.link(camera)

        target = bpy.data.objects.new("ISS_BATTLE_CAMERA_TARGET", None)
        scene.collection.objects.link(target)

        constraint = camera.constraints.new(type="TRACK_TO")
        constraint.target = target
        constraint.track_axis = "TRACK_NEGATIVE_Z"
        constraint.up_axis = "UP_Y"

        camera_data.lens = 46.0
        camera_data.sensor_width = 32.0
        scene.camera = camera
        self.camera = camera
        self.target = target

    def _ensure(self) -> tuple[bpy.types.Object, bpy.types.Object]:
        if self.camera is None or self.target is None:
            self.setup()
        assert self.camera is not None
        assert self.target is not None
        return self.camera, self.target

    @staticmethod
    def _relevant_actors(
        event: RuntimeEvent | None,
        actors: dict[str, RuntimeActor],
    ) -> list[RuntimeActor]:
        if event is None:
            return list(actors.values())
        ids: list[str] = list(event.attackers)
        if event.target_id:
            ids.append(event.target_id)
        rows = [actors[x] for x in ids if x in actors]
        return rows or list(actors.values())

    @staticmethod
    def _bounds(rows: Iterable[RuntimeActor]) -> tuple[Vector, float, float]:
        rows = list(rows)
        if not rows:
            return Vector((0.0, 0.0, 1.0)), 6.0, 2.0

        centers = [a.chassis.matrix_world.translation.copy() for a in rows]
        center = sum(centers, Vector((0.0, 0.0, 0.0))) / len(centers)
        radius = 1.0
        height = 1.0
        for actor, pos in zip(rows, centers):
            half = 0.5 * math.sqrt(
                float(actor.dimensions.x) ** 2
                + float(actor.dimensions.y) ** 2
            )
            radius = max(radius, (pos - center).length + half)
            height = max(height, float(actor.dimensions.z))
        center.z = max(center.z, height * 0.45)
        return center, radius, height

    def observe(
        self,
        frame: int,
        event: RuntimeEvent | None,
        actors: dict[str, RuntimeActor],
        *,
        force_key: bool = False,
        impact_emphasis: bool = False,
    ) -> None:
        camera, target = self._ensure()
        rows = self._relevant_actors(event, actors)
        center, radius, height = self._bounds(rows)

        event_key = event.event_id if event is not None else "world"
        phase = event.phase if event is not None else "WORLD"
        seed = stable_unit(f"{event_key}:{phase}")
        azimuth = math.radians(20.0 + seed * 55.0)

        distance_scale = 1.65 if impact_emphasis else 2.20
        distance = clamp(radius * distance_scale + 2.8, 6.0, 62.0)
        elevation = clamp(
            height * (1.4 if impact_emphasis else 1.8) + radius * 0.24,
            2.4,
            18.0,
        )

        side = -1.0 if seed < 0.5 else 1.0
        offset = Vector((
            math.cos(azimuth) * distance,
            math.sin(azimuth) * distance * side,
            elevation,
        ))
        desired_camera = center + offset
        desired_target = center.copy()

        stride = max(1, self.fps // 8)
        should_key = force_key or frame == 1 or frame % stride == 0
        if not should_key:
            return

        camera.location = desired_camera
        target.location = desired_target
        camera.keyframe_insert(data_path="location", frame=frame)
        target.keyframe_insert(data_path="location", frame=frame)
        self.keyed_frames.append(int(frame))

    def mark_impact(
        self,
        frame: int,
        event: RuntimeEvent | None,
        actors: dict[str, RuntimeActor],
    ) -> None:
        if frame not in self.impact_frames:
            self.impact_frames.append(int(frame))
        self.observe(
            frame,
            event,
            actors,
            force_key=True,
            impact_emphasis=True,
        )

    def finalize(self, total_frames: int) -> None:
        camera, target = self._ensure()
        for obj in (camera, target):
            if obj.animation_data and obj.animation_data.action:
                for curve in obj.animation_data.action.fcurves:
                    for point in curve.keyframe_points:
                        point.interpolation = "BEZIER"
        if total_frames not in self.keyed_frames:
            camera.keyframe_insert(data_path="location", frame=total_frames)
            target.keyframe_insert(data_path="location", frame=total_frames)
            self.keyed_frames.append(int(total_frames))

    def preview_frames(self, total_frames: int) -> tuple[int, int, int]:
        if self.impact_frames:
            impact = max(1, min(total_frames, self.impact_frames[0]))
            approach = max(1, impact - max(2, int(round(self.fps * 0.30))))
            aftermath = min(
                total_frames,
                impact + max(3, int(round(self.fps * 0.55))),
            )
            return approach, impact, aftermath
        midpoint = max(1, min(total_frames, total_frames // 2))
        return (
            max(1, midpoint - max(2, self.fps // 3)),
            midpoint,
            min(total_frames, midpoint + max(3, self.fps // 2)),
        )
