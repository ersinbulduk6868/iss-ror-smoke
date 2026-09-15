from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

import bpy

from blender import iss_blender_battle_runtime_v1 as runtime
from blender import iss_blender_battle_runtime_v1_hardened as hardened
from blender import run_generic_battle_runtime_v1_candidate40 as candidate40
from blender import run_generic_battle_runtime_v1_candidate42 as candidate42
from blender.iss_battle_runtime_assets import BlenderBattleRuntimeError, marker

CANDIDATE = "ISS_GENERIC_BATTLE_RUNTIME_V1_CANDIDATE_4_3_G06"
PERSISTENCE_MODEL = "CAUSAL_DAMAGE_PERSISTENT_STATE_V1"

_ORIGINAL_SET_CONTROLS = candidate40.autonomous_set_controls
_ORIGINAL_C42_RESOLVE = candidate42.pairwise_resolve_pending_contacts
_ORIGINAL_OUTCOME_RESOLVE = runtime.OutcomeResolver.resolve

_actor_refs: dict[str, Any] = {}
_program_ref: Any | None = None
_control_samples_ref: list[dict[str, Any]] | None = None
_g05_bound_impacts: list[dict[str, Any]] = []
_damage_first_seen: dict[str, dict[str, Any]] = {}
_later_damaged_event_rows: list[dict[str, Any]] = []
_g05_damage_provenance_bound_count = 0


def _json_copy(value: Any) -> Any:
    return json.loads(json.dumps(value))


def _damage_state(actor: Any) -> dict[str, Any]:
    state = actor.state
    return {
        "structuralIntegrity": float(state.structural_integrity),
        "driveEfficiency": float(state.drive_efficiency),
        "disabled": bool(state.disabled),
        "zoneIntegrity": {str(k): float(v) for k, v in sorted(state.zone_integrity.items())},
        "damageEventCount": len(state.damage_events),
        "damageEvents": _json_copy(state.damage_events),
        "lastImpactFrame": int(state.last_impact_frame) if state.last_impact_frame is not None else None,
    }


def _shape_key_rows(actor: Any) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for obj in actor.realized_meshes:
        keys = getattr(obj.data, "shape_keys", None)
        if keys is None:
            continue
        for key in keys.key_blocks:
            if not str(key.name).startswith("ISS_DAMAGE_"):
                continue
            rows.append({
                "object": str(obj.name),
                "key": str(key.name),
                "value": float(key.value),
            })
    return rows


def _debris_rows(actor_id: str) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for obj in bpy.data.objects:
        source = str(obj.get("iss_debris_source_actor", ""))
        if source != actor_id:
            continue
        rb = getattr(obj, "rigid_body", None)
        rows.append({
            "name": str(obj.name),
            "sourceActor": source,
            "originEventFrame": int(obj.get("iss_debris_origin_event_frame", -1)),
            "trajectoryInjection": bool(obj.get("iss_debris_trajectory_injection", True)),
            "rigidBodyPresent": rb is not None,
            "kinematic": bool(rb.kinematic) if rb is not None else None,
            "hideRender": bool(obj.hide_render),
            "hideViewport": bool(obj.hide_viewport),
        })
    return rows


def _visual_state(actor: Any) -> dict[str, Any]:
    return {
        "realizedRootPresent": actor.realized_root is not None,
        "realizedMeshCount": len(actor.realized_meshes),
        "originalVisualHiddenRender": bool(actor.visual_instance.hide_render),
        "originalVisualHiddenViewport": bool(actor.visual_instance.hide_viewport),
        "damageShapeKeys": _shape_key_rows(actor),
        "damageVisualEvidence": _json_copy(actor.damage_visual_evidence),
        "debris": _debris_rows(actor.profile.entity_id),
    }


def _actor_snapshot(actor: Any, frame: int) -> dict[str, Any]:
    return {
        "frame": int(frame),
        "actorId": str(actor.profile.entity_id),
        "state": _damage_state(actor),
        "visual": _visual_state(actor),
    }


def _bind_damage_event_provenance(
    row: dict[str, Any],
    actors: dict[str, Any],
) -> int:
    receipt = row.get("nativeContactReceipt")
    if not isinstance(receipt, dict) or receipt.get("status") != "VERIFIED":
        return 0
    bound = 0
    for evidence_field in ("evidence", "attackerEvidence"):
        evidence = row.get(evidence_field)
        if not isinstance(evidence, dict):
            continue
        frame = int(evidence.get("frame") or -1)
        attacker_id = str(evidence.get("attacker_id") or "")
        target_id = str(evidence.get("target_id") or "")
        if not attacker_id or not target_id:
            continue
        actor = actors.get(target_id)
        if actor is None:
            continue
        for damage in actor.state.damage_events:
            if (
                int(damage.get("frame") or -2) == frame
                and str(damage.get("attackerId") or "") == attacker_id
                and str(damage.get("targetId") or "") == target_id
            ):
                damage["g05NativeContactAuthority"] = True
                damage["g05ContactAuthorityModel"] = candidate42.CONTACT_AUTHORITY
                damage["g05PhysicalEventId"] = str(row.get("eventId") or "")
                damage["g05ReceiptStatus"] = "VERIFIED"
                damage["g05ReceiptContactFrame"] = int(receipt.get("contactFrame") or frame)
                bound += 1
    return bound


def g06_pairwise_resolve_pending_contacts(
    frame: int,
    actors: dict[str, Any],
    states: dict[str, Any],
    events_by_id: dict[str, Any],
    pending: list[Any],
    camera: Any,
    impact_log: list[dict[str, Any]],
) -> None:
    global _g05_damage_provenance_bound_count
    before = len(impact_log)
    _ORIGINAL_C42_RESOLVE(
        frame,
        actors,
        states,
        events_by_id,
        pending,
        camera,
        impact_log,
    )
    for row in impact_log[before:]:
        if row.get("nativeContactAuthority") is not True:
            raise BlenderBattleRuntimeError(
                f"G06_DAMAGE_PATH_WITHOUT_G05_AUTHORITY:{row.get('eventId')}"
            )
        receipt = row.get("nativeContactReceipt")
        if not isinstance(receipt, dict) or receipt.get("status") != "VERIFIED":
            raise BlenderBattleRuntimeError(
                f"G06_G05_RECEIPT_INVALID:{row.get('eventId')}"
            )
        bound = _bind_damage_event_provenance(row, actors)
        _g05_damage_provenance_bound_count += bound
        _g05_bound_impacts.append({
            "eventId": str(row.get("eventId") or ""),
            "damageEarned": bool(row.get("damageEarned")),
            "boundDamageEventCount": int(bound),
            "evidence": _json_copy(row.get("evidence") or {}),
            "attackerEvidence": _json_copy(row.get("attackerEvidence")) if row.get("attackerEvidence") else None,
            "nativeContactReceipt": _json_copy(receipt),
            "physicalTransactionEventId": row.get("physicalTransactionEventId"),
            "inherited": bool(row.get("nativeContactInheritedFromPhysicalTransaction")),
        })


def _new_control_sample_for(
    control_samples: list[dict[str, Any]],
    before: int,
    *,
    frame: int,
    event_id: str,
    actor_id: str,
) -> dict[str, Any] | None:
    for row in reversed(control_samples[before:]):
        if (
            int(row.get("frame") or -1) == int(frame)
            and str(row.get("eventId") or "") == event_id
            and str(row.get("actorId") or "") == actor_id
        ):
            return _json_copy(row)
    return None


def g06_set_controls(
    frame: int,
    program: Any,
    actors: dict[str, Any],
    states: dict[str, Any],
    control_samples: list[dict[str, Any]],
) -> None:
    global _actor_refs, _program_ref, _control_samples_ref
    _actor_refs = actors
    _program_ref = program
    _control_samples_ref = control_samples

    active_before: dict[str, Any] = {}
    for entity, actor in actors.items():
        event = candidate40._active_goal_for_actor(entity, frame, program, states)
        if event is not None:
            active_before[entity] = event

    before = len(control_samples)
    _ORIGINAL_SET_CONTROLS(frame, program, actors, states, control_samples)

    for entity, actor in actors.items():
        if actor.state.damage_events and entity not in _damage_first_seen:
            snapshot = _actor_snapshot(actor, frame)
            _damage_first_seen[entity] = snapshot
            marker(
                "G06_DAMAGE_STATE_FIRST_OBSERVED",
                frame=frame,
                actorId=entity,
                damageEventCount=snapshot["state"]["damageEventCount"],
                structuralIntegrity=round(snapshot["state"]["structuralIntegrity"], 6),
                driveEfficiency=round(snapshot["state"]["driveEfficiency"], 6),
                model=PERSISTENCE_MODEL,
            )

        event = active_before.get(entity)
        last_impact = actor.state.last_impact_frame
        if (
            event is None
            or last_impact is None
            or int(event.start_frame) <= int(last_impact)
            or entity not in event.attackers
        ):
            continue
        if any(
            row["eventId"] == event.event_id and row["actorId"] == entity
            for row in _later_damaged_event_rows
        ):
            continue

        sample = _new_control_sample_for(
            control_samples,
            before,
            frame=frame,
            event_id=event.event_id,
            actor_id=entity,
        )
        snapshot = _actor_snapshot(actor, frame)
        efficiency = float(actor.state.drive_efficiency)
        capability = {
            "profileMaxSpeedMps": float(actor.profile.max_speed_mps),
            "profileMaxReverseMps": float(actor.profile.max_reverse_mps),
            "profileMaxYawRateRadS": float(actor.profile.max_yaw_rate_rad_s),
            "driveEfficiency": efficiency,
            "effectiveMaxSpeedMps": float(actor.profile.max_speed_mps) * max(0.0, efficiency),
            "effectiveMaxReverseMps": float(actor.profile.max_reverse_mps) * max(0.0, efficiency),
            "effectiveMaxYawRateRadS": float(actor.profile.max_yaw_rate_rad_s) * max(0.15, efficiency),
        }
        row = {
            "frame": int(frame),
            "actorId": entity,
            "eventId": str(event.event_id),
            "eventStartFrame": int(event.start_frame),
            "priorImpactFrame": int(last_impact),
            "state": snapshot["state"],
            "effectiveCapability": capability,
            "controlSample": sample,
        }
        _later_damaged_event_rows.append(row)
        marker(
            "G06_DAMAGED_STATE_CONSUMED_BY_LATER_EVENT",
            frame=frame,
            actorId=entity,
            eventId=event.event_id,
            priorImpactFrame=int(last_impact),
            structuralIntegrity=round(float(actor.state.structural_integrity), 6),
            driveEfficiency=round(efficiency, 6),
            effectiveMaxSpeedMps=round(capability["effectiveMaxSpeedMps"], 6),
            disabled=bool(actor.state.disabled),
            controlSamplePresent=sample is not None,
            model=PERSISTENCE_MODEL,
        )


def _write_persistence_evidence(states: dict[str, Any], events: dict[str, Any]) -> None:
    if hardened._capture_output is None:
        raise BlenderBattleRuntimeError("G06_OUTPUT_DIR_UNAVAILABLE")
    if _program_ref is None or not _actor_refs:
        raise BlenderBattleRuntimeError("G06_RUNTIME_REFERENCES_MISSING")

    frame = int(bpy.context.scene.frame_current)
    final_actors = {
        entity: _actor_snapshot(actor, frame)
        for entity, actor in sorted(_actor_refs.items())
    }
    evidence = {
        "status": "OBSERVED",
        "candidate": CANDIDATE,
        "model": PERSISTENCE_MODEL,
        "finalFrame": frame,
        "programTotalFrames": int(_program_ref.total_frames),
        "g05BoundImpacts": _json_copy(_g05_bound_impacts),
        "g05DamageProvenanceBoundCount": int(_g05_damage_provenance_bound_count),
        "firstDamageState": _json_copy(_damage_first_seen),
        "laterDamagedEventObservations": _json_copy(_later_damaged_event_rows),
        "finalActors": final_actors,
        "eventStates": {
            event_id: {
                "status": str(state.status),
                "contactCount": int(state.contact_count),
                "damageCount": int(state.damage_count),
                "completedFrame": int(state.completed_frame) if state.completed_frame is not None else None,
            }
            for event_id, state in sorted(events.items())
        },
        "actorPoseOrVelocityMutation": False,
        "damageThresholdChanged": False,
        "contactThresholdChanged": False,
        "stateResetMechanismIntroduced": False,
        "debrisTrajectoryInjectionIntroduced": False,
        "productionReadyClaimed": False,
    }
    path = Path(hardened._capture_output) / "g06-persistence-evidence.json"
    path.write_text(json.dumps(evidence, indent=2, sort_keys=True), encoding="utf-8")
    marker(
        "G06_PERSISTENCE_EVIDENCE_WRITTEN",
        path=str(path),
        finalFrame=frame,
        g05BoundImpactCount=len(_g05_bound_impacts),
        g05DamageProvenanceBoundCount=int(_g05_damage_provenance_bound_count),
        damagedActorCount=len(_damage_first_seen),
        laterDamagedEventObservationCount=len(_later_damaged_event_rows),
        model=PERSISTENCE_MODEL,
    )


def g06_outcome_resolve(states: dict[str, Any], events: dict[str, Any]) -> dict[str, Any]:
    _write_persistence_evidence(states, events)
    return _ORIGINAL_OUTCOME_RESOLVE(states, events)


def _reset() -> None:
    global _g05_damage_provenance_bound_count
    _actor_refs.clear()
    _g05_bound_impacts.clear()
    _damage_first_seen.clear()
    _later_damaged_event_rows.clear()
    _g05_damage_provenance_bound_count = 0


def main() -> None:
    _reset()
    candidate42.CANDIDATE = CANDIDATE
    candidate42.pairwise_resolve_pending_contacts = g06_pairwise_resolve_pending_contacts
    candidate40.autonomous_set_controls = g06_set_controls
    runtime.OutcomeResolver.resolve = staticmethod(g06_outcome_resolve)

    print(json.dumps({
        "marker": "GENERIC_BATTLE_RUNTIME_CANDIDATE43_G06_ENGINEERING_PASS",
        "candidate": CANDIDATE,
        "persistenceModel": PERSISTENCE_MODEL,
        "g04AutonomySourceChanged": False,
        "g05ContactAuthoritySourceChanged": False,
        "candidate39AssetSemanticSourceChanged": False,
        "candidate371ConsequenceSourceChanged": False,
        "damageThresholdChanged": False,
        "contactThresholdChanged": False,
        "actorPoseOrVelocityMutation": False,
        "stateResetMechanismIntroduced": False,
        "assetSpecificBattleCode": False,
        "exactCollisionFrameTarget": False,
        "exactImpactEnergyTarget": False,
        "productionReadyClaimed": False,
    }, sort_keys=True), flush=True)
    candidate42.main()


if __name__ == "__main__":
    main()
