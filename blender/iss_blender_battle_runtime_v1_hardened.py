from __future__ import annotations

import argparse
import json
from dataclasses import asdict
from pathlib import Path
from typing import Any

import bpy
from mathutils import Vector

from blender import iss_blender_battle_runtime_v1 as runtime
from blender import iss_battle_runtime_physics as physics
from blender.iss_battle_runtime_core import DamageAccumulator, ImpactEvidence, ImpactModel
from blender.iss_battle_runtime_consequences import ConsequenceEngine
from blender.iss_battle_runtime_lifecycle import BattleLifecycle, TERMINAL
from blender.iss_battle_runtime_assets import BlenderBattleRuntimeError, marker

RUNTIME_VERSION = "ISS_GENERIC_BATTLE_RUNTIME_V1_CANDIDATE_3_HARDENED"
MIN_DAMAGE_SEVERITY = 0.055

_lifecycle = BattleLifecycle()
_cutoff_frames: dict[tuple[str, str], int] = {}
_capture_enabled = False
_capture_output: Path | None = None
_capture_rows: dict[str, dict[str, Any]] = {}

_original_parse_args = runtime.parse_args
_original_load_json = runtime.load_json
_original_detect_contacts = runtime.detect_contacts


def _reset_process_state() -> None:
    global _lifecycle, _cutoff_frames, _capture_rows
    _lifecycle = BattleLifecycle()
    _cutoff_frames = {}
    _capture_rows = {}


def parse_args() -> argparse.Namespace:
    global _capture_enabled, _capture_output
    args = _original_parse_args()
    _capture_enabled = bool(args.render_previews)
    _capture_output = Path(args.output_dir).expanduser().resolve()
    return args


def load_json(path: Path) -> Any:
    value = _original_load_json(path)
    if isinstance(value, dict) and isinstance(value.get("request_json"), dict):
        return dict(value["request_json"])
    if isinstance(value, list) and all(isinstance(row, dict) for row in value):
        mapped: dict[str, Any] = {}
        for row in value:
            entity = str(row.get("entityId") or "").strip()
            local = row.get("localPath") or row.get("path")
            if not entity or not local:
                raise BlenderBattleRuntimeError("ASSET_MAP_LIST_ROW_INVALID")
            mapped[entity] = {
                "path": str(local),
                "sha256": str(
                    row.get("downloadedSha256")
                    or row.get("sha256")
                    or ""
                ).lower()
                or None,
            }
        return mapped
    return value


def surface_point(actor: physics.RuntimeActor, toward_world: Vector) -> Vector:
    direction = Vector(toward_world)
    if direction.length < 1e-7:
        return actor.chassis.matrix_world.translation.copy()
    direction.normalize()
    q_inv = actor.chassis.matrix_world.to_quaternion().inverted()
    local = q_inv @ direction
    half = actor.chassis.dimensions * 0.5
    candidates: list[float] = []
    for component, extent in (
        (abs(float(local.x)), float(half.x)),
        (abs(float(local.y)), float(half.y)),
        (abs(float(local.z)), float(half.z)),
    ):
        if component > 1e-8:
            candidates.append(extent / component)
    if not candidates:
        return actor.chassis.matrix_world.translation.copy()
    distance = min(candidates)
    return actor.chassis.matrix_world.translation + direction * distance


def dependency_ready(event: Any, states: dict[str, Any]) -> bool:
    return _lifecycle.dependencies_ready(event, states)


def set_controls(
    frame: int,
    program: Any,
    actors: dict[str, physics.RuntimeActor],
    states: dict[str, Any],
    control_samples: list[dict[str, Any]],
) -> None:
    for entity, actor in actors.items():
        event = physics.active_event_for_actor(entity, frame, program, states)
        if event is None:
            actor.rig.coast()
            continue

        wave = runtime.WaveScheduler.active_attackers(event, frame)
        if entity not in wave:
            actor.rig.brake()
            continue

        state = states[event.event_id]
        target_point = runtime.resolve_target_point(
            actor,
            event,
            actors,
            frame,
            state,
        )
        current_velocity = actor.velocity.get(
            frame,
            Vector((0.0, 0.0, 0.0)),
        )
        left, right, telemetry = physics.drive_command(
            actor,
            event,
            target_point,
            current_velocity,
        )

        native_cutoff = float(telemetry.get("controllerCutoff", 0.0)) >= 0.5
        base_cutoff = float(telemetry.get("contactCutoffDistance", 0.0))
        distance = float(telemetry.get("distance", 0.0))
        predictive_margin = max(
            0.35,
            min(1.50, float(current_velocity.length) * 0.08),
        )
        predictive_cutoff = bool(
            event.requires_contact
            and base_cutoff > 0.0
            and distance <= base_cutoff + predictive_margin
        )
        cutoff = native_cutoff or predictive_cutoff
        telemetry["predictiveCutoffMargin"] = predictive_margin if event.requires_contact else 0.0
        telemetry["predictiveCutoff"] = 1.0 if predictive_cutoff else 0.0
        if cutoff:
            telemetry["controllerCutoff"] = 1.0
            left = 0.0
            right = 0.0
            actor.rig.coast()
            _cutoff_frames[(event.event_id, entity)] = frame
        else:
            actor.rig.command(
                left,
                right,
                impulse_scale=max(0.12, actor.state.drive_efficiency),
            )

        if frame == event.start_frame or frame % max(1, program.fps // 2) == 0 or cutoff:
            control_samples.append(
                {
                    "frame": frame,
                    "eventId": event.event_id,
                    "actorId": entity,
                    "tactic": event.tactic,
                    "leftMps": left,
                    "rightMps": right,
                    "driveEfficiency": actor.state.drive_efficiency,
                    "controllerAuthority": "COAST" if cutoff else "MOTOR",
                    "telemetry": telemetry,
                }
            )


def detect_contacts(
    frame: int,
    program: Any,
    actors: dict[str, physics.RuntimeActor],
    states: dict[str, Any],
    pending: list[physics.PendingContact],
    cooldown: dict[tuple[str, str, str], int],
) -> None:
    before = len(pending)
    _original_detect_contacts(
        frame,
        program,
        actors,
        states,
        pending,
        cooldown,
    )
    accepted: list[physics.PendingContact] = pending[:before]
    for item in pending[before:]:
        attacker = actors[item.attacker_id]
        motors = attacker.rig.motors_left + attacker.rig.motors_right
        motor_authority_zero = all(
            float(m.rigid_body_constraint.motor_ang_max_impulse) <= 1e-9
            for m in motors
        )
        cutoff_frame = _cutoff_frames.get((item.event_id, item.attacker_id))
        recent_cutoff = (
            cutoff_frame is not None
            and cutoff_frame <= item.frame
            and item.frame - cutoff_frame <= max(2, program.fps)
        )
        item.controller_cutoff_observed = bool(
            motor_authority_zero and recent_cutoff
        )
        if item.controller_cutoff_observed:
            accepted.append(item)
        else:
            marker(
                "CONTACT_REJECTED_CONTROLLER_AUTHORITY",
                frame=item.frame,
                eventId=item.event_id,
                attackerId=item.attacker_id,
                targetId=item.target_id,
                motorAuthorityZero=motor_authority_zero,
                cutoffFrame=cutoff_frame,
            )
    pending[:] = accepted


def _mirrored_impact(
    evidence: ImpactEvidence,
    attacker: physics.RuntimeActor,
    target: physics.RuntimeActor,
    frame: int,
    response_attacker: float,
    response_target: float,
) -> ImpactEvidence:
    normal = -Vector(evidence.contact_normal)
    point = surface_point(attacker, -normal)
    return ImpactModel.estimate(
        frame=frame,
        attacker_id=target.profile.entity_id,
        target_id=attacker.profile.entity_id,
        target_zone="front",
        attacker_mass_kg=target.profile.mass_kg,
        target_mass_kg=attacker.profile.mass_kg,
        relative_speed_mps=evidence.relative_speed_mps,
        normal_closing_speed_mps=evidence.normal_closing_speed_mps,
        contact_point=tuple(point),
        contact_normal=tuple(normal),
        response_delta_attacker_mps=response_target,
        response_delta_target_mps=response_attacker,
        target_toughness_j_per_kg=attacker.profile.toughness_j_per_kg,
    )


def resolve_pending_contacts(
    frame: int,
    actors: dict[str, physics.RuntimeActor],
    states: dict[str, Any],
    events_by_id: dict[str, Any],
    pending: list[physics.PendingContact],
    camera: Any,
    impact_log: list[dict[str, Any]],
) -> None:
    keep: list[physics.PendingContact] = []
    for item in pending:
        if frame < item.resolve_frame:
            keep.append(item)
            continue
        if not item.controller_cutoff_observed:
            marker(
                "SOLVER_CONTACT_REJECTED_NO_CONTROLLER_CUTOFF",
                frame=item.frame,
                eventId=item.event_id,
                attackerId=item.attacker_id,
                targetId=item.target_id,
            )
            continue

        attacker = actors[item.attacker_id]
        target = actors[item.target_id]
        post_attacker = attacker.velocity.get(frame, Vector((0.0, 0.0, 0.0)))
        post_target = target.velocity.get(frame, Vector((0.0, 0.0, 0.0)))
        response_attacker = (
            post_attacker - item.pre_attacker_velocity
        ).length
        response_target = (
            post_target - item.pre_target_velocity
        ).length
        relative = item.pre_attacker_velocity - item.pre_target_velocity
        relative_speed = relative.length
        normal = item.contact_normal.normalized()
        closing = max(0.0, relative.dot(normal))

        evidence = ImpactModel.estimate(
            frame=item.frame,
            attacker_id=item.attacker_id,
            target_id=item.target_id,
            target_zone=item.target_zone,
            attacker_mass_kg=attacker.profile.mass_kg,
            target_mass_kg=target.profile.mass_kg,
            relative_speed_mps=relative_speed,
            normal_closing_speed_mps=closing,
            contact_point=tuple(item.contact_point),
            contact_normal=tuple(normal),
            response_delta_attacker_mps=response_attacker,
            response_delta_target_mps=response_target,
            target_toughness_j_per_kg=target.profile.toughness_j_per_kg,
        )
        state = states[item.event_id]
        event = events_by_id[item.event_id]

        if not ImpactModel.qualifies(evidence):
            marker(
                "SOLVER_CONTACT_REJECTED",
                frame=item.frame,
                eventId=item.event_id,
                attackerId=item.attacker_id,
                targetId=item.target_id,
                closingSpeed=round(float(closing), 6),
                responseAttacker=round(float(response_attacker), 6),
                responseTarget=round(float(response_target), 6),
            )
            continue

        state.contact_count += 1
        state.evidence.append(evidence)
        damage_earned = evidence.severity >= MIN_DAMAGE_SEVERITY
        target_damage: dict[str, Any] | None = None
        target_visual: dict[str, Any] | None = None
        if damage_earned:
            target_damage = DamageAccumulator.apply(target.state, evidence)
            target_visual = asdict(ConsequenceEngine.apply(target, evidence))
            state.damage_count += 1
        elif event.damage_required:
            marker(
                "QUALIFIED_CONTACT_DAMAGE_THRESHOLD_NOT_MET",
                frame=item.frame,
                eventId=item.event_id,
                attackerId=item.attacker_id,
                targetId=item.target_id,
                severity=round(float(evidence.severity), 6),
                threshold=MIN_DAMAGE_SEVERITY,
            )

        _lifecycle.note_impact(
            event,
            item.attacker_id,
            damage_earned=damage_earned,
        )

        mirrored: ImpactEvidence | None = None
        attacker_visual: dict[str, Any] | None = None
        mirrored_candidate = _mirrored_impact(
            evidence,
            attacker,
            target,
            item.frame,
            response_attacker,
            response_target,
        )
        if (
            ImpactModel.qualifies(mirrored_candidate)
            and mirrored_candidate.severity >= MIN_DAMAGE_SEVERITY
        ):
            mirrored = mirrored_candidate
            DamageAccumulator.apply(attacker.state, mirrored)
            attacker_visual = asdict(
                ConsequenceEngine.apply(attacker, mirrored)
            )

        camera.mark_impact(item.frame, event, actors)
        impact_log.append(
            {
                "eventId": item.event_id,
                "evidence": asdict(evidence),
                "controllerCutoffObserved": True,
                "semanticDistance": item.semantic_distance,
                "damageEarned": damage_earned,
                "targetDamage": target_damage,
                "targetVisual": target_visual,
                "attackerEvidence": asdict(mirrored) if mirrored else None,
                "attackerVisual": attacker_visual,
            }
        )
        marker(
            "QUALIFIED_NATIVE_RESPONSE_IMPACT",
            frame=item.frame,
            eventId=item.event_id,
            attackerId=item.attacker_id,
            targetId=item.target_id,
            severity=round(float(evidence.severity), 6),
            damageEarned=damage_earned,
            impactEnergyJ=round(float(evidence.impact_energy_j), 3),
        )

    pending[:] = keep


def update_event_lifecycle(
    frame: int,
    program: Any,
    states: dict[str, Any],
) -> None:
    for event in program.events:
        state = states[event.event_id]
        if state.status in TERMINAL:
            continue

        deps_ready = _lifecycle.dependencies_ready(event, states)
        if not deps_ready:
            if (
                frame >= event.end_frame + program.fps
                and _lifecycle.dependency_failure(event, states)
            ):
                state.status = "FAILED_DEPENDENCY"
                state.completed_frame = frame
            continue

        if frame >= event.start_frame and state.first_active_frame is None:
            state.first_active_frame = frame
            state.status = "ACTIVE"

        if state.status != "ACTIVE":
            continue

        if not event.requires_contact:
            if frame >= event.end_frame:
                state.status = "SETTLED" if event.phase == "PAYOFF" else "OBSERVED"
                state.completed_frame = frame
            continue

        if frame >= event.end_frame and _lifecycle.requirements_met(event, state):
            state.status = "SUCCEEDED"
            state.completed_frame = frame
            continue

        if (
            frame >= event.end_frame
            and state.last_replan_frame is None
            and program.policies.get("replanOnPhysicalImpossibility", True)
        ):
            state.attempts += 1
            state.last_replan_frame = frame
            marker(
                "EVENT_REPLAN_WINDOW_OPENED",
                eventId=event.event_id,
                frame=frame,
                attempt=state.attempts,
            )

        grace_end = min(program.total_frames, event.end_frame + program.fps)
        if frame >= grace_end:
            if _lifecycle.requirements_met(event, state):
                state.status = "SUCCEEDED"
            else:
                state.status = "FAILED"
            state.completed_frame = frame


class ForwardPreviewDirector(runtime.CameraDirector):
    def __init__(self, fps: int) -> None:
        super().__init__(fps)
        self._approach_done = False
        self._impact_done = False
        self._aftermath_done = False
        self._impact_scene_frame: int | None = None

    def _render(self, label: str) -> None:
        if not _capture_enabled or _capture_output is None:
            return
        if label in _capture_rows:
            return
        scene = bpy.context.scene
        _capture_output.mkdir(parents=True, exist_ok=True)
        frame = int(scene.frame_current)
        path = _capture_output / f"preview-{label}-f{frame:04d}.png"
        scene.render.filepath = str(path)
        bpy.ops.render.render(write_still=True)
        if not path.is_file() or path.stat().st_size < 5000:
            raise BlenderBattleRuntimeError(
                f"FORWARD_PREVIEW_RENDER_INVALID:{label}:{frame}:{path}"
            )
        _capture_rows[label] = {
            "label": label,
            "frame": frame,
            "path": str(path),
            "bytes": path.stat().st_size,
            "sha256": runtime.sha256_file(path),
        }
        marker(
            "FORWARD_PREVIEW_CAPTURED",
            label=label,
            frame=frame,
            bytes=path.stat().st_size,
        )

    @staticmethod
    def _approach_ready(event: Any, actors: dict[str, physics.RuntimeActor]) -> bool:
        if event is None or not event.requires_contact or not event.target_id:
            return False
        target = actors.get(event.target_id)
        if target is None:
            return False
        target_pos = target.chassis.matrix_world.translation
        for attacker_id in event.attackers:
            attacker = actors.get(attacker_id)
            if attacker is None:
                continue
            distance = (attacker.chassis.matrix_world.translation - target_pos).length
            nominal_contact = 0.5 * (
                float(attacker.chassis.dimensions.x)
                + float(target.chassis.dimensions.x)
            )
            if nominal_contact * 1.10 < distance <= nominal_contact * 1.80:
                return True
        return False

    def observe(
        self,
        frame: int,
        event: Any,
        actors: dict[str, physics.RuntimeActor],
        *,
        force_key: bool = False,
        impact_emphasis: bool = False,
    ) -> None:
        super().observe(
            frame,
            event,
            actors,
            force_key=force_key,
            impact_emphasis=impact_emphasis,
        )
        if (
            _capture_enabled
            and not self._approach_done
            and self._approach_ready(event, actors)
        ):
            self._render("approach")
            self._approach_done = True
        if (
            _capture_enabled
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
        event: Any,
        actors: dict[str, physics.RuntimeActor],
    ) -> None:
        super().mark_impact(frame, event, actors)
        if _capture_enabled and not self._impact_done:
            self._impact_scene_frame = int(bpy.context.scene.frame_current)
            self._render("impact")
            self._impact_done = True


def render_previews(
    output_dir: Path,
    camera: ForwardPreviewDirector,
    total_frames: int,
) -> list[dict[str, Any]]:
    missing = [
        label
        for label in ("approach", "impact", "aftermath")
        if label not in _capture_rows
    ]
    if missing:
        raise BlenderBattleRuntimeError(
            "FORWARD_PREVIEW_MISSING:" + ",".join(missing)
        )
    return [_capture_rows[x] for x in ("approach", "impact", "aftermath")]


def main() -> None:
    _reset_process_state()
    physics.event_dependency_ready = dependency_ready
    runtime.event_dependency_ready = dependency_ready

    runtime.parse_args = parse_args
    runtime.load_json = load_json
    runtime._surface_point = surface_point
    runtime.set_controls = set_controls
    runtime.detect_contacts = detect_contacts
    runtime.resolve_pending_contacts = resolve_pending_contacts
    runtime.update_event_lifecycle = update_event_lifecycle
    runtime.CameraDirector = ForwardPreviewDirector
    runtime.render_previews = render_previews
    runtime.RUNTIME_VERSION = RUNTIME_VERSION
    runtime.main()


if __name__ == "__main__":
    main()
