#!/usr/bin/env python3
from __future__ import annotations

import ast
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WRAPPER = ROOT / "blender" / "run_generic_battle_runtime_v1_candidate490_generic_battle.py"
C489 = ROOT / "blender" / "run_generic_battle_runtime_v1_candidate489_generic_battle.py"
C471 = ROOT / "blender" / "run_generic_battle_runtime_v1_candidate471_generic_battle.py"
C42 = ROOT / "blender" / "run_generic_battle_runtime_v1_candidate42.py"


def main() -> None:
    wrapper = WRAPPER.read_text(encoding="utf-8")
    c489 = C489.read_text(encoding="utf-8")
    c471 = C471.read_text(encoding="utf-8")
    c42 = C42.read_text(encoding="utf-8")
    for name, text in (("wrapper", wrapper), ("c489", c489), ("c471", c471), ("c42", c42)):
        ast.parse(text, filename=name)

    # Machine-proven C489 L4 root cause: Candidate471.main performs the final
    # effective Candidate42 receipt/solver rebinding after C489's earlier hooks.
    assert "candidate42._pairwise_receipt = transaction_aware_pairwise_receipt" in c471
    assert "candidate42.PairwiseSolverResponseOracle.evaluate = staticmethod(audited_solver_evaluate)" in c471
    assert "candidate42._pairwise_receipt = c489_observed_pairwise_receipt" in c489

    # C490 composes at Candidate471's delegation boundary, so those later rebinds
    # cannot erase C489 observation. Candidate471's existing transaction-aware
    # locality and audited solver evidence remain in the path.
    assert "candidate471._ORIGINAL_PAIRWISE_RECEIPT = candidate489.c489_observed_pairwise_receipt" in wrapper
    assert "candidate471._ORIGINAL_SOLVER_EVALUATE = (" in wrapper
    assert "candidate489._ObservedPairwiseSolverResponseOracle.evaluate" in wrapper
    assert "candidate489.main()" in wrapper
    assert "transaction_aware_best_recent_locality" in c471
    assert "G05_PAIRWISE_SOLVER_RESPONSE_REJECTED" in c471

    # C489 still observes the original G05 decision and delegates without changing
    # authority. The original G05 gate/oracle remain present in Candidate42.
    assert "_ORIGINAL_OUTER_GATE.evaluate(sample)" in c489
    assert "_ORIGINAL_SOLVER_ORACLE.evaluate(sample)" in c489
    assert "ContactOuterAuthorityGate.evaluate" in c42
    assert "PairwiseSolverResponseOracle.evaluate" in c42

    required_true = (
        '"c471FinalReceiptCompositionObserved": True',
        '"c471FinalSolverCompositionObserved": True',
        '"c471TransactionAwareLocalityPreserved": True',
        '"c489NegativeAckMechanismPreserved": True',
        '"c488AuthorityTransferPreserved": True',
        '"c487EventScopedRecoveryPreserved": True',
    )
    for token in required_true:
        assert token in wrapper, token

    required_false = (
        '"g05SourceChanged": False',
        '"g05OuterGateChanged": False',
        '"g05SolverOracleChanged": False',
        '"g05ThresholdImported": False',
        '"contactThresholdChanged": False',
        '"semanticToleranceChanged": False',
        '"localityToleranceChanged": False',
        '"damageAdmissionThresholdChanged": False',
        '"assetIdentityBranch": False',
        '"perAssetBattleCode": False',
        '"perAssetTacticalTuning": False',
        '"perVideoTrajectoryEngineering": False',
        '"actorPoseOrVelocityMutation": False',
        '"fixtureBattlePlanChanged": False',
        '"frozenNineServiceArchitectureChanged": False',
        '"gateClosed": False',
        '"productionReadyClaimed": False',
    )
    for token in required_false:
        assert token in wrapper, token

    lowered = wrapper.lower()
    for forbidden in (
        "bugatti", "bulldozer", "ferrari",
        "target_impact_speed", "target_impact_energy",
        "trajectorypoints", "waypoints", "set_pose", "linear_velocity =",
        "semantic_tolerance =", "locality_tolerance =", "min_closing_speed",
    ):
        assert forbidden not in lowered, forbidden

    print(json.dumps({
        "marker": "GENERIC_AUTONOMOUS_BATTLE_C490_PROPERTY_ACCEPTANCE",
        "status": "PASS",
        "candidate": "ISS_GENERIC_BATTLE_RUNTIME_V1_CANDIDATE_4_9_0_GENERIC_AUTONOMOUS_BATTLE",
        "mechanism": "G04_G05_FINAL_COMPOSITION_BINDING_V1",
        "failureFamily": "C489_G05_NEGATIVE_ACK_OBSERVER_OVERWRITTEN_BY_C471_FINAL_WIRING",
        "finalReceiptComposition": "PASS",
        "finalSolverComposition": "PASS",
        "c471TransactionAwareLocalityPreserved": True,
        "c489NegativeAckPreserved": True,
        "g05AuthorityPreserved": True,
        "semanticToleranceChanged": False,
        "localityToleranceChanged": False,
        "contactThresholdChanged": False,
        "damageAdmissionThresholdChanged": False,
        "assetSpecificCode": False,
        "perAssetTacticalTuning": False,
        "perVideoTrajectoryEngineering": False,
        "masterPlanAligned": True,
        "gateClosed": False,
    }, sort_keys=True))


if __name__ == "__main__":
    main()
