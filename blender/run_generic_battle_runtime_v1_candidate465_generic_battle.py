from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from blender import iss_blender_battle_runtime_v1 as runtime
from blender import iss_blender_battle_runtime_v1_hardened as hardened
from blender import iss_battle_runtime_generic_battle_v6 as battle_v6
from blender import run_generic_battle_runtime_v1_candidate43 as candidate43
from blender import run_generic_battle_runtime_v1_candidate44 as candidate44
from blender import run_generic_battle_runtime_v1_candidate446 as candidate446
from blender import run_generic_battle_runtime_v1_candidate453_g08 as candidate453
from blender.iss_battle_runtime_assets import marker
from blender.iss_battle_runtime_handoff_v2 import (
    CUTOFF_FRAME_AUTHORITY_MODEL,
    stabilize_active_handoff_cutoff_frames,
)
from blender.iss_battle_runtime_consequences_v3 import (
    CONSEQUENCE_MODEL_V3,
    DEBRIS_MODEL_V3,
    VISUAL_RESPONSE_MODEL_V3,
    VisibleCausalConsequenceEngineV3,
)
from blender.iss_battle_runtime_tactics_v5 import (
    BATTLE_SIGNAL_SCOPE,
    ENGAGEMENT_RUNWAY_MODEL,
    TACTICAL_MODEL,
)

CANDIDATE = "ISS_GENERIC_BATTLE_RUNTIME_V1_CANDIDATE_4_6_5_GENERIC_AUTONOMOUS_BATTLE"
MECHANISM = "ISS_GENERIC_AUTONOMOUS_BATTLE_MECHANISM_V7_HANDOFF_CUTOFF_STABILITY"
AUDIT = "CONTROLLER_HANDOFF_CUTOFF_FRAME_INTEGRATION_AUDIT_20260918"

_ORIGINAL_G06_OUTCOME = candidate44._ORIGINAL_G06_OUTCOME
_cutoff_stabilization_announced: set[tuple[str, str, int]] = set()


def generic_battle_set_controls(
    frame: int,
    program: Any,
    actors: dict[str, Any],
    states: dict[str, Any],
    control_samples: list[dict[str, Any]],
) -> None:
    battle_v6.set_controls(
        frame,
        program,
        actors,
        states,
        control_samples,
        active_goal_resolver=candidate446.g07_v7_active_goal_for_actor,
    )

    # G05's cutoff frame is the authority-release transition, not a COAST
    # heartbeat. C464 exposed that rewriting it every latched frame can place
    # cutoffFrame after contactFrame even while motor authority is actually zero.
    # Preserve the original handoff transition without changing any G05 gate.
    changes = stabilize_active_handoff_cutoff_frames(
        hardened._cutoff_frames,
        battle_v6._handoff_latches,
    )
    for change in changes:
        key = (
            str(change["eventId"]),
            str(change["actorId"]),
            int(change["authoritativeCutoffFrame"]),
        )
        if key in _cutoff_stabilization_announced:
            continue
        _cutoff_stabilization_announced.add(key)
        marker(
            "GENERIC_SOLVER_HANDOFF_CUTOFF_FRAME_STABILIZED",
            frame=int(frame),
            eventId=change["eventId"],
            actorId=change["actorId"],
            previousCutoffFrame=change["previousCutoffFrame"],
            authoritativeCutoffFrame=change["authoritativeCutoffFrame"],
            model=CUTOFF_FRAME_AUTHORITY_MODEL,
        )


def generic_battle_g06_outcome(states: dict[str, Any], events: dict[str, Any]) -> dict[str, Any]:
    outcome = _ORIGINAL_G06_OUTCOME(states, events)
    if hardened._capture_output is None:
        raise RuntimeError("GENERIC_BATTLE_V6_OUTPUT_DIR_UNAVAILABLE")
    battle_v6.write_evidence(Path(hardened._capture_output))
    return outcome


def main() -> None:
    _cutoff_stabilization_announced.clear()
    battle_v6.reset()
    candidate43._ORIGINAL_SET_CONTROLS = generic_battle_set_controls
    candidate44._ORIGINAL_G06_OUTCOME = generic_battle_g06_outcome

    # G05 admission/contact truth stays untouched. Visible V3 consequences only
    # execute after the preserved physical damage gate has naturally been earned.
    hardened.ConsequenceEngine = VisibleCausalConsequenceEngineV3
    runtime.ConsequenceEngine = VisibleCausalConsequenceEngineV3

    print(
        json.dumps(
            {
                "marker": "GENERIC_AUTONOMOUS_BATTLE_C465_ENGINEERING_READY",
                "candidate": CANDIDATE,
                "mechanism": MECHANISM,
                "affectedLayerAudit": AUDIT,
                "tacticalModel": TACTICAL_MODEL,
                "battleControlModel": battle_v6.BATTLE_CONTROL_MODEL,
                "battleSignalScope": BATTLE_SIGNAL_SCOPE,
                "engagementRunwayModel": ENGAGEMENT_RUNWAY_MODEL,
                "surfaceGapGoalModel": battle_v6.SURFACE_GAP_GOAL_MODEL,
                "cutoffFrameAuthorityModel": CUTOFF_FRAME_AUTHORITY_MODEL,
                "contactAuthority": "RECIPROCAL_NATIVE_SOLVER_RESPONSE_V1",
                "consequenceModel": CONSEQUENCE_MODEL_V3,
                "visualResponseModel": VISUAL_RESPONSE_MODEL_V3,
                "debrisModel": DEBRIS_MODEL_V3,
                "sameRuntimeAcrossAssets": True,
                "liveWorldStateDriven": True,
                "actorProfileCapabilityDriven": True,
                "storyIntentOnly": True,
                "fixtureMutationForAcceptance": False,
                "precontactRunwayRequired": True,
                "surfaceGapRevalidatedDuringReposition": True,
                "standOffUsesLiveSupportGeometry": True,
                "solverHandoffLatchedUntilVerifiedContactOrPhysicalMiss": True,
                "handoffCutoffFrameImmutableWithinLatch": True,
                "g05ControllerAuthorityContractPreserved": True,
                "damageThresholdAwareControl": False,
                "targetToughnessAwareControl": False,
                "desiredImpactSpeedControl": False,
                "desiredImpactEnergyControl": False,
                "payoffTerminatesRecovery": True,
                "nativeContactAuthorityPreserved": True,
                "damageAdmissionThresholdChanged": False,
                "contactThresholdChanged": False,
                "semanticToleranceChanged": False,
                "localityToleranceChanged": False,
                "debrisEligibilityUsesEarnedDamageConsequence": True,
                "debrisTrajectoryInjection": False,
                "perAssetBattleCode": False,
                "perVideoTrajectoryEngineering": False,
                "fixedWorldCoordinates": False,
                "exactCollisionFrameTarget": False,
                "exactImpactEnergyTarget": False,
                "actorPoseOrVelocityMutation": False,
                "forcedWinner": False,
                "stateResetMechanism": False,
                "g01ToG03Changed": False,
                "frozenNineServiceArchitectureChanged": False,
                "issR041SameRuntimeAcrossAssets": True,
                "issR042AutonomousCollisionRealization": True,
                "issR043ScopeChecksRequired": True,
                "issR044FreshUserApprovalRequired": True,
                "issR045MasterPlanAlignedTarget": True,
                "gateClosed": False,
                "productionReadyClaimed": False,
            },
            sort_keys=True,
        ),
        flush=True,
    )
    candidate453.main()


if __name__ == "__main__":
    main()
