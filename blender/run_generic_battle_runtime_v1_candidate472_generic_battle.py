from __future__ import annotations

import json
from pathlib import Path
import sys
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from blender import iss_battle_runtime_generic_battle_v6 as battle_v6
from blender import run_generic_battle_runtime_v1_candidate471_generic_battle as candidate471
from blender.iss_battle_runtime_assets import marker
from blender.iss_battle_runtime_goal_scope_v1 import (
    GOAL_SCOPE_MODEL,
    SAT_GAP_MODEL,
    conservative_physical_gap,
    goal_scope_signature,
    oriented_box_separation_2d,
    rebase_autonomy_progress,
)

CANDIDATE = "ISS_GENERIC_BATTLE_RUNTIME_V1_CANDIDATE_4_7_2_GENERIC_AUTONOMOUS_BATTLE"
MECHANISM = "G04_GOAL_SCOPED_AUTONOMY_AND_SAT_HANDOFF_GEOMETRY_V1"
AUDIT = "G04_GOAL_SCOPE_AND_HANDOFF_GEOMETRY_FULL_AFFECTED_LAYER_AUDIT_20260918"
FAILURE_FAMILY = "TACTICAL_GOAL_SCOPE_LEAK_AND_CENTERLINE_GAP_EARLY_HANDOFF"

_ORIGINAL_SURFACE_GAP = battle_v6.control_v2._surface_gap
_ORIGINAL_AUTONOMY_UPDATE = battle_v6.ClosedLoopGoalController.update

_goal_scope_by_memory: dict[int, tuple[bool, str]] = {}
_goal_scope_rebases: list[dict[str, Any]] = []
_sat_guard_rows: list[dict[str, Any]] = []


def _entity_for_memory(memory: Any) -> tuple[str | None, str | None]:
    for key, value in battle_v6._autonomy_memories.items():
        if value is memory:
            return str(key[0]), str(key[1])
    return None, None


def _actor_sat_gap(actor: Any, target: Any) -> float:
    pa = actor.chassis.matrix_world.translation
    pb = target.chassis.matrix_world.translation
    qa = actor.chassis.matrix_world.to_quaternion()
    qb = target.chassis.matrix_world.to_quaternion()
    ax = qa @ battle_v6.Vector((1.0, 0.0, 0.0))
    ay = qa @ battle_v6.Vector((0.0, 1.0, 0.0))
    bx = qb @ battle_v6.Vector((1.0, 0.0, 0.0))
    by = qb @ battle_v6.Vector((0.0, 1.0, 0.0))
    half_a = actor.chassis.dimensions * 0.5
    half_b = target.chassis.dimensions * 0.5
    return oriented_box_separation_2d(
        (float(pb.x - pa.x), float(pb.y - pa.y)),
        (float(ax.x), float(ax.y)),
        (float(ay.x), float(ay.y)),
        (float(half_a.x), float(half_a.y)),
        (float(bx.x), float(bx.y)),
        (float(by.x), float(by.y)),
        (float(half_b.x), float(half_b.y)),
    )


def sat_aware_surface_gap(actor: Any, target: Any) -> tuple[float, float, Any]:
    base_gap, center_distance, normal = _ORIGINAL_SURFACE_GAP(actor, target)
    sat_gap = _actor_sat_gap(actor, target)
    effective_gap = conservative_physical_gap(float(base_gap), float(sat_gap))
    if float(base_gap) <= 0.30 and float(sat_gap) > float(base_gap) + 0.02:
        row = {
            "attackerId": str(actor.profile.entity_id),
            "targetId": str(target.profile.entity_id),
            "centerlineSupportGapM": float(base_gap),
            "satSeparationM": float(sat_gap),
            "effectivePhysicalGapM": float(effective_gap),
            "g05ContactAuthorityChanged": False,
            "contactThresholdChanged": False,
            "model": SAT_GAP_MODEL,
        }
        _sat_guard_rows.append(row)
        if len(_sat_guard_rows) <= 32:
            marker("G04_SAT_GAP_PREVENTED_EARLY_HANDOFF", **row)
    return float(effective_gap), center_distance, normal


def goal_scoped_autonomy_update(
    memory: Any,
    obs: Any,
    *,
    recovery_bias: float = 1.0,
) -> Any:
    key = id(memory)
    current = goal_scope_signature(bool(obs.requires_contact), str(obs.speed_intent))
    previous = _goal_scope_by_memory.get(key)
    if previous is None:
        _goal_scope_by_memory[key] = current
    elif previous != current:
        event_id, actor_id = _entity_for_memory(memory)
        receipt = rebase_autonomy_progress(memory, obs)
        row = {
            "frame": int(obs.frame),
            "eventId": event_id,
            "actorId": actor_id,
            "previousRequiresContact": bool(previous[0]),
            "previousSpeedIntent": str(previous[1]),
            "requiresContact": bool(current[0]),
            "speedIntent": str(current[1]),
            "attemptLedgerPreserved": receipt["before"]["attempt"] == receipt["after"]["attempt"],
            "replanLedgerPreserved": receipt["before"]["replans"] == receipt["after"]["replans"],
            "contactHistoryPreserved": receipt["before"]["lastContactCount"] == receipt["after"]["lastContactCount"],
            "damageHistoryPreserved": receipt["before"]["lastDamageCount"] == receipt["after"]["lastDamageCount"],
            "model": GOAL_SCOPE_MODEL,
        }
        _goal_scope_rebases.append(row)
        marker("G04_AUTONOMY_GOAL_SCOPE_REBASED", **row)
        _goal_scope_by_memory[key] = current

    if not bool(obs.requires_contact):
        memory.near_seen = False

    return _ORIGINAL_AUTONOMY_UPDATE(
        memory,
        obs,
        recovery_bias=recovery_bias,
    )


def main() -> None:
    _goal_scope_by_memory.clear()
    _goal_scope_rebases.clear()
    _sat_guard_rows.clear()

    battle_v6.control_v2._surface_gap = sat_aware_surface_gap
    battle_v6.ClosedLoopGoalController.update = staticmethod(goal_scoped_autonomy_update)

    candidate471.CANDIDATE = CANDIDATE
    candidate471.MECHANISM = MECHANISM
    candidate471.AUDIT = AUDIT

    print(json.dumps({
        "marker": "GENERIC_AUTONOMOUS_BATTLE_C472_ENGINEERING_READY",
        "candidate": CANDIDATE,
        "mechanism": MECHANISM,
        "affectedLayerAudit": AUDIT,
        "failureFamily": FAILURE_FAMILY,
        "rootCause": "AUTONOMY_PROGRESS_MEMORY_SPANS_INCOMPATIBLE_TACTICAL_GOALS_AND_CENTERLINE_GAP_CAN_PRECEDE_TRUE_OBB_ADJACENCY",
        "goalScopeProgressRebase": True,
        "nonContactMissClassificationBlocked": True,
        "satAwareG04PhysicalGap": True,
        "g05ContactAuthorityChanged": False,
        "existingG05OuterAuthorityGatePreserved": True,
        "existingPairwiseSolverOraclePreserved": True,
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
        "battleStateReset": False,
        "contactDamageHistoryReset": False,
        "g01ToG03Changed": False,
        "frozenNineServiceArchitectureChanged": False,
        "gateClosed": False,
        "productionReadyClaimed": False,
    }, sort_keys=True), flush=True)

    candidate471.main()


if __name__ == "__main__":
    main()
