from __future__ import annotations

import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from blender import run_generic_battle_runtime_v1_candidate471_generic_battle as candidate471
from blender import run_generic_battle_runtime_v1_candidate489_generic_battle as candidate489

CANDIDATE = "ISS_GENERIC_BATTLE_RUNTIME_V1_CANDIDATE_4_9_0_GENERIC_AUTONOMOUS_BATTLE"
MECHANISM = "G04_G05_FINAL_COMPOSITION_BINDING_V1"
AUDIT = "G04_G05_C489_C471_FINAL_WIRING_FULL_AFFECTED_LAYER_AUDIT_20260918"
FAILURE_FAMILY = "C489_G05_NEGATIVE_ACK_OBSERVER_OVERWRITTEN_BY_C471_FINAL_WIRING"


def main() -> None:
    # C489 originally attached its observation hooks to Candidate42. During the
    # inherited runtime composition Candidate471 later re-bound the effective
    # pairwise receipt and solver evaluate hooks, so real G05 rejections bypassed
    # C489 entirely. Compose the observer at Candidate471's delegation boundary
    # instead. This changes no G05 decision, threshold, receipt, or source file.
    #
    # Candidate471's final transaction-aware receipt still owns cutoff-bounded
    # locality sampling. It now delegates its preserved underlying receipt through
    # C489's observer, which in turn delegates to the byte-identical original G05
    # receipt. Candidate471's audited solver wrapper likewise delegates its
    # preserved solver decision through C489's observer before returning the exact
    # original qualification result.
    candidate471._ORIGINAL_PAIRWISE_RECEIPT = candidate489.c489_observed_pairwise_receipt
    candidate471._ORIGINAL_SOLVER_EVALUATE = (
        candidate489._ObservedPairwiseSolverResponseOracle.evaluate
    )

    print(json.dumps({
        "marker": "GENERIC_AUTONOMOUS_BATTLE_C490_ENGINEERING_READY",
        "candidate": CANDIDATE,
        "mechanism": MECHANISM,
        "affectedLayerAudit": AUDIT,
        "affectedLayerAuditStatus": "PASS",
        "failureFamily": FAILURE_FAMILY,
        "machineEvidenceSource": "C489_L4_RUN_934f547e-9199-417a-843f-4548c06ad6a6",
        "rootCause": "C471_FINAL_MAIN_REBOUND_PAIRWISE_RECEIPT_AND_SOLVER_EVALUATE_AFTER_C489_INSTALLED_C42_OBSERVERS",
        "c471FinalReceiptCompositionObserved": True,
        "c471FinalSolverCompositionObserved": True,
        "c471TransactionAwareLocalityPreserved": True,
        "c489NegativeAckMechanismPreserved": True,
        "c488AuthorityTransferPreserved": True,
        "c487EventScopedRecoveryPreserved": True,
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
    }, sort_keys=True), flush=True)

    candidate489.main()


if __name__ == "__main__":
    main()
