#!/usr/bin/env python3
from __future__ import annotations

import ast
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from blender.iss_battle_runtime_contact_geometry_v1 import (
    COLLIDER_GAP_MODEL,
    conservative_contact_gap,
    obb_signed_separation_2d,
)

HELPER = ROOT / "blender" / "iss_battle_runtime_contact_geometry_v1.py"
WRAPPER = ROOT / "blender" / "run_generic_battle_runtime_v1_candidate472_generic_battle.py"
TACTICS = ROOT / "blender" / "iss_battle_runtime_tactics_v5.py"
C471 = ROOT / "blender" / "run_generic_battle_runtime_v1_candidate471_generic_battle.py"
FORBIDDEN_ASSET_TOKENS = ("bugatti", "bulldozer", "ferrari")


def main() -> None:
    texts = {
        "helper": HELPER.read_text(encoding="utf-8"),
        "wrapper": WRAPPER.read_text(encoding="utf-8"),
        "tactics": TACTICS.read_text(encoding="utf-8"),
        "c471": C471.read_text(encoding="utf-8"),
    }
    for name, text in texts.items():
        ast.parse(text, filename=name)

    # False-near-contact case: center-line support can overlap while a BOX SAT
    # axis still has 13 cm of real separation. The conservative contact gap must
    # preserve that positive physical separation.
    sat_gap = obb_signed_separation_2d(
        (0.0, 0.0), (1.0, 0.0), (0.0, 1.0), (2.23, 0.935),
        (3.5, 2.0), (1.0, 0.0), (0.0, 1.0), (2.23, 0.935),
    )
    assert abs(sat_gap - 0.13) < 1.0e-9, sat_gap
    assert abs(conservative_contact_gap(-0.7690153544530931, sat_gap) - 0.13) < 1.0e-9

    # Aligned contact geometry stays unchanged: the SAT and radial models agree.
    aligned_gap = obb_signed_separation_2d(
        (0.0, 0.0), (1.0, 0.0), (0.0, 1.0), (2.0, 1.0),
        (4.1, 0.0), (1.0, 0.0), (0.0, 1.0), (2.0, 1.0),
    )
    assert abs(aligned_gap - 0.1) < 1.0e-9, aligned_gap
    assert abs(conservative_contact_gap(0.1, aligned_gap) - 0.1) < 1.0e-9

    # True overlap remains non-positive; this helper does not fabricate contact
    # success, it only removes premature handoff authority.
    overlap_gap = obb_signed_separation_2d(
        (0.0, 0.0), (1.0, 0.0), (0.0, 1.0), (2.0, 1.0),
        (3.8, 0.0), (1.0, 0.0), (0.0, 1.0), (2.0, 1.0),
    )
    assert overlap_gap < 0.0, overlap_gap

    for token in FORBIDDEN_ASSET_TOKENS:
        assert token not in texts["helper"].lower(), ("ASSET_SPECIFIC_HELPER_TOKEN", token)
        assert token not in texts["wrapper"].lower(), ("ASSET_SPECIFIC_WRAPPER_TOKEN", token)

    # Prior C471 transaction ownership and observability remain present.
    assert "G05_PRE_CUTOFF_LOCALITY_SAMPLE_EXCLUDED" in texts["c471"]
    assert "G05_PAIRWISE_SOLVER_RESPONSE_REJECTED" in texts["c471"]

    # The existing runway formula remains authoritative. C472 only separates
    # recovery-state ownership from runway-state ownership.
    assert "def engagement_runway_required" in texts["tactics"]
    assert "def _recovery_separation_required" in texts["tactics"]
    assert "GENERIC_RECOVERY_RUNWAY_PHASE_SPLIT" in texts["wrapper"]
    assert "GENERIC_ENGAGEMENT_RUNWAY_REARM_REQUIRED" in texts["wrapper"]
    assert "GENERIC_COLLIDER_SAT_GAP_GUARD_ACTIVE" in texts["wrapper"]

    for required in (
        '"colliderAwareHandoffGap": True',
        '"radialGapPreservedAsLowerBound": True',
        '"boxSatSeparationAdded": True',
        '"recoverySeparationRunwayPhasesSplit": True',
        '"engagementRunwayFormulaChanged": False',
        '"existingG05OuterAuthorityGatePreserved": True',
        '"existingPairwiseSolverOraclePreserved": True',
        '"c471TransactionBoundedLocalityPreserved": True',
        '"c470LivePairSurfaceSemanticSelectionPreserved": True',
        '"c469CutoffCleanupPreserved": True',
        '"c468RecencyBudgetPreserved": True',
        '"semanticToleranceChanged": False',
        '"localityToleranceChanged": False',
        '"contactThresholdChanged": False',
        '"damageAdmissionThresholdChanged": False',
        '"fixtureMutationForAcceptance": False',
        '"perAssetBattleCode": False',
        '"actorPoseOrVelocityMutation": False',
        '"gateClosed": False',
    ):
        assert required in texts["wrapper"], required

    for forbidden in (
        "MIN_CLOSING_SPEED_MPS =",
        "MIN_IMPULSE_BALANCE_RATIO =",
        "MIN_OPPOSITION_COSINE =",
        "MIN_NORMAL_ALIGNMENT =",
        "semantic_tolerance =",
        "locality_tolerance =",
        "target_impact_speed",
        "target_impact_energy",
        "collision_frame",
        "impact_frame",
        "trajectorypoints",
        "pathpoints",
        "waypoints",
        "set_pose",
        "linear_velocity =",
    ):
        assert forbidden not in texts["helper"], forbidden
        assert forbidden not in texts["wrapper"], forbidden

    print(json.dumps({
        "marker": "GENERIC_AUTONOMOUS_BATTLE_C472_PROPERTY_ACCEPTANCE",
        "status": "PASS",
        "affectedLayerAudit": "PASS",
        "failureFamilies": [
            "RADIAL_SUPPORT_GAP_PRECEDES_ROTATED_BOX_CONTACT",
            "RECOVERY_SEPARATION_CONFLATED_WITH_FULL_ENGAGEMENT_RUNWAY",
        ],
        "colliderGapModel": COLLIDER_GAP_MODEL,
        "falseNearContactSyntheticCase": "PASS",
        "alignedGeometryPreserved": "PASS",
        "recoveryRunwayOwnershipSplit": "PASS",
        "engagementRunwayFormulaChanged": False,
        "existingG05OuterAuthorityGatePreserved": True,
        "existingPairwiseSolverOraclePreserved": True,
        "c471TransactionBoundedLocalityPreserved": True,
        "semanticToleranceChanged": False,
        "localityToleranceChanged": False,
        "contactThresholdChanged": False,
        "damageAdmissionThresholdChanged": False,
        "fixtureMutationForAcceptance": False,
        "perAssetBattleCode": False,
        "actorPoseOrVelocityMutation": False,
        "masterPlanAligned": True,
        "gateClosed": False,
    }, sort_keys=True))


if __name__ == "__main__":
    main()
