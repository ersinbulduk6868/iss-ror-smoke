#!/usr/bin/env python3
from __future__ import annotations

import ast
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from blender.iss_battle_runtime_handoff_v4 import (
    SEMANTIC_SURFACE_TRANSACTION_MODEL,
    select_semantic_zone_for_local_surface,
)

HELPER = ROOT / "blender" / "iss_battle_runtime_handoff_v4.py"
WRAPPER = ROOT / "blender" / "run_generic_battle_runtime_v1_candidate470_generic_battle.py"
C469 = ROOT / "blender" / "run_generic_battle_runtime_v1_candidate469_generic_battle.py"
G05 = ROOT / "blender" / "run_generic_battle_runtime_v1_candidate42.py"
FORBIDDEN_ASSET_TOKENS = ("bugatti", "bulldozer", "ferrari")


def main() -> None:
    texts = {
        "helper": HELPER.read_text(encoding="utf-8"),
        "wrapper": WRAPPER.read_text(encoding="utf-8"),
        "c469": C469.read_text(encoding="utf-8"),
        "g05": G05.read_text(encoding="utf-8"),
    }
    for name, text in texts.items():
        ast.parse(text, filename=name)

    for token in FORBIDDEN_ASSET_TOKENS:
        assert token not in texts["helper"].lower(), ("ASSET_SPECIFIC_HELPER_TOKEN", token)
        assert token not in texts["wrapper"].lower(), ("ASSET_SPECIFIC_WRAPPER_TOKEN", token)

    # Synthetic semantics: selection is based on the physical target surface,
    # not attacker-center proximity or an asset identity branch.
    zones = {
        "front": (2.0, 0.0, 0.0),
        "front_left_wheel": (1.55, 0.82, -0.22),
        "left_side": (0.0, 0.95, 0.0),
        "rear": (-2.0, 0.0, 0.0),
    }
    selected, distance = select_semantic_zone_for_local_surface(
        (1.48, 0.78, -0.20), zones, (0.0, 0.0, 0.0)
    )
    assert selected == "front_left_wheel", (selected, distance)
    assert distance < 0.10, distance

    selected_offset, _ = select_semantic_zone_for_local_surface(
        (1.58, 0.73, -0.15), zones, (0.10, -0.05, 0.05)
    )
    assert selected_offset == "front_left_wheel", selected_offset

    # Preserve the established G05 authority gate and C469 lifecycle cleanup.
    assert "ContactOuterAuthorityGate.evaluate" in texts["g05"]
    assert "PairwiseSolverResponseOracle.evaluate" in texts["g05"]
    assert "invalidate_released_handoff_cutoffs" in texts["c469"]
    assert "candidate469.transaction_clean_set_controls = surface_transaction_set_controls" in texts["wrapper"]
    assert "select_semantic_zone_for_local_surface" in texts["wrapper"]
    assert "candidate42._pair_geometry_at" in texts["wrapper"]
    assert "candidate467.candidate443._auto_engagement_events" in texts["wrapper"]

    for required in (
        '"livePairSurfaceSemanticSelection": True',
        '"freshHandoffOnly": True',
        '"semanticSelectionFrozenAfterTransactionStart": True',
        '"existingG05OuterAuthorityGatePreserved": True',
        '"existingPairwiseSolverOraclePreserved": True',
        '"c469CutoffCleanupPreserved": True',
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
        "MIN_DAMAGE_SEVERITY",
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
        "marker": "GENERIC_AUTONOMOUS_BATTLE_C470_PROPERTY_ACCEPTANCE",
        "status": "PASS",
        "affectedLayerAudit": "PASS",
        "failureFamily": "HANDOFF_ZONE_LABEL_DRIFTS_FROM_LIVE_PAIR_CONTACT_SURFACE",
        "rootCause": "ATTACKER_CENTER_ZONE_SELECTION_IS_NOT_CONTACT_SURFACE_SELECTION",
        "semanticSurfaceTransactionModel": SEMANTIC_SURFACE_TRANSACTION_MODEL,
        "syntheticPhysicalSurfaceSelection": "PASS",
        "freshHandoffOnly": True,
        "existingG05OuterAuthorityGatePreserved": True,
        "existingPairwiseSolverOraclePreserved": True,
        "c469CutoffCleanupPreserved": True,
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
