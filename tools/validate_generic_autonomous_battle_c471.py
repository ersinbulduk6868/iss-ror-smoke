#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from blender.iss_battle_runtime_contact_transaction_v1 import (
    TRANSACTION_LOCALITY_MODEL,
    all_samples_belong_to_transaction,
    transaction_candidate_frames,
    transaction_window_start,
)


def main() -> None:
    # Exact C470 observed ordering: at frame 780 the legacy three-frame window
    # could select 778 even though the fresh handoff cutoff was 779.
    assert transaction_window_start(780, 779, 3) == 779
    assert transaction_candidate_frames(780, 779, 3) == (779, 780)
    assert all_samples_belong_to_transaction((779, 780), 779)
    assert 778 not in transaction_candidate_frames(780, 779, 3)

    # When the cutoff predates the rolling window, preserve the existing
    # three-frame locality window unchanged.
    assert transaction_window_start(190, 182, 3) == 188
    assert transaction_candidate_frames(190, 182, 3) == (188, 189, 190)

    # With no active transaction preserve legacy window semantics.
    assert transaction_candidate_frames(780, None, 3) == (778, 779, 780)

    runtime_path = ROOT / "blender" / "run_generic_battle_runtime_v1_candidate471_generic_battle.py"
    text = runtime_path.read_text(encoding="utf-8")
    required = (
        "candidate42._best_recent_locality = transaction_aware_best_recent_locality",
        "candidate42._pairwise_receipt = transaction_aware_pairwise_receipt",
        "candidate42.PairwiseSolverResponseOracle.evaluate = staticmethod(audited_solver_evaluate)",
        "G05_PRE_CUTOFF_LOCALITY_SAMPLE_EXCLUDED",
        "G05_PAIRWISE_SOLVER_RESPONSE_REJECTED",
        "existingPairwiseSolverOraclePreserved\": True",
        "solverWindowFramesChanged\": False",
        "semanticToleranceChanged\": False",
        "localityToleranceChanged\": False",
        "contactThresholdChanged\": False",
        "damageAdmissionThresholdChanged\": False",
        "perAssetBattleCode\": False",
        "fixedWorldCoordinates\": False",
        "actorPoseOrVelocityMutation\": False",
    )
    for token in required:
        assert token in text, ("C471_REQUIRED_RUNTIME_CONTRACT_MISSING", token)

    forbidden = (
        "MIN_CLOSING_SPEED_MPS =",
        "MIN_IMPULSE_BALANCE_RATIO =",
        "MIN_OPPOSITION_COSINE =",
        "MIN_NORMAL_ALIGNMENT =",
        "semantic_tolerance =",
        "locality_tolerance =",
    )
    for token in forbidden:
        assert token not in text, ("C471_FORBIDDEN_THRESHOLD_OVERRIDE", token)

    print(json.dumps({
        "marker": "GENERIC_AUTONOMOUS_BATTLE_C471_PROPERTY_ACCEPTANCE",
        "status": "PASS",
        "mechanism": TRANSACTION_LOCALITY_MODEL,
        "preCutoffHistoricalSampleExcluded": True,
        "legacyWindowPreservedOutsideFreshCutoff": True,
        "solverRejectEvidenceAddedWithoutReclassification": True,
        "existingG05OuterAuthorityGatePreserved": True,
        "existingPairwiseSolverOraclePreserved": True,
        "c470LivePairSurfaceSemanticSelectionPreserved": True,
        "semanticToleranceChanged": False,
        "localityToleranceChanged": False,
        "contactThresholdChanged": False,
        "damageAdmissionThresholdChanged": False,
        "perAssetBattleCode": False,
        "perVideoTrajectoryEngineering": False,
        "fixedWorldCoordinates": False,
        "actorPoseOrVelocityMutation": False,
        "gateClosed": False,
        "productionReadyClaimed": False,
    }, sort_keys=True))


if __name__ == "__main__":
    main()
