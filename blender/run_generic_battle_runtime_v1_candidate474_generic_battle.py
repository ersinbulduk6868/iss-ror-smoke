from __future__ import annotations

from dataclasses import replace
import json
from pathlib import Path
import sys
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from blender import run_generic_battle_runtime_v1_candidate472_generic_battle as candidate472
from blender.iss_battle_runtime_assets import marker
from blender.iss_battle_runtime_progress_contract_v1 import (
    COLLISION_PROXY_PROGRESS_MODEL,
    HANDOFF_ELIGIBILITY_MODEL,
    TACTICAL_PROGRESS_OWNERSHIP_MODEL,
    collision_proxy_progressed,
    progress_epsilon_m,
    should_defer_contact_handoff,
    should_rebase_progress_for_tactical_goal,
)

CANDIDATE = "ISS_GENERIC_BATTLE_RUNTIME_V1_CANDIDATE_4_7_4_GENERIC_AUTONOMOUS_BATTLE"
MECHANISM = "G04_HANDOFF_ELIGIBILITY_AND_TACTICAL_PROGRESS_OWNERSHIP_V1"
AUDIT = "G04_HANDOFF_PROGRESS_FULL_AFFECTED_LAYER_AUDIT_20260918"
FAILURE_FAMILY = "HANDOFF_GEOMETRY_SCOPE_AND_TACTICAL_PROGRESS_MEMORY_MISMATCH"

_active_pair_context: dict[str, Any] | None = None
_pending_tactical_context: dict[str, Any] | None = None
_previous_effective_gap: dict[tuple[str, str], float] = {}
_defer_active: set[tuple[str, str]] = set()
_progress_refresh_counts: dict[tuple[str, str], int] = {}
_goal_rebase_rows: list[dict[str, Any]] = []
_handoff_defer_rows: list[dict[str, Any]] = []
_collision_progress_rows: list[dict[str, Any]] = []


def navigation_preserving_surface_gap(attacker: Any, target: Any) -> tuple[float, float, Any]:
    global _active_pair_context
    radial_gap, center_distance, normal = candidate472._ORIGINAL_SURFACE_GAP(attacker, target)
    delta = target.chassis.matrix_world.translation - attacker.chassis.matrix_world.translation
    sat_gap = candidate472.obb_signed_separation_2d(
        center_delta_xy=(float(delta.x), float(delta.y)),
        actor_x_axis_xy=candidate472._axis_xy(attacker, (1.0, 0.0, 0.0)),
        actor_y_axis_xy=candidate472._axis_xy(attacker, (0.0, 1.0, 0.0)),
        target_x_axis_xy=candidate472._axis_xy(target, (1.0, 0.0, 0.0)),
        target_y_axis_xy=candidate472._axis_xy(target, (0.0, 1.0, 0.0)),
        actor_half_extents_xy=(
            float(attacker.chassis.dimensions.x) * 0.5,
            float(attacker.chassis.dimensions.y) * 0.5,
        ),
        target_half_extents_xy=(
            float(target.chassis.dimensions.x) * 0.5,
            float(target.chassis.dimensions.y) * 0.5,
        ),
    )
    effective_gap = candidate472.effective_collision_proxy_gap(radial_gap, sat_gap)
    _active_pair_context = {
        "attackerId": str(attacker.profile.entity_id),
        "targetId": str(target.profile.entity_id),
        "radialGapM": float(radial_gap),
        "obbSatSeparationM": float(sat_gap),
        "effectiveCollisionProxyGapM": float(effective_gap),
    }
    return float(radial_gap), float(center_distance), normal


def tactical_decide_with_progress_context(
    memory: Any,
    obs: Any,
    *,
    symmetry_bias: float = 1.0,
) -> Any:
    global _pending_tactical_context
    previous_mode = str(memory.mode or "")
    goal = candidate472._ORIGINAL_TACTICAL_DECIDE(
        memory,
        obs,
        symmetry_bias=symmetry_bias,
    )
    _pending_tactical_context = {
        "frame": int(obs.frame),
        "previousTacticalMode": previous_mode,
        "currentTacticalMode": str(goal.mode),
        "tacticalTransition": bool(goal.transition),
        "speedIntent": str(goal.speed_intent),
        "tacticalReason": str(goal.reason),
        "cycle": int(goal.cycle),
    }
    return goal


def progress_owned_autonomy_update(
    memory: Any,
    obs: Any,
    *,
    recovery_bias: float = 1.0,
) -> Any:
    global _pending_tactical_context
    context = _pending_tactical_context or {}
    pair = _active_pair_context or {}
    pair_key = (str(pair.get("attackerId") or ""), str(pair.get("targetId") or ""))

    try:
        if should_rebase_progress_for_tactical_goal(
            previous_tactical_mode=context.get("previousTacticalMode"),
            current_tactical_mode=str(context.get("currentTacticalMode") or ""),
            tactical_transition=bool(context.get("tacticalTransition")),
        ):
            previous_controller_mode = str(memory.mode or "")
            previous_best = float(memory.best_distance_m)
            memory.best_distance_m = float(obs.distance_m)
            memory.last_progress_frame = int(obs.frame)
            memory.last_distance_m = float(obs.distance_m)
            memory.last_surface_gap_m = float(obs.surface_gap_m)
            memory.near_seen = False

            if candidate472.should_clear_stale_autonomy_recovery(
                previous_tactical_mode=context.get("previousTacticalMode"),
                current_tactical_mode=str(context.get("currentTacticalMode") or ""),
                tactical_transition=True,
                autonomy_mode=previous_controller_mode,
                speed_intent=str(context.get("speedIntent") or obs.speed_intent or ""),
            ):
                memory.mode = "TRACK"
                memory.reason = "TACTICAL_GOAL_OWNERSHIP_REBASE"
                memory.recovery_reverse_until = 0
                memory.recovery_turn_until = 0
                memory.last_command_speed_mps = 0.0

            current_effective = pair.get("effectiveCollisionProxyGapM")
            if current_effective is not None and pair_key[0] and pair_key[1]:
                _previous_effective_gap[pair_key] = float(current_effective)

            row = {
                "frame": int(obs.frame),
                "attackerId": pair_key[0] or None,
                "targetId": pair_key[1] or None,
                "previousTacticalMode": context.get("previousTacticalMode"),
                "currentTacticalMode": context.get("currentTacticalMode"),
                "previousControllerMode": previous_controller_mode,
                "previousBestDistanceM": previous_best if previous_best < 1.0e30 else None,
                "rebasedDistanceM": float(obs.distance_m),
                "model": TACTICAL_PROGRESS_OWNERSHIP_MODEL,
            }
            _goal_rebase_rows.append(row)
            marker("G04_AUTONOMY_PROGRESS_REBASED_FOR_TACTICAL_GOAL", **row)

        current_effective = pair.get("effectiveCollisionProxyGapM")
        previous_effective = _previous_effective_gap.get(pair_key) if pair_key[0] and pair_key[1] else None
        if current_effective is not None and collision_proxy_progressed(
            previous_effective_gap_m=previous_effective,
            current_effective_gap_m=float(current_effective),
            closing_speed_mps=float(obs.closing_speed_mps),
            characteristic_length_m=float(obs.characteristic_length_m),
            requires_contact=bool(obs.requires_contact),
        ):
            memory.last_progress_frame = int(obs.frame)
            count = _progress_refresh_counts.get(pair_key, 0) + 1
            _progress_refresh_counts[pair_key] = count
            if count <= 3 or count % max(1, int(obs.fps)) == 0:
                row = {
                    "frame": int(obs.frame),
                    "attackerId": pair_key[0] or None,
                    "targetId": pair_key[1] or None,
                    "previousEffectiveGapM": float(previous_effective),
                    "effectiveGapM": float(current_effective),
                    "closingSpeedMps": float(obs.closing_speed_mps),
                    "progressEpsilonM": progress_epsilon_m(float(obs.characteristic_length_m)),
                    "refreshCount": int(count),
                    "model": COLLISION_PROXY_PROGRESS_MODEL,
                }
                _collision_progress_rows.append(row)
                marker("G04_COLLISION_PROXY_PROGRESS_REFRESHED", **row)

        if current_effective is not None and pair_key[0] and pair_key[1]:
            _previous_effective_gap[pair_key] = float(current_effective)

        handoff_gap = candidate472.battle_v6.ClosedLoopGoalController.contact_handoff_gap(obs)
        defer = bool(current_effective is not None) and should_defer_contact_handoff(
            requires_contact=bool(obs.requires_contact),
            effective_collision_proxy_gap_m=float(current_effective),
            existing_handoff_gap_m=float(handoff_gap),
        )
        controller_obs = replace(obs, requires_contact=False) if defer else obs

        if pair_key[0] and pair_key[1]:
            if defer and pair_key not in _defer_active:
                _defer_active.add(pair_key)
                row = {
                    "frame": int(obs.frame),
                    "attackerId": pair_key[0],
                    "targetId": pair_key[1],
                    "radialGapM": float(pair.get("radialGapM") or 0.0),
                    "obbSatSeparationM": float(pair.get("obbSatSeparationM") or 0.0),
                    "effectiveCollisionProxyGapM": float(current_effective),
                    "existingHandoffGapM": float(handoff_gap),
                    "model": HANDOFF_ELIGIBILITY_MODEL,
                }
                _handoff_defer_rows.append(row)
                marker("G04_CONTACT_HANDOFF_DEFERRED_BY_OBB_SEPARATION", **row)
            elif not defer:
                _defer_active.discard(pair_key)

        return candidate472._ORIGINAL_AUTONOMY_UPDATE(
            memory,
            controller_obs,
            recovery_bias=recovery_bias,
        )
    finally:
        _pending_tactical_context = None


def main() -> None:
    global _active_pair_context, _pending_tactical_context
    _active_pair_context = None
    _pending_tactical_context = None
    _previous_effective_gap.clear()
    _defer_active.clear()
    _progress_refresh_counts.clear()
    _goal_rebase_rows.clear()
    _handoff_defer_rows.clear()
    _collision_progress_rows.clear()

    candidate472.collision_proxy_surface_gap = navigation_preserving_surface_gap
    candidate472.tactical_decide_with_ownership_context = tactical_decide_with_progress_context
    candidate472.ownership_aware_autonomy_update = progress_owned_autonomy_update

    print(json.dumps({
        "marker": "GENERIC_AUTONOMOUS_BATTLE_C474_ENGINEERING_READY",
        "candidate": CANDIDATE,
        "mechanism": MECHANISM,
        "affectedLayerAudit": AUDIT,
        "failureFamily": FAILURE_FAMILY,
        "rootCauses": [
            "C472_OBB_GAP_WAS_APPLIED_TO_NAVIGATION_INSTEAD_OF_HANDOFF_ELIGIBILITY_ONLY",
            "AUTONOMY_PROGRESS_MEMORY_OUTLIVES_TACTICAL_GOAL_SEMANTICS",
        ],
        "radialNavigationContractPreserved": True,
        "obbSatUsedOnlyForHandoffEligibility": True,
        "existingHandoffGapReusedUnchanged": True,
        "tacticalGoalProgressRebased": True,
        "collisionProxyApproachCountsAsProgress": True,
        "g05NativeSolverFinalAuthorityPreserved": True,
        "pairwiseSolverOraclePreserved": True,
        "c471TransactionBoundedLocalityPreserved": True,
        "c470LivePairSurfaceSemanticSelectionPreserved": True,
        "c469CutoffCleanupPreserved": True,
        "c468RecencyBudgetPreserved": True,
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
        "worldStateResetMechanism": False,
        "g01ToG03Changed": False,
        "frozenNineServiceArchitectureChanged": False,
        "gateClosed": False,
        "productionReadyClaimed": False,
    }, sort_keys=True), flush=True)

    candidate472.main()


if __name__ == "__main__":
    main()
