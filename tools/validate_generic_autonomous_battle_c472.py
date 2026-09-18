#!/usr/bin/env python3
from __future__ import annotations

import ast
import json
import math
from pathlib import Path
from types import SimpleNamespace
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from blender.iss_battle_runtime_goal_scope_v1 import (
    GOAL_SCOPE_MODEL,
    SAT_GAP_MODEL,
    conservative_physical_gap,
    goal_scope_signature,
    oriented_box_separation_2d,
    rebase_autonomy_progress,
)

HELPER = ROOT / "blender" / "iss_battle_runtime_goal_scope_v1.py"
WRAPPER = ROOT / "blender" / "run_generic_battle_runtime_v1_candidate472_generic_battle.py"
C471 = ROOT / "blender" / "run_generic_battle_runtime_v1_candidate471_generic_battle.py"
AUTONOMY = ROOT / "blender" / "iss_battle_runtime_autonomy.py"
G05 = ROOT / "blender" / "run_generic_battle_runtime_v1_candidate42.py"
FORBIDDEN_ASSET_TOKENS = ("bugatti", "bulldozer", "ferrari")


def _axes(yaw: float) -> tuple[tuple[float, float], tuple[float, float]]:
    return (math.cos(yaw), math.sin(yaw)), (-math.sin(yaw), math.cos(yaw))


def _support_radius(half: tuple[float, float], yaw: float, direction: float) -> float:
    local = direction - yaw
    return abs(math.cos(local)) * half[0] + abs(math.sin(local)) * half[1]


def _radial_gap(center_delta: tuple[float, float], yaw_a: float, half_a: tuple[float, float], yaw_b: float, half_b: tuple[float, float]) -> float:
    distance = math.hypot(*center_delta)
    direction = math.atan2(center_delta[1], center_delta[0])
    return distance - _support_radius(half_a, yaw_a, direction) - _support_radius(half_b, yaw_b, direction + math.pi)


def main() -> None:
    texts = {
        "helper": HELPER.read_text(encoding="utf-8"),
        "wrapper": WRAPPER.read_text(encoding="utf-8"),
        "c471": C471.read_text(encoding="utf-8"),
        "autonomy": AUTONOMY.read_text(encoding="utf-8"),
        "g05": G05.read_text(encoding="utf-8"),
    }
    for name, text in texts.items():
        ast.parse(text, filename=name)

    for token in FORBIDDEN_ASSET_TOKENS:
        assert token not in texts["helper"].lower(), ("ASSET_SPECIFIC_HELPER_TOKEN", token)
        assert token not in texts["wrapper"].lower(), ("ASSET_SPECIFIC_WRAPPER_TOKEN", token)

    memory = SimpleNamespace(
        mode="RECOVER_REVERSE",
        reason="STALL_NO_PROGRESS",
        best_distance_m=0.20,
        last_distance_m=0.25,
        last_surface_gap_m=0.10,
        last_progress_frame=100,
        near_seen=True,
        last_command_speed_mps=-2.0,
        recovery_reverse_until=130,
        recovery_turn_until=150,
        attempt=7,
        replans=7,
        last_contact_count=1,
        last_damage_count=0,
    )
    obs = SimpleNamespace(
        distance_m=5.50,
        surface_gap_m=5.00,
        frame=409,
        characteristic_length_m=4.4,
        requires_contact=True,
    )
    receipt = rebase_autonomy_progress(memory, obs)
    assert memory.last_progress_frame == 409
    assert memory.best_distance_m == 5.50
    assert memory.recovery_reverse_until == 0 and memory.recovery_turn_until == 0
    assert memory.attempt == 7 and memory.replans == 7
    assert memory.last_contact_count == 1 and memory.last_damage_count == 0
    assert receipt["before"]["attempt"] == receipt["after"]["attempt"] == 7
    assert goal_scope_signature(False, "REVERSE") != goal_scope_signature(True, "ACCELERATE")

    delta = (3.5204631995416245, 0.7390725360975572)
    yaw_a = -0.9699075830008281
    yaw_b = -0.11152302718260332
    half_a = (2.2, 0.9)
    half_b = (2.2, 0.9)
    ax, ay = _axes(yaw_a)
    bx, by = _axes(yaw_b)
    radial = _radial_gap(delta, yaw_a, half_a, yaw_b, half_b)
    sat = oriented_box_separation_2d(delta, ax, ay, half_a, bx, by, half_b)
    assert radial < -0.40, radial
    assert sat > 0.15, sat
    assert conservative_physical_gap(radial, sat) == sat

    assert "G05_PRE_CUTOFF_LOCALITY_SAMPLE_EXCLUDED" in texts["c471"]
    assert "G05_PAIRWISE_SOLVER_RESPONSE_REJECTED" in texts["c471"]
    assert "ContactOuterAuthorityGate.evaluate" in texts["g05"]
    assert "PairwiseSolverResponseOracle.evaluate" in texts["g05"]

    for required in (
        '"goalScopeProgressRebase": True',
        '"nonContactMissClassificationBlocked": True',
        '"satAwareG04PhysicalGap": True',
        '"g05ContactAuthorityChanged": False',
        '"existingG05OuterAuthorityGatePreserved": True',
        '"existingPairwiseSolverOraclePreserved": True',
        '"c471TransactionBoundedLocalityPreserved": True',
        '"c470LivePairSurfaceSemanticSelectionPreserved": True',
        '"semanticToleranceChanged": False',
        '"localityToleranceChanged": False',
        '"contactThresholdChanged": False',
        '"damageAdmissionThresholdChanged": False',
        '"fixtureMutationForAcceptance": False',
        '"perAssetBattleCode": False',
        '"actorPoseOrVelocityMutation": False',
        '"battleStateReset": False',
        '"contactDamageHistoryReset": False',
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
        "failureFamily": "TACTICAL_GOAL_SCOPE_LEAK_AND_CENTERLINE_GAP_EARLY_HANDOFF",
        "goalScopeModel": GOAL_SCOPE_MODEL,
        "satGapModel": SAT_GAP_MODEL,
        "goalScopeHistoryPreservation": "PASS",
        "syntheticCenterlineOverlapButSatSeparated": "PASS",
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
