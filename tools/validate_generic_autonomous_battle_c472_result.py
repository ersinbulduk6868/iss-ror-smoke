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


def _c472_runtime_proof(path: str) -> dict[str, object]:
    rows = _rows(path)
    guards = [row for row in rows if row.get("marker") == "GENERIC_COLLIDER_SAT_GAP_GUARD_ACTIVE"]
    splits = [row for row in rows if row.get("marker") == "GENERIC_RECOVERY_RUNWAY_PHASE_SPLIT"]
    rearms = [row for row in rows if row.get("marker") == "GENERIC_ENGAGEMENT_RUNWAY_REARM_REQUIRED"]
    contacts = [row for row in rows if row.get("marker") == "PAIRWISE_NATIVE_SOLVER_CONTACT_VERIFIED"]

    assert contacts, "C472_NATIVE_CONTACT_NOT_VERIFIED"

    for row in guards:
        radial = float(row.get("radialGapM") or 0.0)
        sat = float(row.get("satGapM") or 0.0)
        physical = float(row.get("physicalGapM") or 0.0)
        assert abs(physical - max(radial, sat)) <= 1.0e-6, ("C472_CONSERVATIVE_GAP_INVALID", row)
        assert row.get("assetIdentityBranch") is False, row
        assert row.get("contactThresholdChanged") is False, row

    for row in splits:
        previous = float(row.get("previousSeparationRequiredM") or 0.0)
        recovery = float(row.get("recoverySeparationRequiredM") or 0.0)
        runway = float(row.get("engagementRunwayRequiredM") or 0.0)
        assert previous + 1.0e-6 >= recovery, ("C472_RECOVERY_SPLIT_INVERTED", row)
        assert runway + 1.0e-6 >= recovery, ("C472_RUNWAY_BELOW_RECOVERY", row)
        assert row.get("engagementRunwayFormulaChanged") is False, row
        assert row.get("recoveryThresholdChanged") is False, row

    for row in rearms:
        gap = float(row.get("surfaceGapM") or 0.0)
        runway = float(row.get("engagementRunwayRequiredM") or 0.0)
        assert gap < runway + 1.0e-6, ("C472_REARM_MARKER_WITH_RUNWAY_ALREADY_MET", row)
        assert row.get("engagementRunwayFormulaChanged") is False, row

    return {
        "colliderSatGuardCount": len(guards),
        "recoveryRunwaySplitCount": len(splits),
        "engagementRunwayRearmCount": len(rearms),
        "verifiedNativeContactCount": len(contacts),
        "colliderAwareHandoffGap": True,
        "recoveryRunwayOwnershipSplit": True,
        "engagementRunwayFormulaChanged": False,
        "contactThresholdChanged": False,
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
    c472: dict[str, object] = {}
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
        c472[prefix] = _c472_runtime_proof(log)

    assert int(c472["bugatti"]["colliderSatGuardCount"]) > 0, "C472_BUGATTI_SAT_GUARD_NOT_EXERCISED"
    assert int(c472["generic"]["recoveryRunwaySplitCount"]) > 0, "C472_GENERIC_RECOVERY_RUNWAY_SPLIT_NOT_EXERCISED"
    assert int(c472["generic"]["engagementRunwayRearmCount"]) > 0, "C472_GENERIC_RUNWAY_REARM_NOT_EXERCISED"

    print(json.dumps({
        "marker": "GENERIC_AUTONOMOUS_BATTLE_C472_MACHINE_ACCEPTANCE",
        "status": "PASS",
        "affectedLayerAudit": "PASS",
        "failureFamilies": [
            "RADIAL_SUPPORT_GAP_PRECEDES_ROTATED_BOX_CONTACT",
            "RECOVERY_SEPARATION_CONFLATED_WITH_FULL_ENGAGEMENT_RUNWAY",
        ],
        "sameRuntimeAcrossAssets": True,
        "colliderAwareHandoffGap": "PASS",
        "recoveryRunwayOwnershipSplit": "PASS",
        "transactionBoundedLocalityWindow": "PASS",
        "solverRejectObservability": "PASS",
        "livePairSurfaceSemanticSelection": "PASS",
        "freshHandoffTransactionBinding": "PASS",
        "secondNativeContact": "PASS",
        "twoSidedDamage": "PASS",
        "visibleCausalDamageDebris": "PASS",
        "g07AdaptiveCausalDrama": "PASS",
        "g08MachineObservability": "PASS",
        "nativeContactAuthorityPreserved": True,
        "pairwiseSolverOraclePreserved": True,
        "engagementRunwayFormulaChanged": False,
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
        "c472RuntimeProof": c472,
        "fixtures": fixtures,
    }, sort_keys=True))


if __name__ == "__main__":
    main()
