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
from blender import iss_battle_runtime_generic_battle_v2 as battle_v2
from blender import run_generic_battle_runtime_v1_candidate43 as candidate43
from blender import run_generic_battle_runtime_v1_candidate44 as candidate44
from blender import run_generic_battle_runtime_v1_candidate446 as candidate446
from blender import run_generic_battle_runtime_v1_candidate453_g08 as candidate453
from blender.iss_battle_runtime_consequences_v2 import (
    CONSEQUENCE_MODEL_V2,
    DEBRIS_MODEL_V2,
    VISUAL_RESPONSE_MODEL,
    VisibleCausalConsequenceEngineV2,
)
from blender.iss_battle_runtime_tactics_v2 import TACTICAL_MODEL

CANDIDATE = "ISS_GENERIC_BATTLE_RUNTIME_V1_CANDIDATE_4_6_0_GENERIC_AUTONOMOUS_BATTLE"
MECHANISM = "ISS_GENERIC_AUTONOMOUS_BATTLE_MECHANISM_V2"

_ORIGINAL_G06_OUTCOME = candidate44._ORIGINAL_G06_OUTCOME


def generic_battle_set_controls(
    frame: int,
    program: Any,
    actors: dict[str, Any],
    states: dict[str, Any],
    control_samples: list[dict[str, Any]],
) -> None:
    battle_v2.set_controls(
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
        raise RuntimeError("GENERIC_BATTLE_V2_OUTPUT_DIR_UNAVAILABLE")
    battle_v2.write_evidence(Path(hardened._capture_output))
    return outcome


def main() -> None:
    battle_v2.reset()

    # G04 successor: replace only the control producer underneath the existing
    # G06/G07 instrumentation. G07 still owns causal lifecycle/drama authority.
    candidate43._ORIGINAL_SET_CONTROLS = generic_battle_set_controls

    # Attach battle evidence without replacing G06 persistence or G07 outcome logic.
    candidate44._ORIGINAL_G06_OUTCOME = generic_battle_g06_outcome

    # G06 successor: preserve unchanged G05 admission/damage threshold and swap only
    # the visual consequence realization after physical damage has been earned.
    hardened.ConsequenceEngine = VisibleCausalConsequenceEngineV2
    runtime.ConsequenceEngine = VisibleCausalConsequenceEngineV2

    print(
        json.dumps(
            {
                "marker": "GENERIC_AUTONOMOUS_BATTLE_C460_ENGINEERING_READY",
                "candidate": CANDIDATE,
                "mechanism": MECHANISM,
                "tacticalModel": TACTICAL_MODEL,
                "battleControlModel": battle_v2.BATTLE_CONTROL_MODEL,
                "contactAuthority": "RECIPROCAL_NATIVE_SOLVER_RESPONSE_V1",
                "consequenceModel": CONSEQUENCE_MODEL_V2,
                "visualResponseModel": VISUAL_RESPONSE_MODEL,
                "debrisModel": DEBRIS_MODEL_V2,
                "sameRuntimeAcrossAssets": True,
                "liveWorldStateDriven": True,
                "actorProfileCapabilityDriven": True,
                "storyIntentOnly": True,
                "adaptiveTactics": [
                    "ENGAGE",
                    "FLANK",
                    "BRAKE_APPROACH",
                    "BREAK_CONTACT",
                    "REPOSITION",
                    "EVADE",
                    "COUNTER",
                    "HOLD",
                ],
                "nativeContactAuthorityPreserved": True,
                "damageAdmissionThresholdChanged": False,
                "contactThresholdChanged": False,
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
