#!/usr/bin/env python3
from __future__ import annotations

import ast
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from blender.iss_battle_runtime_engagement_transaction_v1 import (
    ENGAGEMENT_APPROACH_TRANSACTION_MODEL,
    decide_engagement_approach_transaction,
    latest_contact_commit_sample,
)

HELPER = ROOT / "blender" / "iss_battle_runtime_engagement_transaction_v1.py"
WRAPPER = ROOT / "blender" / "run_generic_battle_runtime_v1_candidate480_generic_battle.py"
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

    samples = [
        {"eventId": "evt-a", "frame": 10, "contactCommit": False},
        {"eventId": "evt-b", "frame": 11, "contactCommit": True},
        {"eventId": "evt-a", "frame": 12, "contactCommit": True},
    ]
    latest = latest_contact_commit_sample(samples, "evt-a")
    assert latest is not None and latest["frame"] == 12 and latest["contactCommit"] is True

    start = decide_engagement_approach_transaction(
        frozen_zone=None,
        current_zone="front",
        contact_commit=True,
        event_terminal=False,
        active_handoff=False,
        source_sample_frame=12,
    )
    assert start.hold and start.started and start.frozen_zone == "front"

    # Live nearest-zone selection may change while an approach is committed, but
    # the transaction must retain the semantic label rather than chase it.
    hold = decide_engagement_approach_transaction(
        frozen_zone="front",
        current_zone="right_side",
        contact_commit=True,
        event_terminal=False,
        active_handoff=False,
        source_sample_frame=20,
    )
    assert hold.hold and not hold.started and hold.frozen_zone == "front"

    # The established fresh-handoff live-pair refinement remains later authority.
    refined = decide_engagement_approach_transaction(
        frozen_zone="front",
        current_zone="front_right_wheel",
        contact_commit=True,
        event_terminal=False,
        active_handoff=True,
        source_sample_frame=21,
    )
    assert refined.hold and refined.refined_by_handoff
    assert refined.frozen_zone == "front_right_wheel"

    release = decide_engagement_approach_transaction(
        frozen_zone="front_right_wheel",
        current_zone="front_right_wheel",
        contact_commit=False,
        event_terminal=False,
        active_handoff=False,
        source_sample_frame=30,
    )
    assert not release.hold and release.released and release.frozen_zone is None

    terminal = decide_engagement_approach_transaction(
        frozen_zone="front",
        current_zone="front",
        contact_commit=True,
        event_terminal=True,
        active_handoff=False,
        source_sample_frame=31,
    )
    assert not terminal.hold and terminal.released

    lower = (helper_text + "\n" + wrapper_text).lower()
    for token in FORBIDDEN_ASSET_TOKENS:
        assert token.lower() not in lower, ("C480_ASSET_SPECIFIC_TOKEN_FORBIDDEN", token)

    for required in (
        "GENERIC_APPROACH_SEMANTIC_TRANSACTION_STARTED",
        "GENERIC_APPROACH_SEMANTIC_TRANSACTION_RELEASED",
        "GENERIC_APPROACH_SEMANTIC_TRANSACTION_REFINED_BY_HANDOFF",
        '"semanticWorldPositionRemainsLive": True',
        '"c470FreshHandoffLivePairRefinementPreserved": True',
        '"c474ObbHandoffEligibilityPreserved": True',
        '"g05NativeSolverFinalAuthorityPreserved": True',
        '"assetIdentityBranch": False',
        '"perAssetBattleCode": False',
        '"perAssetTacticalTuning": False',
        '"perVideoTrajectoryEngineering": False',
        '"fixedWorldCoordinates": False',
        '"actorPoseOrVelocityMutation": False',
        '"contactThresholdChanged": False',
        '"damageAdmissionThresholdChanged": False',
    ):
        assert required in wrapper_text, required

    for forbidden in (
        "desiredImpactSpeedMps",
        "desiredImpactEnergyJ",
        "collisionFrame",
        "impactFrame",
        "trajectoryPoints",
        "waypoints",
        "forcedWinner",
        "set_pose",
        "linear_velocity =",
        "MIN_CLOSING_SPEED_MPS =",
        "MIN_IMPULSE_BALANCE_RATIO =",
    ):
        assert forbidden not in helper_text, forbidden
        assert forbidden not in wrapper_text, forbidden

    print(json.dumps({
        "marker": "GENERIC_AUTONOMOUS_BATTLE_C480_PROPERTY_ACCEPTANCE",
        "status": "PASS",
        "affectedLayerAudit": "PASS",
        "failureFamily": "LIVE_SEMANTIC_TARGET_OSCILLATES_WHILE_OBB_HANDOFF_IS_DEFERRED",
        "mechanism": ENGAGEMENT_APPROACH_TRANSACTION_MODEL,
        "semanticLabelFreezeOnly": True,
        "semanticWorldPositionRemainsLive": True,
        "handoffRefinementStillLaterAuthority": True,
        "assetSpecificCode": False,
        "perAssetTacticalTuning": False,
        "thresholdChanged": False,
        "masterPlanAligned": True,
        "gateClosed": False,
    }, sort_keys=True))


if __name__ == "__main__":
    main()
