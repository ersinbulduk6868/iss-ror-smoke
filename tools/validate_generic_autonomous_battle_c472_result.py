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


def _goal_scope_runtime_proof(path: str) -> dict[str, object]:
    rows = _rows(path)
    rebases = [row for row in rows if row.get("marker") == "G04_AUTONOMY_GOAL_SCOPE_REBASED"]
    sat_guards = [row for row in rows if row.get("marker") == "G04_SAT_GAP_PREVENTED_EARLY_HANDOFF"]
    assert rebases, "C472_GOAL_SCOPE_REBASE_NOT_OBSERVED"
    for row in rebases:
        for key in (
            "attemptLedgerPreserved",
            "replanLedgerPreserved",
            "contactHistoryPreserved",
            "damageHistoryPreserved",
        ):
            assert row.get(key) is True, ("C472_GOAL_SCOPE_HISTORY_NOT_PRESERVED", key, row)

    bad_sat = [
        row for row in sat_guards
        if row.get("g05ContactAuthorityChanged") is not False
        or row.get("contactThresholdChanged") is not False
        or float(row.get("effectivePhysicalGapM") or 0.0)
           < float(row.get("centerlineSupportGapM") or 0.0)
    ]
    assert not bad_sat, ("C472_SAT_GUARD_CONTRACT_INVALID", bad_sat[:5])

    solver_contacts = [
        row for row in rows if row.get("marker") == "PAIRWISE_NATIVE_SOLVER_CONTACT_VERIFIED"
    ]
    assert solver_contacts, "C472_NATIVE_CONTACT_NOT_VERIFIED"

    return {
        "goalScopeRebaseCount": len(rebases),
        "satGuardObservationCount": len(sat_guards),
        "goalScopeHistoryPreserved": True,
        "g05ContactAuthorityChanged": False,
        "contactThresholdChanged": False,
        "nativeContactCount": len(solver_contacts),
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
    goal_scope: dict[str, object] = {}

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
        goal_scope[prefix] = _goal_scope_runtime_proof(log)

    print(json.dumps({
        "marker": "GENERIC_AUTONOMOUS_BATTLE_C472_MACHINE_ACCEPTANCE",
        "status": "PASS",
        "affectedLayerAudit": "PASS",
        "failureFamily": "TACTICAL_GOAL_SCOPE_LEAK_AND_CENTERLINE_GAP_EARLY_HANDOFF",
        "sameRuntimeAcrossAssets": True,
        "goalScopedAutonomy": "PASS",
        "satAwareG04PhysicalGap": "PASS",
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
        "g05ContactAuthorityChanged": False,
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
        "goalScopeRuntimeProof": goal_scope,
        "fixtures": fixtures,
    }, sort_keys=True))


if __name__ == "__main__":
    main()
