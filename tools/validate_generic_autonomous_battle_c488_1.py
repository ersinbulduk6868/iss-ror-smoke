#!/usr/bin/env python3
from __future__ import annotations

import ast
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from blender.iss_battle_runtime_precontact_realization_v1 import (
    PRECONTACT_REALIZATION_MODEL,
    PrecontactRealizationSample,
    precontact_sample_eligible,
    previous_frame_sample_valid_for_handoff,
)

HELPER = ROOT / "blender" / "iss_battle_runtime_precontact_realization_v1.py"
WRAPPER = ROOT / "blender" / "run_generic_battle_runtime_v1_candidate488_1_generic_battle.py"


def sample(frame: int = 10, event: str = "evt-a", actor: str = "actor-a", target: str = "actor-b") -> PrecontactRealizationSample:
    return PrecontactRealizationSample(
        frame=frame,
        event_id=event,
        actor_id=actor,
        target_id=target,
        forward_speed_mps=1.4,
        closing_speed_mps=1.3,
        capability_floor_mps=1.0,
        effective_gap_m=0.30,
        handoff_gap_m=0.10,
    )


def main() -> None:
    helper_text = HELPER.read_text(encoding="utf-8")
    wrapper_text = WRAPPER.read_text(encoding="utf-8")
    ast.parse(helper_text, filename=str(HELPER))
    ast.parse(wrapper_text, filename=str(WRAPPER))

    # Qualification is strictly precontact: realized capability + outside the
    # existing handoff corridor + no recovery.
    assert precontact_sample_eligible(
        contact_approach_active=True,
        recovery_active=False,
        forward_speed_mps=1.4,
        closing_speed_mps=1.3,
        capability_floor_mps=1.0,
        effective_gap_m=0.30,
        handoff_gap_m=0.10,
    ) is True
    assert precontact_sample_eligible(
        contact_approach_active=True,
        recovery_active=True,
        forward_speed_mps=1.4,
        closing_speed_mps=1.3,
        capability_floor_mps=1.0,
        effective_gap_m=0.30,
        handoff_gap_m=0.10,
    ) is False
    assert precontact_sample_eligible(
        contact_approach_active=True,
        recovery_active=False,
        forward_speed_mps=1.4,
        closing_speed_mps=1.3,
        capability_floor_mps=1.0,
        effective_gap_m=0.10,
        handoff_gap_m=0.10,
    ) is False

    key = ("evt-a", "actor-a", "actor-b")
    s = sample()
    # Exact TOCTOU bridge: only immediately previous frame may be consumed.
    assert previous_frame_sample_valid_for_handoff(
        s,
        transaction_key=key,
        decision_frame=11,
        current_capability_floor_mps=1.0,
        current_closing_speed_mps=0.01,
        controller_handoff_requested=True,
    ) is True
    # Stale or future samples fail closed.
    for decision in (10, 12, 20):
        assert previous_frame_sample_valid_for_handoff(
            s,
            transaction_key=key,
            decision_frame=decision,
            current_capability_floor_mps=1.0,
            current_closing_speed_mps=0.01,
            controller_handoff_requested=True,
        ) is False
    # Cross-event/cross-target evidence may never satisfy another transaction.
    for wrong in (("evt-b", "actor-a", "actor-b"), ("evt-a", "actor-a", "actor-c")):
        assert previous_frame_sample_valid_for_handoff(
            s,
            transaction_key=wrong,
            decision_frame=11,
            current_capability_floor_mps=1.0,
            current_closing_speed_mps=0.01,
            controller_handoff_requested=True,
        ) is False
    # Preserve base controller's current-state safety condition. Solver bounce or
    # separation (negative current closing) cannot use historical approach proof.
    assert previous_frame_sample_valid_for_handoff(
        s,
        transaction_key=key,
        decision_frame=11,
        current_capability_floor_mps=1.0,
        current_closing_speed_mps=-0.001,
        controller_handoff_requested=True,
    ) is False
    assert previous_frame_sample_valid_for_handoff(
        s,
        transaction_key=key,
        decision_frame=11,
        current_capability_floor_mps=1.0,
        current_closing_speed_mps=0.01,
        controller_handoff_requested=False,
    ) is False
    # If current capability floor rises, old weaker evidence cannot be reused.
    assert previous_frame_sample_valid_for_handoff(
        s,
        transaction_key=key,
        decision_frame=11,
        current_capability_floor_mps=1.5,
        current_closing_speed_mps=0.01,
        controller_handoff_requested=True,
    ) is False

    combined = helper_text + "\n" + wrapper_text
    for required in (
        "G04_EVENT_SCOPED_PRECONTACT_REALIZATION_WINDOW_V1",
        "int(decision_frame) - int(sample.frame) != 1",
        "float(current_closing_speed_mps) < 0.0",
        "effective_gap_m) > float(handoff_gap_m",
        "G04_PRECONTACT_REALIZATION_SAMPLE_ARMED",
        "G04_PRECONTACT_REALIZATION_CARRIED_TO_HANDOFF",
        'evidenceSource="IMMEDIATELY_PREVIOUS_PRECONTACT_FRAME"',
        '"previousFrameOnlyEvidence":True',
        '"currentNonNegativeClosingRequired":True',
        '"g05SourceChanged":False',
        '"contactThresholdChanged":False',
        '"perAssetBattleCode":False',
        '"perVideoTrajectoryEngineering":False',
        "candidate486.main = candidate485.main",
        "candidate487.main()",
    ):
        assert required in combined, required

    # Superseded broad C488 certificate mechanism must not be composed by C488.1.
    for forbidden in (
        "iss_battle_runtime_engagement_authority_v2",
        "ApproachMotionCertificate",
        "currentClosingSignRequiredAfterCertifiedProximity",
        "HANDOFF_TO_SOLVER",
        "bugatti",
        "bulldozer",
        "min_closing_speed_mps",
        "min_damage_severity",
        "desiredimpactspeedmps",
        "desiredimpactenergyj",
        "trajectorypoints",
        "waypoints",
        "set_pose",
        "linear_velocity =",
    ):
        assert forbidden not in combined.lower(), forbidden

    print(json.dumps({
        "marker": "GENERIC_AUTONOMOUS_BATTLE_C488_1_PROPERTY_ACCEPTANCE",
        "status": "PASS",
        "candidate": "ISS_GENERIC_BATTLE_RUNTIME_V1_CANDIDATE_4_8_8_1_GENERIC_AUTONOMOUS_BATTLE",
        "mechanism": PRECONTACT_REALIZATION_MODEL,
        "failureFamily": "G04_POST_PHYSICS_INSTANTANEOUS_REALIZATION_HANDOFF_TOCTOU",
        "previousFrameOnlyEvidence": "PASS",
        "eventActorTargetIsolation": "PASS",
        "currentNonNegativeClosingPreserved": "PASS",
        "recoveryEvidenceRejected": "PASS",
        "staleEvidenceRejected": "PASS",
        "capabilityFloorPreserved": "PASS",
        "c488BroadCertificateRejected": "PASS",
        "g05ThresholdImported": False,
        "assetSpecificCode": False,
        "perAssetTacticalTuning": False,
        "perVideoTrajectoryEngineering": False,
        "masterPlanAligned": True,
        "gateClosed": False,
    }, sort_keys=True))


if __name__ == "__main__":
    main()
