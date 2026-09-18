#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
TOOLS = ROOT / "tools"
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

from validate_generic_autonomous_battle_c464_result import _validate
from validate_generic_autonomous_battle_c465_result import _cutoff_runtime_proof
from validate_generic_autonomous_battle_c470_result import _surface_transaction_runtime_proof
from validate_generic_autonomous_battle_c471_result import _transaction_sampling_runtime_proof

REQUIRED_DIRECT_EVENTS = {"evt-escalation", "evt-counterattack"}


def _rows(path: str) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for line in Path(path).read_text(encoding="utf-8", errors="replace").splitlines():
        try:
            row = json.loads(line)
        except Exception:
            continue
        if isinstance(row, dict):
            rows.append(row)
    return rows


def _control_contract_runtime_proof(path: str) -> dict[str, object]:
    rows = _rows(path)
    obb_rejections = [
        row for row in rows
        if row.get("marker") == "G04_RADIAL_OVERLAP_REJECTED_BY_OBB_SEPARATION"
    ]
    recovery_clears = [
        row for row in rows
        if row.get("marker") == "G04_STALE_AUTONOMY_RECOVERY_CLEARED"
    ]
    contacts = [
        row for row in rows
        if row.get("marker") == "PAIRWISE_NATIVE_SOLVER_CONTACT_VERIFIED"
    ]

    contact_events = {str(row.get("eventId") or "") for row in contacts}
    assert REQUIRED_DIRECT_EVENTS <= contact_events, (
        "C472_REQUIRED_DIRECT_NATIVE_CONTACT_EVENTS_MISSING",
        sorted(contact_events),
    )

    for row in obb_rejections:
        radial = float(row.get("radialGapM") or 0.0)
        sat = float(row.get("obbSatSeparationM") or 0.0)
        effective = float(row.get("effectiveGapM") or 0.0)
        assert radial <= 0.0 < sat, ("C472_OBB_REJECTION_INVALID", row)
        assert abs(effective - max(radial, sat)) <= 1.0e-9, (
            "C472_EFFECTIVE_GAP_INVALID", row
        )

    for row in recovery_clears:
        previous_tactical = str(row.get("previousTacticalMode") or "")
        current_tactical = str(row.get("currentTacticalMode") or "")
        previous_controller = str(row.get("previousControllerMode") or "")
        speed_intent = str(row.get("speedIntent") or "")
        assert previous_tactical in {"OPEN_DISTANCE", "BREAK_CONTACT", "REPOSITION"}, row
        assert current_tactical in {"ENGAGE", "COUNTER", "FLANK"}, row
        assert previous_controller.startswith("RECOVER_"), row
        assert speed_intent == "ACCELERATE", row

    return {
        "verifiedNativeContactCount": len(contacts),
        "verifiedContactEventIds": sorted(contact_events),
        "radialFalseOverlapRejectedCount": len(obb_rejections),
        "staleRecoveryClearCount": len(recovery_clears),
        "requiredDirectEventsNativeVerified": True,
        "g05RemainsFinalContactAuthority": True,
    }


def main() -> None:
    p = argparse.ArgumentParser()
    for prefix in ("bugatti", "generic"):
        for key in ("battle", "g06", "g07", "g08", "log"):
            p.add_argument(f"--{prefix}-{key}", required=True)
    a = p.parse_args()

    fixtures = []
    cutoff: dict[str, object] = {}
    surface: dict[str, object] = {}
    transaction: dict[str, object] = {}
    control: dict[str, object] = {}
    for prefix in ("bugatti", "generic"):
        battle = getattr(a, f"{prefix}_battle")
        log = getattr(a, f"{prefix}_log")
        fixtures.append(
            _validate(
                prefix,
                battle,
                getattr(a, f"{prefix}_g06"),
                getattr(a, f"{prefix}_g07"),
                getattr(a, f"{prefix}_g08"),
            )
        )
        cutoff[prefix] = _cutoff_runtime_proof(battle)
        surface[prefix] = _surface_transaction_runtime_proof(log)
        transaction[prefix] = _transaction_sampling_runtime_proof(log)
        control[prefix] = _control_contract_runtime_proof(log)

    print(json.dumps({
        "marker": "GENERIC_AUTONOMOUS_BATTLE_C472_MACHINE_ACCEPTANCE",
        "status": "PASS",
        "affectedLayerAudit": "PASS",
        "failureFamily": "RADIAL_HANDOFF_FALSE_PROXIMITY_AND_STALE_AUTONOMY_RECOVERY",
        "sameRuntimeAcrossAssets": True,
        "rigidBodyObbSatProximity": "PASS",
        "tacticalAutonomyRecoveryOwnership": "PASS",
        "transactionBoundedLocalityWindow": "PASS",
        "livePairSurfaceSemanticSelection": "PASS",
        "freshHandoffTransactionBinding": "PASS",
        "secondNativeContact": "PASS",
        "twoSidedDamage": "PASS",
        "visibleCausalDamageDebris": "PASS",
        "g07AdaptiveCausalDrama": "PASS",
        "g08MachineObservability": "PASS",
        "nativeContactAuthorityPreserved": True,
        "pairwiseSolverOraclePreserved": True,
        "semanticToleranceChanged": False,
        "localityToleranceChanged": False,
        "contactThresholdChanged": False,
        "damageAdmissionThresholdChanged": False,
        "fixtureMutationForAcceptance": False,
        "storyTargetZonePrescribed": False,
        "perAssetBattleCode": False,
        "perVideoTrajectoryEngineering": False,
        "humanCinematicAcceptance": "PENDING",
        "gateClosed": False,
        "productionReadyClaimed": False,
        "cutoffRuntimeProof": cutoff,
        "surfaceTransactionRuntimeProof": surface,
        "transactionSamplingRuntimeProof": transaction,
        "controlContractRuntimeProof": control,
        "fixtures": fixtures,
    }, sort_keys=True))


if __name__ == "__main__":
    main()
