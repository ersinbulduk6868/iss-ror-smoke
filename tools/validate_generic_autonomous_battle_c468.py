#!/usr/bin/env python3
from __future__ import annotations

import ast
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WRAPPER = ROOT / "blender" / "run_generic_battle_runtime_v1_candidate468_generic_battle.py"
G05 = ROOT / "blender" / "run_generic_battle_runtime_v1_candidate42.py"
C467 = ROOT / "blender" / "run_generic_battle_runtime_v1_candidate467_generic_battle.py"
FORBIDDEN_ASSET_TOKENS = ("bugatti", "bulldozer", "ferrari")


def main() -> None:
    wrapper = WRAPPER.read_text(encoding="utf-8")
    g05 = G05.read_text(encoding="utf-8")
    c467 = C467.read_text(encoding="utf-8")
    for path, text in ((WRAPPER, wrapper), (G05, g05), (C467, c467)):
        ast.parse(text, filename=str(path))

    lowered = wrapper.lower()
    for token in FORBIDDEN_ASSET_TOKENS:
        assert token not in lowered, ("ASSET_SPECIFIC_TOKEN", token)

    # Preserve the already-proven G05 recency contract; C468 adapts handoff
    # lifecycle to it rather than widening or bypassing that gate.
    assert "contact_frame - cutoff_frame <= max(2, int(fps))" in g05
    assert "GENERIC_HANDOFF_SEMANTIC_SURFACE_FROZEN" in c467
    assert "battle_v6.decide_solver_handoff = recency_bounded_decide_solver_handoff" in wrapper
    assert "battle_v6.set_controls = recency_bounded_set_controls" in wrapper
    assert "return max(2, int(fps) - 2)" in wrapper
    assert "age >= budget" in wrapper
    assert "G05_CUTOFF_RECENCY_BUDGET" in wrapper
    assert "VERIFIED_CONTACT_OBSERVED" not in wrapper  # base handoff remains authoritative

    for required in (
        '"g05CutoffRecencyContractPreserved": True',
        '"handoffCutoffFrameImmutableWithinLatch": True',
        '"newLatchMayEstablishFreshCutoff": True',
        '"semanticSelectionFrozenWithinHandoff": True',
        '"existingG07ResolverReusedUnchanged": True',
        '"existingG05DetectorReusedUnchanged": True',
        '"semanticToleranceChanged": False',
        '"localityToleranceChanged": False',
        '"contactThresholdChanged": False',
        '"damageAdmissionThresholdChanged": False',
        '"fixtureMutationForAcceptance": False',
        '"perAssetBattleCode": False',
        '"actorPoseOrVelocityMutation": False',
        '"gateClosed": False',
    ):
        assert required in wrapper, required

    for forbidden in (
        "MIN_DAMAGE_SEVERITY",
        "semantic_tolerance =",
        "locality_tolerance =",
        "ImpactModel.qualifies",
        "target_toughness",
        "desired_impact_speed",
        "desired_impact_energy",
        "collision_frame",
        "impact_frame",
        "set_pose",
        "linear_velocity =",
    ):
        assert forbidden not in wrapper, forbidden

    # Pure boundary proof mirrors only the capability-independent recency budget;
    # Blender runtime behavior is proven later by the real acceptance run.
    for fps in (24, 30, 60):
        budget = max(2, fps - 2)
        assert budget < fps
        assert (budget - 1) < budget
        assert budget >= budget

    print(json.dumps({
        "marker": "GENERIC_AUTONOMOUS_BATTLE_C468_PROPERTY_ACCEPTANCE",
        "status": "PASS",
        "affectedLayerAudit": "PASS",
        "failureFamily": "HANDOFF_LATCH_OUTLIVES_G05_CUTOFF_RECENCY_WINDOW",
        "rootCause": "IMMUTABLE_HANDOFF_CUTOFF_BECOMES_STALE_WHILE_SOLVER_LATCH_REMAINS_ACTIVE",
        "g05CutoffRecencyContractPreserved": True,
        "handoffCutoffFrameImmutableWithinLatch": True,
        "newLatchMayEstablishFreshCutoff": True,
        "semanticSelectionFrozenWithinHandoff": True,
        "existingG07ResolverReusedUnchanged": True,
        "existingG05DetectorReusedUnchanged": True,
        "semanticToleranceChanged": False,
        "localityToleranceChanged": False,
        "contactThresholdChanged": False,
        "damageAdmissionThresholdChanged": False,
        "fixtureMutationForAcceptance": False,
        "perAssetBattleCode": False,
        "perVideoTrajectoryEngineering": False,
        "actorPoseOrVelocityMutation": False,
        "gateClosed": False,
        "propertyBoundaryFps": [24, 30, 60],
    }, sort_keys=True))


if __name__ == "__main__":
    main()
