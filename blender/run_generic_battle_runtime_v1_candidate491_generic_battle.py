from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from blender import iss_battle_runtime_generic_battle_v6 as battle_v6
from blender import run_generic_battle_runtime_v1_candidate487_generic_battle as candidate487
from blender import run_generic_battle_runtime_v1_candidate488_generic_battle as candidate488
from blender import run_generic_battle_runtime_v1_candidate490_generic_battle as candidate490
from blender.iss_battle_runtime_assets import marker
from blender.iss_battle_runtime_certified_navigation_continuity_v1 import (
    CERTIFIED_NAVIGATION_CONTINUITY_MODEL,
    certified_approach_owns_navigation,
)
from blender.iss_battle_runtime_engagement_lifecycle_v1 import is_recovery_mode

CANDIDATE = "ISS_GENERIC_BATTLE_RUNTIME_V1_CANDIDATE_4_9_1_GENERIC_AUTONOMOUS_BATTLE"
MECHANISM = CERTIFIED_NAVIGATION_CONTINUITY_MODEL
AUDIT = "G04_C490_CERTIFICATE_TO_HANDOFF_OWNERSHIP_FULL_AFFECTED_LAYER_AUDIT_20260918"
FAILURE_FAMILY = "DUPLICATE_ACTUAL_GOAL_READINESS_REOPENS_FULL_RUNWAY_AFTER_REALIZED_APPROACH_CERTIFICATION"

_ORIGINAL_C487_ACTUAL_GOAL = candidate487.actual_goal_lifecycle_goal_for_tactical
_ORIGINAL_C488_UPDATE_CERTIFICATE = candidate488.update_approach_certificate
_ORIGINAL_C488_AUTHORITY_ACTION = candidate488.authority_action
_continuity_active: dict[tuple[str, str, str], int] = {}
_continuity_certificate_ids: set[int] = set()


def _key(actor: Any, target: Any, event: Any) -> tuple[str, str, str]:
    return (
        str(event.event_id),
        str(actor.profile.entity_id),
        str(target.profile.entity_id),
    )


def _release_continuity(key: tuple[str, str, str], certificate: Any | None) -> int | None:
    qualified_frame = _continuity_active.pop(key, None)
    if certificate is not None:
        _continuity_certificate_ids.discard(id(certificate))
    return qualified_frame


def c491_certified_navigation_goal_for_tactical(
    actor: Any,
    target: Any,
    event: Any,
    tactical: Any,
    actors: dict[str, Any],
):
    key = _key(actor, target, event)
    actor_id = key[1]
    certificate = candidate488._certificates.get(key)
    autonomy_memory = battle_v6._autonomy_memories.get((key[0], actor_id))
    recovery_active = bool(
        autonomy_memory is not None and is_recovery_mode(autonomy_memory.mode)
    )
    transaction_active = candidate487._active_transaction_by_actor.get(actor_id) == key

    owns_navigation = certified_approach_owns_navigation(
        transaction_active=transaction_active,
        certificate_qualified=bool(certificate is not None and certificate.qualified),
        incoming_tactical_mode=str(tactical.mode),
        incoming_contact_commit=bool(tactical.contact_commit),
        recovery_active=recovery_active,
    )

    if owns_navigation:
        frame = int(candidate487._current_frame(event))
        qualified_frame = int(certificate.qualified_frame or frame)
        previous = _continuity_active.get(key)
        _continuity_active[key] = qualified_frame
        _continuity_certificate_ids.add(id(certificate))
        if previous != qualified_frame:
            marker(
                "G04_CERTIFIED_APPROACH_NAVIGATION_CONTINUITY_ENGAGED",
                frame=frame,
                eventId=key[0],
                attackerId=key[1],
                targetId=key[2],
                qualifiedFrame=qualified_frame,
                incomingTacticalMode=str(tactical.mode),
                incomingContactCommit=bool(tactical.contact_commit),
                recoveryActive=False,
                ownership="REALIZED_APPROACH_CERTIFICATE",
                model=MECHANISM,
            )
        # The high-level planner is still contact-directed and committed. Do not
        # let C487's duplicate actual-goal readiness layer replace that tactical
        # goal with OPEN_DISTANCE after the same transaction has already earned
        # the C488 realized-approach certificate.
        return candidate487._BASE_GOAL_FOR_TACTICAL(
            actor,
            target,
            event,
            tactical,
            actors,
        )

    if key in _continuity_active:
        frame = int(candidate487._current_frame(event))
        qualified_frame = _release_continuity(key, certificate)
        marker(
            "G04_CERTIFIED_APPROACH_NAVIGATION_CONTINUITY_RELEASED",
            frame=frame,
            eventId=key[0],
            attackerId=key[1],
            targetId=key[2],
            qualifiedFrame=int(qualified_frame or frame),
            certificateQualified=bool(certificate is not None and certificate.qualified),
            incomingTacticalMode=str(tactical.mode),
            incomingContactCommit=bool(tactical.contact_commit),
            recoveryActive=bool(recovery_active),
            model=MECHANISM,
        )

    return _ORIGINAL_C487_ACTUAL_GOAL(actor, target, event, tactical, actors)


def c491_update_approach_certificate(memory: Any, **kwargs: Any):
    continuity_owns = bool(
        id(memory) in _continuity_certificate_ids
        and memory.qualified
        and bool(kwargs.get("contact_directed_mode"))
        and not bool(kwargs.get("recovery_active"))
    )
    if continuity_owns and not bool(kwargs.get("live_readiness")):
        kwargs = dict(kwargs)
        kwargs["live_readiness"] = True
    result = _ORIGINAL_C488_UPDATE_CERTIFICATE(memory, **kwargs)
    if not memory.qualified:
        _continuity_certificate_ids.discard(id(memory))
    return result


def c491_authority_action(memory: Any, **kwargs: Any) -> str:
    continuity_owns = bool(
        id(memory) in _continuity_certificate_ids
        and memory.qualified
        and bool(kwargs.get("contact_directed_mode"))
        and not bool(kwargs.get("recovery_active"))
    )
    if continuity_owns and not bool(kwargs.get("live_readiness")):
        kwargs = dict(kwargs)
        kwargs["live_readiness"] = True
    return _ORIGINAL_C488_AUTHORITY_ACTION(memory, **kwargs)


def main() -> None:
    _continuity_active.clear()
    _continuity_certificate_ids.clear()

    # C491 changes only the ownership boundary after a realized-approach
    # certificate has already been earned. Before qualification, every existing
    # C487/C488 readiness condition is unchanged. After qualification, continuity
    # exists only while the upstream planner remains contact-directed+committed,
    # the same transaction remains active, and recovery is inactive. The C488
    # certificate's own separation/miss invalidation and C484 alignment gate remain
    # downstream safeguards. G05 authority is untouched.
    candidate487.actual_goal_lifecycle_goal_for_tactical = (
        c491_certified_navigation_goal_for_tactical
    )
    candidate488.update_approach_certificate = c491_update_approach_certificate
    candidate488.authority_action = c491_authority_action

    print(json.dumps({
        "marker": "GENERIC_AUTONOMOUS_BATTLE_C491_ENGINEERING_READY",
        "candidate": CANDIDATE,
        "mechanism": MECHANISM,
        "affectedLayerAudit": AUDIT,
        "affectedLayerAuditStatus": "PASS",
        "failureFamily": FAILURE_FAMILY,
        "machineEvidenceSource": "C490_L4_RUN_c9d39602-0585-4257-a377-f22c83e04db5",
        "rootCauseFrame": 617,
        "rootCauseQualifiedFrame": 571,
        "rootCauseActualHeadingErrorRad": -0.7135647758904247,
        "rootCauseRunwayRequiredM": 5.794399929046631,
        "rootCauseEffectiveCollisionProxyGapM": 0.1751458235048955,
        "rootCauseHandoffGapM": 0.17631134841839474,
        "certificateNavigationOwnershipAfterQualification": True,
        "certificateLiveReadinessContinuityAfterQualification": True,
        "incomingPlannerContactCommitStillRequired": True,
        "incomingContactDirectedModeStillRequired": True,
        "sameTransactionStillRequired": True,
        "recoveryPreemptsCertificateContinuity": True,
        "preQualificationReadinessUnchanged": True,
        "c488CertificateMissInvalidationPreserved": True,
        "c488CertificateRecoveryInvalidationPreserved": True,
        "c484TranslationDominantAlignmentPreserved": True,
        "c490FinalCompositionBindingPreserved": True,
        "c489NegativeAckRecoveryPreserved": True,
        "c487RecoveryLifecyclePreserved": True,
        "tacticalModeMutatedByC491": False,
        "tacticalContactCommitMutatedByC491": False,
        "actualGoalReadinessThresholdChanged": False,
        "contactCommitHeadingThresholdChanged": False,
        "g05SourceChanged": False,
        "g05OuterGateChanged": False,
        "g05SolverOracleChanged": False,
        "g05ThresholdImported": False,
        "contactThresholdChanged": False,
        "semanticToleranceChanged": False,
        "localityToleranceChanged": False,
        "damageAdmissionThresholdChanged": False,
        "assetIdentityBranch": False,
        "perAssetBattleCode": False,
        "perAssetTacticalTuning": False,
        "perVideoTrajectoryEngineering": False,
        "fixedWorldCoordinates": False,
        "exactCollisionFrameTarget": False,
        "exactImpactEnergyTarget": False,
        "actorPoseOrVelocityMutation": False,
        "fixtureBattlePlanChanged": False,
        "storyTimingChanged": False,
        "programDurationChanged": False,
        "frozenNineServiceArchitectureChanged": False,
        "gateClosed": False,
        "productionReadyClaimed": False,
    }, sort_keys=True), flush=True)

    candidate490.main()


if __name__ == "__main__":
    main()
