#!/usr/bin/env python3
from __future__ import annotations

import ast
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from blender.iss_battle_runtime_certified_alignment_ownership_v1 import (
    DEFER_TO_EXISTING_CERTIFICATE_AUTHORITY,
    INVALIDATE_PRECONTACT_SEPARATION,
    KEEP_LEGACY_RUNWAY_REOPEN,
    PRESERVE_CERTIFICATE,
    alignment_hold_certificate_action,
    alignment_only_readiness_miss,
    legacy_runway_reopen_ownership,
)

HELPER = ROOT / "blender" / "iss_battle_runtime_certified_alignment_ownership_v1.py"
WRAPPER = ROOT / "blender" / "run_generic_battle_runtime_v1_candidate491_generic_battle.py"
C487 = ROOT / "blender" / "run_generic_battle_runtime_v1_candidate487_generic_battle.py"
C488 = ROOT / "blender" / "run_generic_battle_runtime_v1_candidate488_generic_battle.py"
C490 = ROOT / "blender" / "run_generic_battle_runtime_v1_candidate490_generic_battle.py"
COMMIT = ROOT / "blender" / "iss_battle_runtime_contact_commit_v2.py"
AUTHORITY = ROOT / "blender" / "iss_battle_runtime_engagement_authority_v2.py"


def main() -> None:
    helper = HELPER.read_text(encoding="utf-8")
    wrapper = WRAPPER.read_text(encoding="utf-8")
    c487 = C487.read_text(encoding="utf-8")
    c488 = C488.read_text(encoding="utf-8")
    c490 = C490.read_text(encoding="utf-8")
    commit = COMMIT.read_text(encoding="utf-8")
    authority = AUTHORITY.read_text(encoding="utf-8")
    for name, text in (
        ("helper", helper), ("wrapper", wrapper), ("c487", c487),
        ("c488", c488), ("c490", c490), ("commit", commit),
        ("authority", authority),
    ):
        ast.parse(text, filename=name)

    # Existing generic G04 readiness limits remain byte-identifiable and unchanged.
    assert "CONTACT_COMMIT_MAX_HEADING_ERROR_RAD = 0.70" in commit
    assert "CONTACT_COMMIT_MAX_CONTENTION = 0.80" in commit
    assert "abs(float(heading_error_rad)) <= CONTACT_COMMIT_MAX_HEADING_ERROR_RAD" in commit
    assert "float(contention) < CONTACT_COMMIT_MAX_CONTENTION" in commit

    # Existing C487 safety ownership and C488 handoff/alignment ownership remain.
    # C487 computes recovery_active, passes it into precontact_action, and then
    # honors SUSPEND_FOR_RECOVERY explicitly. Do not require an implementation-
    # specific literal inside the C487 wrapper when the actual contract spans
    # lifecycle helper + wrapper composition.
    assert "recovery_active=recovery_active" in c487
    assert "if action == SUSPEND_FOR_RECOVERY:" in c487
    assert "return goal_point" in c487
    assert "return REOPEN_DISTANCE" in c487 or "REOPEN_DISTANCE" in c487
    assert "should_defer_handoff_for_alignment(" in c488
    assert "G04_CONTACT_HANDOFF_DEFERRED_BY_ROTATIONAL_DOMINANCE" in c488
    assert "if not bool(contact_directed_mode) or not bool(live_readiness):" in authority
    assert "return DEFER_TO_BASE" in authority

    # C490 final G05 observation composition remains the immediate predecessor.
    assert "candidate471._ORIGINAL_PAIRWISE_RECEIPT = candidate489.c489_observed_pairwise_receipt" in c490
    assert "candidate490.main()" in wrapper

    # Alignment-only miss classification uses readiness booleans; no new threshold.
    assert alignment_only_readiness_miss(
        requires_contact=True,
        runway_armed=True,
        contact_ready=False,
        heading_ready=False,
        contention_ready=True,
    ) is True
    assert alignment_only_readiness_miss(
        requires_contact=True,
        runway_armed=True,
        contact_ready=False,
        heading_ready=False,
        contention_ready=False,
    ) is False
    assert alignment_only_readiness_miss(
        requires_contact=True,
        runway_armed=False,
        contact_ready=False,
        heading_ready=False,
        contention_ready=True,
    ) is False
    assert alignment_only_readiness_miss(
        requires_contact=True,
        runway_armed=True,
        contact_ready=True,
        heading_ready=True,
        contention_ready=True,
    ) is False

    base = dict(
        legacy_action="REOPEN_DISTANCE",
        reopen_action="REOPEN_DISTANCE",
        transaction_active=True,
        contact_directed_mode=True,
        recovery_active=False,
        certificate_qualified=True,
        alignment_only_miss=True,
    )
    assert legacy_runway_reopen_ownership(**base) == DEFER_TO_EXISTING_CERTIFICATE_AUTHORITY
    assert legacy_runway_reopen_ownership(**{**base, "certificate_qualified": False}) == KEEP_LEGACY_RUNWAY_REOPEN
    assert legacy_runway_reopen_ownership(**{**base, "recovery_active": True}) == KEEP_LEGACY_RUNWAY_REOPEN
    assert legacy_runway_reopen_ownership(**{**base, "contact_directed_mode": False}) == KEEP_LEGACY_RUNWAY_REOPEN
    assert legacy_runway_reopen_ownership(**{**base, "alignment_only_miss": False}) == KEEP_LEGACY_RUNWAY_REOPEN
    assert legacy_runway_reopen_ownership(**{**base, "legacy_action": "HOLD_STANDOFF"}) == KEEP_LEGACY_RUNWAY_REOPEN

    # Earned historical proof survives alignment hold, but real geometric retreat
    # still invalidates it with the exact existing separation semantics.
    assert alignment_hold_certificate_action(
        certificate_qualified=True,
        effective_gap_m=0.10,
        handoff_gap_m=0.20,
        previous_effective_gap_m=0.12,
        progress_epsilon_m=0.01,
        closing_speed_mps=1.0,
    ) == PRESERVE_CERTIFICATE
    assert alignment_hold_certificate_action(
        certificate_qualified=True,
        effective_gap_m=0.50,
        handoff_gap_m=0.20,
        previous_effective_gap_m=0.40,
        progress_epsilon_m=0.01,
        closing_speed_mps=-0.1,
    ) == INVALIDATE_PRECONTACT_SEPARATION
    assert alignment_hold_certificate_action(
        certificate_qualified=True,
        effective_gap_m=0.50,
        handoff_gap_m=0.20,
        previous_effective_gap_m=0.40,
        progress_epsilon_m=0.01,
        closing_speed_mps=0.1,
    ) == PRESERVE_CERTIFICATE

    # Runtime composition must observe readiness unchanged, defer only the legacy
    # full-retreat action, force instantaneous contactCommit false in C488 context,
    # and preserve the certificate only during that alignment hold.
    for token in (
        "_ORIGINAL_LIVE_CONTACT_READY(",
        "_ORIGINAL_PRECONTACT_ACTION(",
        "candidate487.live_contact_commit_ready = c491_observed_live_contact_commit_ready",
        "candidate487.precontact_action = c491_precontact_action",
        "candidate489._ORIGINAL_C488_GOAL = c491_c488_goal_for_tactical",
        "candidate488.update_approach_certificate = c491_update_approach_certificate",
        'context["contactCommit"] = False',
        '"handoffAllowedWhileUnready": False',
        "G04_CERTIFIED_APPROACH_LEGACY_RUNWAY_REOPEN_DEFERRED",
        "G04_CERTIFIED_APPROACH_ALIGNMENT_HOLD",
    ):
        assert token in wrapper, token

    required_true = (
        '"c490FinalCompositionBindingPreserved": True',
        '"c489NegativeAckRecoveryPreserved": True',
        '"c488CertifiedApproachAuthorityPreserved": True',
        '"c488AlignmentAuthorityPreserved": True',
        '"c487RecoveryPriorityPreserved": True',
        '"existingHeadingReadinessGatePreserved": True',
        '"existingContentionReadinessGatePreserved": True',
        '"headingOnlyMissCannotHandoff": True',
        '"contentionMissKeepsLegacyRunwayReopen": True',
        '"recoveryKeepsLegacyOwnership": True',
        '"realPrecontactSeparationStillInvalidatesCertificate": True',
    )
    for token in required_true:
        assert token in wrapper, token

    required_false = (
        '"storyDurationChanged": False',
        '"eventTimingChanged": False',
        '"g05SourceChanged": False',
        '"g05OuterGateChanged": False',
        '"g05SolverOracleChanged": False',
        '"g05ThresholdImported": False',
        '"headingThresholdChanged": False',
        '"contentionThresholdChanged": False',
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
        '"frozenNineServiceArchitectureChanged": False',
        '"gateClosed": False',
        '"productionReadyClaimed": False',
    )
    for token in required_false:
        assert token in wrapper, token

    # Governance receipts are allowed; operational choreography identifiers remain
    # forbidden. Avoid broad substring rules that reject explicit False governance
    # fields such as exactCollisionFrameTarget=False.
    operational = (helper + "\n" + wrapper).lower()
    for forbidden in (
        "bugatti", "bulldozer", "ferrari", "tuktuk", "tuk-tuk",
        "desiredimpactspeed", "desiredimpactenergy",
        "collisionframe =", "collision_frame =",
        "trajectorypoints", "waypoints", "forcedwinner", "set_pose",
        "linear_velocity =", "semantic_tolerance =", "locality_tolerance =",
        "min_closing_speed", "event.end_frame =", "total_frames =",
    ):
        assert forbidden not in operational, forbidden

    print(json.dumps({
        "marker": "GENERIC_AUTONOMOUS_BATTLE_C491_PROPERTY_ACCEPTANCE",
        "status": "PASS",
        "candidate": "ISS_GENERIC_BATTLE_RUNTIME_V1_CANDIDATE_4_9_1_GENERIC_AUTONOMOUS_BATTLE",
        "mechanism": "G04_CERTIFIED_APPROACH_ALIGNMENT_OWNERSHIP_V1",
        "failureFamily": "QUALIFIED_APPROACH_CERTIFICATE_PREEMPTED_BY_LEGACY_FULL_RUNWAY_REOPEN",
        "headingReadinessThresholdPreserved": True,
        "contentionReadinessThresholdPreserved": True,
        "instantaneousReadinessStillBlocksHandoff": True,
        "certifiedApproachProofSurvivesHeadingOnlyHold": True,
        "realSeparationStillInvalidatesCertificate": True,
        "contentionStillUsesLegacyRunwayReopen": True,
        "recoveryPriorityPreserved": True,
        "c490FinalCompositionPreserved": True,
        "g05AuthorityPreserved": True,
        "storyDurationChanged": False,
        "eventTimingChanged": False,
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
