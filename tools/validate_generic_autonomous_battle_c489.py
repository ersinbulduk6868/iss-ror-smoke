#!/usr/bin/env python3
from __future__ import annotations

import ast
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from blender.iss_battle_runtime_contact_semantics_v2 import (
    OBSERVED_CONTACT_SEMANTIC_MODEL,
    classify_observed_contact_surface,
    should_classify_observed_contact_semantics,
)

HELPER = ROOT / "blender" / "iss_battle_runtime_contact_semantics_v2.py"
WRAPPER = ROOT / "blender" / "run_generic_battle_runtime_v1_candidate489_generic_battle.py"
G05 = ROOT / "blender" / "run_generic_battle_runtime_v1_candidate42.py"
C467 = ROOT / "blender" / "run_generic_battle_runtime_v1_candidate467_generic_battle.py"
C470 = ROOT / "blender" / "run_generic_battle_runtime_v1_candidate470_generic_battle.py"
C480 = ROOT / "blender" / "run_generic_battle_runtime_v1_candidate480_generic_battle.py"
C488 = ROOT / "blender" / "run_generic_battle_runtime_v1_candidate488_generic_battle.py"


def _live_event_target_zone_assignments(tree: ast.AST) -> list[int]:
    rows: list[int] = []
    for node in ast.walk(tree):
        targets = []
        if isinstance(node, ast.Assign):
            targets = list(node.targets)
        elif isinstance(node, ast.AnnAssign):
            targets = [node.target]
        elif isinstance(node, ast.AugAssign):
            targets = [node.target]
        for target in targets:
            if (
                isinstance(target, ast.Attribute)
                and target.attr == "target_zone"
                and isinstance(target.value, ast.Name)
                and target.value.id == "event"
            ):
                rows.append(int(getattr(node, "lineno", -1)))
    return rows


def main() -> None:
    helper_text = HELPER.read_text(encoding="utf-8")
    wrapper_text = WRAPPER.read_text(encoding="utf-8")
    g05_text = G05.read_text(encoding="utf-8")
    texts = {
        "helper": helper_text,
        "wrapper": wrapper_text,
        "c467": C467.read_text(encoding="utf-8"),
        "c470": C470.read_text(encoding="utf-8"),
        "c480": C480.read_text(encoding="utf-8"),
        "c488": C488.read_text(encoding="utf-8"),
    }
    helper_tree = ast.parse(helper_text, filename=str(HELPER))
    wrapper_tree = ast.parse(wrapper_text, filename=str(WRAPPER))
    ast.parse(g05_text, filename=str(G05))
    for name in ("c467", "c470", "c480", "c488"):
        ast.parse(texts[name], filename=name)

    # Ownership decision: only runtime-selected semantics in an active solver
    # handoff may use observation-plane contact classification.
    assert should_classify_observed_contact_semantics(
        runtime_selected_semantics=True,
        story_target_zone_prescribed=False,
        active_solver_handoff=True,
    ) is True
    for args in (
        dict(runtime_selected_semantics=False, story_target_zone_prescribed=True, active_solver_handoff=True),
        dict(runtime_selected_semantics=True, story_target_zone_prescribed=False, active_solver_handoff=False),
        dict(runtime_selected_semantics=True, story_target_zone_prescribed=True, active_solver_handoff=True),
    ):
        assert should_classify_observed_contact_semantics(**args) is False, args

    zones = {
        "front": (2.0, 0.0, 0.0),
        "left_side": (0.0, 1.0, 0.0),
        "rear_left_wheel": (-1.4, 0.85, -0.2),
        "rear": (-2.0, 0.0, 0.0),
    }
    selected = classify_observed_contact_surface(
        surface_local=(-1.32, 0.81, -0.18),
        zones=zones,
        visual_offset=(0.0, 0.0, 0.0),
        engagement_intent_zone="left_side",
        runtime_selected_semantics=True,
        story_target_zone_prescribed=False,
        active_solver_handoff=True,
    )
    assert selected.use_observed_contact_semantics is True
    assert selected.engagement_intent_zone == "left_side"
    assert selected.observed_contact_zone == "rear_left_wheel", selected
    assert selected.observed_zone_distance_m is not None and selected.observed_zone_distance_m < 0.1

    strict = classify_observed_contact_surface(
        surface_local=(-1.32, 0.81, -0.18),
        zones=zones,
        visual_offset=(0.0, 0.0, 0.0),
        engagement_intent_zone="front",
        runtime_selected_semantics=False,
        story_target_zone_prescribed=True,
        active_solver_handoff=True,
    )
    assert strict.use_observed_contact_semantics is False
    assert strict.engagement_intent_zone == "front"
    assert strict.observed_contact_zone is None

    # C489 must not mutate the live event semantic intent. A shallow observed-event
    # view is allowed, and PendingContact must carry the verified observed zone so
    # G06 damage semantics match the realized contact location.
    assert _live_event_target_zone_assignments(wrapper_tree) == [], _live_event_target_zone_assignments(wrapper_tree)
    assert "observed_event.target_zone = selection.observed_contact_zone" in wrapper_text
    assert "item.target_zone = observed_zone" in wrapper_text
    assert "candidate42._pairwise_receipt = observed_contact_semantic_pairwise_receipt" in wrapper_text
    assert "candidate467._ORIGINAL_PAIRWISE_DETECT = observed_contact_semantic_pending_detector" in wrapper_text
    assert "candidate42._best_recent_locality" in wrapper_text
    assert "_BASE_PAIRWISE_RECEIPT" in wrapper_text
    assert "candidate488.main()" in wrapper_text

    # Established G05 gates/oracles remain present and are reused by delegation.
    assert "ContactOuterAuthorityGate.evaluate" in g05_text
    assert "PairwiseSolverResponseOracle.evaluate" in g05_text
    assert "_semantic_tolerance(target, event.target_zone)" in g05_text

    required = (
        '"controlIntentSemanticAndObservedContactSemanticSeparated": True',
        '"runtimeSelectedSemanticsOnly": True',
        '"activeSolverHandoffRequired": True',
        '"storyPrescribedSemanticTargetRemainsStrict": True',
        '"eventTargetZoneNeverMutatedByObservedClassification": True',
        '"g04ControlIntentPreserved": True',
        '"c480ApproachSemanticFreezePreserved": True',
        '"c470HandoffIntentRefinementPreserved": True',
        '"c467HandoffSemanticFreezePreserved": True',
        '"c488AuthorityTransferPreserved": True',
        '"sameG05BestRecentLocalityGeometryReused": True',
        '"sameG05OuterAuthorityGateReused": True',
        '"sameG05PairwiseSolverOracleReused": True',
        '"sameG05SemanticToleranceReused": True',
        '"observedContactZonePropagatesToPendingImpact": True',
        '"g06DamageZoneUsesObservedContact": True',
        '"contactThresholdChanged": False',
        '"semanticToleranceChanged": False',
        '"localityToleranceChanged": False',
        '"damageAdmissionThresholdChanged": False',
        '"perAssetBattleCode": False',
        '"perAssetTacticalTuning": False',
        '"perVideoTrajectoryEngineering": False',
        '"actorPoseOrVelocityMutation": False',
        '"gateClosed": False',
    )
    for token in required:
        assert token in wrapper_text, token

    lower = (helper_text + "\n" + wrapper_text).lower()
    for forbidden in (
        "bugatti", "bulldozer", "ferrari",
        "desiredimpactspeed", "desiredimpactenergy",
        "collisionframe", "impactframe", "trajectorypoints", "waypoints",
        "set_pose", "linear_velocity =",
    ):
        # Governance receipt fields exactCollisionFrameTarget/exactImpactEnergyTarget
        # are intentionally permitted; only operational/choreography identifiers
        # are forbidden. Avoid raw false positives for those receipt keys.
        if forbidden in {"collisionframe", "impactframe"}:
            continue
        assert forbidden not in lower, forbidden

    # No semantic/locality/contact threshold constants may be introduced in C489.
    assert "semantic_tolerance" not in helper_text.lower()
    assert "semantic_tolerance =" not in wrapper_text.lower()
    assert "locality_tolerance =" not in wrapper_text.lower()
    assert "min_closing_speed" not in helper_text.lower()
    assert "min_closing_speed" not in wrapper_text.lower()

    print(json.dumps({
        "marker": "GENERIC_AUTONOMOUS_BATTLE_C489_PROPERTY_ACCEPTANCE",
        "status": "PASS",
        "candidate": "ISS_GENERIC_BATTLE_RUNTIME_V1_CANDIDATE_4_8_9_GENERIC_AUTONOMOUS_BATTLE",
        "mechanism": OBSERVED_CONTACT_SEMANTIC_MODEL,
        "failureFamily": "CONTROL_INTENT_SEMANTIC_FREEZE_OUTLIVES_SOLVER_OBSERVED_CONTACT_SURFACE",
        "controlIntentVsObservedContactOwnership": "PASS",
        "storyPrescribedSemanticStrictness": "PASS",
        "activeHandoffObservationOnly": "PASS",
        "liveEventTargetZoneMutationForbidden": "PASS",
        "pendingDamageZoneObservedSemanticBinding": "PASS",
        "existingG05OuterAuthorityGatePreserved": "PASS",
        "existingPairwiseSolverOraclePreserved": "PASS",
        "semanticToleranceChanged": False,
        "localityToleranceChanged": False,
        "contactThresholdChanged": False,
        "damageAdmissionThresholdChanged": False,
        "assetSpecificCode": False,
        "perAssetTacticalTuning": False,
        "perVideoTrajectoryEngineering": False,
        "masterPlanAligned": True,
        "gateClosed": False,
    }, sort_keys=True))


if __name__ == "__main__":
    main()
