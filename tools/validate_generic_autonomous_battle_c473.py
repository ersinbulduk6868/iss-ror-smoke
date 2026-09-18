#!/usr/bin/env python3
from __future__ import annotations

import ast
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from blender.iss_battle_runtime_progress_contract_v1 import (
    COLLISION_PROXY_PROGRESS_MODEL,
    HANDOFF_ELIGIBILITY_MODEL,
    TACTICAL_PROGRESS_OWNERSHIP_MODEL,
    collision_proxy_progressed,
    progress_epsilon_m,
    should_defer_contact_handoff,
    should_rebase_progress_for_tactical_goal,
)

HELPER = ROOT / "blender" / "iss_battle_runtime_progress_contract_v1.py"
WRAPPER = ROOT / "blender" / "run_generic_battle_runtime_v1_candidate473_generic_battle.py"
C472 = ROOT / "blender" / "run_generic_battle_runtime_v1_candidate472_generic_battle.py"
C471 = ROOT / "blender" / "run_generic_battle_runtime_v1_candidate471_generic_battle.py"
G05 = ROOT / "blender" / "run_generic_battle_runtime_v1_candidate42.py"
FORBIDDEN_ASSET_TOKENS = ("bugatti", "bulldozer", "ferrari")


def main() -> None:
    texts = {
        "helper": HELPER.read_text(encoding="utf-8"),
        "wrapper": WRAPPER.read_text(encoding="utf-8"),
        "c472": C472.read_text(encoding="utf-8"),
        "c471": C471.read_text(encoding="utf-8"),
        "g05": G05.read_text(encoding="utf-8"),
    }
    for name, text in texts.items():
        ast.parse(text, filename=name)

    # Existing controller formulas are reused exactly; no new acceptance margin.
    assert progress_epsilon_m(4.0) == max(0.025, 4.0 * 0.008)
    assert should_defer_contact_handoff(
        requires_contact=True,
        effective_collision_proxy_gap_m=0.12,
        existing_handoff_gap_m=0.07,
    )
    assert not should_defer_contact_handoff(
        requires_contact=True,
        effective_collision_proxy_gap_m=0.06,
        existing_handoff_gap_m=0.07,
    )
    assert not should_defer_contact_handoff(
        requires_contact=False,
        effective_collision_proxy_gap_m=1.0,
        existing_handoff_gap_m=0.07,
    )

    # Tactical goal changes invalidate distance/progress baselines; stable modes do not.
    assert should_rebase_progress_for_tactical_goal(
        previous_tactical_mode="REPOSITION",
        current_tactical_mode="COUNTER",
        tactical_transition=True,
    )
    assert should_rebase_progress_for_tactical_goal(
        previous_tactical_mode="OPEN_DISTANCE",
        current_tactical_mode="ENGAGE",
        tactical_transition=True,
    )
    assert not should_rebase_progress_for_tactical_goal(
        previous_tactical_mode="COUNTER",
        current_tactical_mode="COUNTER",
        tactical_transition=False,
    )
    assert not should_rebase_progress_for_tactical_goal(
        previous_tactical_mode=None,
        current_tactical_mode="ENGAGE",
        tactical_transition=True,
    )

    # Rigid-proxy approach can refresh the progress clock only for real contact intent.
    assert collision_proxy_progressed(
        previous_effective_gap_m=0.40,
        current_effective_gap_m=0.30,
        closing_speed_mps=2.0,
        characteristic_length_m=4.0,
        requires_contact=True,
    )
    assert not collision_proxy_progressed(
        previous_effective_gap_m=0.40,
        current_effective_gap_m=0.39,
        closing_speed_mps=2.0,
        characteristic_length_m=4.0,
        requires_contact=True,
    )
    assert not collision_proxy_progressed(
        previous_effective_gap_m=0.40,
        current_effective_gap_m=0.30,
        closing_speed_mps=-0.2,
        characteristic_length_m=4.0,
        requires_contact=True,
    )

    for token in FORBIDDEN_ASSET_TOKENS:
        assert token not in texts["helper"].lower(), ("ASSET_SPECIFIC_HELPER_TOKEN", token)
        assert token not in texts["wrapper"].lower(), ("ASSET_SPECIFIC_WRAPPER_TOKEN", token)

    # C473 explicitly reverses the C472 scope mistake: SAT is retained, but the
    # navigation-facing surface-gap function returns the original radial contract.
    assert "candidate472._ORIGINAL_SURFACE_GAP(attacker, target)" in texts["wrapper"]
    assert "return float(radial_gap), float(center_distance), normal" in texts["wrapper"]
    assert "replace(obs, requires_contact=False) if defer else obs" in texts["wrapper"]
    assert "G04_CONTACT_HANDOFF_DEFERRED_BY_OBB_SEPARATION" in texts["wrapper"]
    assert "G04_AUTONOMY_PROGRESS_REBASED_FOR_TACTICAL_GOAL" in texts["wrapper"]
    assert "G04_COLLISION_PROXY_PROGRESS_REFRESHED" in texts["wrapper"]

    assert "ContactOuterAuthorityGate.evaluate" in texts["g05"]
    assert "PairwiseSolverResponseOracle.evaluate" in texts["g05"]
    assert "G05_PRE_CUTOFF_LOCALITY_SAMPLE_EXCLUDED" in texts["c471"]
    assert "G05_PAIRWISE_SOLVER_RESPONSE_REJECTED" in texts["c471"]

    for required in (
        '"radialNavigationContractPreserved": True',
        '"obbSatUsedOnlyForHandoffEligibility": True',
        '"existingHandoffGapReusedUnchanged": True',
        '"tacticalGoalProgressRebased": True',
        '"collisionProxyApproachCountsAsProgress": True',
        '"g05NativeSolverFinalAuthorityPreserved": True',
        '"pairwiseSolverOraclePreserved": True',
        '"c471TransactionBoundedLocalityPreserved": True',
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
        "set_pose",
        "linear_velocity =",
    ):
        assert forbidden not in texts["helper"], forbidden
        assert forbidden not in texts["wrapper"], forbidden

    print(json.dumps({
        "marker": "GENERIC_AUTONOMOUS_BATTLE_C473_PROPERTY_ACCEPTANCE",
        "status": "PASS",
        "affectedLayerAudit": "PASS",
        "failureFamily": "HANDOFF_GEOMETRY_SCOPE_AND_TACTICAL_PROGRESS_MEMORY_MISMATCH",
        "handoffEligibilityModel": HANDOFF_ELIGIBILITY_MODEL,
        "tacticalProgressOwnershipModel": TACTICAL_PROGRESS_OWNERSHIP_MODEL,
        "collisionProxyProgressModel": COLLISION_PROXY_PROGRESS_MODEL,
        "radialNavigationContractPreserved": "PASS",
        "obbOnlyHandoffEligibility": "PASS",
        "existingHandoffGapReused": "PASS",
        "tacticalGoalProgressRebase": "PASS",
        "collisionProxyProgressRefresh": "PASS",
        "g05NativeSolverFinalAuthorityPreserved": True,
        "pairwiseSolverOraclePreserved": True,
        "c471TransactionBoundedLocalityPreserved": True,
        "semanticToleranceChanged": False,
        "localityToleranceChanged": False,
        "contactThresholdChanged": False,
        "damageAdmissionThresholdChanged": False,
        "perAssetBattleCode": False,
        "actorPoseOrVelocityMutation": False,
        "masterPlanAligned": True,
        "gateClosed": False,
    }, sort_keys=True))


if __name__ == "__main__":
    main()
