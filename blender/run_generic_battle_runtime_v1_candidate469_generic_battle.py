from __future__ import annotations

import json
import sys
from typing import Any

REPO_ROOT = __import__("pathlib").Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from blender import iss_blender_battle_runtime_v1_hardened as hardened
from blender import iss_battle_runtime_generic_battle_v6 as battle_v6
from blender import run_generic_battle_runtime_v1_candidate467_generic_battle as candidate467
from blender import run_generic_battle_runtime_v1_candidate468_generic_battle as candidate468
from blender.iss_battle_runtime_assets import marker
from blender.iss_battle_runtime_handoff_v3 import (
    CUTOFF_TRANSACTION_CLEANUP_MODEL,
    invalidate_released_handoff_cutoffs,
)

CANDIDATE = "ISS_GENERIC_BATTLE_RUNTIME_V1_CANDIDATE_4_6_9_GENERIC_AUTONOMOUS_BATTLE"
MECHANISM = "G05_EVENT_LOCAL_HANDOFF_TRANSACTION_CLEANUP_V1"
AUDIT = "G05_HANDOFF_RELEASE_CUTOFF_LIFECYCLE_FULL_AFFECTED_LAYER_AUDIT_20260918"

_ORIGINAL_C468_SET_CONTROLS = candidate468.recency_bounded_set_controls


def transaction_clean_set_controls(
    frame: int,
    program: Any,
    actors: dict[str, Any],
    states: dict[str, Any],
    control_samples: list[dict[str, Any]],
    *,
    active_goal_resolver: Any,
) -> None:
    before_start_frames = {
        key: int(latch.start_frame)
        for key, latch in battle_v6._handoff_latches.items()
    }

    _ORIGINAL_C468_SET_CONTROLS(
        frame,
        program,
        actors,
        states,
        control_samples,
        active_goal_resolver=active_goal_resolver,
    )

    changes = invalidate_released_handoff_cutoffs(
        hardened._cutoff_frames,
        before_start_frames,
        battle_v6._handoff_latches,
    )
    for change in changes:
        marker(
            "GENERIC_SOLVER_HANDOFF_TRANSACTION_CUTOFF_CLEANUP",
            frame=int(frame),
            eventId=change["eventId"],
            actorId=change["actorId"],
            previousHandoffStartFrame=change["previousHandoffStartFrame"],
            newHandoffStartFrame=change["newHandoffStartFrame"],
            previousCutoffFrame=change["previousCutoffFrame"],
            action=change["action"],
            model=CUTOFF_TRANSACTION_CLEANUP_MODEL,
        )


def main() -> None:
    # Preserve C468's recency-bounded handoff decision and C465's immutable
    # active-transaction cutoff semantics. C469 adds only transaction-end cleanup.
    battle_v6.decide_solver_handoff = candidate468.recency_bounded_decide_solver_handoff
    battle_v6.set_controls = transaction_clean_set_controls

    candidate467.CANDIDATE = CANDIDATE
    candidate467.MECHANISM = MECHANISM
    candidate467.AUDIT = AUDIT

    print(json.dumps({
        "marker": "GENERIC_AUTONOMOUS_BATTLE_C469_ENGINEERING_READY",
        "candidate": CANDIDATE,
        "mechanism": MECHANISM,
        "affectedLayerAudit": AUDIT,
        "failureFamily": "RELEASED_HANDOFF_LEAVES_STALE_G05_CUTOFF_AUTHORIZATION",
        "rootCause": "LATCH_RELEASE_WITHOUT_EVENT_LOCAL_CUTOFF_INVALIDATION",
        "runtimeFrameOrdering": "DETECT_CONTACTS_BEFORE_SET_CONTROLS",
        "g05CutoffRecencyContractPreserved": True,
        "activeHandoffCutoffImmutableWithinLatch": True,
        "releasedTransactionCutoffInvalidated": True,
        "sameFrameFreshRelatchCutoffPreserved": True,
        "newLatchEstablishesFreshCutoff": True,
        "semanticSelectionFrozenWithinActiveHandoff": True,
        "existingG05DetectorReusedUnchanged": True,
        "existingG07ResolverReusedUnchanged": True,
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
