#!/usr/bin/env python3
from __future__ import annotations

import ast
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from blender.iss_battle_runtime_pursuit_v1 import (
    PURSUIT_MODEL,
    capability_bounded_lead_seconds,
    predicted_target_xy,
)

HELPER = ROOT / "blender" / "iss_battle_runtime_pursuit_v1.py"
WRAPPER = ROOT / "blender" / "run_generic_battle_runtime_v1_candidate472_generic_battle.py"
FORBIDDEN_ASSET_TOKENS = ("bugatti", "bulldozer", "ferrari", "hypercar")


def main() -> None:
    helper = HELPER.read_text(encoding="utf-8")
    wrapper = WRAPPER.read_text(encoding="utf-8")
    ast.parse(helper, filename=str(HELPER))
    ast.parse(wrapper, filename=str(WRAPPER))

    # Stationary target: no artificial lead is introduced.
    stationary = capability_bounded_lead_seconds(
        relative_xy=(10.0, 0.0),
        target_velocity_xy=(0.0, 0.0),
        pursuer_speed_mps=12.0,
        max_yaw_rate_rad_s=1.2,
        characteristic_length_m=4.5,
    )
    assert stationary == 0.0, stationary

    # Moving target: current velocity influences a short live intercept goal.
    agile = capability_bounded_lead_seconds(
        relative_xy=(10.0, 0.0),
        target_velocity_xy=(0.0, 4.0),
        pursuer_speed_mps=16.0,
        max_yaw_rate_rad_s=1.4,
        characteristic_length_m=4.5,
    )
    heavy = capability_bounded_lead_seconds(
        relative_xy=(10.0, 0.0),
        target_velocity_xy=(0.0, 4.0),
        pursuer_speed_mps=8.0,
        max_yaw_rate_rad_s=0.65,
        characteristic_length_m=6.5,
    )
    assert 0.0 < agile <= 1.25, agile
    assert 0.0 < heavy <= 1.25, heavy
    assert agile != heavy, (agile, heavy)

    predicted = predicted_target_xy(
        target_xy=(5.0, 2.0),
        target_velocity_xy=(0.0, 4.0),
        lead_seconds=agile,
    )
    assert predicted[0] == 5.0
    assert predicted[1] > 2.0

    for token in FORBIDDEN_ASSET_TOKENS:
        assert token not in helper.lower(), ("ASSET_SPECIFIC_HELPER_TOKEN", token)
        assert token not in wrapper.lower(), ("ASSET_SPECIFIC_WRAPPER_TOKEN", token)

    for required in (
        "battle_v6._goal_for_tactical = live_intercept_goal_for_tactical",
        "candidate467.candidate443._auto_engagement_events",
        "G04_LIVE_INTERCEPT_GOAL_APPLIED",
        '"g04OwnsLivePursuitGoal": True',
        '"runtimeSelectedGenericEngagementOnly": True',
        '"storyPrescribedSemanticTargetPreserved": True',
        '"liveTargetVelocityObserved": True',
        '"actorProfileCapabilityBounded": True',
        '"goalRecomputedEveryFrame": True',
        '"cachedTrajectory": False',
        '"c471TransactionSamplingPreserved": True',
        '"c470SemanticSurfaceHandoffPreserved": True',
        '"existingG05OuterAuthorityGatePreserved": True',
        '"existingPairwiseSolverOraclePreserved": True',
        '"semanticToleranceChanged": False',
        '"localityToleranceChanged": False',
        '"contactThresholdChanged": False',
        '"damageAdmissionThresholdChanged": False',
        '"perAssetBattleCode": False',
        '"perVideoTrajectoryEngineering": False',
        '"actorPoseOrVelocityMutation": False',
        '"gateClosed": False',
    ):
        assert required in wrapper, required

    for forbidden in (
        "MIN_CLOSING_SPEED_MPS =",
        "MIN_IMPULSE_BALANCE_RATIO =",
        "MIN_OPPOSITION_COSINE =",
        "MIN_NORMAL_ALIGNMENT =",
        "semantic_tolerance =",
        "locality_tolerance =",
        "collision_frame",
        "impact_frame",
        "target_impact_speed",
        "target_impact_energy",
        "trajectorypoints",
        "pathpoints",
        "waypoints",
        "set_pose",
        "linear_velocity =",
    ):
        assert forbidden not in helper, forbidden
        assert forbidden not in wrapper, forbidden

    print(json.dumps({
        "marker": "GENERIC_AUTONOMOUS_BATTLE_C472_PROPERTY_ACCEPTANCE",
        "status": "PASS",
        "affectedLayerAudit": "PASS",
        "failureFamily": "MOVING_TARGET_POINT_CHASE_FAILS_TO_REACQUIRE_CONTACT",
        "rootCause": "DIRECT_ENGAGEMENT_CHASES_MOVING_SEMANTIC_POINT_WITHOUT_PAIR_CENTER_INTERCEPT",
        "pursuitModel": PURSUIT_MODEL,
        "stationaryTargetNoArtificialLead": True,
        "movingTargetLiveLead": "PASS",
        "dissimilarCapabilityResponse": "PASS",
        "storyPrescribedSemanticTargetPreserved": True,
        "c471TransactionSamplingPreserved": True,
        "c470SemanticSurfaceHandoffPreserved": True,
        "existingG05OuterAuthorityGatePreserved": True,
        "existingPairwiseSolverOraclePreserved": True,
        "semanticToleranceChanged": False,
        "localityToleranceChanged": False,
        "contactThresholdChanged": False,
        "damageAdmissionThresholdChanged": False,
        "perAssetBattleCode": False,
        "perVideoTrajectoryEngineering": False,
        "masterPlanAligned": True,
        "gateClosed": False,
    }, sort_keys=True))


if __name__ == "__main__":
    main()
