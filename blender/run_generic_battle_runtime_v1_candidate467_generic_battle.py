from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from blender import iss_battle_runtime_generic_battle_v6 as battle_v6
from blender import run_generic_battle_runtime_v1_candidate42 as candidate42
from blender import run_generic_battle_runtime_v1_candidate443 as candidate443
from blender import run_generic_battle_runtime_v1_candidate466_generic_battle as candidate466
from blender.iss_battle_runtime_assets import marker

CANDIDATE = "ISS_GENERIC_BATTLE_RUNTIME_V1_CANDIDATE_4_6_7_GENERIC_AUTONOMOUS_BATTLE"
MECHANISM = "LIVE_SEMANTIC_SURFACE_HANDOFF_TRANSACTION_V1"
AUDIT = "SEMANTIC_SELECTION_HANDOFF_TRANSACTION_FULL_AFFECTED_LAYER_AUDIT_20260918"

_ORIGINAL_PAIRWISE_DETECT = candidate42.pairwise_detect_contacts
_frozen_announced: set[tuple[str, str, int]] = set()


def _active_handoff_for_event(event: Any) -> tuple[str, Any] | None:
    for actor_id in event.attackers:
        key = (str(event.event_id), str(actor_id))
        latch = battle_v6._handoff_latches.get(key)
        if latch is not None:
            return str(actor_id), latch
    return None


def _refresh_unlatched_semantic_surfaces(
    frame: int,
    program: Any,
    actors: dict[str, Any],
    states: dict[str, Any],
) -> None:
    """Reuse G07 live semantic selection, but freeze a surface during G05 handoff.

    A solver handoff is one physical contact transaction. Once controller authority
    is released, changing the semantic target mid-flight can invalidate the same
    contact that the handoff was created to observe. The semantic zone therefore
    remains stable only while the existing event-local handoff latch is active.
    Outside that latch, the established G07 live-geometry resolver remains fully
    adaptive. No tolerance, contact threshold, pose, velocity or fixture changes.
    """
    for event in program.events:
        if not event.requires_contact or not event.target_id:
            continue
        state = states[event.event_id]
        if state.status in candidate42.hardened.TERMINAL:
            continue
        if event.target_zone is None:
            candidate443._auto_engagement_events.add(event.event_id)
        if event.event_id not in candidate443._auto_engagement_events:
            continue
        if frame < event.start_frame:
            continue
        if not candidate42.hardened._lifecycle.dependencies_ready(event, states):
            continue

        active = _active_handoff_for_event(event)
        if active is not None:
            actor_id, latch = active
            if not event.target_zone:
                raise RuntimeError(f"HANDOFF_SEMANTIC_SURFACE_MISSING:{event.event_id}:{actor_id}")
            announce_key = (str(event.event_id), actor_id, int(latch.start_frame))
            if announce_key not in _frozen_announced:
                _frozen_announced.add(announce_key)
                marker(
                    "GENERIC_HANDOFF_SEMANTIC_SURFACE_FROZEN",
                    frame=int(frame),
                    eventId=str(event.event_id),
                    actorId=actor_id,
                    handoffStartFrame=int(latch.start_frame),
                    selectedSemanticZone=str(event.target_zone),
                    model=MECHANISM,
                    selectionAuthority=candidate443.ENGAGEMENT_MODEL,
                )
            continue

        previous = event.target_zone
        event.target_zone = candidate443._select_live_semantic_surface(event, actors, frame)
        if event.target_zone != previous:
            marker(
                "GENERIC_PRECONTACT_SEMANTIC_SURFACE_SYNCHRONIZED",
                frame=int(frame),
                eventId=str(event.event_id),
                targetId=str(event.target_id),
                previousSemanticZone=previous,
                selectedSemanticZone=event.target_zone,
                model=MECHANISM,
                selectionAuthority=candidate443.ENGAGEMENT_MODEL,
            )


def transactional_pairwise_detect_contacts(
    frame: int,
    program: Any,
    actors: dict[str, Any],
    states: dict[str, Any],
    pending: list[Any],
    cooldown: dict[tuple[str, str, str], int],
) -> None:
    _refresh_unlatched_semantic_surfaces(frame, program, actors, states)
    _ORIGINAL_PAIRWISE_DETECT(frame, program, actors, states, pending, cooldown)


def main() -> None:
    _frozen_announced.clear()

    # Candidate466 composes C465 and binds the contact detector through its module
    # symbol. Replace only that wrapper symbol; the established G05 detector itself
    # remains byte-identical and is still the final authority.
    candidate466.synchronized_pairwise_detect_contacts = transactional_pairwise_detect_contacts
    candidate466.CANDIDATE = CANDIDATE
    candidate466.MECHANISM = MECHANISM
    candidate466.AUDIT = AUDIT

    print(json.dumps({
        "marker": "GENERIC_AUTONOMOUS_BATTLE_C467_ENGINEERING_READY",
        "candidate": CANDIDATE,
        "mechanism": MECHANISM,
        "affectedLayerAudit": AUDIT,
        "failureFamily": "SEMANTIC_TARGET_MUTATES_DURING_ACTIVE_SOLVER_HANDOFF_TRANSACTION",
        "existingG07ResolverReusedUnchanged": True,
        "existingG05DetectorReusedUnchanged": True,
        "semanticSelectionAdaptiveOutsideHandoff": True,
        "semanticSelectionFrozenWithinHandoff": True,
        "handoffCutoffFrameImmutableWithinLatch": True,
        "g05ContactAuthorityContractPreserved": True,
        "g07GenericEngagementContractPreserved": True,
        "semanticToleranceChanged": False,
        "localityToleranceChanged": False,
        "contactThresholdChanged": False,
        "damageAdmissionThresholdChanged": False,
        "fixtureMutationForAcceptance": False,
        "storyTargetZonePrescribed": False,
        "perAssetBattleCode": False,
        "perVideoTrajectoryEngineering": False,
        "fixedWorldCoordinates": False,
        "actorPoseOrVelocityMutation": False,
        "forcedWinner": False,
        "stateResetMechanism": False,
        "g01ToG03Changed": False,
        "frozenNineServiceArchitectureChanged": False,
        "gateClosed": False,
        "productionReadyClaimed": False,
    }, sort_keys=True), flush=True)

    candidate466.main()


if __name__ == "__main__":
    main()
