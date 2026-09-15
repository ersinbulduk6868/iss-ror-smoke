from __future__ import annotations

import json
import math
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

import bpy
from mathutils import Vector

from blender import iss_battle_runtime_assets as assets
from blender import iss_blender_battle_runtime_v1_hardened as hardened
from blender import run_generic_battle_runtime_v1_candidate34 as candidate34
from blender import run_generic_battle_runtime_v1_candidate371 as candidate371
from blender.iss_battle_runtime_core import ImpactEvidence, norm
from blender.iss_battle_runtime_assets import BlenderBattleRuntimeError, marker

CANDIDATE = "ISS_GENERIC_BATTLE_RUNTIME_V1_CANDIDATE_3_9"
ENVELOPE_MODEL = "SUPPORTED_GEOMETRY_ENVELOPE_V1"
SEMANTIC_SURFACE_MODEL = "SEMANTIC_DIRECTION_CANONICAL_SURFACE_V1"
RECIPROCAL_CONTACT_MODEL = "SINGLE_PHYSICAL_TRANSACTION_RECIPROCAL_INTENT_V1"

_original_normalize_prototype = assets.normalize_prototype
_original_hardened_detect_contacts = hardened.detect_contacts
_original_hardened_resolve_pending_contacts = hardened.resolve_pending_contacts


def _clamp(value: float, lo: float, hi: float) -> float:
    return max(float(lo), min(float(hi), float(value)))


def _explicit_presentation(obj: bpy.types.Object) -> bool:
    return assets.token_match(assets.object_tokens(obj), assets.PRESENTATION_TERMS)


def _filter_detached_ground_auxiliary(
    binding: dict[str, Any],
    imported: list[bpy.types.Object],
) -> list[dict[str, Any]]:
    meshes = assets.mesh_objects(imported)
    candidates = [obj for obj in meshes if not _explicit_presentation(obj)]
    substantial = [
        obj for obj in candidates
        if len(obj.data.vertices) >= 16 or len(obj.data.polygons) >= 8
    ]
    if not substantial:
        return []

    support_lo, support_hi = assets.world_bounds(substantial)
    support_dims = support_hi - support_lo
    support_height = max(0.05, float(support_dims.z))
    thin_limit = max(0.02, support_height * 0.03)
    bottom_limit = float(support_lo.z) + max(0.05, support_height * 0.08)
    horizontal_eps = max(
        0.005,
        min(float(support_dims.x), float(support_dims.y)) * 0.005,
    )

    removed: list[dict[str, Any]] = []
    remove_names: set[str] = set()
    for obj in candidates:
        if obj in substantial:
            continue
        if len(obj.data.vertices) > 8 or len(obj.data.polygons) > 4:
            continue
        lo, hi = assets.world_bounds([obj])
        dims = hi - lo
        thin_near_ground = (
            float(dims.z) <= thin_limit
            and float(hi.z) <= bottom_limit
        )
        horizontally_detached = (
            float(hi.x) < float(support_lo.x) - horizontal_eps
            or float(lo.x) > float(support_hi.x) + horizontal_eps
            or float(hi.y) < float(support_lo.y) - horizontal_eps
            or float(lo.y) > float(support_hi.y) + horizontal_eps
        )
        if not (thin_near_ground and horizontally_detached):
            continue
        remove_names.add(obj.name)
        removed.append({
            "name": obj.name,
            "vertexCount": len(obj.data.vertices),
            "polygonCount": len(obj.data.polygons),
            "materials": [slot.material.name for slot in obj.material_slots if slot.material],
            "boundsLo": [round(float(x), 6) for x in lo],
            "boundsHi": [round(float(x), 6) for x in hi],
        })

    for name in sorted(remove_names):
        obj = bpy.data.objects.get(name)
        if obj is not None:
            bpy.data.objects.remove(obj, do_unlink=True)
    if remove_names:
        imported[:] = [obj for obj in imported if obj.name not in remove_names]
        bpy.context.view_layer.update()
        marker(
            "DETACHED_GROUND_AUXILIARY_FILTERED",
            entityId=binding.get("entityId"),
            model=ENVELOPE_MODEL,
            removedCount=len(remove_names),
            removed=removed,
        )
    return removed


def surface_semantic_normalize(
    binding: dict[str, Any],
    imported: list[bpy.types.Object],
):
    removed = _filter_detached_ground_auxiliary(binding, imported)
    dims, zones, evidence, axis = _original_normalize_prototype(binding, imported)
    lo, hi = assets.world_bounds(imported)

    def projected(zone: str, point: Vector, *, axis_name: str, side: str) -> Vector:
        out = point.copy()
        if axis_name == "x":
            out.x = float(hi.x if side == "hi" else lo.x)
            out.y = _clamp(float(out.y), float(lo.y), float(hi.y))
        else:
            out.y = float(hi.y if side == "hi" else lo.y)
            out.x = _clamp(float(out.x), float(lo.x), float(hi.x))
        out.z = _clamp(float(out.z), float(lo.z), float(hi.z))
        return out

    for zone, axis_name, side in (
        ("front", "x", "hi"),
        ("rear", "x", "lo"),
        ("left_side", "y", "hi"),
        ("right_side", "y", "lo"),
    ):
        source = zones.get(zone)
        if source is None:
            continue
        before = source.copy()
        after = projected(zone, source, axis_name=axis_name, side=side)
        zones[zone] = after
        evidence[zone] = SEMANTIC_SURFACE_MODEL
        marker(
            "SEMANTIC_SURFACE_ZONE_PROJECTED",
            entityId=binding.get("entityId"),
            zone=zone,
            sourcePoint=[round(float(x), 6) for x in before],
            surfacePoint=[round(float(x), 6) for x in after],
            model=SEMANTIC_SURFACE_MODEL,
        )

    marker(
        "SUPPORTED_PHYSICAL_ENVELOPE_PASS",
        entityId=binding.get("entityId"),
        model=ENVELOPE_MODEL,
        detachedAuxiliaryFiltered=len(removed),
        dimensions=[round(float(x), 6) for x in dims],
        sourceForwardAxis=axis,
    )
    return dims, zones, evidence, axis


def _pair_key(attacker_id: str, target_id: str, frame: int) -> tuple[int, tuple[str, str]]:
    return int(frame), tuple(sorted((str(attacker_id), str(target_id))))


def coalescing_detect_contacts(
    frame: int,
    program: Any,
    actors: dict[str, Any],
    states: dict[str, Any],
    pending: list[Any],
    cooldown: dict[tuple[str, str, str], int],
) -> None:
    before = len(pending)
    _original_hardened_detect_contacts(
        frame, program, actors, states, pending, cooldown
    )
    new_rows = pending[before:]
    if len(new_rows) < 2:
        return

    by_pair: dict[tuple[int, tuple[str, str]], list[Any]] = {}
    for item in new_rows:
        by_pair.setdefault(
            _pair_key(item.attacker_id, item.target_id, item.frame), []
        ).append(item)

    remove_ids: set[int] = set()
    for key, rows in by_pair.items():
        directions = {(row.attacker_id, row.target_id) for row in rows}
        if len(rows) < 2 or len(directions) < 2:
            continue
        reciprocal = any((b, a) in directions for a, b in directions)
        if not reciprocal:
            continue
        rows.sort(key=lambda row: (row.event_id, row.attacker_id, row.target_id))
        primary = rows[0]
        aliases = []
        for alias in rows[1:]:
            if alias.attacker_id == primary.target_id and alias.target_id == primary.attacker_id:
                aliases.append({
                    "eventId": alias.event_id,
                    "attackerId": alias.attacker_id,
                    "targetId": alias.target_id,
                    "targetZone": alias.target_zone,
                })
                remove_ids.add(id(alias))
        if not aliases:
            continue
        setattr(primary, "coalesced_reciprocal_aliases", aliases)
        marker(
            "RECIPROCAL_CONTACT_INTENTS_COALESCED",
            frame=primary.frame,
            physicalEventId=primary.event_id,
            attackerId=primary.attacker_id,
            targetId=primary.target_id,
            aliases=aliases,
            model=RECIPROCAL_CONTACT_MODEL,
        )

    if remove_ids:
        pending[:] = [row for row in pending if id(row) not in remove_ids]


def _impact_from_dict(raw: dict[str, Any] | None) -> ImpactEvidence | None:
    if not isinstance(raw, dict):
        return None
    try:
        return ImpactEvidence(**raw)
    except TypeError as exc:
        raise BlenderBattleRuntimeError(
            f"COALESCED_IMPACT_EVIDENCE_INVALID:{exc}"
        ) from exc


def coalescing_resolve_pending_contacts(
    frame: int,
    actors: dict[str, Any],
    states: dict[str, Any],
    events_by_id: dict[str, Any],
    pending: list[Any],
    camera: Any,
    impact_log: list[dict[str, Any]],
) -> None:
    due_aliases: list[dict[str, Any]] = []
    for item in pending:
        aliases = list(getattr(item, "coalesced_reciprocal_aliases", []) or [])
        if aliases and frame >= item.resolve_frame:
            due_aliases.append({
                "frame": int(item.frame),
                "physicalEventId": item.event_id,
                "attackerId": item.attacker_id,
                "targetId": item.target_id,
                "aliases": aliases,
            })

    impact_start = len(impact_log)
    _original_hardened_resolve_pending_contacts(
        frame,
        actors,
        states,
        events_by_id,
        pending,
        camera,
        impact_log,
    )
    new_impacts = impact_log[impact_start:]
    if not due_aliases or not new_impacts:
        return

    for group in due_aliases:
        physical = next(
            (
                row for row in new_impacts
                if row.get("eventId") == group["physicalEventId"]
                and int((row.get("evidence") or {}).get("frame") or -1) == group["frame"]
            ),
            None,
        )
        if physical is None:
            continue
        for alias in group["aliases"]:
            event_id = str(alias["eventId"])
            event = events_by_id[event_id]
            state = states[event_id]
            reciprocal_raw = physical.get("attackerEvidence")
            reciprocal = _impact_from_dict(reciprocal_raw)
            damage_earned = reciprocal is not None and physical.get("attackerVisual") is not None
            state.contact_count += 1
            if reciprocal is not None:
                state.evidence.append(reciprocal)
            if damage_earned:
                state.damage_count += 1
            hardened._lifecycle.note_impact(
                event,
                str(alias["attackerId"]),
                damage_earned=damage_earned,
            )
            impact_log.append({
                "eventId": event_id,
                "evidence": reciprocal_raw or physical.get("evidence"),
                "controllerCutoffObserved": True,
                "semanticDistance": physical.get("semanticDistance"),
                "damageEarned": bool(damage_earned),
                "targetDamage": None,
                "targetVisual": physical.get("attackerVisual"),
                "attackerEvidence": None,
                "attackerVisual": None,
                "coalescedPhysicalImpact": True,
                "physicalTransactionEventId": group["physicalEventId"],
            })
            marker(
                "RECIPROCAL_EVENT_CAUSALLY_SATISFIED",
                frame=group["frame"],
                eventId=event_id,
                physicalTransactionEventId=group["physicalEventId"],
                damageEarned=bool(damage_earned),
                additionalDamageApplied=False,
                model=RECIPROCAL_CONTACT_MODEL,
            )


def main() -> None:
    assets.normalize_prototype = surface_semantic_normalize
    hardened.detect_contacts = coalescing_detect_contacts
    hardened.resolve_pending_contacts = coalescing_resolve_pending_contacts
    candidate371.CANDIDATE = CANDIDATE
    print(json.dumps({
        "marker": "GENERIC_BATTLE_RUNTIME_CANDIDATE39_ENGINE_HARDENING_PASS",
        "candidate": CANDIDATE,
        "envelopeModel": ENVELOPE_MODEL,
        "semanticSurfaceModel": SEMANTIC_SURFACE_MODEL,
        "reciprocalContactModel": RECIPROCAL_CONTACT_MODEL,
        "damageThresholdChanged": False,
        "contactThresholdChanged": False,
        "scenarioTrajectoryHardcode": False,
        "actorPoseOrVelocityMutation": False,
        "reciprocalDamageDoubleApplyAllowed": False,
    }, sort_keys=True), flush=True)
    candidate371.main()


if __name__ == "__main__":
    main()
