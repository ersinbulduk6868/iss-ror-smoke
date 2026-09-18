from __future__ import annotations

import json
from pathlib import Path
import sys
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from mathutils import Vector

from blender import iss_battle_runtime_generic_battle_v6 as battle_v6
from blender import iss_blender_battle_runtime_v1 as runtime
from blender import run_generic_battle_runtime_v1_candidate467_generic_battle as candidate467
from blender import run_generic_battle_runtime_v1_candidate471_generic_battle as candidate471
from blender.iss_battle_runtime_assets import marker
from blender.iss_battle_runtime_pursuit_v1 import (
    PURSUIT_MODEL,
    capability_bounded_lead_seconds,
    predicted_target_xy,
)

CANDIDATE = "ISS_GENERIC_BATTLE_RUNTIME_V1_CANDIDATE_4_7_2_GENERIC_AUTONOMOUS_BATTLE"
MECHANISM = PURSUIT_MODEL
AUDIT = "G04_MOVING_TARGET_REACQUISITION_FULL_AFFECTED_LAYER_AUDIT_20260918"
FAILURE_FAMILY = "MOVING_TARGET_POINT_CHASE_FAILS_TO_REACQUIRE_CONTACT"

_ORIGINAL_GOAL_FOR_TACTICAL = battle_v6._goal_for_tactical
_pursuit_rows: list[dict[str, Any]] = []
_last_marker_frame: dict[tuple[str, str], int] = {}


def _latest_frame(actor: Any, target: Any) -> int | None:
    actor_frames = set(int(x) for x in actor.velocity.keys())
    target_frames = set(int(x) for x in target.velocity.keys())
    shared = actor_frames & target_frames
    return max(shared) if shared else None


def live_intercept_goal_for_tactical(
    actor: Any,
    target: Any,
    event: Any,
    tactical: Any,
    actors: dict[str, Any],
) -> Vector:
    # Preserve every non-direct tactic and every story-prescribed semantic target.
    if tactical.mode not in {"ENGAGE", "COUNTER"}:
        return _ORIGINAL_GOAL_FOR_TACTICAL(actor, target, event, tactical, actors)
    if str(event.event_id) not in candidate467.candidate443._auto_engagement_events:
        return _ORIGINAL_GOAL_FOR_TACTICAL(actor, target, event, tactical, actors)

    frame = _latest_frame(actor, target)
    if frame is None:
        return _ORIGINAL_GOAL_FOR_TACTICAL(actor, target, event, tactical, actors)

    actor_pos = actor.chassis.matrix_world.translation.copy()
    target_pos = target.chassis.matrix_world.translation.copy()
    actor_velocity = actor.velocity.get(frame, Vector((0.0, 0.0, 0.0))).copy()
    target_velocity = target.velocity.get(frame, Vector((0.0, 0.0, 0.0))).copy()
    relative = target_pos - actor_pos
    relative.z = 0.0
    target_velocity.z = 0.0

    effective_speed = (
        float(actor.profile.max_speed_mps)
        * max(0.10, float(tactical.speed_scale))
        * max(0.15, float(actor.state.drive_efficiency))
    )
    lead_seconds = capability_bounded_lead_seconds(
        relative_xy=(float(relative.x), float(relative.y)),
        target_velocity_xy=(float(target_velocity.x), float(target_velocity.y)),
        pursuer_speed_mps=effective_speed,
        max_yaw_rate_rad_s=float(actor.profile.max_yaw_rate_rad_s),
        characteristic_length_m=max(0.25, float(actor.dimensions.x)),
    )
    predicted_x, predicted_y = predicted_target_xy(
        target_xy=(float(target_pos.x), float(target_pos.y)),
        target_velocity_xy=(float(target_velocity.x), float(target_velocity.y)),
        lead_seconds=lead_seconds,
    )
    desired = Vector((predicted_x, predicted_y, float(target_pos.z)))

    avoidance = getattr(runtime, "_reactive_avoidance", None)
    if callable(avoidance):
        desired = avoidance(actor, desired, actors, event.target_id)

    row = {
        "frame": int(frame),
        "eventId": str(event.event_id),
        "actorId": str(actor.profile.entity_id),
        "targetId": str(event.target_id or ""),
        "tacticalMode": str(tactical.mode),
        "leadSeconds": float(lead_seconds),
        "relativeDistanceM": float(relative.length),
        "actorSpeedCapabilityMps": float(effective_speed),
        "targetObservedSpeedMps": float(target_velocity.length),
        "goalAuthority": "LIVE_PAIR_CENTER_AND_CURRENT_TARGET_VELOCITY",
        "storyTargetZonePrescribed": False,
        "assetIdentityBranch": False,
        "fixedWorldCoordinate": False,
        "cachedTrajectory": False,
        "exactCollisionFrameTarget": False,
        "exactImpactEnergyTarget": False,
        "model": PURSUIT_MODEL,
    }
    _pursuit_rows.append(row)
    key = (row["eventId"], row["actorId"])
    previous = _last_marker_frame.get(key)
    if previous is None or int(frame) - int(previous) >= 30:
        _last_marker_frame[key] = int(frame)
        marker("G04_LIVE_INTERCEPT_GOAL_APPLIED", **row)
    return desired


def main() -> None:
    _pursuit_rows.clear()
    _last_marker_frame.clear()

    # C472 changes only G04's generic direct-engagement goal producer.  C471's
    # transaction-bounded G05 evidence, C470 semantic-surface handoff, all G05
    # thresholds/oracles and G06/G07/G08 contracts remain unchanged.
    battle_v6._goal_for_tactical = live_intercept_goal_for_tactical

    candidate471.CANDIDATE = CANDIDATE
    candidate471.MECHANISM = MECHANISM
    candidate471.AUDIT = AUDIT

    print(json.dumps({
        "marker": "GENERIC_AUTONOMOUS_BATTLE_C472_ENGINEERING_READY",
        "candidate": CANDIDATE,
        "mechanism": MECHANISM,
        "affectedLayerAudit": AUDIT,
        "failureFamily": FAILURE_FAMILY,
        "rootCause": "DIRECT_ENGAGEMENT_CHASES_MOVING_SEMANTIC_POINT_WITHOUT_PAIR_CENTER_INTERCEPT",
        "g04OwnsLivePursuitGoal": True,
        "runtimeSelectedGenericEngagementOnly": True,
        "storyPrescribedSemanticTargetPreserved": True,
        "liveTargetVelocityObserved": True,
        "actorProfileCapabilityBounded": True,
        "goalRecomputedEveryFrame": True,
        "cachedTrajectory": False,
        "c471TransactionSamplingPreserved": True,
        "c470SemanticSurfaceHandoffPreserved": True,
        "existingG05OuterAuthorityGatePreserved": True,
        "existingPairwiseSolverOraclePreserved": True,
        "semanticToleranceChanged": False,
        "localityToleranceChanged": False,
        "contactThresholdChanged": False,
        "damageAdmissionThresholdChanged": False,
        "fixtureMutationForAcceptance": False,
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
        "gateClosed": False,
        "productionReadyClaimed": False,
    }, sort_keys=True), flush=True)

    candidate471.main()


if __name__ == "__main__":
    main()
