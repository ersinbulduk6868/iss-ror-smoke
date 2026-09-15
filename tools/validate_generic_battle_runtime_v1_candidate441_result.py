#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import validate_generic_battle_runtime_v1_candidate44_result as base

EXPECTED_RUNTIME = "ISS_GENERIC_BATTLE_RUNTIME_V1_CANDIDATE_4_4_1_G07"
EXPECTED_DRAMA_MODEL = "PHYSICAL_CAUSAL_DRAMA_STATE_MACHINE_V1"
EXPECTED_DOMINANCE_MODEL = "LATEST_UNIQUE_DIRECT_G05_PHYSICAL_INITIATIVE_V2"


def require(condition: bool, code: str) -> None:
    if not condition:
        raise base.ValidationError(code)


def transition_map(drama: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return base.transition_map(drama)


def validate_g07_v2(drama: dict[str, Any], label: str) -> dict[str, Any]:
    require(drama.get("status") == "COMPLETE", f"{label}:G07_STATUS_NOT_COMPLETE:{drama.get('status')}")
    require(drama.get("candidate") == EXPECTED_RUNTIME, f"{label}:G07_CANDIDATE_MISMATCH:{drama.get('candidate')}")
    require(drama.get("model") == EXPECTED_DRAMA_MODEL, f"{label}:G07_MODEL_MISMATCH:{drama.get('model')}")
    require(drama.get("dominanceModel") == EXPECTED_DOMINANCE_MODEL, f"{label}:G07_DOMINANCE_MODEL_MISMATCH:{drama.get('dominanceModel')}")

    for flag in (
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
        require(drama.get(flag) is False, f"{label}:G07_FORBIDDEN_FLAG:{flag}:{drama.get(flag)}")

    transactions = drama.get("directTransactions") or []
    keys = [str(row.get("transactionKey") or "") for row in transactions]
    require(len(keys) == len(set(keys)), f"{label}:G07_DUPLICATE_DIRECT_TRANSACTION")
    require(len(transactions) >= 3, f"{label}:G07_DIRECT_G05_TRANSACTION_COUNT_LOW:{len(transactions)}")
    for row in transactions:
        require(row.get("g05ReceiptStatus") == "VERIFIED", f"{label}:G07_TRANSACTION_G05_UNVERIFIED:{row.get('eventId')}")
        require(row.get("g05ContactAuthorityModel") == base.EXPECTED_CONTACT_AUTHORITY, f"{label}:G07_TRANSACTION_AUTHORITY_MISMATCH:{row.get('eventId')}")
        require(row.get("inheritedReciprocalAlias") is False, f"{label}:G07_INHERITED_ALIAS_COUNTED_AS_DIRECT")

    opening = [
        row for row in transactions
        if str(row.get("phase") or "") in {"ESCALATION", "FIRST_ATTACK"}
        and row.get("damageEarned") is True
        and row.get("physicalInitiativeQualified") is True
    ]
    require(bool(opening), f"{label}:G07_OPENING_PERSISTENT_DAMAGE_TRANSACTION_MISSING")
    opening_tx = sorted(opening, key=lambda row: int(row.get("frame") or 0))[0]
    require(
        opening_tx.get("physicalInitiativeReason") == "OPENING_G05_G06_PERSISTENT_DAMAGE",
        f"{label}:G07_OPENING_INITIATIVE_REASON_INVALID:{opening_tx.get('physicalInitiativeReason')}",
    )

    counters = [
        row for row in transactions
        if str(row.get("phase") or "") == "COUNTERATTACK"
        and row.get("physicalInitiativeQualified") is True
    ]
    require(bool(counters), f"{label}:G07_COUNTER_DIRECT_G05_TRANSACTION_MISSING")
    counter_tx = sorted(counters, key=lambda row: int(row.get("frame") or 0))[0]
    require(counter_tx.get("attackerPreviouslyDamagedByTarget") is True, f"{label}:G07_COUNTER_NOT_CAUSED_BY_PRIOR_DAMAGE")
    require(
        counter_tx.get("physicalInitiativeReason") == "DIRECT_G05_COUNTER_AFTER_PRIOR_G06_DAMAGE",
        f"{label}:G07_COUNTER_INITIATIVE_REASON_INVALID:{counter_tx.get('physicalInitiativeReason')}",
    )

    climaxes = [
        row for row in transactions
        if str(row.get("phase") or "") == "CLIMAX"
        and row.get("physicalInitiativeQualified") is True
    ]
    require(bool(climaxes), f"{label}:G07_CLIMAX_DIRECT_G05_TRANSACTION_MISSING")
    climax_tx = sorted(climaxes, key=lambda row: int(row.get("frame") or 0))[0]
    require(
        climax_tx.get("physicalInitiativeReason") == "DIRECT_G05_CLIMAX_AFTER_REVERSAL",
        f"{label}:G07_CLIMAX_INITIATIVE_REASON_INVALID:{climax_tx.get('physicalInitiativeReason')}",
    )

    transitions = transition_map(drama)
    required_stages = (
        "ESCALATION_PHYSICALLY_EARNED",
        "INITIAL_PHYSICAL_DOMINANCE_ESTABLISHED",
        "COUNTERATTACK_CAUSALLY_EARNED",
        "DOMINANCE_REVERSAL_COMEBACK_PHYSICALLY_EARNED",
        "CLIMAX_PHYSICALLY_EARNED",
        "PAYOFF_RESOLVED",
    )
    for stage in required_stages:
        require(stage in transitions, f"{label}:G07_TRANSITION_MISSING:{stage}")

    escalation_frame = int(transitions["ESCALATION_PHYSICALLY_EARNED"]["frame"])
    initial_frame = int(transitions["INITIAL_PHYSICAL_DOMINANCE_ESTABLISHED"]["frame"])
    counter_frame = int(transitions["COUNTERATTACK_CAUSALLY_EARNED"]["frame"])
    reversal_frame = int(transitions["DOMINANCE_REVERSAL_COMEBACK_PHYSICALLY_EARNED"]["frame"])
    climax_frame = int(transitions["CLIMAX_PHYSICALLY_EARNED"]["frame"])
    payoff_frame = int(transitions["PAYOFF_RESOLVED"]["frame"])
    require(escalation_frame == initial_frame, f"{label}:G07_INITIAL_DOMINANCE_NOT_FROM_ESCALATION")
    require(counter_frame > escalation_frame, f"{label}:G07_COUNTER_NOT_AFTER_ESCALATION")
    require(reversal_frame >= counter_frame, f"{label}:G07_REVERSAL_NOT_FROM_COUNTER")
    require(climax_frame > reversal_frame, f"{label}:G07_CLIMAX_NOT_AFTER_REVERSAL")
    require(payoff_frame > climax_frame, f"{label}:G07_PAYOFF_NOT_AFTER_CLIMAX")

    reversal = drama.get("reversal") or {}
    initial_actor = str(drama.get("initialDominantActor") or "")
    require(bool(initial_actor), f"{label}:G07_INITIAL_DOMINANT_ACTOR_MISSING")
    require(str(reversal.get("fromActorId") or "") == initial_actor, f"{label}:G07_REVERSAL_FROM_ACTOR_MISMATCH")
    require(str(reversal.get("toActorId") or "") != initial_actor, f"{label}:G07_REVERSAL_DID_NOT_CHANGE_ACTOR")
    require(str(reversal.get("toActorId") or "") == str(counter_tx.get("attackerId") or ""), f"{label}:G07_REVERSAL_NOT_EARNED_BY_COUNTERATTACKER")

    activations = drama.get("eventActivations") or {}
    counter_activation = activations.get("evt-counterattack") or {}
    climax_activation = activations.get("evt-climax") or {}
    payoff_activation = activations.get("evt-payoff") or {}
    require(counter_activation.get("reason") == "PRIOR_G05_G06_DAMAGE_FROM_TARGET", f"{label}:G07_COUNTER_GUARD_NOT_STATE_DRIVEN:{counter_activation.get('reason')}")
    require(int(counter_activation.get("frame") or -1) > escalation_frame, f"{label}:G07_COUNTER_ACTIVATED_BEFORE_OPENING_DAMAGE")
    require(climax_activation.get("reason") == "PHYSICAL_DOMINANCE_REVERSAL_OBSERVED", f"{label}:G07_CLIMAX_GUARD_NOT_REVERSAL_DRIVEN:{climax_activation.get('reason')}")
    require(int(climax_activation.get("frame") or -1) >= reversal_frame, f"{label}:G07_CLIMAX_ACTIVATED_BEFORE_REVERSAL")
    require(payoff_activation.get("reason") == "CAUSAL_CLIMAX_OBSERVED", f"{label}:G07_PAYOFF_GUARD_NOT_CLIMAX_DRIVEN:{payoff_activation.get('reason')}")
    require(int(payoff_activation.get("frame") or -1) >= climax_frame, f"{label}:G07_PAYOFF_ACTIVATED_BEFORE_CLIMAX")

    event_states = drama.get("eventStates") or {}
    expected_status = {
        "evt-setup": "OBSERVED",
        "evt-escalation-alpha": "SUCCEEDED",
        "evt-escalation-beta": "SUCCEEDED",
        "evt-counterattack": "SUCCEEDED",
        "evt-climax": "SUCCEEDED",
        "evt-payoff": "SETTLED",
    }
    for event_id, expected in expected_status.items():
        actual = (event_states.get(event_id) or {}).get("status")
        require(actual == expected, f"{label}:G07_EVENT_STATUS:{event_id}:{actual}:{expected}")

    outcome = drama.get("outcome") or {}
    require(outcome.get("allRequiredEventsSucceeded") is True, f"{label}:G07_OUTCOME_REQUIRED_EVENTS_FALSE")
    require(not (outcome.get("failedOrIncompleteEvents") or []), f"{label}:G07_OUTCOME_HAS_FAILED_EVENTS")
    require(bool(outcome.get("mostOperationalActors") or []), f"{label}:G07_OUTCOME_OPERATIONAL_RANKING_EMPTY")

    return {
        "directVerifiedTransactions": len(transactions),
        "openingDamageEarned": True,
        "counterattackDamageEarned": bool(counter_tx.get("damageEarned")),
        "climaxDamageEarned": bool(climax_tx.get("damageEarned")),
        "initialDominantActor": initial_actor,
        "reversalToActor": str(reversal.get("toActorId") or ""),
        "escalationFrame": escalation_frame,
        "counterattackFrame": counter_frame,
        "reversalFrame": reversal_frame,
        "climaxFrame": climax_frame,
        "payoffFrame": payoff_frame,
    }


def validate_one(base_evidence: dict[str, Any], persistence: dict[str, Any], drama: dict[str, Any], *, expected_sha: str, label: str) -> dict[str, Any]:
    require(base_evidence.get("runtime") == EXPECTED_RUNTIME, f"{label}:RUNTIME_MISMATCH:{base_evidence.get('runtime')}")
    require(base_evidence.get("success") is True, f"{label}:BASE_RUNTIME_SUCCESS_FALSE")
    base.asset_sha_check(base_evidence, expected_sha, label)
    gates = base_evidence.get("gates") or {}
    bad = sorted(name for name, value in gates.items() if value is not True)
    require(not bad, f"{label}:BASE_GATE_FAIL:{','.join(bad)}")
    require((base_evidence.get("outcome") or {}).get("allRequiredEventsSucceeded") is True, f"{label}:BASE_OUTCOME_REQUIRED_EVENTS_FALSE")
    require(bool(base_evidence.get("debrisObjects") or []), f"{label}:BASE_DEBRIS_EMPTY")

    direct, damage = base.validate_g05_and_damage(base_evidence, label)
    g06 = base.validate_g06_persistence(persistence, label)
    g07 = validate_g07_v2(drama, label)
    return {
        "status": "PASS",
        "directG05PhysicalTransactions": direct,
        "damageEventsWithG05Provenance": damage,
        **g06,
        **g07,
        "finalFrame": int(drama.get("finalFrame") or 0),
    }


def main() -> None:
    base.EXPECTED_RUNTIME = EXPECTED_RUNTIME
    base.EXPECTED_DOMINANCE_MODEL = EXPECTED_DOMINANCE_MODEL

    parser = argparse.ArgumentParser()
    parser.add_argument("--bugatti-evidence", required=True)
    parser.add_argument("--bugatti-persistence", required=True)
    parser.add_argument("--bugatti-drama", required=True)
    parser.add_argument("--generic-evidence", required=True)
    parser.add_argument("--generic-persistence", required=True)
    parser.add_argument("--generic-drama", required=True)
    args = parser.parse_args()

    bugatti = validate_one(
        base.load(Path(args.bugatti_evidence)),
        base.load(Path(args.bugatti_persistence)),
        base.load(Path(args.bugatti_drama)),
        expected_sha=base.EXPECTED_BUGATTI_SHA,
        label="EXACT_BUGATTI",
    )
    generic = validate_one(
        base.load(Path(args.generic_evidence)),
        base.load(Path(args.generic_persistence)),
        base.load(Path(args.generic_drama)),
        expected_sha=base.EXPECTED_GENERIC_SHA,
        label="GENERIC_HYPERCAR",
    )

    print(json.dumps({
        "marker": "GENERIC_BATTLE_RUNTIME_CANDIDATE441_G07_MACHINE_ACCEPTANCE",
        "status": "PASS",
        "runtime": EXPECTED_RUNTIME,
        "dramaModel": EXPECTED_DRAMA_MODEL,
        "dominanceModel": EXPECTED_DOMINANCE_MODEL,
        "g04Preserved": True,
        "g05Preserved": True,
        "g06Preserved": True,
        "g07BattleStateMachineDramaticCausalProgression": True,
        "issR041ScopePreserved": True,
        "exactBugatti": bugatti,
        "genericHypercar": generic,
        "productionReadyClaimed": False,
    }, sort_keys=True))


if __name__ == "__main__":
    main()
