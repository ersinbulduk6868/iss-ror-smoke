from __future__ import annotations

import json
from pathlib import Path
import sys
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from blender import iss_battle_runtime_generic_battle_v6 as battle_v6
from blender import run_generic_battle_runtime_v1_candidate443 as candidate443
from blender import run_generic_battle_runtime_v1_candidate467_generic_battle as candidate467
from blender import run_generic_battle_runtime_v1_candidate479_generic_battle as candidate479
from blender.iss_battle_runtime_assets import marker
from blender.iss_battle_runtime_engagement_transaction_v1 import (
    ENGAGEMENT_APPROACH_TRANSACTION_MODEL,
    decide_engagement_approach_transaction,
    latest_contact_commit_sample,
)

CANDIDATE = "ISS_GENERIC_BATTLE_RUNTIME_V1_CANDIDATE_4_8_0_GENERIC_AUTONOMOUS_BATTLE"
MECHANISM = ENGAGEMENT_APPROACH_TRANSACTION_MODEL
AUDIT = "G04_G07_PREHANDOFF_SEMANTIC_APPROACH_FULL_AFFECTED_LAYER_AUDIT_20260918"
FAILURE_FAMILY = "LIVE_SEMANTIC_TARGET_OSCILLATES_WHILE_OBB_HANDOFF_IS_DEFERRED"

_ORIGINAL_C443_RESET = candidate443.g07_v4_reset
_approach_by_event: dict[str, dict[str, Any]] = {}
_approach_history: list[dict[str, Any]] = []


def _record(event_id: str) -> dict[str, Any] | None:
    return _approach_by_event.get(str(event_id))


def _latest_commit(event_id: str) -> tuple[bool, int | None, dict[str, Any] | None]:
    sample = latest_contact_commit_sample(battle_v6._tactical_samples, str(event_id))
    if sample is None:
        return False, None, None
    return bool(sample.get("contactCommit")), int(sample.get("frame") or -1), sample


def _announce(kind: str, *, frame: int, event: Any, zone: str | None, sample: dict[str, Any] | None, **extra: Any) -> None:
    row = {
        "frame": int(frame),
        "eventId": str(event.event_id),
        "targetId": str(event.target_id),
        "selectedSemanticZone": zone,
        "sourceSampleFrame": int(sample.get("frame")) if sample and sample.get("frame") is not None else None,
        "sourceTacticalMode": str(sample.get("tacticalMode") or "") if sample else None,
        "sourceContactCommit": bool(sample.get("contactCommit")) if sample else False,
        "selectionAuthority": candidate443.ENGAGEMENT_MODEL,
        "model": MECHANISM,
        "storyTargetZonePrescribed": False,
        "assetIdentityBranch": False,
        "fixedWorldCoordinate": False,
        **extra,
    }
    _approach_history.append({"marker": kind, **row})
    marker(kind, **row)


def approach_transaction_refresh(
    frame: int,
    program: Any,
    actors: dict[str, Any],
    states: dict[str, Any],
) -> None:
    """Keep one live-selected semantic zone stable for one generic contact attempt.

    The zone label is frozen only while tactical contact commitment is active.  Its
    world-space point still comes from target.zone_world(...) each frame.  When a
    fresh G05 handoff refines the zone from live pair geometry, that refined label
    becomes the transaction's current label.  Outside contact commitment, the
    established G07 live semantic selector remains fully adaptive.
    """
    for event in program.events:
        if not event.requires_contact or not event.target_id:
            continue
        state = states[event.event_id]
        event_id = str(event.event_id)
        terminal = state.status in candidate467.candidate42.hardened.TERMINAL

        if event.target_zone is None:
            candidate443._auto_engagement_events.add(event_id)
        if event_id not in candidate443._auto_engagement_events:
            continue
        if frame < event.start_frame:
            continue
        if not candidate467.candidate42.hardened._lifecycle.dependencies_ready(event, states):
            continue

        current = _record(event_id)
        frozen_zone = str(current.get("zone")) if current and current.get("zone") else None
        contact_commit, sample_frame, sample = _latest_commit(event_id)
        active_handoff = candidate467._active_handoff_for_event(event)

        if terminal:
            decision = decide_engagement_approach_transaction(
                frozen_zone=frozen_zone,
                current_zone=str(event.target_zone) if event.target_zone else None,
                contact_commit=False,
                event_terminal=True,
                active_handoff=False,
                source_sample_frame=sample_frame,
            )
            if decision.released and current is not None:
                _announce(
                    "GENERIC_APPROACH_SEMANTIC_TRANSACTION_RELEASED",
                    frame=frame,
                    event=event,
                    zone=frozen_zone,
                    sample=sample,
                    releaseReason="EVENT_TERMINAL",
                )
                _approach_by_event.pop(event_id, None)
            continue

        # Preserve the established C467/C470 handoff transaction as the later,
        # more precise authority.  A live-pair handoff refinement updates the
        # approach transaction's label rather than being overwritten by it.
        if active_handoff is not None:
            actor_id, latch = active_handoff
            decision = decide_engagement_approach_transaction(
                frozen_zone=frozen_zone,
                current_zone=str(event.target_zone) if event.target_zone else None,
                contact_commit=contact_commit,
                event_terminal=False,
                active_handoff=True,
                source_sample_frame=sample_frame,
            )
            if decision.hold and decision.frozen_zone:
                previous = frozen_zone
                _approach_by_event[event_id] = {
                    "zone": decision.frozen_zone,
                    "startFrame": int(current.get("startFrame")) if current else int(frame),
                    "sampleFrame": sample_frame,
                }
                event.target_zone = decision.frozen_zone
                if decision.refined_by_handoff:
                    _announce(
                        "GENERIC_APPROACH_SEMANTIC_TRANSACTION_REFINED_BY_HANDOFF",
                        frame=frame,
                        event=event,
                        zone=decision.frozen_zone,
                        sample=sample,
                        previousSemanticZone=previous,
                        actorId=actor_id,
                        handoffStartFrame=int(latch.start_frame),
                    )
                announce_key = (event_id, str(actor_id), int(latch.start_frame))
                if announce_key not in candidate467._frozen_announced:
                    candidate467._frozen_announced.add(announce_key)
                    marker(
                        "GENERIC_HANDOFF_SEMANTIC_SURFACE_FROZEN",
                        frame=int(frame),
                        eventId=event_id,
                        actorId=str(actor_id),
                        handoffStartFrame=int(latch.start_frame),
                        selectedSemanticZone=str(event.target_zone),
                        model=candidate467.MECHANISM,
                        selectionAuthority=candidate443.ENGAGEMENT_MODEL,
                    )
            continue

        # On the first frame after tactical contact commitment is observed, retain
        # the already live-selected zone label.  Do not retain a world coordinate.
        if contact_commit and event.target_zone is None:
            event.target_zone = candidate443._select_live_semantic_surface(event, actors, frame)

        decision = decide_engagement_approach_transaction(
            frozen_zone=frozen_zone,
            current_zone=str(event.target_zone) if event.target_zone else None,
            contact_commit=contact_commit,
            event_terminal=False,
            active_handoff=False,
            source_sample_frame=sample_frame,
        )

        if decision.hold and decision.frozen_zone:
            event.target_zone = decision.frozen_zone
            if current is None:
                _approach_by_event[event_id] = {
                    "zone": decision.frozen_zone,
                    "startFrame": int(frame),
                    "sampleFrame": sample_frame,
                }
                _announce(
                    "GENERIC_APPROACH_SEMANTIC_TRANSACTION_STARTED",
                    frame=frame,
                    event=event,
                    zone=decision.frozen_zone,
                    sample=sample,
                    transactionStartFrame=int(frame),
                )
            continue

        if decision.released and current is not None:
            _announce(
                "GENERIC_APPROACH_SEMANTIC_TRANSACTION_RELEASED",
                frame=frame,
                event=event,
                zone=frozen_zone,
                sample=sample,
                releaseReason="TACTICAL_CONTACT_COMMIT_ENDED",
            )
            _approach_by_event.pop(event_id, None)

        previous = event.target_zone
        event.target_zone = candidate443._select_live_semantic_surface(event, actors, frame)
        if event.target_zone != previous:
            marker(
                "GENERIC_PRECONTACT_SEMANTIC_SURFACE_SYNCHRONIZED",
                frame=int(frame),
                eventId=event_id,
                targetId=str(event.target_id),
                previousSemanticZone=previous,
                selectedSemanticZone=event.target_zone,
                model=MECHANISM,
                selectionAuthority=candidate443.ENGAGEMENT_MODEL,
            )


def c480_reset(self: Any) -> None:
    _approach_by_event.clear()
    _approach_history.clear()
    _ORIGINAL_C443_RESET(self)


def main() -> None:
    _approach_by_event.clear()
    _approach_history.clear()

    # Both pre-G05 and pre-G04/G07 semantic refresh paths use one transaction-aware
    # resolver so a second refresh in the same frame cannot undo the frozen label.
    candidate467._refresh_unlatched_semantic_surfaces = approach_transaction_refresh
    candidate443._refresh_generic_engagement_surfaces = approach_transaction_refresh
    candidate443.g07_v4_reset = c480_reset

    print(json.dumps({
        "marker": "GENERIC_AUTONOMOUS_BATTLE_C480_ENGINEERING_READY",
        "candidate": CANDIDATE,
        "mechanism": MECHANISM,
        "affectedLayerAudit": AUDIT,
        "failureFamily": FAILURE_FAMILY,
        "rootCause": "LIVE_SEMANTIC_ZONE_IDENTITY_CHANGES_DURING_DEFERRED_GENERIC_CONTACT_APPROACH",
        "approachTransactionStartsFromTacticalContactCommit": True,
        "semanticZoneLabelStableWithinApproachTransaction": True,
        "semanticWorldPositionRemainsLive": True,
        "c470FreshHandoffLivePairRefinementPreserved": True,
        "c467HandoffSemanticFreezePreserved": True,
        "c474ObbHandoffEligibilityPreserved": True,
        "g05NativeSolverFinalAuthorityPreserved": True,
        "pairwiseSolverOraclePreserved": True,
        "storyTargetZonePrescribed": False,
        "assetIdentityBranch": False,
        "perAssetBattleCode": False,
        "perAssetTacticalTuning": False,
        "perVideoTrajectoryEngineering": False,
        "fixedWorldCoordinates": False,
        "exactCollisionFrameTarget": False,
        "exactImpactEnergyTarget": False,
        "actorPoseOrVelocityMutation": False,
        "contactThresholdChanged": False,
        "semanticToleranceChanged": False,
        "localityToleranceChanged": False,
        "damageAdmissionThresholdChanged": False,
        "damageThresholdAwareControl": False,
        "targetToughnessAwareControl": False,
        "desiredImpactSpeedControl": False,
        "desiredImpactEnergyControl": False,
        "fixtureBattlePlanChanged": False,
        "g01ToG03Changed": False,
        "frozenNineServiceArchitectureChanged": False,
        "gateClosed": False,
        "productionReadyClaimed": False,
    }, sort_keys=True), flush=True)

    candidate479.main()


if __name__ == "__main__":
    main()
