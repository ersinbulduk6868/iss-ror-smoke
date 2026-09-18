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
from blender import iss_battle_runtime_generic_battle_v2 as control_v2
from blender import run_generic_battle_runtime_v1_candidate471_generic_battle as candidate471
from blender.iss_battle_runtime_assets import marker
from blender.iss_battle_runtime_control_contract_v1 import (
    COLLISION_PROXY_PROXIMITY_MODEL,
    TACTICAL_AUTONOMY_OWNERSHIP_MODEL,
    effective_collision_proxy_gap,
    obb_signed_separation_2d,
    should_clear_stale_autonomy_recovery,
)

CANDIDATE = "ISS_GENERIC_BATTLE_RUNTIME_V1_CANDIDATE_4_7_2_GENERIC_AUTONOMOUS_BATTLE"
MECHANISM = "G04_OBB_HANDOFF_AND_TACTICAL_RECOVERY_OWNERSHIP_V1"
AUDIT = "G04_G05_HANDOFF_AND_RECOVERY_FULL_AFFECTED_LAYER_AUDIT_20260918"
FAILURE_FAMILY = "RADIAL_HANDOFF_FALSE_PROXIMITY_AND_STALE_AUTONOMY_RECOVERY"

_ORIGINAL_SURFACE_GAP = control_v2._surface_gap
_ORIGINAL_TACTICAL_DECIDE = battle_v6.GenericBattleTacticalPlanner.decide
_ORIGINAL_AUTONOMY_UPDATE = battle_v6.ClosedLoopGoalController.update

_pending_tactical_context: dict[str, Any] | None = None
_obb_mismatch_active: set[tuple[str, str]] = set()
_obb_mismatch_rows: list[dict[str, Any]] = []
_recovery_clear_rows: list[dict[str, Any]] = []


def _axis_xy(actor: Any, local: tuple[float, float, float]) -> tuple[float, float]:
    axis = actor.chassis.matrix_world.to_quaternion() @ Vector(local)
    axis.z = 0.0
    if axis.length <= 1.0e-8:
        raise RuntimeError("G04_OBB_AXIS_DEGENERATE")
    axis.normalize()
    return float(axis.x), float(axis.y)


def collision_proxy_surface_gap(attacker: Any, target: Any) -> tuple[float, float, Vector]:
    radial_gap, center_distance, normal = _ORIGINAL_SURFACE_GAP(attacker, target)
    delta = target.chassis.matrix_world.translation - attacker.chassis.matrix_world.translation
    sat_gap = obb_signed_separation_2d(
        center_delta_xy=(float(delta.x), float(delta.y)),
        actor_x_axis_xy=_axis_xy(attacker, (1.0, 0.0, 0.0)),
        actor_y_axis_xy=_axis_xy(attacker, (0.0, 1.0, 0.0)),
        target_x_axis_xy=_axis_xy(target, (1.0, 0.0, 0.0)),
        target_y_axis_xy=_axis_xy(target, (0.0, 1.0, 0.0)),
        actor_half_extents_xy=(
            float(attacker.chassis.dimensions.x) * 0.5,
            float(attacker.chassis.dimensions.y) * 0.5,
        ),
        target_half_extents_xy=(
            float(target.chassis.dimensions.x) * 0.5,
            float(target.chassis.dimensions.y) * 0.5,
        ),
    )
    effective_gap = effective_collision_proxy_gap(radial_gap, sat_gap)

    attacker_id = str(attacker.profile.entity_id)
    target_id = str(target.profile.entity_id)
    key = (attacker_id, target_id)
    false_radial_overlap = float(radial_gap) <= 0.0 < float(sat_gap)
    if false_radial_overlap and key not in _obb_mismatch_active:
        _obb_mismatch_active.add(key)
        row = {
            "attackerId": attacker_id,
            "targetId": target_id,
            "radialGapM": float(radial_gap),
            "obbSatSeparationM": float(sat_gap),
            "effectiveGapM": float(effective_gap),
            "model": COLLISION_PROXY_PROXIMITY_MODEL,
        }
        _obb_mismatch_rows.append(row)
        marker("G04_RADIAL_OVERLAP_REJECTED_BY_OBB_SEPARATION", **row)
    elif not false_radial_overlap:
        _obb_mismatch_active.discard(key)

    return float(effective_gap), float(center_distance), normal


def tactical_decide_with_ownership_context(
    memory: Any,
    obs: Any,
    *,
    symmetry_bias: float = 1.0,
) -> Any:
    global _pending_tactical_context
    previous_mode = str(memory.mode or "")
    goal = _ORIGINAL_TACTICAL_DECIDE(
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


def ownership_aware_autonomy_update(
    memory: Any,
    obs: Any,
    *,
    recovery_bias: float = 1.0,
) -> Any:
    global _pending_tactical_context
    context = _pending_tactical_context or {}
    clear = should_clear_stale_autonomy_recovery(
        previous_tactical_mode=context.get("previousTacticalMode"),
        current_tactical_mode=str(context.get("currentTacticalMode") or ""),
        tactical_transition=bool(context.get("tacticalTransition")),
        autonomy_mode=str(memory.mode or ""),
        speed_intent=str(context.get("speedIntent") or obs.speed_intent or ""),
    )
    if clear:
        previous_controller_mode = str(memory.mode)
        previous_controller_reason = str(memory.reason)
        memory.mode = "TRACK"
        memory.reason = "TACTICAL_FORWARD_OWNERSHIP"
        memory.recovery_reverse_until = 0
        memory.recovery_turn_until = 0
        memory.last_progress_frame = int(obs.frame)
        memory.best_distance_m = float(obs.distance_m)
        memory.last_distance_m = float(obs.distance_m)
        memory.last_surface_gap_m = float(obs.surface_gap_m)
        memory.last_command_speed_mps = 0.0
        memory.near_seen = False
        row = {
            "frame": int(obs.frame),
            "previousTacticalMode": context.get("previousTacticalMode"),
            "currentTacticalMode": context.get("currentTacticalMode"),
            "previousControllerMode": previous_controller_mode,
            "previousControllerReason": previous_controller_reason,
            "speedIntent": context.get("speedIntent"),
            "tacticalReason": context.get("tacticalReason"),
            "cycle": context.get("cycle"),
            "model": TACTICAL_AUTONOMY_OWNERSHIP_MODEL,
        }
        _recovery_clear_rows.append(row)
        marker("G04_STALE_AUTONOMY_RECOVERY_CLEARED", **row)

    try:
        return _ORIGINAL_AUTONOMY_UPDATE(
            memory,
            obs,
            recovery_bias=recovery_bias,
        )
    finally:
        _pending_tactical_context = None


def main() -> None:
    global _pending_tactical_context
    _pending_tactical_context = None
    _obb_mismatch_active.clear()
    _obb_mismatch_rows.clear()
    _recovery_clear_rows.clear()

    # G04 controller proximity is now bound to the same rigid chassis BOX proxies
    # used by Blender physics. This does not declare contact; G05 native solver
    # response remains the sole final authority.
    control_v2._surface_gap = collision_proxy_surface_gap

    # Tactical recovery owns BREAK_CONTACT/REPOSITION. Once the planner explicitly
    # transitions back to a forward tactical mode, stale low-level RECOVER_* state
    # may no longer override that new plan. Low-level recovery remains unchanged in
    # every other case.
    battle_v6.GenericBattleTacticalPlanner.decide = staticmethod(
        tactical_decide_with_ownership_context
    )
    battle_v6.ClosedLoopGoalController.update = staticmethod(
        ownership_aware_autonomy_update
    )

    print(json.dumps({
        "marker": "GENERIC_AUTONOMOUS_BATTLE_C472_ENGINEERING_READY",
        "candidate": CANDIDATE,
        "mechanism": MECHANISM,
        "affectedLayerAudit": AUDIT,
        "failureFamily": FAILURE_FAMILY,
        "rootCauses": [
            "RADIAL_SUPPORT_GAP_CAN_REPORT_FALSE_COLLISION_PROXIMITY_FOR_ANGLED_OBB_PAIR",
            "LOW_LEVEL_RECOVERY_CAN_OUTLIVE_TACTICAL_REENGAGEMENT_TRANSITION",
        ],
        "rigidBodyObbSatProximity": True,
        "radialGapStillPreservedAsConservativeAxis": True,
        "g05NativeSolverFinalAuthorityPreserved": True,
        "tacticalRecoveryOwnershipReconciled": True,
        "controllerRecoveryStateReconciledOnTacticalTransition": True,
        "lowLevelRecoveryOtherwisePreserved": True,
        "worldStateResetMechanism": False,
        "c471TransactionBoundedLocalityPreserved": True,
        "c470LivePairSurfaceSemanticSelectionPreserved": True,
        "c469CutoffCleanupPreserved": True,
        "c468RecencyBudgetPreserved": True,
        "pairwiseSolverOraclePreserved": True,
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
        "g01ToG03Changed": False,
        "frozenNineServiceArchitectureChanged": False,
        "gateClosed": False,
        "productionReadyClaimed": False,
    }, sort_keys=True), flush=True)

    candidate471.main()


if __name__ == "__main__":
    main()
