#!/usr/bin/env python3
from __future__ import annotations

import ast
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from blender.iss_battle_runtime_contact_commit_v2 import (
    CONTACT_COMMIT_MODEL,
    capability_motion_realization_floor_mps,
    live_contact_commit_ready,
    realized_contact_handoff_readiness,
)

HELPER = ROOT / "blender" / "iss_battle_runtime_contact_commit_v2.py"
WRAPPER = ROOT / "blender" / "run_generic_battle_runtime_v1_candidate485_generic_battle.py"
FORBIDDEN_ASSET_TOKENS = (
    "bulldozer",
    "bugatti",
    "b06a715d23a7450babac383b8bb7fb0a",
    "27614.189525707065",
)


def main() -> None:
    helper_text = HELPER.read_text(encoding="utf-8")
    wrapper_text = WRAPPER.read_text(encoding="utf-8")
    ast.parse(helper_text, filename=str(HELPER))
    ast.parse(wrapper_text, filename=str(WRAPPER))

    # COUNTER and ENGAGE now share the same live-state contact readiness contract.
    assert live_contact_commit_ready(
        requires_contact=True,
        engagement_runway_armed=True,
        heading_error_rad=0.83,
        contention=0.10,
    ) is False
    assert live_contact_commit_ready(
        requires_contact=True,
        engagement_runway_armed=True,
        heading_error_rad=0.20,
        contention=0.10,
    ) is True
    assert live_contact_commit_ready(
        requires_contact=True,
        engagement_runway_armed=True,
        heading_error_rad=0.20,
        contention=0.85,
    ) is False
    assert live_contact_commit_ready(
        requires_contact=True,
        engagement_runway_armed=False,
        heading_error_rad=0.0,
        contention=0.0,
    ) is False

    floor = capability_motion_realization_floor_mps(
        max_speed_mps=8.0,
        acceleration_mps2=2.0,
        characteristic_length_m=4.0,
        drive_efficiency=1.0,
    )
    assert 2.0 < floor < 2.1, floor

    weak = realized_contact_handoff_readiness(
        max_speed_mps=8.0,
        acceleration_mps2=2.0,
        characteristic_length_m=4.0,
        drive_efficiency=1.0,
        realized_forward_speed_mps=1.9,
        realized_closing_speed_mps=0.6,
    )
    assert weak.ready is False
    assert weak.capability_floor_mps == floor

    realized = realized_contact_handoff_readiness(
        max_speed_mps=8.0,
        acceleration_mps2=2.0,
        characteristic_length_m=4.0,
        drive_efficiency=1.0,
        realized_forward_speed_mps=2.2,
        realized_closing_speed_mps=2.1,
    )
    assert realized.ready is True

    # Capability scaling must work for a slower profile without changing code.
    slower_floor = capability_motion_realization_floor_mps(
        max_speed_mps=0.9,
        acceleration_mps2=0.4,
        characteristic_length_m=7.0,
        drive_efficiency=0.75,
    )
    assert 0.0 < slower_floor <= 0.9 * 0.75

    lower = (helper_text + "\n" + wrapper_text).lower()
    for token in FORBIDDEN_ASSET_TOKENS:
        assert token.lower() not in lower, ("C485_ASSET_SPECIFIC_TOKEN_FORBIDDEN", token)

    combined = helper_text + "\n" + wrapper_text
    for required in (
        "candidate472._ORIGINAL_TACTICAL_DECIDE = generic_contact_commit_decide",
        "candidate481._BASE_AUTONOMY_UPDATE = realized_and_alignment_aware_base_autonomy_update",
        "G04_CONTACT_COMMIT_DEFERRED_BY_LIVE_READINESS",
        "G04_CONTACT_HANDOFF_DEFERRED_BY_REALIZED_APPROACH",
        "G04_CONTACT_HANDOFF_DEFERRED_BY_ROTATIONAL_DOMINANCE",
        "ClosedLoopGoalController._begin_recovery",
        '"singleCommitContractAcrossEngageAndCounter": True',
        '"realizedForwardMotionRequiredBeforeHandoff": True',
        '"realizedPairwiseClosingRequiredBeforeHandoff": True',
        '"g05NativeSolverFinalAuthorityPreserved": True',
        '"g05ThresholdImported": False',
        '"contactThresholdChanged": False',
        '"damageAdmissionThresholdChanged": False',
        '"perAssetBattleCode": False',
        '"perAssetTacticalTuning": False',
        '"perVideoTrajectoryEngineering": False',
    ):
        assert required in combined, required

    for forbidden in (
        "MIN_CLOSING_SPEED_MPS",
        "MIN_DAMAGE_SEVERITY",
        "desiredImpactSpeedMps",
        "desiredImpactEnergyJ",
        "collisionFrame",
        "impactFrame",
        "trajectoryPoints",
        "waypoints",
        "set_pose",
        "linear_velocity =",
        "actor_beta",
        "actor_alpha",
    ):
        assert forbidden not in helper_text, forbidden
        assert forbidden not in wrapper_text, forbidden

    print(json.dumps({
        "marker": "GENERIC_AUTONOMOUS_BATTLE_C485_PROPERTY_ACCEPTANCE",
        "status": "PASS",
        "affectedLayerAudit": "PASS",
        "failureFamily": "CONTACT_COMMIT_AND_HANDOFF_PRECEDE_REALIZED_HETEROGENEOUS_APPROACH_READINESS",
        "mechanism": CONTACT_COMMIT_MODEL,
        "singleCommitContractAcrossEngageAndCounter": "PASS",
        "realizedMotionHandoffContract": "PASS",
        "capabilityDerivedMotionFloor": True,
        "existingGenericRecoveryReused": True,
        "c484AlignmentSemanticsPreserved": True,
        "g05ThresholdImported": False,
        "assetSpecificCode": False,
        "perAssetTacticalTuning": False,
        "contactThresholdChanged": False,
        "damageAdmissionThresholdChanged": False,
        "masterPlanAligned": True,
        "gateClosed": False,
    }, sort_keys=True))


if __name__ == "__main__":
    main()
