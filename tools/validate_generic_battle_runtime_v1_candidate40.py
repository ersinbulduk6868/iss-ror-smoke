#!/usr/bin/env python3
from __future__ import annotations

import json
import math
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from blender.iss_battle_runtime_autonomy import (  # noqa: E402
    AUTONOMY_MODEL,
    REPLAN_MODEL,
    AutonomyMemory,
    AutonomyObservation,
    ClosedLoopGoalController,
)


class ValidationError(RuntimeError):
    pass


def obs(**overrides):
    base = dict(
        frame=1,
        fps=30,
        distance_m=12.0,
        surface_gap_m=7.0,
        heading_error_rad=0.25,
        forward_speed_mps=0.0,
        closing_speed_mps=0.0,
        contention=0.0,
        contact_count=0,
        damage_count=0,
        damage_required=True,
        actor_disabled=False,
        requires_contact=True,
        max_speed_mps=20.0,
        max_reverse_mps=6.0,
        max_yaw_rate_rad_s=1.35,
        acceleration_mps2=7.0,
        braking_mps2=10.0,
        drive_efficiency=1.0,
        characteristic_length_m=4.8,
        speed_intent="ACCELERATE",
    )
    base.update(overrides)
    return AutonomyObservation(**base)


def moving_target_property() -> dict[str, object]:
    memory = AutonomyMemory()
    a = ClosedLoopGoalController.update(memory, obs(frame=1, distance_m=12.0, heading_error_rad=0.55))
    b = ClosedLoopGoalController.update(memory, obs(frame=2, distance_m=11.7, heading_error_rad=-0.55, closing_speed_mps=1.5))
    if not (a.yaw_rate_rad_s > 0.0 and b.yaw_rate_rad_s < 0.0):
        raise ValidationError("MOVING_TARGET_STEERING_NOT_REACTIVE")
    if memory.target_refreshes != 2:
        raise ValidationError("TARGET_NOT_REFRESHED_EVERY_CONTROL_STEP")
    return {"status": "PASS", "yawA": a.yaw_rate_rad_s, "yawB": b.yaw_rate_rad_s, "refreshes": memory.target_refreshes}


def stall_recovery_property() -> dict[str, object]:
    probe = obs()
    timeout = ClosedLoopGoalController.progress_timeout_frames(probe)
    memory = AutonomyMemory(
        best_distance_m=10.0,
        last_distance_m=10.0,
        last_surface_gap_m=5.0,
        last_progress_frame=1,
        last_command_speed_mps=4.0,
    )
    command = ClosedLoopGoalController.update(
        memory,
        obs(frame=timeout + 2, distance_m=10.0, surface_gap_m=5.0, closing_speed_mps=0.0),
        recovery_bias=1.0,
    )
    if not command.replan_triggered or command.reason != "STALL_NO_PROGRESS" or command.mode != "RECOVER_REVERSE":
        raise ValidationError("STALL_RECOVERY_NOT_TRIGGERED")
    return {"status": "PASS", "timeoutFrames": timeout, "mode": command.mode, "reason": command.reason}


def miss_recovery_property() -> dict[str, object]:
    memory = AutonomyMemory(
        best_distance_m=4.5,
        last_distance_m=4.5,
        last_surface_gap_m=0.08,
        last_progress_frame=10,
        near_seen=True,
        last_command_speed_mps=4.0,
    )
    command = ClosedLoopGoalController.update(
        memory,
        obs(frame=11, distance_m=5.2, surface_gap_m=0.55, closing_speed_mps=-1.2),
        recovery_bias=-1.0,
    )
    if not command.replan_triggered or command.reason != "MISSED_TARGET":
        raise ValidationError("MISS_RECOVERY_NOT_TRIGGERED")
    return {"status": "PASS", "mode": command.mode, "reason": command.reason}


def contention_recovery_property() -> dict[str, object]:
    probe = obs()
    timeout = ClosedLoopGoalController.progress_timeout_frames(probe)
    memory = AutonomyMemory(
        best_distance_m=10.0,
        last_distance_m=10.0,
        last_surface_gap_m=5.0,
        last_progress_frame=1,
        last_command_speed_mps=3.0,
    )
    command = ClosedLoopGoalController.update(
        memory,
        obs(frame=max(3, timeout // 2 + 2), distance_m=10.0, surface_gap_m=5.0, contention=0.92),
        recovery_bias=1.0,
    )
    if not command.replan_triggered or command.reason != "BLOCKED_CONTENTION":
        raise ValidationError("CONTENTION_RECOVERY_NOT_TRIGGERED")
    return {"status": "PASS", "mode": command.mode, "reason": command.reason}


def nonproductive_contact_property() -> dict[str, object]:
    memory = AutonomyMemory(
        best_distance_m=4.8,
        last_distance_m=4.8,
        last_surface_gap_m=0.01,
        last_progress_frame=1,
        last_contact_count=0,
        last_damage_count=0,
        last_command_speed_mps=2.0,
    )
    command = ClosedLoopGoalController.update(
        memory,
        obs(frame=2, distance_m=4.8, surface_gap_m=0.02, contact_count=1, damage_count=0, damage_required=True),
        recovery_bias=-1.0,
    )
    if not command.replan_triggered or command.reason != "NONPRODUCTIVE_CONTACT":
        raise ValidationError("NONPRODUCTIVE_CONTACT_NOT_REPLANNED")
    return {"status": "PASS", "mode": command.mode, "reason": command.reason}


def disabled_actor_property() -> dict[str, object]:
    memory = AutonomyMemory()
    command = ClosedLoopGoalController.update(memory, obs(actor_disabled=True))
    if command.mode != "DISABLED" or command.motor_authority != "COAST":
        raise ValidationError("DISABLED_ACTOR_STILL_HAS_AUTHORITY")
    if abs(command.forward_speed_mps) > 1e-9 or abs(command.yaw_rate_rad_s) > 1e-9:
        raise ValidationError("DISABLED_ACTOR_NONZERO_COMMAND")
    return {"status": "PASS", "mode": command.mode, "motorAuthority": command.motor_authority}


def recovery_progression_property() -> dict[str, object]:
    probe = obs()
    timeout = ClosedLoopGoalController.progress_timeout_frames(probe)
    memory = AutonomyMemory(
        best_distance_m=10.0,
        last_distance_m=10.0,
        last_surface_gap_m=5.0,
        last_progress_frame=1,
        last_command_speed_mps=4.0,
    )
    first = ClosedLoopGoalController.update(memory, obs(frame=timeout + 2, distance_m=10.0, surface_gap_m=5.0), recovery_bias=1.0)
    reverse_until = memory.recovery_reverse_until
    turn_until = memory.recovery_turn_until
    second = ClosedLoopGoalController.update(memory, obs(frame=reverse_until + 1, distance_m=10.2, surface_gap_m=5.2), recovery_bias=1.0)
    third = ClosedLoopGoalController.update(memory, obs(frame=turn_until + 1, distance_m=10.1, surface_gap_m=5.1), recovery_bias=1.0)
    if first.mode != "RECOVER_REVERSE" or second.mode != "RECOVER_TURN" or third.mode != "TRACK":
        raise ValidationError("RECOVERY_STATE_MACHINE_INVALID")
    if memory.replans != 1 or memory.attempt != 1:
        raise ValidationError("RECOVERY_COUNTER_INVALID")
    return {"status": "PASS", "modes": [first.mode, second.mode, third.mode], "replans": memory.replans}


def contact_handoff_property() -> dict[str, object]:
    memory = AutonomyMemory()
    probe = obs(frame=10, distance_m=4.9, surface_gap_m=0.01, closing_speed_mps=4.0, damage_required=False)
    gap = ClosedLoopGoalController.contact_handoff_gap(probe)
    command = ClosedLoopGoalController.update(memory, probe)
    if command.mode != "CONTACT_HANDOFF" or command.motor_authority != "COAST":
        raise ValidationError("CONTACT_HANDOFF_NOT_SOLVER_OWNED")
    if gap <= 0.0:
        raise ValidationError("CONTACT_HANDOFF_GAP_INVALID")
    return {"status": "PASS", "handoffGapM": gap, "mode": command.mode}


def static_source_audit() -> dict[str, object]:
    autonomy = (ROOT / "blender/iss_battle_runtime_autonomy.py").read_text(encoding="utf-8")
    candidate = (ROOT / "blender/run_generic_battle_runtime_v1_candidate40.py").read_text(encoding="utf-8")
    audit = (ROOT / "docs/ISS_G04_FULL_AFFECTED_LAYER_AUDIT.md").read_text(encoding="utf-8")

    required = (
        AUTONOMY_MODEL,
        REPLAN_MODEL,
        "INTENT_ONLY_EXECUTION_CONTRACT_PASS",
        "AUTONOMY_REPLAN_TRIGGERED",
        "AUTONOMY_MODE_CHANGED",
        "STORY_WINDOW_EXCEEDED_GOAL_STILL_ACTIVE",
        "nativeContactTruthClaimed\": False",
        "damageGateClaimed\": False",
        "productionReadyClaimed\": False",
        "FULL_AFFECTED_LAYER_AUDIT = PASS_FOR_IMPLEMENTATION",
    )
    combined = autonomy + "\n" + candidate + "\n" + audit
    missing = [token for token in required if token not in combined]
    if missing:
        raise ValidationError("G04_REQUIRED_SOURCE_TOKEN_MISSING:" + ",".join(missing))

    forbidden_runtime_identity = ("bugatti", "bulldozer", "actor_alpha", "actor_beta", "sourceuid")
    lowered_autonomy = autonomy.lower()
    identity_hits = [token for token in forbidden_runtime_identity if token in lowered_autonomy]
    if identity_hits:
        raise ValidationError("AUTONOMY_ASSET_OR_FIXTURE_IDENTITY_HARDCODE:" + ",".join(identity_hits))

    forbidden_cheats = (
        ".location =",
        ".linear_velocity =",
        "seed_velocity",
        "keyframe_insert(data_path=\"location\"",
        "MIN_DAMAGE_SEVERITY =",
    )
    cheat_hits = [token for token in forbidden_cheats if token in autonomy]
    if cheat_hits:
        raise ValidationError("AUTONOMY_FORBIDDEN_CHEAT_OR_THRESHOLD:" + ",".join(cheat_hits))

    for token in (
        "targetenergyj",
        "impactenergyj",
        "collisionframe",
        "impactspeedmps",
        "trajectorypoints",
        "positionkeyframes",
        "velocitykeyframes",
    ):
        if token not in candidate.lower():
            raise ValidationError("INTENT_FIREWALL_TOKEN_MISSING:" + token)

    if "physics.drive_command(" in candidate:
        raise ValidationError("CANDIDATE40_STILL_USES_FIXED_TACTIC_DRIVE_COMMAND")

    return {
        "status": "PASS",
        "autonomyModel": AUTONOMY_MODEL,
        "replanModel": REPLAN_MODEL,
        "assetSpecificRuntimeIdentityHits": identity_hits,
        "forbiddenCheatHits": cheat_hits,
        "legacyFixedTacticDriveCommandUsed": False,
    }


def main() -> None:
    result = {
        "static": static_source_audit(),
        "movingTarget": moving_target_property(),
        "stallRecovery": stall_recovery_property(),
        "missRecovery": miss_recovery_property(),
        "contentionRecovery": contention_recovery_property(),
        "nonproductiveContact": nonproductive_contact_property(),
        "disabledActor": disabled_actor_property(),
        "recoveryProgression": recovery_progression_property(),
        "contactHandoff": contact_handoff_property(),
    }
    print(json.dumps({"marker": "GENERIC_BATTLE_RUNTIME_CANDIDATE40_G04_PROPERTY_ACCEPTANCE", "status": "PASS", "result": result}, sort_keys=True))


if __name__ == "__main__":
    main()
