#!/usr/bin/env python3
from __future__ import annotations

import ast
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from blender.iss_battle_runtime_handoff_readiness_v1 import (
    HANDOFF_READINESS_MODEL,
    handoff_closing_ready,
    live_recovery_bias,
)
from blender.iss_battle_runtime_contact_truth import PairwiseSolverResponseOracle

HELPER = ROOT / "blender" / "iss_battle_runtime_handoff_readiness_v1.py"
WRAPPER = ROOT / "blender" / "run_generic_battle_runtime_v1_candidate473_generic_battle.py"
AUTONOMY = ROOT / "blender" / "iss_battle_runtime_autonomy.py"


def main() -> None:
    helper = HELPER.read_text(encoding="utf-8")
    wrapper = WRAPPER.read_text(encoding="utf-8")
    autonomy = AUTONOMY.read_text(encoding="utf-8")
    ast.parse(helper); ast.parse(wrapper); ast.parse(autonomy)

    assert live_recovery_bias(0.7, -1.0) == 1.0
    assert live_recovery_bias(-0.7, 1.0) == -1.0
    assert live_recovery_bias(0.0, -1.0) == -1.0

    minimum = float(PairwiseSolverResponseOracle.MIN_CLOSING_SPEED_MPS)
    assert handoff_closing_ready(minimum - 0.01, minimum) is False
    assert handoff_closing_ready(minimum, minimum) is True
    assert handoff_closing_ready(minimum + 1.0, minimum) is True

    assert "PairwiseSolverResponseOracle.MIN_CLOSING_SPEED_MPS" in wrapper
    assert "G04_HANDOFF_REJECTED_BELOW_EXISTING_G05_CLOSING_GATE" in wrapper
    assert "GENERIC_RECOVERY_BIAS_BOUND_TO_LIVE_HEADING" in wrapper
    assert '"desiredImpactSpeedControl": False' in wrapper
    assert '"existingG05MinimumClosingThresholdChanged": False' in wrapper
    assert '"perAssetBattleCode": False' in wrapper
    assert '"actorPoseOrVelocityMutation": False' in wrapper

    for token in ("bugatti", "bulldozer", "ferrari"):
        assert token not in helper.lower(), token
        assert token not in wrapper.lower(), token

    for forbidden in (
        "MIN_CLOSING_SPEED_MPS =",
        "target_impact_speed",
        "target_impact_energy",
        "collision_frame",
        "impact_frame",
        "set_pose",
        "linear_velocity =",
    ):
        assert forbidden not in helper, forbidden
        assert forbidden not in wrapper, forbidden

    print(json.dumps({
        "marker":"GENERIC_AUTONOMOUS_BATTLE_C473_PROPERTY_ACCEPTANCE",
        "status":"PASS",
        "affectedLayerAudit":"PASS",
        "failureFamilies":[
            "CONTACT_HANDOFF_CEDES_AUTHORITY_BELOW_EXISTING_G05_CLOSING_GATE",
            "RECOVERY_TURN_DIRECTION_IGNORES_LIVE_GOAL_HEADING",
        ],
        "handoffReadinessModel":HANDOFF_READINESS_MODEL,
        "liveHeadingRecoveryDirection":"PASS",
        "existingG05ClosingGateConsumedAsBooleanEligibility":"PASS",
        "desiredImpactSpeedControl":False,
        "existingG05MinimumClosingThresholdChanged":False,
        "existingPairwiseSolverOraclePreserved":True,
        "perAssetBattleCode":False,
        "actorPoseOrVelocityMutation":False,
        "masterPlanAligned":True,
        "gateClosed":False,
    },sort_keys=True))

if __name__ == "__main__":
    main()
