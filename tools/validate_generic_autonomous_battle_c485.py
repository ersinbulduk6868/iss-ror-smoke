#!/usr/bin/env python3
from __future__ import annotations

import ast
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from blender.iss_battle_runtime_contact_truth import PairwiseSolverResponseOracle
from blender.iss_battle_runtime_g05_handoff_readiness_v1 import (
    G05_HANDOFF_READINESS_MODEL,
    handoff_readiness_recovery_required,
    required_normal_closing_speed_mps,
)

HELPER = ROOT / "blender" / "iss_battle_runtime_g05_handoff_readiness_v1.py"
WRAPPER = ROOT / "blender" / "run_generic_battle_runtime_v1_candidate485_generic_battle.py"
FORBIDDEN_ASSET_TOKENS = (
    "bulldozer",
    "b06a715d23a7450babac383b8bb7fb0a",
    "2c0be359bbc6c99118751e7caa4b71a205961914e78d2e58c5dd7afc0f498468",
    "27614.189525707065",
)


def main() -> None:
    helper_text = HELPER.read_text(encoding="utf-8")
    wrapper_text = WRAPPER.read_text(encoding="utf-8")
    ast.parse(helper_text, filename=str(HELPER))
    ast.parse(wrapper_text, filename=str(WRAPPER))

    authoritative = float(PairwiseSolverResponseOracle.MIN_CLOSING_SPEED_MPS)
    assert required_normal_closing_speed_mps() == authoritative
    assert handoff_readiness_recovery_required(
        contact_handoff_requested=False,
        live_normal_closing_speed_mps=0.0,
    ) is False
    assert handoff_readiness_recovery_required(
        contact_handoff_requested=True,
        live_normal_closing_speed_mps=authoritative - 1.0e-6,
    ) is True
    assert handoff_readiness_recovery_required(
        contact_handoff_requested=True,
        live_normal_closing_speed_mps=authoritative,
    ) is False
    assert handoff_readiness_recovery_required(
        contact_handoff_requested=True,
        live_normal_closing_speed_mps=authoritative + 1.0,
    ) is False

    lower = (helper_text + "\n" + wrapper_text).lower()
    for token in FORBIDDEN_ASSET_TOKENS:
        assert token.lower() not in lower, ("C485_ASSET_SPECIFIC_TOKEN_FORBIDDEN", token)

    # The downstream G05 value must never be copied into C485.  G05 remains the
    # single source of truth for the locked physical solver-admission contract.
    assert "1.25" not in helper_text
    assert "1.25" not in wrapper_text
    assert "PairwiseSolverResponseOracle.MIN_CLOSING_SPEED_MPS" in helper_text

    for required in (
        "candidate484.alignment_aware_base_autonomy_update = g05_readiness_aware_base_autonomy_update",
        "G04_G05_HANDOFF_READINESS_RECOVERY_TRIGGERED",
        "G04_G05_HANDOFF_READINESS_CONFIRMED",
        '"g05ReadinessUsesAuthoritativeOracleConstant": True',
        '"g05ThresholdCopiedOrRetuned": False',
        '"g05NativeSolverFinalAuthorityPreserved": True',
        '"existingGenericRecoveryReused": True',
        '"desiredImpactSpeedControl": False',
        '"desiredImpactEnergyControl": False',
        '"assetIdentityBranch": False',
        '"perAssetBattleCode": False',
        '"perAssetTacticalTuning": False',
        '"perVideoTrajectoryEngineering": False',
        '"actorPoseOrVelocityMutation": False',
        '"contactThresholdChanged": False',
        '"damageAdmissionThresholdChanged": False',
    ):
        assert required in wrapper_text, required

    for forbidden in (
        "targetImpactSpeed",
        "target_impact_speed",
        "desiredImpactSpeedMps",
        "desiredImpactEnergyJ",
        "collisionFrame",
        "impactFrame",
        "trajectoryPoints",
        "waypoints",
        "set_pose",
        "linear_velocity =",
        "MIN_CLOSING_SPEED_MPS =",
        "MIN_IMPULSE_BALANCE_RATIO =",
        "MIN_OPPOSITION_COSINE =",
        "MIN_NORMAL_ALIGNMENT =",
    ):
        assert forbidden not in helper_text, forbidden
        assert forbidden not in wrapper_text, forbidden

    print(json.dumps({
        "marker": "GENERIC_AUTONOMOUS_BATTLE_C485_PROPERTY_ACCEPTANCE",
        "status": "PASS",
        "affectedLayerAudit": "PASS",
        "mechanism": G05_HANDOFF_READINESS_MODEL,
        "failureFamily": "G04_RELEASES_MOTOR_AUTHORITY_BEFORE_G05_SOLVER_ADMISSION_IS_PHYSICALLY_POSSIBLE",
        "authoritativeG05ReadinessContract": "PASS",
        "g05ThresholdCopiedOrRetuned": False,
        "existingGenericRecoveryReused": True,
        "assetSpecificCode": False,
        "perAssetTacticalTuning": False,
        "desiredImpactSpeedControl": False,
        "desiredImpactEnergyControl": False,
        "thresholdChanged": False,
        "masterPlanAligned": True,
        "gateClosed": False,
    }, sort_keys=True))


if __name__ == "__main__":
    main()
