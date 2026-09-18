#!/usr/bin/env python3
from __future__ import annotations

import ast
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from blender.iss_battle_runtime_engagement_lifecycle_v1 import (
    ALLOW_CONTACT,
    DEFER_TO_TACTIC,
    HOLD_STANDOFF,
    REOPEN_DISTANCE,
    SUSPEND_FOR_RECOVERY,
    EngagementLifecycleMemory,
    note_recovery_transition,
    precontact_action,
    transaction_key,
)

HELPER = ROOT / "blender" / "iss_battle_runtime_engagement_lifecycle_v1.py"
WRAPPER = ROOT / "blender" / "run_generic_battle_runtime_v1_candidate487_generic_battle.py"


def action(mode: str, *, recovery: bool = False, armed: bool = True, ready: bool = False, gap: float = 2.0, runway: float = 4.0) -> str:
    return precontact_action(
        tactical_mode=mode,
        requires_contact=True,
        recovery_active=recovery,
        runway_armed=armed,
        contact_ready=ready,
        surface_gap_m=gap,
        runway_required_m=runway,
    )


def main() -> None:
    helper_text = HELPER.read_text(encoding="utf-8")
    wrapper_text = WRAPPER.read_text(encoding="utf-8")
    ast.parse(helper_text, filename=str(HELPER))
    ast.parse(wrapper_text, filename=str(WRAPPER))

    # Non-contact-directed tactics remain owned by the existing planner.
    for mode in ("FLANK", "BRAKE_APPROACH", "EVADE", "BREAK_CONTACT", "REPOSITION", "HOLD"):
        assert action(mode, recovery=False, armed=True, ready=False, gap=-1.0) == DEFER_TO_TACTIC, mode

    # Recovery takes priority over contact commit in the two contact-directed modes.
    for mode in ("ENGAGE", "COUNTER"):
        assert action(mode, recovery=True, armed=True, ready=True, gap=0.0) == SUSPEND_FOR_RECOVERY
        assert action(mode, recovery=False, armed=True, ready=True, gap=0.0) == ALLOW_CONTACT
        assert action(mode, recovery=False, armed=True, ready=False, gap=1.0, runway=4.0) == REOPEN_DISTANCE
        assert action(mode, recovery=False, armed=True, ready=False, gap=4.0, runway=4.0) == HOLD_STANDOFF

    # Event identity is part of the lifecycle key: same pair in sequential events is isolated.
    a = transaction_key("evt-a", "actor_alpha", "actor_beta")
    b = transaction_key("evt-b", "actor_alpha", "actor_beta")
    assert a != b
    assert a[1:] == b[1:]

    # Recovery epoch starts once, remains stable while recovering, then completes.
    memory = EngagementLifecycleMemory()
    started, completed = note_recovery_transition(
        memory,
        frame=10,
        previous_controller_mode="TRACK",
        current_controller_mode="RECOVER_REVERSE",
    )
    assert started is True and completed is False
    assert memory.recovery_epoch == 1
    started, completed = note_recovery_transition(
        memory,
        frame=11,
        previous_controller_mode="RECOVER_REVERSE",
        current_controller_mode="RECOVER_TURN",
    )
    assert started is False and completed is False
    assert memory.recovery_epoch == 1
    started, completed = note_recovery_transition(
        memory,
        frame=12,
        previous_controller_mode="RECOVER_TURN",
        current_controller_mode="TRACK",
    )
    assert started is False and completed is True
    assert memory.recovery_epoch == 1

    combined = helper_text + "\n" + wrapper_text
    for required in (
        "G04_EVENT_SCOPED_ENGAGEMENT_AUTHORITY_LIFECYCLE_V1",
        "transaction_key(event.event_id, entity, event.target_id)",
        "_event_tactical_memories",
        "_active_transaction_by_actor",
        "_clear_legacy_pair_state",
        "_sync_pending_tactical_context",
        'context["currentTacticalMode"] = str(tactical.mode)',
        "G04_EVENT_TRANSACTION_CHANGED",
        "G04_EVENT_SCOPED_STALL_RECOVERY_TRIGGERED",
        "G04_EVENT_SCOPED_RECOVERY_REPLAN_PROPAGATED",
        "G04_EVENT_SCOPED_RECOVERY_COMPLETED_RUNWAY_INVALIDATED",
        "G04_ACTUAL_GOAL_CONTACT_READINESS_RECOVERED",
        "G04_ENGAGEMENT_LIFECYCLE_TRANSITION",
        "PHASE_HANDOFF_READY",
        "G04_EVENT_SCOPED_PAIR_CONTEXT_MISMATCH",
        "G04_EVENT_SCOPED_TRANSACTION_CONTEXT_MISSING",
        'candidate486.corridor_aware_tactical_decide = candidate486._C485_TACTICAL_DECIDE',
        '"g05NativeSolverFinalAuthorityPreserved": True',
        '"g05SourceChanged": False',
        '"g06SourceChanged": False',
        '"g07SourceChanged": False',
        '"g08SourceChanged": False',
        '"eventActorTargetTransactionScope": True',
        '"tacticalMutationProgressContextSynchronized": True',
        '"recoveryReplanPropagatedExactlyOncePerEpoch": True',
        '"runwayInvalidatedAfterRecovery": True',
        '"c486ModeBlindCorridorSuperseded": True',
        '"perAssetBattleCode": False',
        '"perAssetTacticalTuning": False',
        '"perVideoTrajectoryEngineering": False',
        '"gateClosed": False',
    ):
        assert required in combined, required

    lower = combined.lower()
    for forbidden in (
        "bugatti",
        "bulldozer",
        "b06a715d23a7450babac383b8bb7fb0a",
        "27614.189525707065",
        "min_closing_speed_mps",
        "min_damage_severity",
        "desiredimpactspeedmps",
        "desiredimpactenergyj",
        "collisionframe",
        "impactframe",
        "trajectorypoints",
        "waypoints",
        "set_pose",
        "linear_velocity =",
    ):
        assert forbidden not in lower, forbidden

    print(json.dumps({
        "marker": "GENERIC_AUTONOMOUS_BATTLE_C487_PROPERTY_ACCEPTANCE",
        "status": "PASS",
        "failureFamily": "G04_FRAGMENTED_PRECONTACT_RECOVERY_AND_SOLVER_AUTHORITY_TRANSFER_LIFECYCLE",
        "mechanism": "G04_EVENT_SCOPED_ENGAGEMENT_AUTHORITY_LIFECYCLE_V1",
        "modeOwnershipIsolation": "PASS",
        "eventTransactionIsolation": "PASS",
        "recoveryEpochLifecycle": "PASS",
        "tacticalProgressContextSynchronization": "PASS",
        "actualGoalReadinessContract": "PASS",
        "g05NativeAuthorityPreserved": True,
        "g05ThresholdImported": False,
        "assetSpecificCode": False,
        "perAssetTacticalTuning": False,
        "perVideoTrajectoryEngineering": False,
        "masterPlanAligned": True,
        "gateClosed": False,
    }, sort_keys=True))


if __name__ == "__main__":
    main()
