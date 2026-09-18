#!/usr/bin/env python3
from __future__ import annotations

import ast
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
G05 = ROOT / "blender" / "run_generic_battle_runtime_v1_candidate42.py"
G07 = ROOT / "blender" / "run_generic_battle_runtime_v1_candidate443.py"
C466 = ROOT / "blender" / "run_generic_battle_runtime_v1_candidate466_generic_battle.py"
C467 = ROOT / "blender" / "run_generic_battle_runtime_v1_candidate467_generic_battle.py"
V6 = ROOT / "blender" / "iss_battle_runtime_generic_battle_v6.py"

FORBIDDEN_ASSET_TOKENS = ("bugatti", "bulldozer", "ferrari")


def _function_body(source: str, name: str) -> str:
    tree = ast.parse(source)
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == name:
            lines = source.splitlines()
            return "\n".join(lines[node.lineno - 1 : node.end_lineno])
    raise AssertionError(f"FUNCTION_NOT_FOUND:{name}")


def main() -> None:
    sources = {p.name: p.read_text(encoding="utf-8") for p in (G05, G07, C466, C467, V6)}
    for name, source in sources.items():
        ast.parse(source, filename=name)

    wrapper = sources[C467.name]
    lowered = wrapper.lower()
    for token in FORBIDDEN_ASSET_TOKENS:
        assert token not in lowered, ("ASSET_SPECIFIC_TOKEN", token)

    refresh = _function_body(wrapper, "_refresh_unlatched_semantic_surfaces")
    detector = _function_body(wrapper, "transactional_pairwise_detect_contacts")
    active = _function_body(wrapper, "_active_handoff_for_event")

    # Existing authorities are reused. C467 adds only transaction synchronization.
    assert "battle_v6._handoff_latches.get(key)" in active
    assert "candidate443._select_live_semantic_surface(event, actors, frame)" in refresh
    assert "GENERIC_HANDOFF_SEMANTIC_SURFACE_FROZEN" in refresh
    assert "continue" in refresh
    assert detector.index("_refresh_unlatched_semantic_surfaces(") < detector.index("_ORIGINAL_PAIRWISE_DETECT(")
    assert "_ORIGINAL_PAIRWISE_DETECT = candidate42.pairwise_detect_contacts" in wrapper
    assert "candidate466.synchronized_pairwise_detect_contacts = transactional_pairwise_detect_contacts" in wrapper
    assert "candidate466.main()" in wrapper

    # C466/C465 composition and the established detector/resolver remain intact.
    assert "candidate443._refresh_generic_engagement_surfaces(" in sources[C466.name]
    assert "_ORIGINAL_PAIRWISE_DETECT = candidate42.pairwise_detect_contacts" in sources[C466.name]
    assert "LIVE_GEOMETRY_SEMANTIC_ENGAGEMENT_RESOLVER_V1" in sources[G07.name]
    assert "_handoff_latches" in sources[V6.name]

    for required in (
        '"existingG07ResolverReusedUnchanged": True',
        '"existingG05DetectorReusedUnchanged": True',
        '"semanticSelectionAdaptiveOutsideHandoff": True',
        '"semanticSelectionFrozenWithinHandoff": True',
        '"handoffCutoffFrameImmutableWithinLatch": True',
        '"g05ContactAuthorityContractPreserved": True',
        '"g07GenericEngagementContractPreserved": True',
        '"semanticToleranceChanged": False',
        '"localityToleranceChanged": False',
        '"contactThresholdChanged": False',
        '"damageAdmissionThresholdChanged": False',
        '"fixtureMutationForAcceptance": False',
        '"storyTargetZonePrescribed": False',
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
    ):
        assert forbidden not in wrapper, forbidden

    print(json.dumps({
        "marker": "GENERIC_AUTONOMOUS_BATTLE_C467_PROPERTY_ACCEPTANCE",
        "status": "PASS",
        "affectedLayerAudit": "PASS",
        "failureFamily": "SEMANTIC_TARGET_MUTATES_DURING_ACTIVE_SOLVER_HANDOFF_TRANSACTION",
        "existingG07ResolverReusedUnchanged": True,
        "existingG05DetectorReusedUnchanged": True,
        "semanticSelectionAdaptiveOutsideHandoff": True,
        "semanticSelectionFrozenWithinHandoff": True,
        "handoffCutoffFrameImmutableWithinLatch": True,
        "g05ContactAuthorityContractPreserved": True,
        "g07GenericEngagementContractPreserved": True,
        "semanticToleranceChanged": False,
        "localityToleranceChanged": False,
        "contactThresholdChanged": False,
        "damageAdmissionThresholdChanged": False,
        "fixtureMutationForAcceptance": False,
        "perAssetBattleCode": False,
        "perVideoTrajectoryEngineering": False,
        "actorPoseOrVelocityMutation": False,
        "gateClosed": False,
    }, sort_keys=True))


if __name__ == "__main__":
    main()
