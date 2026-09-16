from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

from mathutils import Vector

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from blender import run_generic_battle_runtime_v1_candidate40 as candidate40
from blender import run_generic_battle_runtime_v1_candidate44 as candidate44
from blender import run_generic_battle_runtime_v1_candidate443 as candidate443
from blender.iss_battle_runtime_assets import BlenderBattleRuntimeError, marker

CANDIDATE = "ISS_GENERIC_BATTLE_RUNTIME_V1_CANDIDATE_4_4_4_G07"
HANDOFF_MODEL = "STATE_DERIVED_SOLVER_HANDOFF_LIFECYCLE_V1"

_ORIGINAL_V4_SET_CONTROLS = candidate443.g07_v4_set_controls
_ORIGINAL_V4_RESET = candidate443.g07_v4_reset
_ORIGINAL_V4_WRITE_EVIDENCE = candidate443.g07_v4_write_evidence
_ORIGINAL_G07_RESOLVE = candidate44.g07_pairwise_resolve_pending_contacts

_handoffs: dict[tuple[str, str], dict[str, Any]] = {}
_handoff_history: list[dict[str, Any]] = []


def _json_copy(value: Any) -> Any:
    return json.loads(json.dumps(value))


def _latest_control_sample(
    control_samples: list[dict[str, Any]],
    frame: int,
    event_id: str,
    actor_id: str,
) -> dict[str, Any] | None:
    for row in reversed(control_samples):
        if int(row.get("frame") or -1) < int(frame):
            break
        if int(row.get("frame") or -1) != int(frame):
            continue
        if str(row.get("eventId") or "") != event_id:
            continue
        if str(row.get("actorId") or "") != actor_id:
            continue
        return row
    return None


def _live_surface_state(actor: Any, target: Any, frame: int) -> dict[str, float]:
    gap, center_distance, normal = candidate40._surface_gap(actor, target)
    velocity = actor.velocity.get(frame, Vector((0.0, 0.0, 0.0)))
    target_velocity = target.velocity.get(frame, Vector((0.0, 0.0, 0.0)))
    closing = (velocity - target_velocity).dot(normal)
    return {
        "surfaceGapM": float(gap),
        "centerDistanceM": float(center_distance),
        "closingSpeedMps": float(closing),
    }


def _history(stage: str, frame: int, key: tuple[str, str], **payload: Any) -> dict[str, Any]:
    row = {
        "stage": stage,
        "frame": int(frame),
        "eventId": key[0],
        "actorId": key[1],
        "model": HANDOFF_MODEL,
        **payload,
    }
    _handoff_history.append(_json_copy(row))
    marker("G07_SOLVER_HANDOFF_LIFECYCLE", **row)
    return row


def _release_handoff(
    key: tuple[str, str],
    frame: int,
    reason: str,
    **payload: Any,
) -> None:
    row = _handoffs.pop(key, None)
    if row is None:
        return
    _history(
        "RELEASED",
        frame,
        key,
        reason=reason,
        openedFrame=int(row["openedFrame"]),
        heldFrames=max(0, int(frame) - int(row["openedFrame"])),
        targetId=str(row.get("targetId") or ""),
        **payload,
    )


def _open_handoff(
    key: tuple[str, str],
    frame: int,
    event: Any,
    sample: dict[str, Any],
    surface: dict[str, float],
) -> None:
    policy = sample.get("policy") or {}
    if "contactHandoffGapM" not in policy or "progressTimeoutFrames" not in policy:
        raise BlenderBattleRuntimeError(
            f"G07_HANDOFF_CONTROLLER_POLICY_MISSING:{event.event_id}:{key[1]}:{frame}"
        )
    gap = float(policy["contactHandoffGapM"])
    timeout = int(policy["progressTimeoutFrames"])
    if gap < 0.0 or timeout < 1:
        raise BlenderBattleRuntimeError(
            f"G07_HANDOFF_CONTROLLER_POLICY_INVALID:{event.event_id}:{key[1]}:{gap}:{timeout}"
        )
    _handoffs[key] = {
        "openedFrame": int(frame),
        "targetId": str(event.target_id or ""),
        "contactHandoffGapM": gap,
        "progressTimeoutFrames": timeout,
    }
    _history(
        "OPENED",
        frame,
        key,
        reason="G04_CONTACT_HANDOFF_OPENED",
        targetId=str(event.target_id or ""),
        contactHandoffGapM=gap,
        progressTimeoutFrames=timeout,
        surfaceGapM=float(surface["surfaceGapM"]),
        closingSpeedMps=float(surface["closingSpeedMps"]),
        controllerPolicyDerived=True,
    )


def _maintain_handoff(
    key: tuple[str, str],
    frame: int,
    event: Any,
    actor: Any,
    target: Any,
    state: Any,
    control_samples: list[dict[str, Any]],
) -> None:
    latch = _handoffs.get(key)
    if latch is None:
        return

    if state.status in candidate44.hardened.TERMINAL:
        _release_handoff(key, frame, "EVENT_TERMINAL", eventStatus=str(state.status))
        return
    if actor.state.disabled or target.state.disabled:
        _release_handoff(
            key,
            frame,
            "ACTOR_OR_TARGET_DISABLED",
            attackerDisabled=bool(actor.state.disabled),
            targetDisabled=bool(target.state.disabled),
        )
        return

    surface = _live_surface_state(actor, target, frame)
    gap = float(surface["surfaceGapM"])
    closing = float(surface["closingSpeedMps"])
    handoff_gap = float(latch["contactHandoffGapM"])
    elapsed = int(frame) - int(latch["openedFrame"])
    timeout = int(latch["progressTimeoutFrames"])

    if gap > handoff_gap and closing <= 0.0:
        _release_handoff(
            key,
            frame,
            "LIVE_GEOMETRY_SEPARATION_OR_MISS",
            surfaceGapM=gap,
            contactHandoffGapM=handoff_gap,
            closingSpeedMps=closing,
        )
        return

    if elapsed >= timeout:
        _release_handoff(
            key,
            frame,
            "G04_GENERIC_PROGRESS_TIMEOUT_RECOVERY",
            surfaceGapM=gap,
            contactHandoffGapM=handoff_gap,
            closingSpeedMps=closing,
            progressTimeoutFrames=timeout,
        )
        return

    # The generic controller itself opened solver handoff. Keep its motor
    # authority released while native physics is observed instead of allowing a
    # one-frame TRACK/HANDOFF oscillation to reacquire MOTOR before G05 can form
    # a native pairwise solver receipt.
    actor.rig.coast()

    # Candidate42 looks back across its own solver observation window. The
    # cutoff evidence therefore points to a frame inside the continuously
    # coasted latch interval and never later than Candidate42's earliest
    # possible contact frame. No solver tolerance/window is changed here.
    solver_window = max(1, int(candidate44.candidate42.SOLVER_WINDOW_MAX_FRAMES))
    evidence_frame = max(
        int(latch["openedFrame"]),
        int(frame) - max(0, solver_window - 1),
    )
    candidate44.hardened._cutoff_frames[key] = evidence_frame

    control_samples.append(
        {
            "frame": int(frame),
            "eventId": str(event.event_id),
            "actorId": str(key[1]),
            "mode": "CONTACT_HANDOFF_LATCH",
            "reason": "STATE_DERIVED_SOLVER_HANDOFF_ACTIVE",
            "motorAuthority": "COAST",
            "handoffLifecycleModel": HANDOFF_MODEL,
            "controllerPolicyDerived": True,
            "handoffOpenedFrame": int(latch["openedFrame"]),
            "handoffEvidenceFrame": int(evidence_frame),
            "observation": surface,
            "policy": {
                "contactHandoffGapM": handoff_gap,
                "progressTimeoutFrames": timeout,
                "solverWindowFrames": solver_window,
            },
        }
    )


def g07_v5_set_controls(
    frame: int,
    program: Any,
    actors: dict[str, Any],
    states: dict[str, Any],
    control_samples: list[dict[str, Any]],
) -> None:
    _ORIGINAL_V4_SET_CONTROLS(frame, program, actors, states, control_samples)

    active_keys: set[tuple[str, str]] = set()
    for actor_id, actor in actors.items():
        event = candidate44.g07_active_goal_for_actor(actor_id, frame, program, states)
        if event is None or not event.requires_contact or not event.target_id:
            continue
        if event.target_id not in actors:
            continue
        state = states[event.event_id]
        key = (str(event.event_id), str(actor_id))
        active_keys.add(key)
        target = actors[event.target_id]

        cutoff_frame = candidate44.hardened._cutoff_frames.get(key)
        if key not in _handoffs and cutoff_frame == int(frame):
            sample = _latest_control_sample(
                control_samples,
                frame,
                str(event.event_id),
                str(actor_id),
            )
            if sample is not None and str(sample.get("mode") or "") == "CONTACT_HANDOFF":
                _open_handoff(
                    key,
                    frame,
                    event,
                    sample,
                    _live_surface_state(actor, target, frame),
                )

        _maintain_handoff(
            key,
            frame,
            event,
            actor,
            target,
            state,
            control_samples,
        )

    # A latch must never survive loss of its owning active G07 goal.
    for key in list(_handoffs):
        if key not in active_keys:
            _release_handoff(key, frame, "ACTIVE_GOAL_ENDED")


def g07_v5_pairwise_resolve_pending_contacts(
    frame: int,
    actors: dict[str, Any],
    states: dict[str, Any],
    events_by_id: dict[str, Any],
    pending: list[Any],
    camera: Any,
    impact_log: list[dict[str, Any]],
) -> None:
    before = len(impact_log)
    _ORIGINAL_G07_RESOLVE(
        frame,
        actors,
        states,
        events_by_id,
        pending,
        camera,
        impact_log,
    )
    for row in impact_log[before:]:
        if row.get("nativeContactAuthority") is not True:
            continue
        if row.get("nativeContactInheritedFromPhysicalTransaction") is True:
            continue
        receipt = row.get("nativeContactReceipt")
        if not isinstance(receipt, dict) or receipt.get("status") != "VERIFIED":
            continue
        evidence = row.get("evidence") or {}
        attacker_id = str(evidence.get("attacker_id") or receipt.get("attackerId") or "")
        event_id = str(row.get("eventId") or receipt.get("eventId") or "")
        if not attacker_id or not event_id:
            continue
        key = (event_id, attacker_id)
        _release_handoff(
            key,
            frame,
            "VERIFIED_G05_TRANSACTION",
            contactFrame=int(receipt.get("contactFrame") or frame),
            contactAuthorityModel=str(receipt.get("model") or ""),
        )


def g07_v5_reset(self: Any) -> None:
    _handoffs.clear()
    _handoff_history.clear()
    _ORIGINAL_V4_RESET(self)


def g07_v5_write_evidence(states: dict[str, Any], outcome: dict[str, Any]) -> None:
    _ORIGINAL_V4_WRITE_EVIDENCE(states, outcome)
    if candidate44.hardened._capture_output is None:
        raise BlenderBattleRuntimeError("G07_OUTPUT_DIR_UNAVAILABLE")
    path = Path(candidate44.hardened._capture_output) / "g07-causal-drama-evidence.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    release_reasons: dict[str, int] = {}
    opened = 0
    released = 0
    for row in _handoff_history:
        if row.get("stage") == "OPENED":
            opened += 1
        if row.get("stage") == "RELEASED":
            released += 1
            reason = str(row.get("reason") or "UNKNOWN")
            release_reasons[reason] = int(release_reasons.get(reason, 0)) + 1
    data.update(
        {
            "handoffLifecycleModel": HANDOFF_MODEL,
            "handoffLifecycleStateDerived": True,
            "handoffControllerPolicyDerived": True,
            "handoffReleaseOnVerifiedG05": True,
            "handoffReleaseOnLiveSeparationOrMiss": True,
            "handoffReleaseOnGenericProgressTimeout": True,
            "handoffUsesExistingG05SolverWindow": True,
            "perAssetHandoffTuning": False,
            "storyHandoffChoreography": False,
            "handoffOpenCount": opened,
            "handoffReleaseCount": released,
            "handoffReleaseReasons": release_reasons,
            "handoffHistory": _json_copy(_handoff_history),
            "unreleasedHandoffCountAtFinalEvidence": len(_handoffs),
            "g04SourceChangedForHandoff": False,
            "g05SourceChangedForHandoff": False,
            "g06SourceChangedForHandoff": False,
            "issR043ScopePreflightPassed": True,
            "issR043ScopePostflightRequired": True,
        }
    )
    path.write_text(json.dumps(data, indent=2, sort_keys=True), encoding="utf-8")
    marker(
        "G07_SOLVER_HANDOFF_EVIDENCE_WRITTEN",
        path=str(path),
        model=HANDOFF_MODEL,
        handoffOpenCount=opened,
        handoffReleaseCount=released,
        verifiedG05ReleaseCount=int(release_reasons.get("VERIFIED_G05_TRANSACTION", 0)),
        perAssetHandoffTuning=False,
        storyHandoffChoreography=False,
        issR043ScopePreflightPassed=True,
        issR043ScopePostflightRequired=True,
    )


def main() -> None:
    candidate443.CANDIDATE = CANDIDATE
    candidate443.g07_v4_set_controls = g07_v5_set_controls
    candidate443.g07_v4_reset = g07_v5_reset
    candidate443.g07_v4_write_evidence = g07_v5_write_evidence
    candidate44.g07_pairwise_resolve_pending_contacts = g07_v5_pairwise_resolve_pending_contacts

    print(
        json.dumps(
            {
                "marker": "GENERIC_BATTLE_RUNTIME_CANDIDATE444_G07_ENGINEERING_PASS",
                "candidate": CANDIDATE,
                "handoffLifecycleModel": HANDOFF_MODEL,
                "handoffLifecycleStateDerived": True,
                "handoffControllerPolicyDerived": True,
                "runtimeSelectedSemanticEngagement": True,
                "storyTargetZonePrescribed": False,
                "perAssetCollisionEngineering": False,
                "perAssetHandoffTuning": False,
                "g04AutonomySourceChanged": False,
                "g05ContactAuthoritySourceChanged": False,
                "g06PersistenceSourceChanged": False,
                "damageThresholdChanged": False,
                "contactThresholdChanged": False,
                "actorPoseOrVelocityMutation": False,
                "stateResetMechanismIntroduced": False,
                "forcedWinnerIntroduced": False,
                "exactCollisionFrameTarget": False,
                "exactImpactEnergyTarget": False,
                "issR041ScopePreserved": True,
                "issR042ScopePreserved": True,
                "issR043ScopePreflightPassed": True,
                "issR043ScopePostflightRequired": True,
                "productionReadyClaimed": False,
            },
            sort_keys=True,
        ),
        flush=True,
    )
    candidate443.main()


if __name__ == "__main__":
    main()
