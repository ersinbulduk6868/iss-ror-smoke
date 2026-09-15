from __future__ import annotations

import math
from dataclasses import asdict, dataclass

AUTONOMY_MODEL = "ISS_CLOSED_LOOP_GOAL_CONTROLLER_V1"
REPLAN_MODEL = "ISS_WORLD_STATE_REPLANNER_V1"


def clamp(value: float, lo: float, hi: float) -> float:
    return max(float(lo), min(float(hi), float(value)))


@dataclass(slots=True)
class AutonomyObservation:
    frame: int
    fps: int
    distance_m: float
    surface_gap_m: float
    heading_error_rad: float
    forward_speed_mps: float
    closing_speed_mps: float
    contention: float
    contact_count: int
    damage_count: int
    damage_required: bool
    actor_disabled: bool
    requires_contact: bool
    max_speed_mps: float
    max_reverse_mps: float
    max_yaw_rate_rad_s: float
    acceleration_mps2: float
    braking_mps2: float
    drive_efficiency: float
    characteristic_length_m: float
    speed_intent: str = "ACCELERATE"


@dataclass(slots=True)
class AutonomyMemory:
    mode: str = "TRACK"
    attempt: int = 0
    reason: str = "INIT"
    best_distance_m: float = math.inf
    last_distance_m: float | None = None
    last_surface_gap_m: float | None = None
    last_progress_frame: int = 0
    near_seen: bool = False
    last_contact_count: int = 0
    last_damage_count: int = 0
    last_command_speed_mps: float = 0.0
    recovery_reverse_until: int = 0
    recovery_turn_until: int = 0
    recovery_bias: float = 1.0
    replans: int = 0
    target_refreshes: int = 0

    def snapshot(self) -> dict[str, object]:
        row = asdict(self)
        if not math.isfinite(float(row["best_distance_m"])):
            row["best_distance_m"] = None
        return row


@dataclass(slots=True)
class AutonomyCommand:
    forward_speed_mps: float
    yaw_rate_rad_s: float
    motor_authority: str
    mode: str
    reason: str
    replan_triggered: bool
    progress_timeout_frames: int
    contact_handoff_gap_m: float


class ClosedLoopGoalController:
    """Pure control/replan policy.

    This module deliberately knows nothing about asset identity, world coordinates,
    collision frames, target impact speed, impact energy, or fixture names.  It
    consumes only current observations plus ActorProfile capability limits.
    """

    @staticmethod
    def progress_timeout_frames(obs: AutonomyObservation) -> int:
        # Give slow/large actors enough time to demonstrate progress while still
        # detecting a genuine stall.  This is capability-derived, not fixture timing.
        transit_s = obs.characteristic_length_m / max(0.5, obs.max_speed_mps)
        timeout_s = clamp(0.65 + transit_s * 2.4, 0.8, 3.0)
        return max(2, int(round(timeout_s * max(1, obs.fps))))

    @staticmethod
    def recovery_frames(obs: AutonomyObservation) -> tuple[int, int]:
        yaw_time_s = 1.0 / max(0.15, obs.max_yaw_rate_rad_s)
        reverse_s = clamp(0.45 + yaw_time_s * 0.30, 0.55, 1.35)
        turn_s = clamp(0.55 + yaw_time_s * 0.55, 0.70, 2.20)
        fps = max(1, obs.fps)
        return max(2, int(round(reverse_s * fps))), max(2, int(round(turn_s * fps)))

    @staticmethod
    def contact_handoff_gap(obs: AutonomyObservation) -> float:
        # The handoff only removes motor authority immediately before solver response.
        # It is not a contact detector and does not declare contact success.
        one_step_travel = max(0.0, obs.closing_speed_mps) / max(1, obs.fps)
        geometric_margin = max(0.02, obs.characteristic_length_m * 0.012)
        return geometric_margin + one_step_travel * 1.25

    @staticmethod
    def _begin_recovery(
        memory: AutonomyMemory,
        obs: AutonomyObservation,
        reason: str,
        recovery_bias: float,
    ) -> None:
        reverse_frames, turn_frames = ClosedLoopGoalController.recovery_frames(obs)
        memory.mode = "RECOVER_REVERSE"
        memory.reason = reason
        memory.recovery_bias = 1.0 if recovery_bias >= 0.0 else -1.0
        memory.recovery_reverse_until = obs.frame + reverse_frames
        memory.recovery_turn_until = memory.recovery_reverse_until + turn_frames
        memory.replans += 1
        memory.attempt += 1
        memory.last_progress_frame = obs.frame
        memory.best_distance_m = obs.distance_m
        memory.near_seen = False

    @staticmethod
    def _recovery_command(
        memory: AutonomyMemory,
        obs: AutonomyObservation,
        timeout_frames: int,
        handoff_gap: float,
    ) -> AutonomyCommand | None:
        efficiency = clamp(obs.drive_efficiency, 0.0, 1.0)
        if obs.frame <= memory.recovery_reverse_until:
            memory.mode = "RECOVER_REVERSE"
            reverse = min(
                obs.max_reverse_mps,
                max(0.6, math.sqrt(max(0.1, obs.acceleration_mps2) * max(0.25, obs.characteristic_length_m)) * 0.45),
            )
            speed = -reverse * max(0.15, efficiency)
            yaw = memory.recovery_bias * obs.max_yaw_rate_rad_s * 0.45
            memory.last_command_speed_mps = speed
            return AutonomyCommand(
                speed,
                yaw,
                "MOTOR",
                memory.mode,
                memory.reason,
                False,
                timeout_frames,
                handoff_gap,
            )
        if obs.frame <= memory.recovery_turn_until:
            memory.mode = "RECOVER_TURN"
            yaw = memory.recovery_bias * obs.max_yaw_rate_rad_s * 0.88
            memory.last_command_speed_mps = 0.0
            return AutonomyCommand(
                0.0,
                yaw,
                "MOTOR",
                memory.mode,
                memory.reason,
                False,
                timeout_frames,
                handoff_gap,
            )
        if memory.mode.startswith("RECOVER_"):
            memory.mode = "TRACK"
            memory.reason = "RECOVERY_COMPLETE"
            memory.last_progress_frame = obs.frame
            memory.best_distance_m = obs.distance_m
            memory.last_distance_m = obs.distance_m
            memory.last_surface_gap_m = obs.surface_gap_m
            memory.last_command_speed_mps = 0.0
        return None

    @staticmethod
    def update(
        memory: AutonomyMemory,
        obs: AutonomyObservation,
        *,
        recovery_bias: float = 1.0,
    ) -> AutonomyCommand:
        fps = max(1, int(obs.fps))
        timeout_frames = ClosedLoopGoalController.progress_timeout_frames(obs)
        handoff_gap = ClosedLoopGoalController.contact_handoff_gap(obs)
        memory.target_refreshes += 1

        if memory.last_progress_frame <= 0:
            memory.last_progress_frame = obs.frame
        if not math.isfinite(memory.best_distance_m):
            memory.best_distance_m = obs.distance_m

        progress_epsilon = max(0.025, obs.characteristic_length_m * 0.008)
        if obs.distance_m < memory.best_distance_m - progress_epsilon:
            memory.best_distance_m = obs.distance_m
            memory.last_progress_frame = obs.frame

        near_threshold = max(0.18, obs.characteristic_length_m * 0.20)
        if obs.surface_gap_m <= near_threshold:
            memory.near_seen = True

        new_contact = obs.contact_count > memory.last_contact_count
        new_damage = obs.damage_count > memory.last_damage_count
        replan_reason: str | None = None

        if new_contact and obs.damage_required and not new_damage:
            replan_reason = "NONPRODUCTIVE_CONTACT"
        elif (
            memory.near_seen
            and memory.last_surface_gap_m is not None
            and obs.surface_gap_m > memory.last_surface_gap_m + progress_epsilon
            and obs.closing_speed_mps < -0.10
            and not new_contact
        ):
            replan_reason = "MISSED_TARGET"
        elif (
            obs.contention >= 0.72
            and abs(memory.last_command_speed_mps) > 0.20
            and obs.frame - memory.last_progress_frame >= max(2, timeout_frames // 2)
        ):
            replan_reason = "BLOCKED_CONTENTION"
        elif (
            abs(memory.last_command_speed_mps) > 0.25
            and obs.surface_gap_m > handoff_gap
            and obs.frame - memory.last_progress_frame >= timeout_frames
        ):
            replan_reason = "STALL_NO_PROGRESS"

        memory.last_contact_count = max(memory.last_contact_count, obs.contact_count)
        memory.last_damage_count = max(memory.last_damage_count, obs.damage_count)

        if obs.actor_disabled:
            memory.mode = "DISABLED"
            memory.reason = "ACTOR_DISABLED"
            memory.last_command_speed_mps = 0.0
            memory.last_distance_m = obs.distance_m
            memory.last_surface_gap_m = obs.surface_gap_m
            return AutonomyCommand(
                0.0,
                0.0,
                "COAST",
                memory.mode,
                memory.reason,
                False,
                timeout_frames,
                handoff_gap,
            )

        if replan_reason is not None and not memory.mode.startswith("RECOVER_"):
            ClosedLoopGoalController._begin_recovery(
                memory,
                obs,
                replan_reason,
                recovery_bias,
            )
            command = ClosedLoopGoalController._recovery_command(
                memory, obs, timeout_frames, handoff_gap
            )
            assert command is not None
            command.replan_triggered = True
            memory.last_distance_m = obs.distance_m
            memory.last_surface_gap_m = obs.surface_gap_m
            return command

        recovery = ClosedLoopGoalController._recovery_command(
            memory, obs, timeout_frames, handoff_gap
        )
        if recovery is not None:
            memory.last_distance_m = obs.distance_m
            memory.last_surface_gap_m = obs.surface_gap_m
            return recovery

        speed_intent = str(obs.speed_intent or "ACCELERATE").upper()
        if speed_intent in {"HOLD", "STOP", "BRAKE", "SETTLE"}:
            memory.mode = "IDLE"
            memory.reason = speed_intent
            memory.last_command_speed_mps = 0.0
            memory.last_distance_m = obs.distance_m
            memory.last_surface_gap_m = obs.surface_gap_m
            return AutonomyCommand(
                0.0,
                0.0,
                "MOTOR",
                memory.mode,
                memory.reason,
                False,
                timeout_frames,
                handoff_gap,
            )

        if (
            obs.requires_contact
            and obs.surface_gap_m <= handoff_gap
            and obs.closing_speed_mps >= 0.0
        ):
            memory.mode = "CONTACT_HANDOFF"
            memory.reason = "SOLVER_AUTHORITY_IMMINENT"
            memory.last_command_speed_mps = 0.0
            memory.last_distance_m = obs.distance_m
            memory.last_surface_gap_m = obs.surface_gap_m
            return AutonomyCommand(
                0.0,
                0.0,
                "COAST",
                memory.mode,
                memory.reason,
                False,
                timeout_frames,
                handoff_gap,
            )

        efficiency = clamp(obs.drive_efficiency, 0.0, 1.0)
        max_forward = max(0.0, obs.max_speed_mps * efficiency)
        max_reverse = max(0.0, obs.max_reverse_mps * efficiency)
        max_yaw = max(0.05, obs.max_yaw_rate_rad_s * max(0.15, efficiency))

        # Current heading error drives current yaw demand. No trajectory is cached.
        yaw_time_constant_s = 0.55
        yaw_rate = clamp(
            obs.heading_error_rad / yaw_time_constant_s,
            -max_yaw,
            max_yaw,
        )

        abs_error = abs(obs.heading_error_rad)
        heading_quality = max(
            0.10,
            math.cos(min(abs_error, math.pi / 2.0)) ** 2,
        )

        if speed_intent == "REVERSE":
            forward_speed = -max_reverse * heading_quality
        else:
            accel = max(0.1, obs.acceleration_mps2)
            characteristic = max(0.25, obs.characteristic_length_m)
            approach_distance = max(0.0, obs.surface_gap_m) + characteristic * 0.55
            distance_cap = math.sqrt(2.0 * accel * approach_distance)
            if obs.requires_contact:
                # A contact goal must not asymptotically brake to zero before contact.
                # The floor comes from actor capability/scale, not desired impact energy.
                engagement_floor = math.sqrt(accel * characteristic) * 0.72
                distance_cap = max(distance_cap, engagement_floor)
            forward_speed = min(max_forward, distance_cap) * heading_quality
            if abs_error > 1.35:
                forward_speed = min(forward_speed, max_forward * 0.22)

        if obs.contention > 0.0 and forward_speed > 0.0:
            forward_speed *= 1.0 - 0.55 * clamp(obs.contention, 0.0, 1.0)

        memory.mode = "TRACK"
        memory.reason = "GOAL_ERROR_CONTROL"
        memory.last_command_speed_mps = forward_speed
        memory.last_distance_m = obs.distance_m
        memory.last_surface_gap_m = obs.surface_gap_m
        return AutonomyCommand(
            forward_speed,
            yaw_rate,
            "MOTOR",
            memory.mode,
            memory.reason,
            False,
            timeout_frames,
            handoff_gap,
        )
