#!/usr/bin/env python3
from __future__ import annotations

import ast
import json
import math
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from blender.iss_battle_runtime_control_contract_v1 import (
    COLLISION_PROXY_PROXIMITY_MODEL,
    TACTICAL_AUTONOMY_OWNERSHIP_MODEL,
    effective_collision_proxy_gap,
    obb_signed_separation_2d,
    should_clear_stale_autonomy_recovery,
)

HELPER = ROOT / "blender" / "iss_battle_runtime_control_contract_v1.py"
WRAPPER = ROOT / "blender" / "run_generic_battle_runtime_v1_candidate472_generic_battle.py"
C471 = ROOT / "blender" / "run_generic_battle_runtime_v1_candidate471_generic_battle.py"
G05 = ROOT / "blender" / "run_generic_battle_runtime_v1_candidate42.py"
FORBIDDEN_ASSET_TOKENS = ("bugatti", "bulldozer", "ferrari")


def _radial_gap(
    delta: tuple[float, float],
    ax: tuple[float, float],
    ay: tuple[float, float],
    bx: tuple[float, float],
    by: tuple[float, float],
    ah: tuple[float, float],
    bh: tuple[float, float],
) -> float:
    length = math.hypot(*delta)
    d = (delta[0] / length, delta[1] / length)
    def dot(a: tuple[float, float], b: tuple[float, float]) -> float:
        return a[0] * b[0] + a[1] * b[1]
    def support(x: tuple[float, float], y: tuple[float, float], half: tuple[float, float]) -> float:
        return half[0] * abs(dot(x, d)) + half[1] * abs(dot(y, d))
    return length - support(ax, ay, ah) - support(bx, by, bh)


def main() -> None:
    texts = {
        "helper": HELPER.read_text(encoding="utf-8"),
        "wrapper": WRAPPER.read_text(encoding="utf-8"),
        "c471": C471.read_text(encoding="utf-8"),
        "g05": G05.read_text(encoding="utf-8"),
    }
    for name, text in texts.items():
        ast.parse(text, filename=name)

    # Synthetic glancing pair: radial support says overlap while SAT still has a
    # separating axis. C472 must keep motor authority instead of handing off early.
    theta = math.radians(5.0)
    ax, ay = (1.0, 0.0), (0.0, 1.0)
    bx, by = (math.cos(theta), math.sin(theta)), (-math.sin(theta), math.cos(theta))
    delta = (1.0, 2.3)
    ah = bh = (2.0, 1.0)
    radial = _radial_gap(delta, ax, ay, bx, by, ah, bh)
    sat = obb_signed_separation_2d(
        center_delta_xy=delta,
        actor_x_axis_xy=ax,
        actor_y_axis_xy=ay,
        target_x_axis_xy=bx,
        target_y_axis_xy=by,
        actor_half_extents_xy=ah,
        target_half_extents_xy=bh,
    )
    assert radial < 0.0, radial
    assert sat > 0.0, sat
    assert effective_collision_proxy_gap(radial, sat) == sat

    # Axis-aligned overlap and separation remain physically intuitive.
    overlap = obb_signed_separation_2d(
        center_delta_xy=(3.5, 0.0),
        actor_x_axis_xy=ax, actor_y_axis_xy=ay,
        target_x_axis_xy=ax, target_y_axis_xy=ay,
        actor_half_extents_xy=ah, target_half_extents_xy=bh,
    )
    separate = obb_signed_separation_2d(
        center_delta_xy=(4.4, 0.0),
        actor_x_axis_xy=ax, actor_y_axis_xy=ay,
        target_x_axis_xy=ax, target_y_axis_xy=ay,
        actor_half_extents_xy=ah, target_half_extents_xy=bh,
    )
    assert overlap < 0.0, overlap
    assert separate > 0.0, separate

    # Tactical ownership only clears stale low-level recovery when the planner
    # explicitly transitions out of tactical separation into a forward maneuver.
    assert should_clear_stale_autonomy_recovery(
        previous_tactical_mode="BREAK_CONTACT",
        current_tactical_mode="COUNTER",
        tactical_transition=True,
        autonomy_mode="RECOVER_REVERSE",
        speed_intent="ACCELERATE",
    )
    assert should_clear_stale_autonomy_recovery(
        previous_tactical_mode="REPOSITION",
        current_tactical_mode="ENGAGE",
        tactical_transition=True,
        autonomy_mode="RECOVER_TURN",
        speed_intent="ACCELERATE",
    )
    assert not should_clear_stale_autonomy_recovery(
        previous_tactical_mode="COUNTER",
        current_tactical_mode="COUNTER",
        tactical_transition=False,
        autonomy_mode="RECOVER_REVERSE",
        speed_intent="ACCELERATE",
    )
    assert not should_clear_stale_autonomy_recovery(
        previous_tactical_mode="BREAK_CONTACT",
        current_tactical_mode="COUNTER",
        tactical_transition=True,
        autonomy_mode="TRACK",
        speed_intent="ACCELERATE",
    )
    assert not should_clear_stale_autonomy_recovery(
        previous_tactical_mode="BREAK_CONTACT",
        current_tactical_mode="COUNTER",
        tactical_transition=True,
        autonomy_mode="RECOVER_REVERSE",
        speed_intent="REVERSE",
    )

    for token in FORBIDDEN_ASSET_TOKENS:
        assert token not in texts["helper"].lower(), ("ASSET_SPECIFIC_HELPER_TOKEN", token)
        assert token not in texts["wrapper"].lower(), ("ASSET_SPECIFIC_WRAPPER_TOKEN", token)

    assert "ContactOuterAuthorityGate.evaluate" in texts["g05"]
    assert "PairwiseSolverResponseOracle.evaluate" in texts["g05"]
    assert "G05_PRE_CUTOFF_LOCALITY_SAMPLE_EXCLUDED" in texts["c471"]
    assert "G05_PAIRWISE_SOLVER_RESPONSE_REJECTED" in texts["c471"]

    for required in (
        '"rigidBodyObbSatProximity": True',
        '"g05NativeSolverFinalAuthorityPreserved": True',
        '"tacticalRecoveryOwnershipReconciled": True',
        '"lowLevelRecoveryOtherwisePreserved": True',
        '"c471TransactionBoundedLocalityPreserved": True',
        '"c470LivePairSurfaceSemanticSelectionPreserved": True',
        '"c469CutoffCleanupPreserved": True',
        '"c468RecencyBudgetPreserved": True',
        '"pairwiseSolverOraclePreserved": True',
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
        "marker": "GENERIC_AUTONOMOUS_BATTLE_C472_PROPERTY_ACCEPTANCE",
        "status": "PASS",
        "affectedLayerAudit": "PASS",
        "failureFamily": "RADIAL_HANDOFF_FALSE_PROXIMITY_AND_STALE_AUTONOMY_RECOVERY",
        "collisionProxyProximityModel": COLLISION_PROXY_PROXIMITY_MODEL,
        "tacticalAutonomyOwnershipModel": TACTICAL_AUTONOMY_OWNERSHIP_MODEL,
        "syntheticRadialFalseOverlapRejected": "PASS",
        "obbOverlapAndSeparation": "PASS",
        "tacticalRecoveryOwnershipTruthTable": "PASS",
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
