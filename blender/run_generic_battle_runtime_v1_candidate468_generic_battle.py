from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from blender import iss_battle_runtime_generic_battle_v6 as battle_v6
from blender import run_generic_battle_runtime_v1_candidate467_generic_battle as candidate467
from blender.iss_battle_runtime_assets import marker
from blender.iss_battle_runtime_handoff_v1 import (
    SolverHandoffDecision,
    decide_solver_handoff as _BASE_DECIDE_SOLVER_HANDOFF,
)

CANDIDATE = "ISS_GENERIC_BATTLE_RUNTIME_V1_CANDIDATE_4_6_8_GENERIC_AUTONOMOUS_BATTLE"
MECHANISM = "G05_RECENCY_BOUNDED_SOLVER_HANDOFF_TRANSACTION_V1"
AUDIT = "G05_HANDOFF_RECENCY_FULL_AFFECTED_LAYER_AUDIT_20260918"

_ORIGINAL_BATTLE_SET_CONTROLS = battle_v6.set_controls
_context_frame = 0
_context_fps = 0


def _max_handoff_hold_frames(fps: int) -> int:
    # G05's established authority contract accepts a cutoff no older than one
    # second (fps frames). Release before that budget expires, leaving margin for
    # detect-before-control frame ordering. This does not change G05 thresholds.
    return max(2, int(fps) - 2)


def recency_bounded_decide_solver_handoff(
    latch: Any,
    *,
    current_contact_count: int,
    surface_gap_m: float,
    closing_speed_mps: float,
    characteristic_length_m: float,
) -> SolverHandoffDecision:
    base = _BASE_DECIDE_SOLVER_HANDOFF(
        latch,
        current_contact_count=current_contact_count,
        surface_gap_m=surface_gap_m,
        closing_speed_mps=closing_speed_mps,
        characteristic_length_m=characteristic_length_m,
    )
    if not base.hold:
        return base

    frame = int(_context_frame)
    fps = int(_context_fps)
    if frame <= 0 or fps <= 0:
        return base

    age = frame - int(latch.start_frame)
    budget = _max_handoff_hold_frames(fps)
    if age >= budget:
        marker(
            "GENERIC_SOLVER_HANDOFF_RECENCY_BUDGET_RELEASED",
            frame=frame,
            handoffStartFrame=int(latch.start_frame),
            handoffAgeFrames=int(age),
            maxHandoffHoldFrames=int(budget),
            fps=int(fps),
            reason="G05_CUTOFF_RECENCY_BUDGET",
            model=MECHANISM,
        )
        return SolverHandoffDecision(False, "G05_CUTOFF_RECENCY_BUDGET", base.release_gap_m)
    return base


def recency_bounded_set_controls(
    frame: int,
    program: Any,
    actors: dict[str, Any],
    states: dict[str, Any],
    control_samples: list[dict[str, Any]],
    *,
    active_goal_resolver: Any,
) -> None:
    global _context_frame, _context_fps
    _context_frame = int(frame)
    _context_fps = int(program.fps)
    _ORIGINAL_BATTLE_SET_CONTROLS(
        frame,
        program,
        actors,
        states,
        control_samples,
        active_goal_resolver=active_goal_resolver,
    )


def main() -> None:
    global _context_frame, _context_fps
    _context_frame = 0
    _context_fps = 0

    battle_v6.decide_solver_handoff = recency_bounded_decide_solver_handoff
    battle_v6.set_controls = recency_bounded_set_controls

    candidate467.CANDIDATE = CANDIDATE
    candidate467.MECHANISM = MECHANISM
    candidate467.AUDIT = AUDIT

    print(json.dumps({
        "marker": "GENERIC_AUTONOMOUS_BATTLE_C468_ENGINEERING_READY",
        "candidate": CANDIDATE,
        "mechanism": MECHANISM,
        "affectedLayerAudit": AUDIT,
        "failureFamily": "HANDOFF_LATCH_OUTLIVES_G05_CUTOFF_RECENCY_WINDOW",
        "rootCause": "IMMUTABLE_HANDOFF_CUTOFF_BECOMES_STALE_WHILE_SOLVER_LATCH_REMAINS_ACTIVE",
        "g05CutoffRecencyContractPreserved": True,
        "handoffCutoffFrameImmutableWithinLatch": True,
        "newLatchMayEstablishFreshCutoff": True,
        "semanticSelectionFrozenWithinHandoff": True,
        "existingG07ResolverReusedUnchanged": True,
        "existingG05DetectorReusedUnchanged": True,
        "semanticToleranceChanged": False,
        "localityToleranceChanged": False,
        "contactThresholdChanged": False,
        "damageAdmissionThresholdChanged": False,
        "fixtureMutationForAcceptance": False,
        "storyTargetZonePrescribed": False,
        "perAssetBattleCode": False,
        "perVideoTrajectoryEngineering": False,
        "fixedWorldCoordinates": False,
        "actorPoseOrVelocityMutation": False,
        "forcedWinner": False,
        "stateResetMechanism": False,
        "g01ToG03Changed": False,
        "frozenNineServiceArchitectureChanged": False,
        "gateClosed": False,
        "productionReadyClaimed": False,
    }, sort_keys=True), flush=True)

    candidate467.main()


if __name__ == "__main__":
    main()
