#!/usr/bin/env python3
from __future__ import annotations

import ast
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from blender.iss_battle_runtime_g05_negative_ack_v1 import (
    G05_NEGATIVE_ACK_MODEL,
    STAGE_IMPACT_GATE,
    STAGE_OUTER,
    STAGE_SOLVER,
    G05NegativeAcknowledgement,
    recoverable_post_handoff_nack,
)

HELPER = ROOT / "blender" / "iss_battle_runtime_g05_negative_ack_v1.py"
WRAPPER = ROOT / "blender" / "run_generic_battle_runtime_v1_candidate489_generic_battle.py"
C488 = ROOT / "blender" / "run_generic_battle_runtime_v1_candidate488_generic_battle.py"


def nack(
    *,
    stage: str,
    reason: str,
    handoff: bool = True,
    motor_zero: bool = True,
    event: str = "evt-a",
    actor: str = "actor-a",
    target: str = "actor-b",
) -> G05NegativeAcknowledgement:
    return G05NegativeAcknowledgement(
        frame=100,
        event_id=event,
        attacker_id=actor,
        target_id=target,
        stage=stage,
        reason=reason,
        contact_frame=100,
        controller_handoff=handoff,
        motor_authority_zero=motor_zero,
    )


def decision(row: G05NegativeAcknowledgement, *, latched: bool = True, event: str = "evt-a", actor: str = "actor-a", target: str = "actor-b") -> bool:
    return recoverable_post_handoff_nack(
        row,
        active_event_id=event,
        active_attacker_id=actor,
        active_target_id=target,
        handoff_latched=latched,
    )


def main() -> None:
    helper_text = HELPER.read_text(encoding="utf-8")
    wrapper_text = WRAPPER.read_text(encoding="utf-8")
    c488_text = C488.read_text(encoding="utf-8")
    ast.parse(helper_text, filename=str(HELPER))
    ast.parse(wrapper_text, filename=str(WRAPPER))

    assert decision(nack(stage=STAGE_OUTER, reason="SEMANTIC_ZONE_MISMATCH")) is True
    assert decision(nack(stage=STAGE_OUTER, reason="PAIR_NOT_LOCALLY_ADJACENT")) is True
    assert decision(nack(stage=STAGE_SOLVER, reason="CLOSING_SPEED_BELOW_EXISTING_GATE")) is True
    assert decision(nack(stage=STAGE_SOLVER, reason="SOLVER_RESPONSE_BELOW_EXISTING_FLOOR")) is True
    assert decision(nack(stage=STAGE_IMPACT_GATE, reason="EXISTING_IMPACT_GATE_REJECTED")) is True

    # Contract regressions must remain visible instead of being hidden by retry/recovery.
    assert decision(nack(stage=STAGE_OUTER, reason="CONTROLLER_AUTHORITY_NOT_RELEASED", handoff=False, motor_zero=False)) is False
    assert decision(nack(stage=STAGE_OUTER, reason="TARGET_IDENTITY_MISMATCH")) is False

    # No cross-event/actor/target or pre-handoff feedback leakage.
    assert decision(nack(stage=STAGE_OUTER, reason="SEMANTIC_ZONE_MISMATCH"), latched=False) is False
    assert decision(nack(stage=STAGE_OUTER, reason="SEMANTIC_ZONE_MISMATCH"), event="evt-b") is False
    assert decision(nack(stage=STAGE_OUTER, reason="SEMANTIC_ZONE_MISMATCH"), actor="actor-c") is False
    assert decision(nack(stage=STAGE_OUTER, reason="SEMANTIC_ZONE_MISMATCH"), target="actor-c") is False
    assert decision(nack(stage=STAGE_OUTER, reason="SEMANTIC_ZONE_MISMATCH", handoff=False)) is False
    assert decision(nack(stage=STAGE_OUTER, reason="SEMANTIC_ZONE_MISMATCH", motor_zero=False)) is False

    combined = helper_text + "\n" + wrapper_text
    for required in (
        "G04_G05_NEGATIVE_ACKNOWLEDGEMENT_RECOVERY_V1",
        "_ObservedOuterAuthorityGate",
        "_ObservedPairwiseSolverResponseOracle",
        "_ORIGINAL_OUTER_GATE.evaluate(sample)",
        "_ORIGINAL_SOLVER_ORACLE.evaluate(sample)",
        "G05_PAIRWISE_CONTACT_REJECTED_BY_EXISTING_IMPACT_GATE",
        "G04_G05_NEGATIVE_ACK_OBSERVED",
        "G04_G05_NEGATIVE_ACK_HANDOFF_RELEASED",
        "G04_G05_NEGATIVE_ACK_CONTACT_COMMIT_SUSPENDED",
        "G04_G05_NEGATIVE_ACK_RECOVERY_TRIGGERED",
        "ClosedLoopGoalController._begin_recovery",
        "candidate488.main()",
        '"g05SourceChanged": False',
        '"g05OuterGateChanged": False',
        '"g05SolverOracleChanged": False',
        '"g05ThresholdImported": False',
        '"contactThresholdChanged": False',
        '"semanticToleranceChanged": False',
        '"localityToleranceChanged": False',
        '"damageAdmissionThresholdChanged": False',
        '"perAssetBattleCode": False',
        '"perVideoTrajectoryEngineering": False',
    ):
        assert required in combined, required

    # C489 may observe/delegate G05 decisions, but must not copy or weaken G05 thresholds.
    lowered = combined.lower()
    for forbidden in (
        "bugatti",
        "bulldozer",
        "desiredimpactspeedmps",
        "desiredimpactenergyj",
        "trajectorypoints",
        "waypoints",
        "set_pose",
        "linear_velocity =",
        "1.23216",
        "min_closing_speed_mps =",
        "min_damage_severity =",
        "response_floor_mps =",
        "semantic_tolerance =",
        "locality_tolerance =",
    ):
        assert forbidden not in lowered, forbidden

    # C488 remains the inherited handoff implementation; C489 only supplies NACK feedback.
    assert "G04_EVENT_SCOPED_ENGAGEMENT_AUTHORITY_V2" in c488_text
    assert "currentClosingSignRequiredAfterCertifiedProximity\": False" in c488_text

    print(json.dumps({
        "marker": "GENERIC_AUTONOMOUS_BATTLE_C489_PROPERTY_ACCEPTANCE",
        "status": "PASS",
        "candidate": "ISS_GENERIC_BATTLE_RUNTIME_V1_CANDIDATE_4_8_9_GENERIC_AUTONOMOUS_BATTLE",
        "mechanism": G05_NEGATIVE_ACK_MODEL,
        "outerGeometryNackRecovery": "PASS",
        "solverNackRecovery": "PASS",
        "impactGateNackRecovery": "PASS",
        "controllerAuthorityRegressionVisible": "PASS",
        "targetIdentityRegressionVisible": "PASS",
        "eventActorTargetIsolation": "PASS",
        "preHandoffFeedbackRejected": "PASS",
        "g05DecisionDelegatedUnchanged": "PASS",
        "g05ThresholdImported": False,
        "assetSpecificCode": False,
        "perAssetTacticalTuning": False,
        "perVideoTrajectoryEngineering": False,
        "masterPlanAligned": True,
        "gateClosed": False,
    }, sort_keys=True))


if __name__ == "__main__":
    main()
