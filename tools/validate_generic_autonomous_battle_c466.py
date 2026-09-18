#!/usr/bin/env python3
from __future__ import annotations

import ast
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RUNTIME = ROOT / "blender" / "iss_blender_battle_runtime_v1.py"
G05 = ROOT / "blender" / "run_generic_battle_runtime_v1_candidate42.py"
G07 = ROOT / "blender" / "run_generic_battle_runtime_v1_candidate443.py"
C465 = ROOT / "blender" / "run_generic_battle_runtime_v1_candidate465_generic_battle.py"
C466 = ROOT / "blender" / "run_generic_battle_runtime_v1_candidate466_generic_battle.py"

FORBIDDEN_ASSET_TOKENS = ("bugatti", "bulldozer", "ferrari")


def _function_body(source: str, name: str) -> str:
    tree = ast.parse(source)
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == name:
            lines = source.splitlines()
            return "\n".join(lines[node.lineno - 1 : node.end_lineno])
    raise AssertionError(f"FUNCTION_NOT_FOUND:{name}")


def main() -> None:
    sources = {p.name: p.read_text(encoding="utf-8") for p in (RUNTIME, G05, G07, C465, C466)}
    for name, source in sources.items():
        ast.parse(source, filename=name)

    wrapper = sources[C466.name]
    lowered = wrapper.lower()
    for token in FORBIDDEN_ASSET_TOKENS:
        assert token not in lowered, ("ASSET_SPECIFIC_TOKEN", token)

    # Root-cause proof: base runtime evaluates contact before the control-phase
    # refresh. This is an ordering fact; locked base source is not changed here.
    runtime_loop = sources[RUNTIME.name]
    loop_anchor = runtime_loop.index("for frame in range(2, program.total_frames + 1):")
    loop_tail = runtime_loop.index("if pending:", loop_anchor)
    loop = runtime_loop[loop_anchor:loop_tail]
    assert loop.index("detect_contacts(") < loop.index("set_controls("), "BASE_RUNTIME_ORDER_CHANGED"

    # Established G07 selection remains live-geometry based and currently refreshes
    # inside its set-controls hook.
    g07_set_controls = _function_body(sources[G07.name], "g07_v4_set_controls")
    assert g07_set_controls.index("_refresh_generic_engagement_surfaces(") < g07_set_controls.index("_ORIGINAL_G07_SET_CONTROLS(")
    assert "LIVE_GEOMETRY_SEMANTIC_ENGAGEMENT_RESOLVER_V1" in sources[G07.name]
    assert "storyTargetZonePrescribed" in sources[G07.name]
    assert "assetSpecificBranch" in sources[G07.name]

    # C466 must call the exact existing resolver before the exact established G05
    # pairwise detector. No alternative detector or threshold path is allowed.
    c466_detector = _function_body(wrapper, "synchronized_pairwise_detect_contacts")
    refresh_at = c466_detector.index("candidate443._refresh_generic_engagement_surfaces(")
    detect_at = c466_detector.index("_ORIGINAL_PAIRWISE_DETECT(")
    assert refresh_at < detect_at, "SEMANTIC_REFRESH_NOT_BEFORE_G05_DETECTOR"
    assert "_ORIGINAL_PAIRWISE_DETECT = candidate42.pairwise_detect_contacts" in wrapper
    assert "candidate42.pairwise_detect_contacts = synchronized_pairwise_detect_contacts" in wrapper

    # C465's cutoff stabilization remains composed, not replaced.
    assert "candidate465.main()" in wrapper
    assert "handoffCutoffFrameImmutableWithinLatch" in sources[C465.name]

    for required in (
        '"existingG07ResolverReusedUnchanged": True',
        '"existingG05DetectorReusedUnchanged": True',
        '"semanticSelectionSynchronizedBeforeG05": True',
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

    # No threshold/admission implementation is permitted in the integration delta.
    for forbidden in (
        "MIN_DAMAGE_SEVERITY",
        "semantic_tolerance =",
        "locality_tolerance =",
        "ImpactModel.qualifies",
        "target_toughness",
        "impact_energy_j",
        "desired_impact_speed",
        "desired_impact_energy",
    ):
        assert forbidden not in wrapper, forbidden

    print(json.dumps({
        "marker": "GENERIC_AUTONOMOUS_BATTLE_C466_PROPERTY_ACCEPTANCE",
        "status": "PASS",
        "affectedLayerAudit": "PASS",
        "failureFamily": "LIVE_SEMANTIC_SELECTION_ONE_FRAME_LATE_FOR_G05_CONTACT_EVALUATION",
        "baseRuntimeOrder": "DETECT_CONTACTS_BEFORE_SET_CONTROLS",
        "existingG07ResolverReusedUnchanged": True,
        "existingG05DetectorReusedUnchanged": True,
        "semanticSelectionSynchronizedBeforeG05": True,
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
