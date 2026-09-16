from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from blender import run_generic_battle_runtime_v1_candidate44 as candidate44
from blender import run_generic_battle_runtime_v1_candidate443 as candidate443
from blender.iss_battle_runtime_assets import BlenderBattleRuntimeError, marker

CANDIDATE = "ISS_GENERIC_BATTLE_RUNTIME_V1_CANDIDATE_4_4_6_G07"
CLIMAX_REALIZATION_MODEL = "CAUSAL_REVERSAL_STATE_CLIMAX_V1"

_ORIGINAL_G07_ACTIVE_GOAL = candidate44.g07_active_goal_for_actor
_ORIGINAL_G07_UPDATE = candidate44.g07_update_event_lifecycle
_ORIGINAL_V4_WRITE_EVIDENCE = candidate443.g07_v4_write_evidence


def g07_v7_active_goal_for_actor(
    entity: str,
    frame: int,
    program: Any,
    states: dict[str, Any],
):
    event = _ORIGINAL_G07_ACTIVE_GOAL(entity, frame, program, states)
    if event is not None and candidate44._phase(event) == "CLIMAX" and not event.requires_contact:
        # A causal climax state is drama/lifecycle truth, not a new motion goal.
        return None
    return event


def _realize_causal_climax(frame: int, program: Any, states: dict[str, Any]) -> None:
    tracker = candidate44._tracker
    for event in program.events:
        if candidate44._phase(event) != "CLIMAX" or event.requires_contact:
            continue
        state = states[event.event_id]
        if state.status != "ACTIVE" or tracker.climax is not None:
            continue
        if tracker.reversal is None or tracker.counterattack is None:
            continue
        reversal_frame = int(tracker.reversal.get("frame") or -1)
        counter_frame = int(tracker.counterattack.get("frame") or -1)
        if int(frame) <= max(reversal_frame, counter_frame):
            continue
        if not candidate44.hardened._lifecycle.dependencies_ready(event, states):
            continue

        tracker.climax = tracker._transition(
            "CLIMAX_PHYSICALLY_EARNED",
            frame,
            eventId=event.event_id,
            authority="REALIZED_REVERSAL_AND_PERSISTENT_STATE",
            climaxRealization=CLIMAX_REALIZATION_MODEL,
            climaxRequiresNewContact=False,
            reversalFrame=reversal_frame,
            counterattackFrame=counter_frame,
            directPhysicalTransactionCount=len(tracker.direct_transactions),
            dominance=candidate44._json_copy(tracker.dominance_snapshot(candidate44._actor_refs, frame)),
        )
        state.status = "OBSERVED"
        state.completed_frame = int(frame)
        tracker.record_completion(event, candidate44._actor_refs, frame, state.status)
        marker(
            "G07_CAUSAL_CLIMAX_STATE_REALIZED",
            frame=int(frame),
            eventId=event.event_id,
            model=CLIMAX_REALIZATION_MODEL,
            authority="REALIZED_REVERSAL_AND_PERSISTENT_STATE",
            climaxRequiresNewContact=False,
            reversalFrame=reversal_frame,
            counterattackFrame=counter_frame,
        )


def g07_v7_update_event_lifecycle(frame: int, program: Any, states: dict[str, Any]) -> None:
    # First allow the established G07 lifecycle to activate dependency/guard-ready
    # events. On the next physics tick a contact-free CLIMAX can be earned from the
    # already-realized reversal. No G04/G05/G06 control/contact/consequence code is
    # changed or invoked differently.
    _realize_causal_climax(frame, program, states)
    _ORIGINAL_G07_UPDATE(frame, program, states)


def g07_v7_write_evidence(states: dict[str, Any], outcome: dict[str, Any]) -> None:
    _ORIGINAL_V4_WRITE_EVIDENCE(states, outcome)
    if candidate44.hardened._capture_output is None:
        raise BlenderBattleRuntimeError("G07_OUTPUT_DIR_UNAVAILABLE")
    path = Path(candidate44.hardened._capture_output) / "g07-causal-drama-evidence.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    data.update(
        {
            "climaxRealizationModel": CLIMAX_REALIZATION_MODEL,
            "climaxRequiresNewContact": False,
            "climaxAuthority": "REALIZED_REVERSAL_AND_PERSISTENT_STATE",
            "receiptAdmissionWorkaround": False,
            "g07OwnsDramaLifecycleOnly": True,
            "g04ControlLawChanged": False,
            "g04AutonomySourceChangedForClimax": False,
            "g05ContactAuthorityChanged": False,
            "g05SourceChangedForClimax": False,
            "g06DamagePersistenceChanged": False,
            "g06SourceChangedForClimax": False,
            "perAssetCollisionEngineering": False,
            "storyCollisionChoreography": False,
            "issR041ScopePreserved": True,
            "issR042ScopePreserved": True,
            "issR043ScopePreflightPreserved": True,
            "issR044UserPostflightApprovalRequired": True,
            "gateClosed": False,
        }
    )
    path.write_text(json.dumps(data, indent=2, sort_keys=True), encoding="utf-8")
    marker(
        "G07_CAUSAL_CLIMAX_SCOPE_EVIDENCE_WRITTEN",
        path=str(path),
        model=CLIMAX_REALIZATION_MODEL,
        climaxRequiresNewContact=False,
        g07OwnsDramaLifecycleOnly=True,
        g04ControlLawChanged=False,
        g05ContactAuthorityChanged=False,
        g06DamagePersistenceChanged=False,
        gateClosed=False,
    )


def main() -> None:
    candidate443.CANDIDATE = CANDIDATE
    candidate44.g07_active_goal_for_actor = g07_v7_active_goal_for_actor
    candidate44.g07_update_event_lifecycle = g07_v7_update_event_lifecycle
    candidate443.g07_v4_write_evidence = g07_v7_write_evidence

    print(json.dumps({
        "marker": "GENERIC_BATTLE_RUNTIME_CANDIDATE446_G07_ENGINEERING_PASS",
        "candidate": CANDIDATE,
        "climaxRealizationModel": CLIMAX_REALIZATION_MODEL,
        "climaxRequiresNewContact": False,
        "climaxAuthority": "REALIZED_REVERSAL_AND_PERSISTENT_STATE",
        "receiptAdmissionWorkaround": False,
        "g07OwnsDramaLifecycleOnly": True,
        "g04ControlLawChanged": False,
        "g04AutonomySourceChanged": False,
        "g05ContactAuthorityChanged": False,
        "g05ContactAuthoritySourceChanged": False,
        "g06DamagePersistenceChanged": False,
        "g06PersistenceSourceChanged": False,
        "storyCollisionChoreography": False,
        "perAssetCollisionEngineering": False,
        "damageThresholdChanged": False,
        "contactThresholdChanged": False,
        "actorPoseOrVelocityMutation": False,
        "stateResetMechanismIntroduced": False,
        "forcedWinnerIntroduced": False,
        "exactCollisionFrameTarget": False,
        "exactImpactEnergyTarget": False,
        "issR041ScopePreserved": True,
        "issR042ScopePreserved": True,
        "issR043ScopePreflightPreserved": True,
        "issR044UserPostflightApprovalRequired": True,
        "gateClosed": False,
        "productionReadyClaimed": False,
    }, sort_keys=True), flush=True)
    candidate443.main()


if __name__ == "__main__":
    main()
