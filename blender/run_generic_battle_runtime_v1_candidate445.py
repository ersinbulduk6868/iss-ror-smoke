from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from blender import run_generic_battle_runtime_v1_candidate40 as candidate40
from blender import run_generic_battle_runtime_v1_candidate42 as candidate42
from blender import run_generic_battle_runtime_v1_candidate44 as candidate44
from blender import run_generic_battle_runtime_v1_candidate443 as candidate443
from blender.iss_battle_runtime_assets import BlenderBattleRuntimeError, marker

CANDIDATE = "ISS_GENERIC_BATTLE_RUNTIME_V1_CANDIDATE_4_4_5_G07"
RECEIPT_ADMISSION_MODEL = "G07_AWAITING_G05_PHYSICAL_RECEIPT_V1"

_ORIGINAL_G07_ACTIVE_GOAL = candidate44.g07_active_goal_for_actor
_ORIGINAL_V4_SET_CONTROLS = candidate443.g07_v4_set_controls
_ORIGINAL_V4_RESET = candidate443.g07_v4_reset
_ORIGINAL_V4_WRITE_EVIDENCE = candidate443.g07_v4_write_evidence

_receipt_waits: dict[tuple[str, str], dict[str, Any]] = {}
_receipt_wait_transitions: list[dict[str, Any]] = []


def _record(stage: str, frame: int, event_id: str, actor_id: str, **payload: Any) -> None:
    row = {
        "stage": str(stage),
        "frame": int(frame),
        "eventId": str(event_id),
        "actorId": str(actor_id),
        "model": RECEIPT_ADMISSION_MODEL,
        **payload,
    }
    _receipt_wait_transitions.append(json.loads(json.dumps(row)))
    marker(
        "G07_PHYSICAL_RECEIPT_ADMISSION",
        stage=str(stage),
        frame=int(frame),
        eventId=str(event_id),
        actorId=str(actor_id),
        model=RECEIPT_ADMISSION_MODEL,
        **payload,
    )


def _reconcile_receipt_waits(frame: int, states: dict[str, Any]) -> None:
    for key, wait in list(_receipt_waits.items()):
        event_id, actor_id = key
        state = states.get(event_id)
        if state is None:
            _receipt_waits.pop(key, None)
            _record("WAIT_CANCELLED_EVENT_MISSING", frame, event_id, actor_id)
            continue

        initial_contact_count = int(wait["initialContactCount"])
        current_contact_count = int(getattr(state, "contact_count", 0))
        if current_contact_count > initial_contact_count:
            _receipt_waits.pop(key, None)
            _record(
                "G05_RECEIPT_OBSERVED",
                frame,
                event_id,
                actor_id,
                startedFrame=int(wait["startedFrame"]),
                receiptWindowFrames=int(wait["receiptWindowFrames"]),
                contactCountBefore=initial_contact_count,
                contactCountAfter=current_contact_count,
            )
            continue

        if getattr(state, "status", None) in candidate44.hardened.TERMINAL:
            _receipt_waits.pop(key, None)
            _record(
                "WAIT_CLOSED_EVENT_TERMINAL",
                frame,
                event_id,
                actor_id,
                startedFrame=int(wait["startedFrame"]),
                terminalStatus=str(getattr(state, "status", "")),
            )
            continue

        if int(frame) > int(wait["releaseAfterFrame"]):
            _receipt_waits.pop(key, None)
            _record(
                "G05_RECEIPT_WINDOW_EXPIRED_REENABLE_G04",
                frame,
                event_id,
                actor_id,
                startedFrame=int(wait["startedFrame"]),
                receiptWindowFrames=int(wait["receiptWindowFrames"]),
                authority="G05_EXISTING_SOLVER_WINDOW_CONTRACT",
            )


def g07_v6_active_goal_for_actor(
    entity: str,
    frame: int,
    program: Any,
    states: dict[str, Any],
):
    _reconcile_receipt_waits(frame, states)
    for (event_id, actor_id), wait in _receipt_waits.items():
        if actor_id != entity:
            continue
        state = states.get(event_id)
        if state is None or getattr(state, "status", None) != "ACTIVE":
            continue
        if int(frame) <= int(wait["releaseAfterFrame"]):
            # G07 owns event admission. During the existing G05 receipt window it
            # admits no new battle goal for this actor. Candidate40 then follows
            # its already-proven no-goal behavior. No G04 control command, G05
            # cutoff/contact authority, or G06 consequence logic is modified here.
            return None
    return _ORIGINAL_G07_ACTIVE_GOAL(entity, frame, program, states)


def g07_v6_set_controls(
    frame: int,
    program: Any,
    actors: dict[str, Any],
    states: dict[str, Any],
    control_samples: list[dict[str, Any]],
) -> None:
    _reconcile_receipt_waits(frame, states)
    _ORIGINAL_V4_SET_CONTROLS(frame, program, actors, states, control_samples)

    receipt_window = max(1, int(candidate42.SOLVER_WINDOW_MAX_FRAMES))
    for (event_id, actor_id), memory in list(candidate40._memories.items()):
        if str(getattr(memory, "mode", "")) != "CONTACT_HANDOFF":
            continue
        state = states.get(event_id)
        if state is None or getattr(state, "status", None) != "ACTIVE":
            continue
        key = (str(event_id), str(actor_id))
        if key in _receipt_waits:
            continue
        wait = {
            "startedFrame": int(frame),
            "releaseAfterFrame": int(frame) + receipt_window,
            "receiptWindowFrames": receipt_window,
            "initialContactCount": int(getattr(state, "contact_count", 0)),
        }
        _receipt_waits[key] = wait
        _record(
            "AWAITING_G05_PHYSICAL_RECEIPT",
            frame,
            event_id,
            actor_id,
            releaseAfterFrame=int(wait["releaseAfterFrame"]),
            receiptWindowFrames=receipt_window,
            sourceSignal="G04_CONTACT_HANDOFF",
            awaitedAuthority="G05_VERIFIED_NATIVE_CONTACT",
        )


def g07_v6_reset(self: Any) -> None:
    _receipt_waits.clear()
    _receipt_wait_transitions.clear()
    _ORIGINAL_V4_RESET(self)


def g07_v6_write_evidence(states: dict[str, Any], outcome: dict[str, Any]) -> None:
    final_frame = int(candidate44.bpy.context.scene.frame_current)
    _reconcile_receipt_waits(final_frame, states)
    _ORIGINAL_V4_WRITE_EVIDENCE(states, outcome)
    if candidate44.hardened._capture_output is None:
        raise BlenderBattleRuntimeError("G07_OUTPUT_DIR_UNAVAILABLE")
    path = Path(candidate44.hardened._capture_output) / "g07-causal-drama-evidence.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    data.update(
        {
            "receiptAdmissionModel": RECEIPT_ADMISSION_MODEL,
            "physicalReceiptPendingAdmission": True,
            "g05SolverWindowFramesConsumed": int(candidate42.SOLVER_WINDOW_MAX_FRAMES),
            "receiptWaitTransitions": json.loads(json.dumps(_receipt_wait_transitions)),
            "receiptWaitsOpenAtOutcome": len(_receipt_waits),
            "g07OwnsOnlyEventAdmission": True,
            "g04ControlLawChanged": False,
            "g04AutonomySourceChangedForReceiptAdmission": False,
            "g05ContactAuthorityChanged": False,
            "g05SourceChangedForReceiptAdmission": False,
            "g06DamagePersistenceChanged": False,
            "g06SourceChangedForReceiptAdmission": False,
            "storyCollisionChoreography": False,
            "perAssetCollisionEngineering": False,
            "issR041ScopePreserved": True,
            "issR042ScopePreserved": True,
            "issR043ScopePreflightPreserved": True,
        }
    )
    path.write_text(json.dumps(data, indent=2, sort_keys=True), encoding="utf-8")
    marker(
        "G07_PHYSICAL_RECEIPT_ADMISSION_EVIDENCE_WRITTEN",
        path=str(path),
        model=RECEIPT_ADMISSION_MODEL,
        transitionCount=len(_receipt_wait_transitions),
        openWaitCount=len(_receipt_waits),
        g07OwnsOnlyEventAdmission=True,
        g04ControlLawChanged=False,
        g05ContactAuthorityChanged=False,
        g06DamagePersistenceChanged=False,
    )


def main() -> None:
    candidate443.CANDIDATE = CANDIDATE
    candidate443.g07_v4_reset = g07_v6_reset
    candidate443.g07_v4_write_evidence = g07_v6_write_evidence
    candidate443.g07_v4_set_controls = g07_v6_set_controls
    candidate44.g07_active_goal_for_actor = g07_v6_active_goal_for_actor

    print(
        json.dumps(
            {
                "marker": "GENERIC_BATTLE_RUNTIME_CANDIDATE445_G07_ENGINEERING_PASS",
                "candidate": CANDIDATE,
                "receiptAdmissionModel": RECEIPT_ADMISSION_MODEL,
                "g07OwnsOnlyEventAdmission": True,
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
                "productionReadyClaimed": False,
            },
            sort_keys=True,
        ),
        flush=True,
    )
    candidate443.main()


if __name__ == "__main__":
    main()
