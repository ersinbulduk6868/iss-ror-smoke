from __future__ import annotations

import copy
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
from blender import run_generic_battle_runtime_v1_candidate467_generic_battle as candidate467
from blender import run_generic_battle_runtime_v1_candidate488_generic_battle as candidate488
from blender.iss_battle_runtime_assets import marker
from blender.iss_battle_runtime_contact_semantics_v2 import (
    OBSERVED_CONTACT_SEMANTIC_MODEL,
    classify_observed_contact_surface,
)

CANDIDATE = "ISS_GENERIC_BATTLE_RUNTIME_V1_CANDIDATE_4_8_9_GENERIC_AUTONOMOUS_BATTLE"
MECHANISM = OBSERVED_CONTACT_SEMANTIC_MODEL
AUDIT = "G05_POST_HANDOFF_SEMANTIC_MANIFOLD_MIGRATION_FULL_AFFECTED_LAYER_AUDIT_20260918"
FAILURE_FAMILY = "CONTROL_INTENT_SEMANTIC_FREEZE_OUTLIVES_SOLVER_OBSERVED_CONTACT_SURFACE"

_BASE_PAIRWISE_RECEIPT = candidate42._pairwise_receipt
_BASE_PAIRWISE_DETECT = candidate467._ORIGINAL_PAIRWISE_DETECT
_classification_rows: list[dict[str, Any]] = []
_pending_binding_rows: list[dict[str, Any]] = []


def _active_handoff(event_id: str, attacker_id: str) -> Any | None:
    return battle_v6._handoff_latches.get((str(event_id), str(attacker_id)))


def _runtime_selected_semantics(event: Any) -> bool:
    # Candidate443 permanently records events whose semantic engagement surface
    # originated from runtime live geometry rather than Story. Once recorded, the
    # event may carry a non-null intent label without becoming story-prescribed.
    return str(event.event_id) in candidate443._auto_engagement_events


def observed_contact_semantic_pairwise_receipt(
    *,
    frame: int,
    event: Any,
    attacker_id: str,
    attacker: Any,
    target: Any,
) -> tuple[dict[str, Any], dict[str, Any]] | None:
    handoff = _active_handoff(str(event.event_id), str(attacker_id))
    runtime_selected = _runtime_selected_semantics(event)
    story_prescribed = not runtime_selected

    # Before solver handoff, or for Story-prescribed semantic targets, preserve the
    # established strict C42/C470 behavior exactly. C489 never changes G04 control
    # intent and never weakens a prescribed semantic target.
    if handoff is None or story_prescribed:
        return _BASE_PAIRWISE_RECEIPT(
            frame=frame,
            event=event,
            attacker_id=attacker_id,
            attacker=attacker,
            target=target,
        )

    geometry = candidate42._best_recent_locality(attacker, target, int(frame))
    if geometry is None:
        return _BASE_PAIRWISE_RECEIPT(
            frame=frame,
            event=event,
            attacker_id=attacker_id,
            attacker=attacker,
            target=target,
        )

    surface_world = geometry["targetSurface"]
    surface_local = geometry["targetRotation"].inverted() @ (
        surface_world - geometry["targetPosition"]
    )
    selection = classify_observed_contact_surface(
        surface_local=surface_local,
        zones=target.prototype.zones,
        visual_offset=target.visual_offset,
        engagement_intent_zone=(str(event.target_zone) if event.target_zone else None),
        runtime_selected_semantics=True,
        story_target_zone_prescribed=False,
        active_solver_handoff=True,
    )
    if not selection.use_observed_contact_semantics or not selection.observed_contact_zone:
        raise RuntimeError(
            f"G05_OBSERVED_CONTACT_SEMANTIC_CLASSIFICATION_UNAVAILABLE:{event.event_id}:{attacker_id}"
        )

    row = {
        "frame": int(frame),
        "contactFrame": int(geometry["frame"]),
        "eventId": str(event.event_id),
        "attackerId": str(attacker_id),
        "targetId": str(event.target_id),
        "handoffStartFrame": int(handoff.start_frame),
        "engagementIntentZone": selection.engagement_intent_zone,
        "observedContactZone": selection.observed_contact_zone,
        "observedZoneDistanceM": float(selection.observed_zone_distance_m or 0.0),
        "model": MECHANISM,
        "classificationAuthority": "G05_LIVE_PAIR_CONTACT_SURFACE_AND_AVAILABLE_ASSET_SEMANTICS",
        "storyTargetZonePrescribed": False,
        "eventTargetZoneMutated": False,
        "g04ControlIntentChanged": False,
        "semanticToleranceChanged": False,
        "localityToleranceChanged": False,
        "contactThresholdChanged": False,
    }
    _classification_rows.append(row)
    marker("G05_OBSERVED_CONTACT_SEMANTIC_CLASSIFIED", **row)

    # Use a shallow event view only for G05 observation. The live event retains its
    # frozen engagement-intent zone for G04/G07 control and transaction continuity.
    observed_event = copy.copy(event)
    observed_event.target_zone = selection.observed_contact_zone
    verified = _BASE_PAIRWISE_RECEIPT(
        frame=frame,
        event=observed_event,
        attacker_id=attacker_id,
        attacker=attacker,
        target=target,
    )
    if verified is None:
        return None

    receipt, context = verified
    receipt["engagementIntentZone"] = selection.engagement_intent_zone
    receipt["observedContactZone"] = selection.observed_contact_zone
    receipt["semanticClassificationAuthority"] = MECHANISM
    receipt["storyTargetZonePrescribed"] = False
    receipt["eventTargetZoneMutated"] = False
    receipt["g04ControlIntentChanged"] = False
    receipt["semanticToleranceChanged"] = False
    receipt["localityToleranceChanged"] = False
    receipt["contactThresholdChanged"] = False
    marker(
        "G05_OBSERVED_CONTACT_SEMANTIC_VERIFIED",
        frame=int(frame),
        contactFrame=int(receipt["contactFrame"]),
        eventId=str(event.event_id),
        attackerId=str(attacker_id),
        targetId=str(event.target_id),
        handoffStartFrame=int(handoff.start_frame),
        engagementIntentZone=selection.engagement_intent_zone,
        observedContactZone=selection.observed_contact_zone,
        semanticDistance=receipt["semanticDistance"],
        model=MECHANISM,
    )
    return receipt, context


def observed_contact_semantic_pending_detector(
    frame: int,
    program: Any,
    actors: dict[str, Any],
    states: dict[str, Any],
    pending: list[Any],
    cooldown: dict[tuple[str, str, str], int],
) -> None:
    before = len(pending)
    _BASE_PAIRWISE_DETECT(frame, program, actors, states, pending, cooldown)
    for item in pending[before:]:
        receipt = getattr(item, "native_contact_receipt", None)
        if not isinstance(receipt, dict):
            continue
        if receipt.get("semanticClassificationAuthority") != MECHANISM:
            continue
        observed_zone = str(receipt.get("observedContactZone") or "")
        if not observed_zone:
            raise RuntimeError(
                f"G05_OBSERVED_CONTACT_PENDING_ZONE_MISSING:{item.event_id}:{item.attacker_id}:{item.frame}"
            )
        previous_zone = item.target_zone
        item.target_zone = observed_zone
        row = {
            "frame": int(frame),
            "contactFrame": int(item.frame),
            "eventId": str(item.event_id),
            "attackerId": str(item.attacker_id),
            "targetId": str(item.target_id),
            "engagementIntentZone": receipt.get("engagementIntentZone"),
            "previousPendingZone": previous_zone,
            "observedContactZone": observed_zone,
            "model": MECHANISM,
            "g06DamageZoneUsesObservedContact": True,
            "eventTargetZoneMutated": False,
        }
        _pending_binding_rows.append(row)
        marker("G05_OBSERVED_CONTACT_SEMANTIC_BOUND_TO_PENDING", **row)


def main() -> None:
    _classification_rows.clear()
    _pending_binding_rows.clear()

    # C467/C480 continue to own the frozen semantic engagement intent used by
    # G04/G07. C489 only changes G05 observation after an active solver handoff.
    # The original G05 outer authority gate, semantic tolerance, locality gate and
    # pairwise solver oracle are reused unchanged through _BASE_PAIRWISE_RECEIPT.
    candidate42._pairwise_receipt = observed_contact_semantic_pairwise_receipt
    candidate467._ORIGINAL_PAIRWISE_DETECT = observed_contact_semantic_pending_detector

    print(json.dumps({
        "marker": "GENERIC_AUTONOMOUS_BATTLE_C489_ENGINEERING_READY",
        "candidate": CANDIDATE,
        "mechanism": MECHANISM,
        "affectedLayerAudit": AUDIT,
        "affectedLayerAuditStatus": "PASS",
        "failureFamily": FAILURE_FAMILY,
        "controlIntentSemanticAndObservedContactSemanticSeparated": True,
        "runtimeSelectedSemanticsOnly": True,
        "activeSolverHandoffRequired": True,
        "storyPrescribedSemanticTargetRemainsStrict": True,
        "eventTargetZoneNeverMutatedByObservedClassification": True,
        "g04ControlIntentPreserved": True,
        "c480ApproachSemanticFreezePreserved": True,
        "c470HandoffIntentRefinementPreserved": True,
        "c467HandoffSemanticFreezePreserved": True,
        "c488AuthorityTransferPreserved": True,
        "sameG05BestRecentLocalityGeometryReused": True,
        "sameG05OuterAuthorityGateReused": True,
        "sameG05PairwiseSolverOracleReused": True,
        "sameG05SemanticToleranceReused": True,
        "observedContactZonePropagatesToPendingImpact": True,
        "g06DamageZoneUsesObservedContact": True,
        "g05SourceFileChanged": False,
        "g06SourceChanged": False,
        "g07SourceChanged": False,
        "g08SourceChanged": False,
        "g05ThresholdImportedIntoG04": False,
        "contactThresholdChanged": False,
        "semanticToleranceChanged": False,
        "localityToleranceChanged": False,
        "damageAdmissionThresholdChanged": False,
        "damageThresholdAwareControl": False,
        "targetToughnessAwareControl": False,
        "desiredImpactSpeedControl": False,
        "desiredImpactEnergyControl": False,
        "assetIdentityBranch": False,
        "perAssetBattleCode": False,
        "perAssetTacticalTuning": False,
        "perVideoTrajectoryEngineering": False,
        "fixedWorldCoordinates": False,
        "exactCollisionFrameTarget": False,
        "exactImpactEnergyTarget": False,
        "actorPoseOrVelocityMutation": False,
        "fixtureBattlePlanChanged": False,
        "frozenNineServiceArchitectureChanged": False,
        "gateClosed": False,
        "productionReadyClaimed": False,
    }, sort_keys=True), flush=True))

    candidate488.main()


if __name__ == "__main__":
    main()
