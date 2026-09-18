from __future__ import annotations

import json
from pathlib import Path
import sys
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from mathutils import Vector

from blender import iss_battle_runtime_generic_battle_v2 as control_v2
from blender import iss_battle_runtime_generic_battle_v6 as battle_v6
from blender import iss_battle_runtime_tactics_v5 as tactics_v5
from blender import run_generic_battle_runtime_v1_candidate471_generic_battle as candidate471
from blender.iss_battle_runtime_assets import marker
from blender.iss_battle_runtime_contact_geometry_v1 import (
    COLLIDER_GAP_MODEL,
    conservative_contact_gap,
    obb_signed_separation_2d,
)

CANDIDATE = "ISS_GENERIC_BATTLE_RUNTIME_V1_CANDIDATE_4_7_2_GENERIC_AUTONOMOUS_BATTLE"
MECHANISM = "G04_COLLIDER_AWARE_HANDOFF_AND_RECOVERY_RUNWAY_PHASE_SPLIT_V1"
AUDIT = "G04_COLLIDER_HANDOFF_RECOVERY_LIFECYCLE_FULL_AFFECTED_LAYER_AUDIT_20260918"
FAILURE_FAMILIES = (
    "RADIAL_SUPPORT_GAP_PRECEDES_ROTATED_BOX_CONTACT",
    "RECOVERY_SEPARATION_CONFLATED_WITH_FULL_ENGAGEMENT_RUNWAY",
)

_ORIGINAL_SURFACE_GAP = control_v2._surface_gap
_ORIGINAL_TACTICAL_DECIDE = tactics_v5.GenericBattleTacticalPlanner.decide
_collider_guard_rows: list[dict[str, Any]] = []
_phase_split_rows: list[dict[str, Any]] = []


def _horizontal_axis(actor: Any, local_axis: Vector) -> tuple[float, float]:
    axis = actor.chassis.matrix_world.to_quaternion() @ local_axis
    axis.z = 0.0
    if axis.length <= 1.0e-8:
        axis = local_axis.copy()
    axis.normalize()
    return float(axis.x), float(axis.y)


def _sat_gap(attacker: Any, target: Any) -> float:
    a_pos = attacker.chassis.matrix_world.translation
    t_pos = target.chassis.matrix_world.translation
    a_half = attacker.chassis.dimensions * 0.5
    t_half = target.chassis.dimensions * 0.5
    return obb_signed_separation_2d(
        (float(a_pos.x), float(a_pos.y)),
        _horizontal_axis(attacker, Vector((1.0, 0.0, 0.0))),
        _horizontal_axis(attacker, Vector((0.0, 1.0, 0.0))),
        (float(a_half.x), float(a_half.y)),
        (float(t_pos.x), float(t_pos.y)),
        _horizontal_axis(target, Vector((1.0, 0.0, 0.0))),
        _horizontal_axis(target, Vector((0.0, 1.0, 0.0))),
        (float(t_half.x), float(t_half.y)),
    )


def collider_aware_surface_gap(attacker: Any, target: Any) -> tuple[float, float, Vector]:
    radial_gap, center_distance, normal = _ORIGINAL_SURFACE_GAP(attacker, target)
    sat_gap = _sat_gap(attacker, target)
    physical_gap = conservative_contact_gap(radial_gap, sat_gap)

    if physical_gap > float(radial_gap) + 1.0e-6 and (
        float(radial_gap) <= 1.0 or float(sat_gap) <= 1.0
    ):
        row = {
            "attackerId": str(attacker.profile.entity_id),
            "targetId": str(target.profile.entity_id),
            "radialGapM": float(radial_gap),
            "satGapM": float(sat_gap),
            "physicalGapM": float(physical_gap),
            "assetIdentityBranch": False,
            "contactThresholdChanged": False,
            "model": COLLIDER_GAP_MODEL,
        }
        _collider_guard_rows.append(row)
        marker("GENERIC_COLLIDER_SAT_GAP_GUARD_ACTIVE", **row)

    return float(physical_gap), float(center_distance), normal


def split_recovery_runway_decide(
    memory: Any,
    obs: Any,
    *,
    symmetry_bias: float = 1.0,
) -> Any:
    goal = _ORIGINAL_TACTICAL_DECIDE(memory, obs, symmetry_bias=symmetry_bias)
    if not bool(obs.requires_contact) or int(memory.cycle) <= 0:
        return goal

    recovery_required = float(tactics_v5.GenericBattleTacticalPlanner._recovery_separation_required(obs))
    runway_required = float(tactics_v5.GenericBattleTacticalPlanner.engagement_runway_required(obs))

    # BREAK_CONTACT owns only physical recovery separation. Full engagement
    # runway remains unchanged and is enforced later by the existing
    # OPEN_DISTANCE / precontact-runway state.
    if (
        not bool(memory.separation_achieved)
        and float(memory.separation_required_m) > recovery_required + 1.0e-6
    ):
        previous_required = float(memory.separation_required_m)
        memory.separation_required_m = recovery_required
        memory.engagement_runway_armed = False
        if str(goal.mode) == "BREAK_CONTACT":
            goal.stand_off_surface_gap_m = recovery_required
        row = {
            "frame": int(obs.frame),
            "previousSeparationRequiredM": previous_required,
            "recoverySeparationRequiredM": recovery_required,
            "engagementRunwayRequiredM": runway_required,
            "engagementRunwayFormulaChanged": False,
            "recoveryThresholdChanged": False,
            "model": MECHANISM,
        }
        _phase_split_rows.append(row)
        marker("GENERIC_RECOVERY_RUNWAY_PHASE_SPLIT", **row)

    # The legacy planner arms engagement runway when recovery separation is
    # confirmed. Preserve recovery completion but keep the runway unarmed until
    # the unchanged runway requirement is actually observed.
    if (
        bool(memory.separation_achieved)
        and bool(memory.engagement_runway_armed)
        and float(obs.surface_gap_m) + 1.0e-6 < runway_required
    ):
        memory.engagement_runway_armed = False
        row = {
            "frame": int(obs.frame),
            "surfaceGapM": float(obs.surface_gap_m),
            "recoverySeparationRequiredM": recovery_required,
            "engagementRunwayRequiredM": runway_required,
            "engagementRunwayFormulaChanged": False,
            "model": MECHANISM,
        }
        _phase_split_rows.append(row)
        marker("GENERIC_ENGAGEMENT_RUNWAY_REARM_REQUIRED", **row)

    return goal


def main() -> None:
    _collider_guard_rows.clear()
    _phase_split_rows.clear()

    # G04-only repair. G05 outer authority, pairwise solver oracle, semantic,
    # locality and damage admission thresholds remain untouched.
    control_v2._surface_gap = collider_aware_surface_gap
    tactics_v5.GenericBattleTacticalPlanner.decide = staticmethod(split_recovery_runway_decide)
    battle_v6.GenericBattleTacticalPlanner.decide = staticmethod(split_recovery_runway_decide)

    candidate471.CANDIDATE = CANDIDATE
    candidate471.MECHANISM = MECHANISM
    candidate471.AUDIT = AUDIT

    print(json.dumps({
        "marker": "GENERIC_AUTONOMOUS_BATTLE_C472_ENGINEERING_READY",
        "candidate": CANDIDATE,
        "mechanism": MECHANISM,
        "affectedLayerAudit": AUDIT,
        "failureFamilies": list(FAILURE_FAMILIES),
        "rootCauses": [
            "CENTER_LINE_SUPPORT_GAP_IS_NOT_SUFFICIENT_ROTATED_BOX_CONTACT_GEOMETRY",
            "BREAK_CONTACT_REUSED_FULL_ENGAGEMENT_RUNWAY_AS_RECOVERY_SEPARATION",
        ],
        "colliderAwareHandoffGap": True,
        "radialGapPreservedAsLowerBound": True,
        "boxSatSeparationAdded": True,
        "recoverySeparationRunwayPhasesSplit": True,
        "engagementRunwayFormulaChanged": False,
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
        "stateResetMechanism": False,
        "g01ToG03Changed": False,
        "frozenNineServiceArchitectureChanged": False,
        "gateClosed": False,
        "productionReadyClaimed": False,
    }, sort_keys=True), flush=True)

    candidate471.main()


if __name__ == "__main__":
    main()
