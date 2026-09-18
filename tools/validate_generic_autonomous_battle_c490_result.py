#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
TOOLS = ROOT / "tools"
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

import validate_generic_autonomous_battle_c489_result as c489
from validate_generic_autonomous_battle_c480_result import _json_markers

CANDIDATE = "ISS_GENERIC_BATTLE_RUNTIME_V1_CANDIDATE_4_9_0_GENERIC_AUTONOMOUS_BATTLE"
MECHANISM = "G04_G05_FINAL_COMPOSITION_BINDING_V1"
FAILURE_FAMILY = "C489_G05_NEGATIVE_ACK_OBSERVER_OVERWRITTEN_BY_C471_FINAL_WIRING"


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--log", required=True)
    a = p.parse_args()

    rows = _json_markers(a.log)
    ready = [r for r in rows if r.get("marker") == "GENERIC_AUTONOMOUS_BATTLE_C490_ENGINEERING_READY"]
    assert len(ready) == 1, ("C490_ENGINEERING_READY_COUNT", len(ready))
    receipt = ready[0]
    assert receipt.get("candidate") == CANDIDATE, receipt
    assert receipt.get("mechanism") == MECHANISM, receipt
    assert receipt.get("affectedLayerAuditStatus") == "PASS", receipt
    assert receipt.get("failureFamily") == FAILURE_FAMILY, receipt
    for field in (
        "c471FinalReceiptCompositionObserved",
        "c471FinalSolverCompositionObserved",
        "c471TransactionAwareLocalityPreserved",
        "c489NegativeAckMechanismPreserved",
        "c488AuthorityTransferPreserved",
        "c487EventScopedRecoveryPreserved",
    ):
        assert receipt.get(field) is True, (field, receipt.get(field))
    for field in (
        "g05SourceChanged", "g05OuterGateChanged", "g05SolverOracleChanged",
        "g05ThresholdImported", "contactThresholdChanged", "semanticToleranceChanged",
        "localityToleranceChanged", "damageAdmissionThresholdChanged",
        "assetIdentityBranch", "perAssetBattleCode", "perAssetTacticalTuning",
        "perVideoTrajectoryEngineering", "fixedWorldCoordinates",
        "exactCollisionFrameTarget", "exactImpactEnergyTarget",
        "actorPoseOrVelocityMutation", "fixtureBattlePlanChanged",
        "frozenNineServiceArchitectureChanged", "gateClosed", "productionReadyClaimed",
    ):
        assert receipt.get(field) is False, (field, receipt.get(field))

    # Reuse the complete C489 runtime proof: confirmed G05 negative acknowledgement
    # must release the failed handoff, enter event-scoped recovery/replan, restart
    # the semantic transaction, reach a fresh handoff, and finally earn native G05
    # contact without hiding controller-authority or target-identity regressions.
    nack = c489.c489_runtime_proof(a.log)

    print(json.dumps({
        "marker": "GENERIC_AUTONOMOUS_BATTLE_C490_MACHINE_ACCEPTANCE",
        "status": "PASS",
        "candidate": CANDIDATE,
        "mechanism": MECHANISM,
        "failureFamily": FAILURE_FAMILY,
        "executionProfile": "NVIDIA_L4",
        "finalCompositionBinding": "PASS",
        "c489NegativeAckRuntimeProof": "PASS",
        "g05AuthorityPreserved": True,
        "contactThresholdChanged": False,
        "semanticToleranceChanged": False,
        "localityToleranceChanged": False,
        "damageAdmissionThresholdChanged": False,
        "perAssetBattleCode": False,
        "perAssetTacticalTuning": False,
        "perVideoTrajectoryEngineering": False,
        "gateClosed": False,
        "productionReadyClaimed": False,
        "negativeAckProof": nack,
    }, sort_keys=True))


if __name__ == "__main__":
    main()
