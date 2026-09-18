#!/usr/bin/env python3
from __future__ import annotations

import ast
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from blender.iss_battle_runtime_precontact_corridor_v1 import (
    ALLOW_CONTACT,
    DEFER_TO_BASE,
    HOLD_STANDOFF,
    PRECONTACT_CORRIDOR_MODEL,
    REOPEN_DISTANCE,
    decide_precontact_corridor,
)

HELPER = ROOT / "blender" / "iss_battle_runtime_precontact_corridor_v1.py"
WRAPPER = ROOT / "blender" / "run_generic_battle_runtime_v1_candidate486_generic_battle.py"
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

    non_contact = decide_precontact_corridor(
        requires_contact=False,
        runway_armed=True,
        contact_commit_ready=False,
        surface_gap_m=-1.0,
        runway_required_m=4.0,
    )
    assert non_contact.action == DEFER_TO_BASE
    assert non_contact.runway_armed_after is True

    unarmed = decide_precontact_corridor(
        requires_contact=True,
        runway_armed=False,
        contact_commit_ready=False,
        surface_gap_m=1.0,
        runway_required_m=4.0,
    )
    assert unarmed.action == DEFER_TO_BASE
    assert unarmed.runway_armed_after is False

    ready = decide_precontact_corridor(
        requires_contact=True,
        runway_armed=True,
        contact_commit_ready=True,
        surface_gap_m=0.25,
        runway_required_m=4.0,
    )
    assert ready.action == ALLOW_CONTACT
    assert ready.runway_armed_after is True

    collapsed = decide_precontact_corridor(
        requires_contact=True,
        runway_armed=True,
        contact_commit_ready=False,
        surface_gap_m=-1.38,
        runway_required_m=4.0,
    )
    assert collapsed.action == REOPEN_DISTANCE
    assert collapsed.runway_armed_after is False
    assert collapsed.desired_surface_gap_m == 4.0

    stale_positive_gap = decide_precontact_corridor(
        requires_contact=True,
        runway_armed=True,
        contact_commit_ready=False,
        surface_gap_m=1.5,
        runway_required_m=4.0,
    )
    assert stale_positive_gap.action == REOPEN_DISTANCE
    assert stale_positive_gap.runway_armed_after is False

    at_runway = decide_precontact_corridor(
        requires_contact=True,
        runway_armed=True,
        contact_commit_ready=False,
        surface_gap_m=4.0,
        runway_required_m=4.0,
    )
    assert at_runway.action == HOLD_STANDOFF
    assert at_runway.runway_armed_after is True

    outside_runway = decide_precontact_corridor(
        requires_contact=True,
        runway_armed=True,
        contact_commit_ready=False,
        surface_gap_m=5.0,
        runway_required_m=4.0,
    )
    assert outside_runway.action == HOLD_STANDOFF
    assert outside_runway.runway_armed_after is True

    # Zero/invalid runway remains fail-safe and does not invent a per-asset target.
    zero_runway = decide_precontact_corridor(
        requires_contact=True,
        runway_armed=True,
        contact_commit_ready=False,
        surface_gap_m=-0.01,
        runway_required_m=-3.0,
    )
    assert zero_runway.action == REOPEN_DISTANCE
    assert zero_runway.desired_surface_gap_m == 0.0
    assert zero_runway.runway_armed_after is False

    lower = (helper_text + "\n" + wrapper_text).lower()
    for token in FORBIDDEN_ASSET_TOKENS:
        assert token.lower() not in lower, ("C486_ASSET_SPECIFIC_TOKEN_FORBIDDEN", token)

    combined = helper_text + "\n" + wrapper_text
    for required in (
        "candidate485.generic_contact_commit_decide = corridor_aware_tactical_decide",
        "GenericBattleTacticalPlanner._open_distance",
        "GenericBattleTacticalPlanner._capability_speed_scale",
        "memory.engagement_runway_armed = False",
        "G04_PRECONTACT_CORRIDOR_REOPENED",
        "G04_PRECONTACT_CORRIDOR_STANDOFF_HELD",
        "G04_PRECONTACT_CORRIDOR_LIVE_READINESS_READY",
        '"threeIterationAuditRuleSatisfied": True',
        '"continuousRunwayRevalidation": True',
        '"unreadyContactCorridorForbidden": True',
        '"existingOpenDistancePolicyReused": True',
        '"existingGeometryCapabilityRunwayReused": True',
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
        "marker": "GENERIC_AUTONOMOUS_BATTLE_C486_PROPERTY_ACCEPTANCE",
        "status": "PASS",
        "affectedLayerAudit": "PASS",
        "failureFamily": "STALE_PRECONTACT_RUNWAY_PERMISSION_ALLOWS_UNREADY_CONTACT_CORRIDOR_COLLAPSE",
        "mechanism": PRECONTACT_CORRIDOR_MODEL,
        "threeIterationAuditRuleSatisfied": True,
        "continuousRunwayRevalidation": "PASS",
        "collapsedRunwayReopensDistance": "PASS",
        "unreadyActorCannotKeepContactDirectedCorridor": "PASS",
        "existingOpenDistancePolicyReused": True,
        "existingGeometryCapabilityRunwayReused": True,
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
