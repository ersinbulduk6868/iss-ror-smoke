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

CANDIDATE = "ISS_GENERIC_BATTLE_RUNTIME_V1_CANDIDATE_4_6_1_GENERIC_AUTONOMOUS_BATTLE"
MECHANISM = "ISS_GENERIC_AUTONOMOUS_BATTLE_MECHANISM_V2"
EVENT_LIFECYCLE_MODEL = "ISS_EVENT_SCOPED_TACTICAL_MEMORY_V1"

_ORIGINAL_G06_OUTCOME = candidate44._ORIGINAL_G06_OUTCOME
_last_event_by_actor: dict[str, str | None] = {}


def _enforce_event_scoped_tactical_memory(
    frame: int,
    program: Any,
    actors: dict[str, Any],
    states: dict[str, Any],
) -> None:
    """Reset only tactical decision memory when an actor enters a new story event.

    Persistent physical actor state (damage, velocity, geometry, debris, G05 receipts)
    is deliberately untouched. The new TacticalMemory then baselines those persistent
    values, so prior-event damage cannot masquerade as a new impact.
    """
    for entity in actors:
        event = candidate446.g07_v7_active_goal_for_actor(entity, frame, program, states)
        event_id = str(event.event_id) if event is not None else None
        previous = _last_event_by_actor.get(entity)
        if event_id == previous:
            continue
        if previous is not None:
            battle_v2._tactical_memories.pop(entity, None)
            battle_v2._last_tactical_mode.pop(entity, None)
            print(
                json.dumps(
                    {
                        "marker": "GENERIC_BATTLE_EVENT_TACTICAL_MEMORY_RESET",
                        "actorId": entity,
                        "previousEventId": previous,
                        "eventId": event_id,
                        "frame": int(frame),
                        "model": EVENT_LIFECYCLE_MODEL,
                        "persistentActorStateReset": False,
                        "g05ContactTruthReset": False,
                    },
                    sort_keys=True,
                ),
                flush=True,
            )
        _last_event_by_actor[entity] = event_id


def generic_battle_set_controls(
    frame: int,
    program: Any,
    actors: dict[str, Any],
    states: dict[str, Any],
    control_samples: list[dict[str, Any]],
) -> None:
    _enforce_event_scoped_tactical_memory(frame, program, actors, states)
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
    _last_event_by_actor.clear()

    candidate43._ORIGINAL_SET_CONTROLS = generic_battle_set_controls
    candidate44._ORIGINAL_G06_OUTCOME = generic_battle_g06_outcome

    hardened.ConsequenceEngine = VisibleCausalConsequenceEngineV2
    runtime.ConsequenceEngine = VisibleCausalConsequenceEngineV2

    print(
        json.dumps(
            {
                "marker": "GENERIC_AUTONOMOUS_BATTLE_C461_ENGINEERING_READY",
                "candidate": CANDIDATE,
                "mechanism": MECHANISM,
                "eventLifecycleModel": EVENT_LIFECYCLE_MODEL,
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
                "eventScopedTacticalMemory": True,
                "persistentActorDamagePreservedAcrossEvents": True,
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
