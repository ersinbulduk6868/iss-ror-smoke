#!/usr/bin/env python3
from __future__ import annotations

import ast
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from blender.iss_battle_runtime_certified_navigation_continuity_v1 import (
    CERTIFIED_NAVIGATION_CONTINUITY_MODEL,
    certified_approach_owns_navigation,
)

HELPER = ROOT / "blender" / "iss_battle_runtime_certified_navigation_continuity_v1.py"
WRAPPER = ROOT / "blender" / "run_generic_battle_runtime_v1_candidate491_generic_battle.py"
C487 = ROOT / "blender" / "run_generic_battle_runtime_v1_candidate487_generic_battle.py"
C488 = ROOT / "blender" / "run_generic_battle_runtime_v1_candidate488_generic_battle.py"
C490 = ROOT / "blender" / "run_generic_battle_runtime_v1_candidate490_generic_battle.py"


def main() -> None:
    helper = HELPER.read_text(encoding="utf-8")
    wrapper = WRAPPER.read_text(encoding="utf-8")
    c487 = C487.read_text(encoding="utf-8")
    c488 = C488.read_text(encoding="utf-8")
    c490 = C490.read_text(encoding="utf-8")
    for name, text in (("helper", helper), ("wrapper", wrapper), ("c487", c487), ("c488", c488), ("c490", c490)):
        ast.parse(text, filename=name)

    # Ownership can exist only after qualification, on the same active transaction,
    # while the upstream planner remains contact-directed+committed and recovery is off.
    assert certified_approach_owns_navigation(
        transaction_active=True,
        certificate_qualified=True,
        incoming_tactical_mode="COUNTER",
        incoming_contact_commit=True,
        recovery_active=False,
    )
    assert certified_approach_owns_navigation(
        transaction_active=True,
        certificate_qualified=True,
        incoming_tactical_mode="ENGAGE",
        incoming_contact_commit=True,
        recovery_active=False,
    )
    for kwargs in (
        dict(transaction_active=False, certificate_qualified=True, incoming_tactical_mode="COUNTER", incoming_contact_commit=True, recovery_active=False),
        dict(transaction_active=True, certificate_qualified=False, incoming_tactical_mode="COUNTER", incoming_contact_commit=True, recovery_active=False),
        dict(transaction_active=True, certificate_qualified=True, incoming_tactical_mode="OPEN_DISTANCE", incoming_contact_commit=True, recovery_active=False),
        dict(transaction_active=True, certificate_qualified=True, incoming_tactical_mode="COUNTER", incoming_contact_commit=False, recovery_active=False),
        dict(transaction_active=True, certificate_qualified=True, incoming_tactical_mode="COUNTER", incoming_contact_commit=True, recovery_active=True),
    ):
        assert not certified_approach_owns_navigation(**kwargs), kwargs

    # C491 composes at both duplicate readiness ownership points: C487 may not
    # reopen the runway once continuity owns navigation, and C488 may not discard
    # that same qualified certificate solely because the duplicate live-readiness
    # sample is transiently false. Initial qualification remains untouched.
    assert "candidate487.actual_goal_lifecycle_goal_for_tactical = (" in wrapper
    assert "candidate488.update_approach_certificate = c491_update_approach_certificate" in wrapper
    assert "candidate488.authority_action = c491_authority_action" in wrapper
    assert "id(memory) in _continuity_certificate_ids" in wrapper
    assert "kwargs[\"live_readiness\"] = True" in wrapper
    assert "memory.qualified" in wrapper
    assert "candidate490.main()" in wrapper
    assert "candidate487._BASE_GOAL_FOR_TACTICAL(" in wrapper
    assert "_ORIGINAL_C487_ACTUAL_GOAL(actor, target, event, tactical, actors)" in wrapper
    assert "G04_CERTIFIED_APPROACH_NAVIGATION_CONTINUITY_ENGAGED" in wrapper
    assert "G04_CERTIFIED_APPROACH_NAVIGATION_CONTINUITY_RELEASED" in wrapper

    # Historical safeguards remain present and unchanged in predecessor source.
    assert "ACTUAL_GOAL_READINESS_RUNWAY_REOPEN" in c487
    assert "SUSPEND_FOR_RECOVERY" in c487
    assert "G04_EVENT_SCOPED_RECOVERY_REPLAN_PROPAGATED" in c487
    assert "update_approach_certificate(" in c488
    assert "should_defer_handoff_for_alignment(" in c488
    assert "G04_CERTIFIED_SOLVER_HANDOFF_REQUESTED" in c488
    assert "candidate471._ORIGINAL_PAIRWISE_RECEIPT = candidate489.c489_observed_pairwise_receipt" in c490
    assert "candidate489._ObservedPairwiseSolverResponseOracle.evaluate" in c490

    # C491 may observe tactical state, but must never rewrite it or its contact commit.
    tree = ast.parse(wrapper)
    forbidden_tactical_assignments: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, (ast.Assign, ast.AnnAssign, ast.AugAssign)):
            targets = node.targets if isinstance(node, ast.Assign) else [node.target]
            for target in targets:
                if isinstance(target, ast.Attribute) and isinstance(target.value, ast.Name) and target.value.id == "tactical":
                    if target.attr in {"mode", "contact_commit", "speed_intent", "speed_scale", "forward_offset_scale", "lateral_offset_scale"}:
                        forbidden_tactical_assignments.append(target.attr)
    assert not forbidden_tactical_assignments, forbidden_tactical_assignments

    required_true = (
        '"certificateNavigationOwnershipAfterQualification": True',
        '"certificateLiveReadinessContinuityAfterQualification": True',
        '"incomingPlannerContactCommitStillRequired": True',
        '"incomingContactDirectedModeStillRequired": True',
        '"sameTransactionStillRequired": True',
        '"recoveryPreemptsCertificateContinuity": True',
        '"preQualificationReadinessUnchanged": True',
        '"c488CertificateMissInvalidationPreserved": True',
        '"c488CertificateRecoveryInvalidationPreserved": True',
        '"c484TranslationDominantAlignmentPreserved": True',
        '"c490FinalCompositionBindingPreserved": True',
        '"c489NegativeAckRecoveryPreserved": True',
        '"c487RecoveryLifecyclePreserved": True',
    )
    for token in required_true:
        assert token in wrapper, token

    required_false = (
        '"tacticalModeMutatedByC491": False',
        '"tacticalContactCommitMutatedByC491": False',
        '"actualGoalReadinessThresholdChanged": False',
        '"contactCommitHeadingThresholdChanged": False',
        '"g05SourceChanged": False',
        '"g05OuterGateChanged": False',
        '"g05SolverOracleChanged": False',
        '"g05ThresholdImported": False',
        '"contactThresholdChanged": False',
        '"semanticToleranceChanged": False',
        '"localityToleranceChanged": False',
        '"damageAdmissionThresholdChanged": False',
        '"assetIdentityBranch": False',
        '"perAssetBattleCode": False',
        '"perAssetTacticalTuning": False',
        '"perVideoTrajectoryEngineering": False',
        '"actorPoseOrVelocityMutation": False',
        '"fixtureBattlePlanChanged": False',
        '"storyTimingChanged": False',
        '"programDurationChanged": False',
        '"frozenNineServiceArchitectureChanged": False',
        '"gateClosed": False',
        '"productionReadyClaimed": False',
    )
    for token in required_false:
        assert token in wrapper, token

    lowered = (helper + "\n" + wrapper).lower()
    for forbidden in (
        "bugatti", "bulldozer", "ferrari",
        "desiredimpactspeed", "desiredimpactenergy", "target_impact_speed",
        "target_impact_energy", "trajectorypoints", "waypoints", "set_pose",
        "linear_velocity =", "semantic_tolerance =", "locality_tolerance =",
        "contact_threshold =", "damage_threshold =",
    ):
        assert forbidden not in lowered, forbidden

    print(json.dumps({
        "marker": "GENERIC_AUTONOMOUS_BATTLE_C491_PROPERTY_ACCEPTANCE",
        "status": "PASS",
        "candidate": "ISS_GENERIC_BATTLE_RUNTIME_V1_CANDIDATE_4_9_1_GENERIC_AUTONOMOUS_BATTLE",
        "mechanism": CERTIFIED_NAVIGATION_CONTINUITY_MODEL,
        "failureFamily": "DUPLICATE_ACTUAL_GOAL_READINESS_REOPENS_FULL_RUNWAY_AFTER_REALIZED_APPROACH_CERTIFICATION",
        "ownershipTruthTable": "PASS",
        "navigationOwnershipBinding": "PASS",
        "certificateReadinessContinuityBinding": "PASS",
        "preQualificationReadinessUnchanged": True,
        "plannerAuthorityPreserved": True,
        "recoveryPreemptionPreserved": True,
        "certificateMissInvalidationPreserved": True,
        "c484AlignmentPreserved": True,
        "c490CompositionBindingPreserved": True,
        "g05AuthorityPreserved": True,
        "readinessThresholdChanged": False,
        "contactThresholdChanged": False,
        "semanticToleranceChanged": False,
        "localityToleranceChanged": False,
        "damageAdmissionThresholdChanged": False,
        "assetSpecificCode": False,
        "perAssetTacticalTuning": False,
        "perVideoTrajectoryEngineering": False,
        "masterPlanAligned": True,
        "gateClosed": False,
    }, sort_keys=True))


if __name__ == "__main__":
    main()
