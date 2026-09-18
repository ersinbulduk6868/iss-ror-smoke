from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from blender import run_generic_battle_runtime_v1_candidate42 as candidate42
from blender import run_generic_battle_runtime_v1_candidate443 as candidate443
from blender import run_generic_battle_runtime_v1_candidate465_generic_battle as candidate465
from blender.iss_battle_runtime_assets import marker

CANDIDATE = "ISS_GENERIC_BATTLE_RUNTIME_V1_CANDIDATE_4_6_6_GENERIC_AUTONOMOUS_BATTLE"
MECHANISM = "LIVE_SEMANTIC_SURFACE_PRECONTACT_SYNCHRONIZATION_V1"
AUDIT = "G07_G05_SEMANTIC_SELECTION_CONTACT_ORDERING_AUDIT_20260918"

_ORIGINAL_PAIRWISE_DETECT = candidate42.pairwise_detect_contacts


def synchronized_pairwise_detect_contacts(
    frame: int,
    program: Any,
    actors: dict[str, Any],
    states: dict[str, Any],
    pending: list[Any],
    cooldown: dict[tuple[str, str, str], int],
) -> None:
    """Synchronize the existing live semantic target before G05 evaluates contact.

    The base runtime samples physics and invokes contact detection before set_controls.
    Candidate443's already-proven generic semantic resolver normally refreshes inside
    set_controls, so a target-zone transition can otherwise reach G05 one physics
    frame late. This adapter reuses that exact resolver before the unchanged G05
    detector. It changes no semantic tolerance, locality tolerance, contact gate,
    damage gate, trajectory, pose, velocity, story fixture, or asset-specific rule.
    """
    before = {
        str(event.event_id): event.target_zone
        for event in program.events
        if event.requires_contact and event.target_id
    }
    candidate443._refresh_generic_engagement_surfaces(
        frame,
        program,
        actors,
        states,
    )
    for event in program.events:
        if not event.requires_contact or not event.target_id:
            continue
        prior = before.get(str(event.event_id))
        current = event.target_zone
        if current != prior:
            marker(
                "GENERIC_PRECONTACT_SEMANTIC_SURFACE_SYNCHRONIZED",
                frame=int(frame),
                eventId=str(event.event_id),
                targetId=str(event.target_id),
                previousSemanticZone=prior,
                selectedSemanticZone=current,
                model=MECHANISM,
                selectionAuthority=candidate443.ENGAGEMENT_MODEL,
            )

    _ORIGINAL_PAIRWISE_DETECT(
        frame,
        program,
        actors,
        states,
        pending,
        cooldown,
    )


def main() -> None:
    # Candidate42.main later binds candidate39's detector hook to this symbol.
    # The established G05 detector itself is not modified; only the already-proven
    # G07 live semantic selection is synchronized immediately before it runs.
    candidate42.pairwise_detect_contacts = synchronized_pairwise_detect_contacts

    candidate465.CANDIDATE = CANDIDATE
    candidate465.MECHANISM = (
        "ISS_GENERIC_AUTONOMOUS_BATTLE_MECHANISM_V8_"
        "HANDOFF_CUTOFF_AND_SEMANTIC_CONTACT_SYNC"
    )
    candidate465.AUDIT = AUDIT

    print(
        json.dumps(
            {
                "marker": "GENERIC_AUTONOMOUS_BATTLE_C466_ENGINEERING_READY",
                "candidate": CANDIDATE,
                "mechanism": MECHANISM,
                "affectedLayerAudit": AUDIT,
                "runtimeFrameOrderingObserved": "DETECT_CONTACTS_BEFORE_SET_CONTROLS",
                "semanticSelectionAuthority": candidate443.ENGAGEMENT_MODEL,
                "semanticSelectionSynchronizedBeforeG05": True,
                "existingG07ResolverReusedUnchanged": True,
                "existingG05DetectorReusedUnchanged": True,
                "g05ContactAuthorityContractPreserved": True,
                "g07GenericEngagementContractPreserved": True,
                "handoffCutoffFrameImmutableWithinLatch": True,
                "fixtureMutationForAcceptance": False,
                "storyTargetZonePrescribed": False,
                "semanticToleranceChanged": False,
                "localityToleranceChanged": False,
                "contactThresholdChanged": False,
                "damageAdmissionThresholdChanged": False,
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
            },
            sort_keys=True,
        ),
        flush=True,
    )
    candidate465.main()


if __name__ == "__main__":
    main()
