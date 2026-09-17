#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import validate_generic_battle_runtime_v1_candidate442_result as base

EXPECTED_RUNTIME = "ISS_GENERIC_BATTLE_RUNTIME_V1_CANDIDATE_4_4_6_G07"
EXPECTED_ENGAGEMENT_MODEL = "LIVE_GEOMETRY_SEMANTIC_ENGAGEMENT_RESOLVER_V1"
EXPECTED_CLIMAX_MODEL = "CAUSAL_REVERSAL_STATE_CLIMAX_V1"

base.EXPECTED_RUNTIME = EXPECTED_RUNTIME


def require(condition: bool, code: str) -> None:
    if not condition:
        raise base.ValidationError(code)


def validate_g05_two_event_chain(evidence: dict[str, Any], label: str) -> dict[str, Any]:
    impacts = evidence.get("impacts") or []
    require(bool(impacts), f"{label}:IMPACTS_EMPTY")
    direct: list[dict[str, Any]] = []
    for row in impacts:
        require(row.get("nativeContactAuthority") is True, f"{label}:IMPACT_WITHOUT_NATIVE_AUTHORITY:{row.get('eventId')}")
        receipt = row.get("nativeContactReceipt")
        require(isinstance(receipt, dict), f"{label}:G05_RECEIPT_MISSING:{row.get('eventId')}")
        require(receipt.get("status") == "VERIFIED", f"{label}:G05_RECEIPT_NOT_VERIFIED:{row.get('eventId')}")
        model = str(row.get("contactAuthorityModel") or receipt.get("model") or "")
        require(model == base.EXPECTED_CONTACT_AUTHORITY, f"{label}:CONTACT_AUTHORITY_MODEL_MISMATCH:{model}")
        require(receipt.get("actorPoseOrVelocityMutation") is False, f"{label}:G05_POSE_VELOCITY_MUTATION")
        require(receipt.get("obbFinalContactAuthority") is False, f"{label}:OBB_FINAL_AUTHORITY_REGRESSION")
        require(receipt.get("nativeSweepFinalContactAuthority") is False, f"{label}:SWEEP_FINAL_AUTHORITY_REGRESSION")
        if row.get("nativeContactInheritedFromPhysicalTransaction") is not True:
            direct.append(row)

    require(len(direct) >= 2, f"{label}:DIRECT_G05_TRANSACTION_COVERAGE_LOW:{len(direct)}")

    damage_events: list[dict[str, Any]] = []
    damaged_actors: set[str] = set()
    for actor_id, actor in (evidence.get("actors") or {}).items():
        for damage in ((actor or {}).get("state") or {}).get("damageEvents") or []:
            if not isinstance(damage, dict):
                continue
            damage_events.append(damage)
            damaged_actors.add(str(actor_id))
            require(damage.get("g05NativeContactAuthority") is True, f"{label}:NATURAL_DAMAGE_WITHOUT_G05_AUTHORITY:{actor_id}")
            require(damage.get("g05ReceiptStatus") == "VERIFIED", f"{label}:NATURAL_DAMAGE_RECEIPT_NOT_VERIFIED:{actor_id}")
            require(damage.get("g05ContactAuthorityModel") == base.EXPECTED_CONTACT_AUTHORITY, f"{label}:NATURAL_DAMAGE_AUTHORITY_MISMATCH:{actor_id}")

    require(len(damage_events) >= 2, f"{label}:G06_PERSISTENT_DAMAGE_EVENT_COVERAGE_LOW:{len(damage_events)}")
    require(len(damaged_actors) >= 2, f"{label}:G06_TWO_SIDED_DAMAGE_NOT_PROVEN:{sorted(damaged_actors)}")
    return {
        "directG05PhysicalTransactions": len(direct),
        "naturalDamageEventCount": len(damage_events),
        "damagedActorCount": len(damaged_actors),
    }


def transitions(drama: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {
        str(row.get("stage")): row
        for row in (drama.get("transitions") or [])
        if isinstance(row, dict) and row.get("stage")
    }


def validate_drama_446(drama: dict[str, Any], label: str) -> dict[str, Any]:
    require(drama.get("status") == "COMPLETE", f"{label}:G07_STATUS_NOT_COMPLETE:{drama.get('status')}")
    require(drama.get("candidate") == EXPECTED_RUNTIME, f"{label}:G07_CANDIDATE_MISMATCH:{drama.get('candidate')}")
    require(drama.get("model") == base.EXPECTED_DRAMA_MODEL, f"{label}:G07_MODEL_MISMATCH:{drama.get('model')}")
    require(drama.get("dominanceModel") == base.EXPECTED_DOMINANCE_MODEL, f"{label}:G07_DOMINANCE_MODEL_MISMATCH:{drama.get('dominanceModel')}")
    require(drama.get("collisionPlanningAuthority") == base.EXPECTED_COLLISION_AUTHORITY, f"{label}:COLLISION_AUTHORITY_INVALID:{drama.get('collisionPlanningAuthority')}")

    for flag in (
        "storyCollisionChoreography",
        "perAssetCollisionEngineering",
        "hardCodedContactZone",
        "g07DamageThresholdDependency",
        "g04AutonomySourceChanged",
        "g05ContactAuthoritySourceChanged",
        "g06PersistenceSourceChanged",
        "damageThresholdChanged",
        "contactThresholdChanged",
        "actorPoseOrVelocityMutation",
        "stateResetMechanismIntroduced",
        "forcedWinnerIntroduced",
        "exactCollisionFrameTarget",
        "exactImpactEnergyTarget",
        "productionReadyClaimed",
    ):
        require(drama.get(flag) is False, f"{label}:FORBIDDEN_G07_FLAG:{flag}:{drama.get(flag)}")

    require(drama.get("issR041ScopePreserved") is True, f"{label}:ISS_R041_SCOPE_NOT_PRESERVED")
    require(drama.get("issR042ScopePreserved") is True, f"{label}:ISS_R042_SCOPE_NOT_PRESERVED")
    require(drama.get("issR043ScopePreflightPreserved") is True, f"{label}:ISS_R043_SCOPE_NOT_PRESERVED")
    require(drama.get("issR044UserPostflightApprovalRequired") is True, f"{label}:ISS_R044_NOT_PRESERVED")
    require(drama.get("gateClosed") is False, f"{label}:GATE_CLOSED_BEFORE_USER_OK")

    require(drama.get("engagementTargetingModel") == EXPECTED_ENGAGEMENT_MODEL, f"{label}:ENGAGEMENT_MODEL_MISMATCH:{drama.get('engagementTargetingModel')}")
    require(drama.get("runtimeSelectedSemanticEngagement") is True, f"{label}:RUNTIME_SEMANTIC_ENGAGEMENT_NOT_PROVEN")
    require(drama.get("storyTargetZonePrescribed") is False, f"{label}:STORY_TARGET_ZONE_PRESCRIBED")
    require(drama.get("hardCodedSemanticZone") is False, f"{label}:HARDCODED_SEMANTIC_ZONE")
    require(drama.get("semanticSelectionFromLiveGeometry") is True, f"{label}:LIVE_GEOMETRY_SELECTION_NOT_PROVEN")
    selections = drama.get("engagementSurfaceSelections") or []
    selected_events = {
        str(row.get("eventId") or "")
        for row in selections
        if isinstance(row, dict)
    }
    for event_id in ("evt-escalation", "evt-counterattack"):
        require(event_id in selected_events, f"{label}:ENGAGEMENT_SELECTION_MISSING:{event_id}")
    for row in selections:
        if not isinstance(row, dict):
            continue
        require(row.get("model") == EXPECTED_ENGAGEMENT_MODEL, f"{label}:SELECTION_MODEL_MISMATCH")
        require(row.get("selectionAuthority") == "LIVE_TARGET_GEOMETRY_AND_AVAILABLE_ASSET_SEMANTICS", f"{label}:SELECTION_AUTHORITY_INVALID")
        require(row.get("storyTargetZonePrescribed") is False, f"{label}:SELECTION_STORY_ZONE_PRESCRIBED")
        require(row.get("assetSpecificBranch") is False, f"{label}:SELECTION_ASSET_BRANCH")

    require(drama.get("climaxRealizationModel") == EXPECTED_CLIMAX_MODEL, f"{label}:CLIMAX_MODEL_MISMATCH:{drama.get('climaxRealizationModel')}")
    require(drama.get("climaxRequiresNewContact") is False, f"{label}:CLIMAX_THIRD_CONTACT_REQUIRED")
    require(drama.get("climaxAuthority") == "REALIZED_REVERSAL_AND_PERSISTENT_STATE", f"{label}:CLIMAX_AUTHORITY_INVALID:{drama.get('climaxAuthority')}")
    require(drama.get("receiptAdmissionWorkaround") is False, f"{label}:RECEIPT_ADMISSION_WORKAROUND_PRESENT")
    require(drama.get("g07OwnsDramaLifecycleOnly") is True, f"{label}:G07_SCOPE_NOT_DRAMA_LIFECYCLE_ONLY")
    require(drama.get("g04ControlLawChanged") is False, f"{label}:G04_CONTROL_LAW_CHANGED")
    require(drama.get("g04AutonomySourceChangedForClimax") is False, f"{label}:G04_SOURCE_CHANGED_FOR_CLIMAX")
    require(drama.get("g05ContactAuthorityChanged") is False, f"{label}:G05_CONTACT_AUTHORITY_CHANGED")
    require(drama.get("g05SourceChangedForClimax") is False, f"{label}:G05_SOURCE_CHANGED_FOR_CLIMAX")
    require(drama.get("g06DamagePersistenceChanged") is False, f"{label}:G06_DAMAGE_PERSISTENCE_CHANGED")
    require(drama.get("g06SourceChangedForClimax") is False, f"{label}:G06_SOURCE_CHANGED_FOR_CLIMAX")

    txs = drama.get("directTransactions") or []
    keys = [str(row.get("transactionKey") or "") for row in txs]
    require(len(keys) == len(set(keys)), f"{label}:DUPLICATE_DIRECT_TRANSACTION")
    require(len(txs) >= 2, f"{label}:DIRECT_TRANSACTION_COUNT_LOW:{len(txs)}")
    for row in txs:
        require(row.get("g05ReceiptStatus") == "VERIFIED", f"{label}:TRANSACTION_NOT_G05_VERIFIED:{row.get('eventId')}")
        require(row.get("g05ContactAuthorityModel") == base.EXPECTED_CONTACT_AUTHORITY, f"{label}:TRANSACTION_AUTHORITY_MISMATCH:{row.get('eventId')}")
        require(row.get("inheritedReciprocalAlias") is False, f"{label}:INHERITED_ALIAS_COUNTED_AS_DIRECT")

    opening = [row for row in txs if str(row.get("phase") or "") == "ESCALATION" and row.get("physicalInitiativeQualified") is True]
    counters = [row for row in txs if str(row.get("phase") or "") == "COUNTERATTACK" and row.get("physicalInitiativeQualified") is True]
    climaxes = [row for row in txs if str(row.get("phase") or "") == "CLIMAX" and row.get("physicalInitiativeQualified") is True]
    require(bool(opening), f"{label}:OPENING_DIRECT_G05_AGGRESSION_MISSING")
    require(bool(counters), f"{label}:COUNTER_DIRECT_G05_AGGRESSION_MISSING")
    require(not climaxes, f"{label}:CLIMAX_STILL_DEPENDS_ON_NEW_G05_TRANSACTION:{len(climaxes)}")

    opening_tx = sorted(opening, key=lambda r: int(r.get("frame") or 0))[0]
    counter_tx = sorted(counters, key=lambda r: int(r.get("frame") or 0))[0]
    require(opening_tx.get("physicalInitiativeReason") == "DIRECT_G05_OPENING_AGGRESSION", f"{label}:OPENING_REASON_INVALID")
    require(counter_tx.get("attackerPreviouslyTargetedByOpponent") is True, f"{label}:COUNTER_WITHOUT_PRIOR_AGGRESSION")
    require(counter_tx.get("physicalInitiativeReason") == "DIRECT_G05_COUNTER_AFTER_PRIOR_AGGRESSION", f"{label}:COUNTER_REASON_INVALID")

    # G07 requires a real G05 escalation/counterattack chain and persistent G06
    # battle state before climax. It does not require every direct physical beat
    # to independently cross the unchanged G06 damage threshold. The separate
    # G06 validation above already requires causal, G05-bound persistent damage
    # on both actors, so per-beat damageEarned is diagnostic rather than a G07 gate.
    opening_damage = bool(opening_tx.get("damageEarned"))
    counter_damage = bool(counter_tx.get("damageEarned"))

    t = transitions(drama)
    required = (
        "ESCALATION_PHYSICALLY_EARNED",
        "INITIAL_PHYSICAL_DOMINANCE_ESTABLISHED",
        "COUNTERATTACK_CAUSALLY_EARNED",
        "DOMINANCE_REVERSAL_COMEBACK_PHYSICALLY_EARNED",
        "CLIMAX_PHYSICALLY_EARNED",
        "PAYOFF_RESOLVED",
    )
    for stage in required:
        require(stage in t, f"{label}:TRANSITION_MISSING:{stage}")

    ef = int(t["ESCALATION_PHYSICALLY_EARNED"]["frame"])
    cf = int(t["COUNTERATTACK_CAUSALLY_EARNED"]["frame"])
    rf = int(t["DOMINANCE_REVERSAL_COMEBACK_PHYSICALLY_EARNED"]["frame"])
    xf = int(t["CLIMAX_PHYSICALLY_EARNED"]["frame"])
    pf = int(t["PAYOFF_RESOLVED"]["frame"])
    require(cf > ef, f"{label}:COUNTER_NOT_AFTER_ESCALATION")
    require(rf >= cf, f"{label}:REVERSAL_NOT_FROM_COUNTER")
    require(xf > max(rf, cf), f"{label}:CLIMAX_NOT_CAUSALLY_AFTER_REVERSAL")
    require(pf > xf, f"{label}:PAYOFF_NOT_AFTER_CLIMAX")

    climax = t["CLIMAX_PHYSICALLY_EARNED"]
    require(climax.get("authority") == "REALIZED_REVERSAL_AND_PERSISTENT_STATE", f"{label}:CLIMAX_TRANSITION_AUTHORITY_INVALID")
    require(climax.get("climaxRealization") == EXPECTED_CLIMAX_MODEL, f"{label}:CLIMAX_TRANSITION_MODEL_INVALID")
    require(climax.get("climaxRequiresNewContact") is False, f"{label}:CLIMAX_TRANSITION_REQUIRES_CONTACT")
    require(int(climax.get("reversalFrame") or -1) == rf, f"{label}:CLIMAX_REVERSAL_FRAME_MISMATCH")
    require(int(climax.get("directPhysicalTransactionCount") or 0) >= 2, f"{label}:CLIMAX_WITHOUT_PRIOR_PHYSICAL_CHAIN")

    activations = drama.get("eventActivations") or {}
    require((activations.get("evt-counterattack") or {}).get("reason") == "PRIOR_DIRECT_G05_AGGRESSION_FROM_TARGET", f"{label}:COUNTER_GUARD_NOT_PRIOR_AGGRESSION")
    require((activations.get("evt-climax") or {}).get("reason") == "PHYSICAL_DOMINANCE_REVERSAL_OBSERVED", f"{label}:CLIMAX_GUARD_NOT_REVERSAL")
    require((activations.get("evt-payoff") or {}).get("reason") == "CAUSAL_CLIMAX_OBSERVED", f"{label}:PAYOFF_GUARD_NOT_CLIMAX")

    expected_status = {
        "evt-setup": "OBSERVED",
        "evt-escalation": "SUCCEEDED",
        "evt-counterattack": "SUCCEEDED",
        "evt-climax": "OBSERVED",
        "evt-payoff": "SETTLED",
    }
    states = drama.get("eventStates") or {}
    for event_id, expected in expected_status.items():
        actual = (states.get(event_id) or {}).get("status")
        require(actual == expected, f"{label}:EVENT_STATUS:{event_id}:{actual}:{expected}")

    outcome = drama.get("outcome") or {}
    require(outcome.get("allRequiredEventsSucceeded") is True, f"{label}:OUTCOME_REQUIRED_EVENTS_FALSE")
    require(not (outcome.get("failedOrIncompleteEvents") or []), f"{label}:OUTCOME_HAS_FAILED_EVENTS")
    require(bool(outcome.get("mostOperationalActors") or []), f"{label}:OUTCOME_OPERATIONAL_RANKING_EMPTY")

    return {
        "directDramaTransactions": len(txs),
        "engagementSelectionCount": len(selections),
        "openingDamageEarned": opening_damage,
        "counterDamageEarned": counter_damage,
        "persistentTwoSidedG06DamageRequiredSeparately": True,
        "climaxRequiresNewContact": False,
        "escalationFrame": ef,
        "counterattackFrame": cf,
        "reversalFrame": rf,
        "climaxFrame": xf,
        "payoffFrame": pf,
    }


def validate_one(evidence: dict[str, Any], drama: dict[str, Any], expected_sha: str, label: str) -> dict[str, Any]:
    require(evidence.get("runtime") == EXPECTED_RUNTIME, f"{label}:RUNTIME_MISMATCH:{evidence.get('runtime')}")
    require(evidence.get("success") is True, f"{label}:BASE_RUNTIME_SUCCESS_FALSE")
    base.asset_sha_check(evidence, expected_sha, label)
    gates = evidence.get("gates") or {}
    bad = sorted(name for name, value in gates.items() if value is not True)
    require(not bad, f"{label}:BASE_GATE_FAIL:{','.join(bad)}")
    require((evidence.get("outcome") or {}).get("allRequiredEventsSucceeded") is True, f"{label}:BASE_OUTCOME_REQUIRED_EVENTS_FALSE")
    return {
        "status": "PASS",
        **validate_g05_two_event_chain(evidence, label),
        **validate_drama_446(drama, label),
        "finalFrame": int(drama.get("finalFrame") or 0),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--bugatti-evidence", required=True)
    parser.add_argument("--bugatti-drama", required=True)
    parser.add_argument("--generic-evidence", required=True)
    parser.add_argument("--generic-drama", required=True)
    args = parser.parse_args()

    bugatti = validate_one(
        base.load(Path(args.bugatti_evidence)),
        base.load(Path(args.bugatti_drama)),
        base.EXPECTED_BUGATTI_SHA,
        "EXACT_BUGATTI",
    )
    generic = validate_one(
        base.load(Path(args.generic_evidence)),
        base.load(Path(args.generic_drama)),
        base.EXPECTED_GENERIC_SHA,
        "GENERIC_HYPERCAR",
    )

    print(json.dumps({
        "marker": "GENERIC_BATTLE_RUNTIME_CANDIDATE446_G07_MACHINE_ACCEPTANCE",
        "status": "PASS",
        "runtime": EXPECTED_RUNTIME,
        "dramaModel": base.EXPECTED_DRAMA_MODEL,
        "dominanceModel": base.EXPECTED_DOMINANCE_MODEL,
        "collisionPlanningAuthority": base.EXPECTED_COLLISION_AUTHORITY,
        "engagementTargetingModel": EXPECTED_ENGAGEMENT_MODEL,
        "climaxRealizationModel": EXPECTED_CLIMAX_MODEL,
        "g04Preserved": True,
        "g05Preserved": True,
        "g06Preserved": True,
        "g07BattleStateMachineDramaticCausalProgression": True,
        "g07OwnsDramaLifecycleOnly": True,
        "storyIntentOnly": True,
        "storyTargetActorOnlyForPhysicalEvents": True,
        "storyTargetZonePrescribed": False,
        "runtimeChoosesCollisionRealization": True,
        "runtimeSelectedSemanticEngagement": True,
        "climaxRequiresNewContact": False,
        "perAssetCollisionEngineering": False,
        "g04ControlLawChanged": False,
        "g05ContactAuthorityChanged": False,
        "g06DamagePersistenceChanged": False,
        "issR041ScopePreserved": True,
        "issR042ScopePreserved": True,
        "issR043ScopePreflightPreserved": True,
        "issR044UserPostflightApprovalRequired": True,
        "gateClosed": False,
        "exactBugatti": bugatti,
        "genericHypercar": generic,
        "productionReadyClaimed": False,
    }, sort_keys=True))


if __name__ == "__main__":
    main()
