from __future__ import annotations

import json
from pathlib import Path
import sys
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from blender import iss_blender_battle_runtime_v1_hardened as hardened
from blender import run_generic_battle_runtime_v1_candidate42 as candidate42
from blender import run_generic_battle_runtime_v1_candidate470_generic_battle as candidate470
from blender.iss_battle_runtime_assets import marker
from blender.iss_battle_runtime_contact_transaction_v1 import (
    TRANSACTION_LOCALITY_MODEL,
    transaction_candidate_frames,
)

CANDIDATE = "ISS_GENERIC_BATTLE_RUNTIME_V1_CANDIDATE_4_7_1_GENERIC_AUTONOMOUS_BATTLE"
MECHANISM = TRANSACTION_LOCALITY_MODEL
AUDIT = "G05_HANDOFF_TRANSACTION_SAMPLE_FULL_AFFECTED_LAYER_AUDIT_20260918"
FAILURE_FAMILY = "DETECTOR_HISTORY_SAMPLE_PRECEDES_FRESH_HANDOFF_CUTOFF"

_ORIGINAL_BEST_RECENT_LOCALITY = candidate42._best_recent_locality
_ORIGINAL_PAIRWISE_RECEIPT = candidate42._pairwise_receipt
_ORIGINAL_SOLVER_EVALUATE = candidate42.PairwiseSolverResponseOracle.evaluate

_receipt_context: dict[str, Any] | None = None
_locality_context: dict[str, Any] | None = None
_transaction_exclusion_rows: list[dict[str, Any]] = []
_solver_rejection_rows: list[dict[str, Any]] = []


def transaction_aware_best_recent_locality(
    attacker: Any,
    target: Any,
    frame: int,
) -> dict[str, Any] | None:
    global _locality_context

    context = _receipt_context or {}
    event_id = str(context.get("eventId") or "")
    attacker_id = str(context.get("attackerId") or "")
    cutoff_frame = hardened._cutoff_frames.get((event_id, attacker_id)) if event_id and attacker_id else None

    frames = transaction_candidate_frames(
        int(frame),
        int(cutoff_frame) if cutoff_frame is not None else None,
        candidate42.SOLVER_WINDOW_MAX_FRAMES,
    )
    rows = [
        row
        for sample_frame in frames
        if (row := candidate42._pair_geometry_at(attacker, target, int(sample_frame))) is not None
    ]
    if not rows:
        _locality_context = None
        marker(
            "G05_TRANSACTION_LOCALITY_WINDOW_EMPTY",
            frame=int(frame),
            eventId=event_id or None,
            attackerId=attacker_id or None,
            cutoffFrame=int(cutoff_frame) if cutoff_frame is not None else None,
            candidateFrames=list(frames),
            model=TRANSACTION_LOCALITY_MODEL,
        )
        return None

    selected = min(rows, key=lambda row: (float(row["gapM"]), int(row["frame"])))
    _locality_context = {
        "contactFrame": int(selected["frame"]),
        "gapM": float(selected["gapM"]),
        "cutoffFrame": int(cutoff_frame) if cutoff_frame is not None else None,
        "candidateFrames": list(frames),
    }

    legacy = _ORIGINAL_BEST_RECENT_LOCALITY(attacker, target, int(frame))
    if (
        cutoff_frame is not None
        and legacy is not None
        and int(legacy["frame"]) < int(cutoff_frame)
    ):
        row = {
            "frame": int(frame),
            "eventId": event_id,
            "attackerId": attacker_id,
            "cutoffFrame": int(cutoff_frame),
            "legacyContactFrame": int(legacy["frame"]),
            "selectedContactFrame": int(selected["frame"]),
            "legacyGapM": float(legacy["gapM"]),
            "selectedGapM": float(selected["gapM"]),
            "model": TRANSACTION_LOCALITY_MODEL,
        }
        _transaction_exclusion_rows.append(row)
        marker("G05_PRE_CUTOFF_LOCALITY_SAMPLE_EXCLUDED", **row)

    return selected


def audited_solver_evaluate(sample: Any) -> Any:
    receipt = _ORIGINAL_SOLVER_EVALUATE(sample)
    if not bool(receipt.qualified):
        context = _receipt_context or {}
        locality = _locality_context or {}
        row = {
            "frame": int(context.get("frame") or -1),
            "eventId": context.get("eventId"),
            "attackerId": context.get("attackerId"),
            "targetId": context.get("targetId"),
            "contactFrame": locality.get("contactFrame"),
            "cutoffFrame": locality.get("cutoffFrame"),
            "reason": str(receipt.reason),
            "normalClosingSpeedMps": float(receipt.normal_closing_speed_mps),
            "postNormalClosingSpeedMps": float(receipt.post_normal_closing_speed_mps),
            "closingSpeedDropMps": float(receipt.closing_speed_drop_mps),
            "responseAttackerMps": float(receipt.response_attacker_mps),
            "responseTargetMps": float(receipt.response_target_mps),
            "responseFloorMps": float(receipt.response_floor_mps),
            "impulseBalanceRatio": float(receipt.impulse_balance_ratio),
            "impulseOppositionCosine": float(receipt.impulse_opposition_cosine),
            "attackerNormalAlignment": float(receipt.attacker_normal_alignment),
            "targetNormalAlignment": float(receipt.target_normal_alignment),
            "model": candidate42.CONTACT_AUTHORITY,
        }
        _solver_rejection_rows.append(row)
        marker("G05_PAIRWISE_SOLVER_RESPONSE_REJECTED", **row)
    return receipt


def transaction_aware_pairwise_receipt(
    *,
    frame: int,
    event: Any,
    attacker_id: str,
    attacker: Any,
    target: Any,
) -> tuple[dict[str, Any], dict[str, Any]] | None:
    global _receipt_context, _locality_context
    previous_context = _receipt_context
    previous_locality = _locality_context
    _receipt_context = {
        "frame": int(frame),
        "eventId": str(event.event_id),
        "attackerId": str(attacker_id),
        "targetId": str(event.target_id or ""),
    }
    _locality_context = None
    try:
        return _ORIGINAL_PAIRWISE_RECEIPT(
            frame=frame,
            event=event,
            attacker_id=attacker_id,
            attacker=attacker,
            target=target,
        )
    finally:
        _receipt_context = previous_context
        _locality_context = previous_locality


def main() -> None:
    global _receipt_context, _locality_context
    _receipt_context = None
    _locality_context = None
    _transaction_exclusion_rows.clear()
    _solver_rejection_rows.clear()

    # Preserve the C470 semantic-surface transaction and every existing G05
    # threshold/oracle. Only prevent a fresh transaction from consuming locality
    # evidence that predates its immutable cutoff. Solver rejects are observed,
    # never reclassified or weakened.
    candidate42._best_recent_locality = transaction_aware_best_recent_locality
    candidate42._pairwise_receipt = transaction_aware_pairwise_receipt
    candidate42.PairwiseSolverResponseOracle.evaluate = staticmethod(audited_solver_evaluate)

    candidate470.CANDIDATE = CANDIDATE
    candidate470.MECHANISM = MECHANISM
    candidate470.AUDIT = AUDIT

    print(json.dumps({
        "marker": "GENERIC_AUTONOMOUS_BATTLE_C471_ENGINEERING_READY",
        "candidate": CANDIDATE,
        "mechanism": MECHANISM,
        "affectedLayerAudit": AUDIT,
        "failureFamily": FAILURE_FAMILY,
        "rootCause": "BEST_RECENT_LOCALITY_CAN_SELECT_PRE_TRANSACTION_FRAME",
        "transactionCutoffBoundsHistoricalLocalityWindow": True,
        "solverRejectEvidenceAdded": True,
        "existingG05OuterAuthorityGatePreserved": True,
        "existingPairwiseSolverOraclePreserved": True,
        "c470LivePairSurfaceSemanticSelectionPreserved": True,
        "c469CutoffCleanupPreserved": True,
        "c468RecencyBudgetPreserved": True,
        "solverWindowFramesChanged": False,
        "semanticToleranceChanged": False,
        "localityToleranceChanged": False,
        "contactThresholdChanged": False,
        "damageAdmissionThresholdChanged": False,
        "fixtureMutationForAcceptance": False,
        "perAssetBattleCode": False,
        "perVideoTrajectoryEngineering": False,
        "fixedWorldCoordinates": False,
        "exactCollisionFrameTarget": False,
        "exactImpactEnergyTarget": False,
        "actorPoseOrVelocityMutation": False,
        "forcedWinner": False,
        "stateResetMechanism": False,
        "g01ToG03Changed": False,
        "frozenNineServiceArchitectureChanged": False,
        "gateClosed": False,
        "productionReadyClaimed": False,
    }, sort_keys=True), flush=True)

    candidate470.main()


if __name__ == "__main__":
    main()
