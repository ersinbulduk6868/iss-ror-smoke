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
from blender import iss_battle_runtime_generic_battle_v3 as battle_v3
from blender import run_generic_battle_runtime_v1_candidate43 as candidate43
from blender import run_generic_battle_runtime_v1_candidate44 as candidate44
from blender import run_generic_battle_runtime_v1_candidate446 as candidate446
from blender import run_generic_battle_runtime_v1_candidate453_g08 as candidate453
from blender.iss_battle_runtime_consequences_v3 import (
    CONSEQUENCE_MODEL_V3,
    DEBRIS_MODEL_V3,
    VISUAL_RESPONSE_MODEL_V3,
    VisibleCausalConsequenceEngineV3,
)
from blender.iss_battle_runtime_tactics_v3 import BATTLE_SIGNAL_SCOPE, TACTICAL_MODEL

CANDIDATE = "ISS_GENERIC_BATTLE_RUNTIME_V1_CANDIDATE_4_6_1_GENERIC_AUTONOMOUS_BATTLE"
MECHANISM = "ISS_GENERIC_AUTONOMOUS_BATTLE_MECHANISM_V3"
AUDIT = "C460_FULL_AFFECTED_LAYER_AUDIT_20260917"

_ORIGINAL_G06_OUTCOME = candidate44._ORIGINAL_G06_OUTCOME


def generic_battle_set_controls(
    frame: int,
    program: Any,
    actors: dict[str, Any],
    states: dict[str, Any],
    control_samples: list[dict[str, Any]],
) -> None:
    battle_v3.set_controls(
        frame,
        program,
        actors,
        states,
        control_samples,
        active_goal_resolver=candidate446.g07_v7_active_goal_for_actor,
    )


def generic_battle_g06_outcome(states: dict[str, Any], events: dict[str, Any]) -> dict[str, Any]:
    outcome = _ORIGINAL_G06_OUTCOME(states, events)
    if hardened._capture_output is None:
        raise RuntimeError("GENERIC_BATTLE_V3_OUTPUT_DIR_UNAVAILABLE")
    battle_v3.write_evidence(Path(hardened._capture_output))
    return outcome


def main() -> None:
    battle_v3.reset()
    candidate43._ORIGINAL_SET_CONTROLS = generic_battle_set_controls
    candidate44._ORIGINAL_G06_OUTCOME = generic_battle_g06_outcome

    # Contact/damage admission remains owned by the preserved runtime. V3 only
    # turns already-earned physical consequences into generic visible deformation
    # and native rigid debris using realized recipient geometry.
    hardened.ConsequenceEngine = VisibleCausalConsequenceEngineV3
    runtime.ConsequenceEngine = VisibleCausalConsequenceEngineV3

    print(
        json.dumps(
            {
                "marker": "GENERIC_AUTONOMOUS_BATTLE_C461_ENGINEERING_READY",
                "candidate": CANDIDATE,
                "mechanism": MECHANISM,
                "fullAffectedLayerAudit": AUDIT,
                "tacticalModel": TACTICAL_MODEL,
                "battleControlModel": battle_v3.BATTLE_CONTROL_MODEL,
                "battleSignalScope": BATTLE_SIGNAL_SCOPE,
                "autonomyStateScope": "CURRENT_EVENT_ONLY",
                "contactAuthority": "RECIPROCAL_NATIVE_SOLVER_RESPONSE_V1",
                "consequenceModel": CONSEQUENCE_MODEL_V3,
                "visualResponseModel": VISUAL_RESPONSE_MODEL_V3,
                "debrisModel": DEBRIS_MODEL_V3,
                "sameRuntimeAcrossAssets": True,
                "liveWorldStateDriven": True,
                "actorProfileCapabilityDriven": True,
                "actorScopedContinuousBattleMemory": True,
                "unrelatedActorContactContamination": False,
                "firstObservationHistoricalContactAware": True,
                "payoffTerminatesRecovery": True,
                "storyIntentOnly": True,
                "nativeContactAuthorityPreserved": True,
                "damageAdmissionThresholdChanged": False,
                "contactThresholdChanged": False,
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
