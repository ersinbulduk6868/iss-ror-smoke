#!/usr/bin/env python3
from __future__ import annotations

import ast
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from blender.iss_battle_runtime_engagement_authority_v2 import (
    CONTINUE_APPROACH,
    DEFER_TO_BASE,
    HANDOFF_TO_SOLVER,
    RECOVER_UNQUALIFIED_PROXIMITY,
    RECOVERY_OWNS,
    ApproachMotionCertificate,
    allow_outer_tactical_recovery_clear,
    authority_action,
    update_approach_certificate,
)

HELPER = ROOT / "blender" / "iss_battle_runtime_engagement_authority_v2.py"


def update(memory: ApproachMotionCertificate, **overrides):
    args = dict(
        frame=10,
        contact_directed_mode=True,
        live_readiness=True,
        recovery_active=False,
        effective_gap_m=1.0,
        handoff_gap_m=0.10,
        progress_epsilon_m=0.03,
        capability_floor_mps=1.0,
        realized_forward_speed_mps=1.20,
        realized_closing_speed_mps=1.15,
    )
    args.update(overrides)
    return update_approach_certificate(memory, **args)


def main() -> None:
    text = HELPER.read_text(encoding="utf-8")
    ast.parse(text, filename=str(HELPER))

    # A live, physically realized approach earns a certificate only outside the
    # handoff corridor.
    memory = ApproachMotionCertificate()
    qualified, invalidated, _ = update(memory)
    assert qualified is True and invalidated is False and memory.qualified is True
    assert memory.qualified_frame == 10
    assert authority_action(
        memory,
        contact_directed_mode=True,
        live_readiness=True,
        recovery_active=False,
        effective_gap_m=0.50,
        handoff_gap_m=0.10,
    ) == CONTINUE_APPROACH

    # Solver response can reverse instantaneous closing between sampled frames.
    # A certificate earned in the same uninterrupted approach therefore survives
    # entry into handoff proximity and permits atomic MOTOR -> COAST ownership.
    qualified, invalidated, _ = update(
        memory,
        frame=11,
        effective_gap_m=0.05,
        realized_forward_speed_mps=0.20,
        realized_closing_speed_mps=-0.15,
    )
    assert qualified is False and invalidated is False and memory.qualified is True
    assert authority_action(
        memory,
        contact_directed_mode=True,
        live_readiness=True,
        recovery_active=False,
        effective_gap_m=0.05,
        handoff_gap_m=0.10,
    ) == HANDOFF_TO_SOLVER

    # No certificate means proximity cannot manufacture handoff proof.
    missing = ApproachMotionCertificate()
    update(
        missing,
        effective_gap_m=0.05,
        realized_forward_speed_mps=2.0,
        realized_closing_speed_mps=2.0,
    )
    assert missing.qualified is False
    assert authority_action(
        missing,
        contact_directed_mode=True,
        live_readiness=True,
        recovery_active=False,
        effective_gap_m=0.05,
        handoff_gap_m=0.10,
    ) == RECOVER_UNQUALIFIED_PROXIMITY

    # A meaningful separation before handoff invalidates a previously earned
    # certificate; stale permission may not survive a miss.
    missed = ApproachMotionCertificate()
    update(missed, effective_gap_m=1.0)
    _, invalidated, reason = update(
        missed,
        frame=11,
        effective_gap_m=1.20,
        realized_forward_speed_mps=0.0,
        realized_closing_speed_mps=-0.2,
    )
    assert invalidated is True and missed.qualified is False
    assert reason == "PRECONTACT_SEPARATION_OR_MISS"

    # Readiness loss, tactical ownership loss, and recovery each invalidate the
    # certificate immediately.
    for case in (
        dict(live_readiness=False),
        dict(contact_directed_mode=False),
        dict(recovery_active=True),
    ):
        m = ApproachMotionCertificate()
        update(m)
        _, invalidated, _ = update(m, frame=11, **case)
        assert invalidated is True and m.qualified is False

    # Recovery is event-scoped motor authority. The outer tactical-progress
    # adapter cannot clear RECOVER_* while the transaction is active.
    assert allow_outer_tactical_recovery_clear(
        transaction_active=True,
        autonomy_mode="RECOVER_REVERSE",
        legacy_decision=True,
    ) is False
    assert allow_outer_tactical_recovery_clear(
        transaction_active=True,
        autonomy_mode="RECOVER_TURN",
        legacy_decision=True,
    ) is False
    assert allow_outer_tactical_recovery_clear(
        transaction_active=False,
        autonomy_mode="RECOVER_REVERSE",
        legacy_decision=True,
    ) is True
    assert allow_outer_tactical_recovery_clear(
        transaction_active=True,
        autonomy_mode="TRACK",
        legacy_decision=True,
    ) is True

    assert authority_action(
        ApproachMotionCertificate(qualified=True),
        contact_directed_mode=True,
        live_readiness=True,
        recovery_active=True,
        effective_gap_m=0.01,
        handoff_gap_m=0.10,
    ) == RECOVERY_OWNS
    assert authority_action(
        ApproachMotionCertificate(qualified=True),
        contact_directed_mode=False,
        live_readiness=True,
        recovery_active=False,
        effective_gap_m=0.01,
        handoff_gap_m=0.10,
    ) == DEFER_TO_BASE

    lower = text.lower()
    for forbidden in (
        "bugatti",
        "bulldozer",
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
        "marker": "GENERIC_AUTONOMOUS_BATTLE_C488_AUTHORITY_PROPERTY_ACCEPTANCE",
        "status": "PASS",
        "mechanism": "G04_EVENT_SCOPED_ENGAGEMENT_AUTHORITY_V2",
        "continuousRealizedApproachCertificate": "PASS",
        "postProximityClosingSignDeadzoneClosed": "PASS",
        "staleCertificateInvalidation": "PASS",
        "eventScopedRecoveryOwnership": "PASS",
        "g05ThresholdImported": False,
        "assetSpecificCode": False,
        "perAssetTacticalTuning": False,
        "perVideoTrajectoryEngineering": False,
        "gateClosed": False,
    }, sort_keys=True))


if __name__ == "__main__":
    main()
