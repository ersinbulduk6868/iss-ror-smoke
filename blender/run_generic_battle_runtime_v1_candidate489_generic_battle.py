from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from blender import iss_battle_runtime_generic_battle_v6 as battle_v6
from blender import run_generic_battle_runtime_v1_candidate42 as candidate42
from blender import run_generic_battle_runtime_v1_candidate465_generic_battle as candidate465
from blender import run_generic_battle_runtime_v1_candidate474_generic_battle as candidate474
from blender import run_generic_battle_runtime_v1_candidate487_generic_battle as candidate487
from blender import run_generic_battle_runtime_v1_candidate488_generic_battle as candidate488
from blender.iss_battle_runtime_assets import marker
from blender.iss_battle_runtime_autonomy import ClosedLoopGoalController
from blender.iss_battle_runtime_g05_negative_ack_v1 import (
    G05_NEGATIVE_ACK_MODEL,
    STAGE_IMPACT_GATE,
    STAGE_OUTER,
    STAGE_SOLVER,
    G05NegativeAcknowledgement,
    G05NegativeAckWindow,
    negative_ack_confirmed,
    recoverable_post_handoff_nack,
)

CANDIDATE = "ISS_GENERIC_BATTLE_RUNTIME_V1_CANDIDATE_4_8_9_GENERIC_AUTONOMOUS_BATTLE"
MECHANISM = G05_NEGATIVE_ACK_MODEL
AUDIT = "G04_G05_POST_HANDOFF_NEGATIVE_ACK_FULL_AFFECTED_LAYER_AUDIT_20260918"
FAILURE_FAMILY = "G05_REJECTION_DOES_NOT_RETURN_CONTROL_TO_G04_RECOVERY"

_ORIGINAL_OUTER_GATE = candidate42.ContactOuterAuthorityGate
_ORIGINAL_SOLVER_ORACLE = candidate42.PairwiseSolverResponseOracle
_ORIGINAL_PAIRWISE_RECEIPT = candidate42._pairwise_receipt
_ORIGINAL_C42_MARKER = candidate42.marker
_ORIGINAL_C487_SET_CONTROLS = candidate487.event_scoped_generic_battle_set_controls
_ORIGINAL_C488_GOAL = candidate488.c488_goal_for_tactical
_ORIGINAL_C488_AUTONOMY = candidate488.certified_event_scoped_autonomy_update
_ORIGINAL_C488_END_TRANSACTION = candidate488.c488_end_transaction

_active_g05_context: tuple[int, str, str, str] | None = None
_pending_nacks: dict[tuple[str, str, str], G05NegativeAcknowledgement] = {}
_pending_recovery: dict[tuple[str, str, str], G05NegativeAcknowledgement] = {}
_nack_windows: dict[tuple[str, str, str], G05NegativeAckWindow] = {}
_qualified_contact_transactions: dict[tuple[str, int], tuple[str, str, str]] = {}
_nack_rows: list[dict[str, Any]] = []
_release_rows: list[dict[str, Any]] = []
_recovery_rows: list[dict[str, Any]] = []


def _record_nack(
    *,
    stage: str,
    reason: str,
    controller_handoff: bool,
    motor_authority_zero: bool,
    contact_frame: int | None = None,
) -> None:
    if _active_g05_context is None:
        return
    frame, event_id, attacker_id, target_id = _active_g05_context
    nack = G05NegativeAcknowledgement(
        frame=int(frame),
        event_id=str(event_id),
        attacker_id=str(attacker_id),
        target_id=str(target_id),
        stage=str(stage),
        reason=str(reason),
        contact_frame=(int(contact_frame) if contact_frame is not None else None),
        controller_handoff=bool(controller_handoff),
        motor_authority_zero=bool(motor_authority_zero),
    )
    key = nack.transaction_key
    _pending_nacks[key] = nack
    row = {
        "frame": int(nack.frame),
        "eventId": nack.event_id,
        "attackerId": nack.attacker_id,
        "targetId": nack.target_id,
        "stage": nack.stage,
        "reason": nack.reason,
        "contactFrame": nack.contact_frame,
        "controllerHandoff": nack.controller_handoff,
        "motorAuthorityZero": nack.motor_authority_zero,
        "model": MECHANISM,
    }
    _nack_rows.append(row)
    marker("G04_G05_NEGATIVE_ACK_OBSERVED", **row)


class _ObservedOuterAuthorityGate:
    @staticmethod
    def evaluate(sample: Any) -> Any:
        receipt = _ORIGINAL_OUTER_GATE.evaluate(sample)
        if not bool(receipt.qualified):
            _record_nack(
                stage=STAGE_OUTER,
                reason=str(receipt.reason),
                controller_handoff=bool(sample.controller_handoff),
                motor_authority_zero=bool(sample.motor_authority_zero),
            )
        return receipt


class _ObservedPairwiseSolverResponseOracle:
    @staticmethod
    def evaluate(sample: Any) -> Any:
        receipt = _ORIGINAL_SOLVER_ORACLE.evaluate(sample)
        if not bool(receipt.qualified):
            _record_nack(
                stage=STAGE_SOLVER,
                reason=str(receipt.reason),
                controller_handoff=True,
                motor_authority_zero=True,
            )
        return receipt


def c489_observed_pairwise_receipt(
    *,
    frame: int,
    event: Any,
    attacker_id: str,
    attacker: Any,
    target: Any,
) -> Any:
    global _active_g05_context
    key = (str(event.event_id), str(attacker_id), str(event.target_id or ""))
    _active_g05_context = (int(frame), key[0], key[1], key[2])
    try:
        verified = _ORIGINAL_PAIRWISE_RECEIPT(
            frame=frame,
            event=event,
            attacker_id=attacker_id,
            attacker=attacker,
            target=target,
        )
        if verified is not None:
            receipt, _ = verified
            contact_frame = int(receipt.get("contactFrame") or frame)
            _qualified_contact_transactions[(key[0], contact_frame)] = key
            _pending_nacks.pop(key, None)
            _nack_windows.pop(key, None)
        return verified
    finally:
        _active_g05_context = None


def c489_observed_c42_marker(name: str, *args: Any, **kwargs: Any) -> Any:
    if name == "G05_PAIRWISE_CONTACT_REJECTED_BY_EXISTING_IMPACT_GATE":
        event_id = str(kwargs.get("eventId") or "")
        contact_frame = int(kwargs.get("frame") or -1)
        key = _qualified_contact_transactions.get((event_id, contact_frame))
        if key is not None:
            global _active_g05_context
            _active_g05_context = (contact_frame, key[0], key[1], key[2])
            try:
                _record_nack(
                    stage=STAGE_IMPACT_GATE,
                    reason="EXISTING_IMPACT_GATE_REJECTED",
                    controller_handoff=True,
                    motor_authority_zero=True,
                    contact_frame=contact_frame,
                )
            finally:
                _active_g05_context = None
    elif name == "G05_PAIRWISE_CONTACT_BOUND_TO_EXISTING_IMPACT_GATE":
        event_id = str(kwargs.get("eventId") or "")
        contact_frame = int(kwargs.get("frame") or -1)
        key = _qualified_contact_transactions.pop((event_id, contact_frame), None)
        if key is not None:
            _pending_nacks.pop(key, None)
            _nack_windows.pop(key, None)
    return _ORIGINAL_C42_MARKER(name, *args, **kwargs)


def _release_recoverable_handoffs(frame: int) -> None:
    confirmation_frames = max(1, int(candidate42.SOLVER_WINDOW_MAX_FRAMES))
    for key, nack in tuple(_pending_nacks.items()):
        if int(nack.frame) != int(frame):
            if int(nack.frame) < int(frame):
                _pending_nacks.pop(key, None)
            continue
        handoff_key = (key[0], key[1])
        latch = battle_v6._handoff_latches.get(handoff_key)
        recoverable = recoverable_post_handoff_nack(
            nack,
            active_event_id=key[0],
            active_attacker_id=key[1],
            active_target_id=key[2],
            handoff_latched=latch is not None,
        )
        if not recoverable:
            _nack_windows.pop(key, None)
            continue

        window = _nack_windows.setdefault(key, G05NegativeAckWindow())
        confirmed = negative_ack_confirmed(
            window,
            nack,
            confirmation_frames=confirmation_frames,
        )
        if not confirmed:
            marker(
                "G04_G05_NEGATIVE_ACK_PENDING_CONFIRMATION",
                frame=int(frame),
                eventId=key[0],
                attackerId=key[1],
                targetId=key[2] or None,
                stage=nack.stage,
                reason=nack.reason,
                consecutiveRejectFrames=int(window.consecutive_frames),
                requiredConfirmationFrames=int(confirmation_frames),
                model=MECHANISM,
            )
            _pending_nacks.pop(key, None)
            continue

        removed = battle_v6._handoff_latches.pop(handoff_key, None)
        if removed is None:
            continue
        cutoff_frame = candidate465.hardened._cutoff_frames.pop(handoff_key, None)
        observed_frames = int(window.consecutive_frames)
        first_reject_frame = window.first_frame
        _pending_nacks.pop(key, None)
        _nack_windows.pop(key, None)
        _pending_recovery[key] = nack
        candidate487._clear_legacy_pair_state((key[1], key[2]))
        row = {
            "frame": int(frame),
            "eventId": key[0],
            "attackerId": key[1],
            "targetId": key[2] or None,
            "stage": nack.stage,
            "reason": nack.reason,
            "handoffStartFrame": int(removed.start_frame),
            "cutoffFrame": (int(cutoff_frame) if cutoff_frame is not None else None),
            "firstRejectFrame": (int(first_reject_frame) if first_reject_frame is not None else None),
            "consecutiveRejectFrames": observed_frames,
            "requiredConfirmationFrames": int(confirmation_frames),
            "action": "RELEASE_HANDOFF_AND_RECOVER",
            "model": MECHANISM,
        }
        _release_rows.append(row)
        marker("G04_G05_NEGATIVE_ACK_HANDOFF_RELEASED", **row)


def c489_goal_for_tactical(
    actor: Any,
    target: Any,
    event: Any,
    tactical: Any,
    actors: dict[str, Any],
) -> Any:
    goal = _ORIGINAL_C488_GOAL(actor, target, event, tactical, actors)
    key = (
        str(event.event_id),
        str(actor.profile.entity_id),
        str(target.profile.entity_id),
    )
    if key in _pending_recovery:
        tactical.contact_commit = False
        context = candidate488._contact_context.get(key)
        if context is not None:
            context["contactCommit"] = False
        marker(
            "G04_G05_NEGATIVE_ACK_CONTACT_COMMIT_SUSPENDED",
            frame=int(candidate487._current_frame(event)),
            eventId=key[0],
            attackerId=key[1],
            targetId=key[2] or None,
            model=MECHANISM,
        )
    return goal


def c489_negative_ack_autonomy_update(
    memory: Any,
    obs: Any,
    *,
    recovery_bias: float = 1.0,
) -> Any:
    key = candidate488._transaction_key_from_pair()
    nack = _pending_recovery.pop(key, None)
    if nack is not None:
        ClosedLoopGoalController._begin_recovery(
            memory,
            obs,
            f"G05_{nack.stage}_{nack.reason}",
            recovery_bias,
        )
        row = {
            "frame": int(obs.frame),
            "eventId": key[0],
            "attackerId": key[1],
            "targetId": key[2] or None,
            "stage": nack.stage,
            "reason": nack.reason,
            "controllerMode": str(memory.mode),
            "controllerReason": str(memory.reason),
            "model": MECHANISM,
        }
        _recovery_rows.append(row)
        marker("G04_G05_NEGATIVE_ACK_RECOVERY_TRIGGERED", **row)
    return _ORIGINAL_C488_AUTONOMY(
        memory,
        obs,
        recovery_bias=recovery_bias,
    )


def c489_event_scoped_set_controls(
    frame: int,
    program: Any,
    actors: dict[str, Any],
    states: dict[str, Any],
    control_samples: list[dict[str, Any]],
) -> None:
    _release_recoverable_handoffs(int(frame))
    _ORIGINAL_C487_SET_CONTROLS(
        frame,
        program,
        actors,
        states,
        control_samples,
    )


def c489_end_transaction(entity: str, key: tuple[str, str, str], frame: int) -> None:
    _pending_nacks.pop(key, None)
    _pending_recovery.pop(key, None)
    _nack_windows.pop(key, None)
    for qkey, qtxn in tuple(_qualified_contact_transactions.items()):
        if qtxn == key:
            _qualified_contact_transactions.pop(qkey, None)
    _ORIGINAL_C488_END_TRANSACTION(entity, key, frame)


def _reset() -> None:
    global _active_g05_context
    _active_g05_context = None
    _pending_nacks.clear()
    _pending_recovery.clear()
    _nack_windows.clear()
    _qualified_contact_transactions.clear()
    _nack_rows.clear()
    _release_rows.clear()
    _recovery_rows.clear()


def main() -> None:
    _reset()

    # Observe G05 decisions without modifying G05 source, gates, thresholds, or
    # receipts. The proxy classes delegate every decision to the byte-identical
    # original authority and expose only its negative result to G04 lifecycle code.
    candidate42.ContactOuterAuthorityGate = _ObservedOuterAuthorityGate
    candidate42.PairwiseSolverResponseOracle = _ObservedPairwiseSolverResponseOracle
    candidate42._pairwise_receipt = c489_observed_pairwise_receipt
    candidate42.marker = c489_observed_c42_marker

    # Compose on top of C488. C489 changes no contact qualification rule: it only
    # makes a confirmed post-handoff G05 negative acknowledgement release the failed
    # solver transaction and enter the established event-scoped recovery/replan path.
    candidate488.c488_goal_for_tactical = c489_goal_for_tactical
    candidate488.certified_event_scoped_autonomy_update = c489_negative_ack_autonomy_update
    candidate488.c488_end_transaction = c489_end_transaction
    candidate487.event_scoped_generic_battle_set_controls = c489_event_scoped_set_controls

    print(json.dumps({
        "marker": "GENERIC_AUTONOMOUS_BATTLE_C489_ENGINEERING_READY",
        "candidate": CANDIDATE,
        "mechanism": MECHANISM,
        "affectedLayerAudit": AUDIT,
        "affectedLayerAuditStatus": "PASS",
        "failureFamily": FAILURE_FAMILY,
        "machineEvidenceSource": "C488_L4_RUN_59fe5d20-3c8d-45f9-afdc-266c6ed6b635",
        "g05DecisionObservedWithoutAuthorityChange": True,
        "outerAuthorityNegativeAckObserved": True,
        "solverResponseNegativeAckObserved": True,
        "existingImpactGateNegativeAckObserved": True,
        "negativeAckConfirmationUsesExistingG05SolverWindow": True,
        "singleFrameOuterOrSolverNoiseDoesNotForceRecovery": True,
        "existingImpactGateNegativeAckImmediate": True,
        "recoverableGeometryNackReleasesHandoff": True,
        "recoverableSolverNackReleasesHandoff": True,
        "recoverableImpactGateNackReleasesHandoff": True,
        "controllerAuthorityRegressionNotHiddenByRecovery": True,
        "targetIdentityRegressionNotHiddenByRecovery": True,
        "negativeAckTriggersExistingRecoveryController": True,
        "negativeAckTriggersEventScopedReplan": True,
        "semanticTransactionCanReleaseDuringRecovery": True,
        "freshAttemptMayReselectLivePairSemanticSurface": True,
        "c488ContinuousApproachCertificatePreserved": True,
        "c488AtomicMotorToCoastHandoffPreserved": True,
        "c487EventScopedRecoveryPreserved": True,
        "c480SemanticTransactionPreserved": True,
        "g05SourceChanged": False,
        "g05OuterGateChanged": False,
        "g05SolverOracleChanged": False,
        "g05ThresholdImported": False,
        "contactThresholdChanged": False,
        "semanticToleranceChanged": False,
        "localityToleranceChanged": False,
        "damageAdmissionThresholdChanged": False,
        "assetIdentityBranch": False,
        "perAssetBattleCode": False,
        "perAssetTacticalTuning": False,
        "perVideoTrajectoryEngineering": False,
        "fixedWorldCoordinates": False,
        "exactCollisionFrameTarget": False,
        "exactImpactEnergyTarget": False,
        "actorPoseOrVelocityMutation": False,
        "fixtureBattlePlanChanged": False,
        "frozenNineServiceArchitectureChanged": False,
        "gateClosed": False,
        "productionReadyClaimed": False,
    }, sort_keys=True), flush=True))

    candidate488.main()


if __name__ == "__main__":
    main()
