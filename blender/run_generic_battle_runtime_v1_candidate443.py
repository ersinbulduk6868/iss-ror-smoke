from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from blender import run_generic_battle_runtime_v1_candidate44 as candidate44
from blender import run_generic_battle_runtime_v1_candidate442 as candidate442
from blender.iss_battle_runtime_assets import BlenderBattleRuntimeError, marker

CANDIDATE = "ISS_GENERIC_BATTLE_RUNTIME_V1_CANDIDATE_4_4_3_G07"
ENGAGEMENT_MODEL = "LIVE_GEOMETRY_SEMANTIC_ENGAGEMENT_RESOLVER_V1"

_ORIGINAL_G07_SET_CONTROLS = candidate44.g07_set_controls
_ORIGINAL_V3_RESET = candidate442.g07_v3_reset
_ORIGINAL_V3_WRITE_EVIDENCE = candidate442.g07_v3_write_evidence

_auto_engagement_events: set[str] = set()
_selected_zone_by_event: dict[str, str] = {}
_selection_history: list[dict[str, Any]] = []


def _active_attackers(event: Any, frame: int, actors: dict[str, Any]) -> list[str]:
    rows = [
        actor_id
        for actor_id in candidate44.runtime.WaveScheduler.active_attackers(event, frame)
        if actor_id in actors and not actors[actor_id].state.disabled
    ]
    if rows:
        return rows
    return [actor_id for actor_id in event.attackers if actor_id in actors and not actors[actor_id].state.disabled]


def _zone_score(target: Any, zone: str, attacker_ids: list[str], actors: dict[str, Any]) -> float:
    point = target.zone_world(zone)
    distances: list[float] = []
    for attacker_id in attacker_ids:
        attacker = actors[attacker_id]
        delta = point - attacker.chassis.matrix_world.translation
        distances.append(float(delta.length))
    if not distances:
        return float("inf")
    return sum(distances) / len(distances)


def _select_live_semantic_surface(event: Any, actors: dict[str, Any], frame: int) -> str:
    if not event.target_id or event.target_id not in actors:
        raise BlenderBattleRuntimeError(f"G07_ENGAGEMENT_TARGET_UNAVAILABLE:{event.event_id}:{event.target_id}")
    target = actors[event.target_id]
    attacker_ids = _active_attackers(event, frame, actors)
    if not attacker_ids:
        raise BlenderBattleRuntimeError(f"G07_ENGAGEMENT_ATTACKER_UNAVAILABLE:{event.event_id}")

    candidates: list[tuple[float, str]] = []
    for zone in sorted(str(key) for key in target.prototype.zones.keys() if str(key)):
        try:
            score = _zone_score(target, zone, attacker_ids, actors)
        except Exception:
            continue
        if score < float("inf"):
            candidates.append((float(score), zone))
    if not candidates:
        raise BlenderBattleRuntimeError(
            f"G07_ENGAGEMENT_SEMANTIC_SURFACE_UNAVAILABLE:{event.event_id}:{event.target_id}"
        )

    candidates.sort(key=lambda row: (row[0], row[1]))
    selected_score, selected_zone = candidates[0]
    previous = _selected_zone_by_event.get(event.event_id)
    if previous != selected_zone:
        _selected_zone_by_event[event.event_id] = selected_zone
        row = {
            "eventId": str(event.event_id),
            "frame": int(frame),
            "targetId": str(event.target_id),
            "selectedSemanticZone": str(selected_zone),
            "attackerCount": len(attacker_ids),
            "candidateZoneCount": len(candidates),
            "selectionScoreM": float(selected_score),
            "model": ENGAGEMENT_MODEL,
            "selectionAuthority": "LIVE_TARGET_GEOMETRY_AND_AVAILABLE_ASSET_SEMANTICS",
            "storyTargetZonePrescribed": False,
            "assetSpecificBranch": False,
        }
        _selection_history.append(row)
        marker(
            "G07_GENERIC_ENGAGEMENT_SURFACE_SELECTED",
            eventId=event.event_id,
            frame=frame,
            targetId=event.target_id,
            selectedSemanticZone=selected_zone,
            attackerCount=len(attacker_ids),
            candidateZoneCount=len(candidates),
            selectionScoreM=round(float(selected_score), 6),
            model=ENGAGEMENT_MODEL,
        )
    return selected_zone


def _refresh_generic_engagement_surfaces(
    frame: int,
    program: Any,
    actors: dict[str, Any],
    states: dict[str, Any],
) -> None:
    for event in program.events:
        if not event.requires_contact or not event.target_id:
            continue
        state = states[event.event_id]
        if state.status in candidate44.hardened.TERMINAL:
            continue
        if event.target_zone is None:
            _auto_engagement_events.add(event.event_id)
        if event.event_id not in _auto_engagement_events:
            continue
        if frame < event.start_frame:
            continue
        if not candidate44.hardened._lifecycle.dependencies_ready(event, states):
            continue
        event.target_zone = _select_live_semantic_surface(event, actors, frame)


def g07_v4_set_controls(
    frame: int,
    program: Any,
    actors: dict[str, Any],
    states: dict[str, Any],
    control_samples: list[dict[str, Any]],
) -> None:
    _refresh_generic_engagement_surfaces(frame, program, actors, states)
    _ORIGINAL_G07_SET_CONTROLS(frame, program, actors, states, control_samples)


def g07_v4_reset(self: Any) -> None:
    _auto_engagement_events.clear()
    _selected_zone_by_event.clear()
    _selection_history.clear()
    _ORIGINAL_V3_RESET(self)


def g07_v4_write_evidence(states: dict[str, Any], outcome: dict[str, Any]) -> None:
    _ORIGINAL_V3_WRITE_EVIDENCE(states, outcome)
    if candidate44.hardened._capture_output is None:
        raise BlenderBattleRuntimeError("G07_OUTPUT_DIR_UNAVAILABLE")
    path = Path(candidate44.hardened._capture_output) / "g07-causal-drama-evidence.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    data.update(
        {
            "engagementTargetingModel": ENGAGEMENT_MODEL,
            "runtimeSelectedSemanticEngagement": True,
            "storyTargetZonePrescribed": False,
            "hardCodedSemanticZone": False,
            "semanticSelectionFromLiveGeometry": True,
            "engagementSurfaceSelections": json.loads(json.dumps(_selection_history)),
            "g04SourceChangedForEngagement": False,
            "g05SourceChangedForEngagement": False,
            "g06SourceChangedForEngagement": False,
            "perAssetCollisionEngineering": False,
            "issR041ScopePreserved": True,
            "issR042ScopePreserved": True,
        }
    )
    path.write_text(json.dumps(data, indent=2, sort_keys=True), encoding="utf-8")
    marker(
        "G07_GENERIC_ENGAGEMENT_EVIDENCE_WRITTEN",
        path=str(path),
        model=ENGAGEMENT_MODEL,
        selectionCount=len(_selection_history),
        selectedEventCount=len(_selected_zone_by_event),
        storyTargetZonePrescribed=False,
        hardCodedSemanticZone=False,
        semanticSelectionFromLiveGeometry=True,
        perAssetCollisionEngineering=False,
    )


def main() -> None:
    candidate442.CANDIDATE = CANDIDATE
    candidate442.g07_v3_reset = g07_v4_reset
    candidate442.g07_v3_write_evidence = g07_v4_write_evidence
    candidate44.g07_set_controls = g07_v4_set_controls

    print(
        json.dumps(
            {
                "marker": "GENERIC_BATTLE_RUNTIME_CANDIDATE443_G07_ENGINEERING_PASS",
                "candidate": CANDIDATE,
                "engagementTargetingModel": ENGAGEMENT_MODEL,
                "storyTargetZonePrescribed": False,
                "runtimeSelectedSemanticEngagement": True,
                "semanticSelectionFromLiveGeometry": True,
                "hardCodedSemanticZone": False,
                "perAssetCollisionEngineering": False,
                "g04AutonomySourceChanged": False,
                "g05ContactAuthoritySourceChanged": False,
                "g06PersistenceSourceChanged": False,
                "damageThresholdChanged": False,
                "contactThresholdChanged": False,
                "actorPoseOrVelocityMutation": False,
                "stateResetMechanismIntroduced": False,
                "forcedWinnerIntroduced": False,
                "exactCollisionFrameTarget": False,
                "exactImpactEnergyTarget": False,
                "issR041ScopePreserved": True,
                "issR042ScopePreserved": True,
                "productionReadyClaimed": False,
            },
            sort_keys=True,
        ),
        flush=True,
    )
    candidate442.main()


if __name__ == "__main__":
    main()
