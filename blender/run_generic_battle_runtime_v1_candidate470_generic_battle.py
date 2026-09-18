from __future__ import annotations

import json
from pathlib import Path
import sys
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from blender import iss_battle_runtime_generic_battle_v6 as battle_v6
from blender import run_generic_battle_runtime_v1_candidate42 as candidate42
from blender import run_generic_battle_runtime_v1_candidate467_generic_battle as candidate467
from blender import run_generic_battle_runtime_v1_candidate469_generic_battle as candidate469
from blender.iss_battle_runtime_assets import marker
from blender.iss_battle_runtime_handoff_v4 import (
    SEMANTIC_SURFACE_TRANSACTION_MODEL,
    select_semantic_zone_for_local_surface,
)

CANDIDATE = "ISS_GENERIC_BATTLE_RUNTIME_V1_CANDIDATE_4_7_0_GENERIC_AUTONOMOUS_BATTLE"
MECHANISM = SEMANTIC_SURFACE_TRANSACTION_MODEL
AUDIT = "G05_HANDOFF_SEMANTIC_SURFACE_FULL_AFFECTED_LAYER_AUDIT_20260918"
FAILURE_FAMILY = "HANDOFF_ZONE_LABEL_DRIFTS_FROM_LIVE_PAIR_CONTACT_SURFACE"

_ORIGINAL_C469_SET_CONTROLS = candidate469.transaction_clean_set_controls
_surface_refinements: list[dict[str, Any]] = []


def _event_by_id(program: Any, event_id: str) -> Any | None:
    for event in program.events:
        if str(event.event_id) == str(event_id):
            return event
    return None


def _refine_fresh_handoff_surface(
    frame: int,
    program: Any,
    actors: dict[str, Any],
    before_start_frames: dict[tuple[str, str], int],
) -> None:
    for key, latch in tuple(battle_v6._handoff_latches.items()):
        old_start = before_start_frames.get(key)
        if old_start is not None and int(old_start) == int(latch.start_frame):
            continue

        event_id, actor_id = str(key[0]), str(key[1])
        event = _event_by_id(program, event_id)
        if event is None or not event.target_id:
            continue
        # Only runtime-selected generic engagement surfaces may be refined.
        # Story-prescribed semantic targets remain authoritative.
        if event_id not in candidate467.candidate443._auto_engagement_events:
            continue
        if actor_id not in actors or str(event.target_id) not in actors:
            continue

        attacker = actors[actor_id]
        target = actors[str(event.target_id)]
        geometry = candidate42._pair_geometry_at(attacker, target, int(latch.start_frame))
        if geometry is None:
            geometry = candidate42._pair_geometry_at(attacker, target, int(frame))
        if geometry is None:
            continue

        surface_world = geometry["targetSurface"]
        local_surface = geometry["targetRotation"].inverted() @ (
            surface_world - geometry["targetPosition"]
        )
        selected_zone, local_distance = select_semantic_zone_for_local_surface(
            local_surface,
            target.prototype.zones,
            target.visual_offset,
        )
        previous_zone = event.target_zone
        event.target_zone = selected_zone
        row = {
            "frame": int(frame),
            "eventId": event_id,
            "actorId": actor_id,
            "targetId": str(event.target_id),
            "handoffStartFrame": int(latch.start_frame),
            "previousSemanticZone": previous_zone,
            "selectedSemanticZone": selected_zone,
            "surfaceToSemanticZoneDistanceM": float(local_distance),
            "selectionAuthority": "LIVE_PAIR_GEOMETRY_AND_AVAILABLE_ASSET_SEMANTICS",
            "storyTargetZonePrescribed": False,
            "assetIdentityBranch": False,
            "fixedWorldCoordinate": False,
            "semanticToleranceChanged": False,
            "localityToleranceChanged": False,
            "contactThresholdChanged": False,
            "model": SEMANTIC_SURFACE_TRANSACTION_MODEL,
        }
        _surface_refinements.append(row)
        marker("GENERIC_HANDOFF_LIVE_PAIR_SURFACE_REFINED", **row)


def surface_transaction_set_controls(
    frame: int,
    program: Any,
    actors: dict[str, Any],
    states: dict[str, Any],
    control_samples: list[dict[str, Any]],
    *,
    active_goal_resolver: Any,
) -> None:
    before_start_frames = {
        key: int(latch.start_frame)
        for key, latch in battle_v6._handoff_latches.items()
    }
    _ORIGINAL_C469_SET_CONTROLS(
        frame,
        program,
        actors,
        states,
        control_samples,
        active_goal_resolver=active_goal_resolver,
    )
    _refine_fresh_handoff_surface(frame, program, actors, before_start_frames)


def main() -> None:
    _surface_refinements.clear()

    # Preserve C469 transaction cleanup and all established G05 authority gates.
    # Refine only the semantic surface at the instant a fresh generic handoff
    # transaction begins, using current pair geometry and existing asset semantics.
    candidate469.transaction_clean_set_controls = surface_transaction_set_controls
    candidate469.CANDIDATE = CANDIDATE
    candidate469.MECHANISM = MECHANISM
    candidate469.AUDIT = AUDIT

    print(json.dumps({
        "marker": "GENERIC_AUTONOMOUS_BATTLE_C470_ENGINEERING_READY",
        "candidate": CANDIDATE,
        "mechanism": MECHANISM,
        "affectedLayerAudit": AUDIT,
        "failureFamily": FAILURE_FAMILY,
        "rootCause": "ATTACKER_CENTER_ZONE_SELECTION_IS_NOT_CONTACT_SURFACE_SELECTION",
        "livePairSurfaceSemanticSelection": True,
        "freshHandoffOnly": True,
        "semanticSelectionFrozenAfterTransactionStart": True,
        "storyTargetZonePrescribed": False,
        "existingG05OuterAuthorityGatePreserved": True,
        "existingPairwiseSolverOraclePreserved": True,
        "c469CutoffCleanupPreserved": True,
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

    candidate469.main()


if __name__ == "__main__":
    main()
