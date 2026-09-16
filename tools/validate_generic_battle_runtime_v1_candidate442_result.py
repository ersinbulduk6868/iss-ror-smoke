#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

EXPECTED_RUNTIME = "ISS_GENERIC_BATTLE_RUNTIME_V1_CANDIDATE_4_4_2_G07"
EXPECTED_BUGATTI_SHA = "8cc074c40fe9ced7271cbeddf223cd9a520dee868977ffcbd439cec1c2b62cb4"
EXPECTED_GENERIC_SHA = "0b2710a840d128aee53161277edb8cb77e1930d339f53585c6faece3f1dc2b1c"
EXPECTED_CONTACT_AUTHORITY = "RECIPROCAL_NATIVE_SOLVER_RESPONSE_V1"
EXPECTED_DRAMA_MODEL = "PHYSICAL_CAUSAL_DRAMA_STATE_MACHINE_V1"
EXPECTED_DOMINANCE_MODEL = "LATEST_UNIQUE_DIRECT_G05_AGGRESSION_INITIATIVE_V3"
EXPECTED_COLLISION_AUTHORITY = "G04_G05_GENERIC_RUNTIME_AUTONOMY"


class ValidationError(RuntimeError):
    pass


def require(condition: bool, code: str) -> None:
    if not condition:
        raise ValidationError(code)


def load(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    require(isinstance(data, dict), f"EVIDENCE_NOT_OBJECT:{path}")
    return data


def asset_sha_check(base: dict[str, Any], expected_sha: str, label: str) -> None:
    assets = base.get("resolvedAssets") or {}
    require(set(assets) == {"actor_alpha", "actor_beta"}, f"{label}:ACTOR_SET_INVALID:{sorted(assets)}")
    for actor_id, row in assets.items():
        actual = str((row or {}).get("sha256") or "").lower()
        require(actual == expected_sha, f"{label}:ASSET_SHA_MISMATCH:{actor_id}:{actual}")


def validate_g05(base: dict[str, Any], label: str) -> dict[str, Any]:
    impacts = base.get("impacts") or []
    require(bool(impacts), f"{label}:IMPACTS_EMPTY")
    direct = []
    for row in impacts:
        require(row.get("nativeContactAuthority") is True, f"{label}:IMPACT_WITHOUT_NATIVE_AUTHORITY:{row.get('eventId')}")
        receipt = row.get("nativeContactReceipt")
        require(isinstance(receipt, dict), f"{label}:G05_RECEIPT_MISSING:{row.get('eventId')}")
        require(receipt.get("status") == "VERIFIED", f"{label}:G05_RECEIPT_NOT_VERIFIED:{row.get('eventId')}")
        model = str(row.get("contactAuthorityModel") or receipt.get("model") or "")
        require(model == EXPECTED_CONTACT_AUTHORITY, f"{label}:CONTACT_AUTHORITY_MODEL_MISMATCH:{model}")
        require(receipt.get("actorPoseOrVelocityMutation") is False, f"{label}:G05_POSE_VELOCITY_MUTATION")
        require(receipt.get("obbFinalContactAuthority") is False, f"{label}:OBB_FINAL_AUTHORITY_REGRESSION")
        require(receipt.get("nativeSweepFinalContactAuthority") is False, f"{label}:SWEEP_FINAL_AUTHORITY_REGRESSION")
        if row.get("nativeContactInheritedFromPhysicalTransaction") is not True:
            direct.append(row)
    require(len(direct) >= 3, f"{label}:DIRECT_G05_TRANSACTION_COVERAGE_LOW:{len(direct)}")

    damage_events = []
    for actor_id, actor in (base.get("actors") or {}).items():
        for damage in ((actor or {}).get("state") or {}).get("damageEvents") or []:
            if not isinstance(damage, dict):
                continue
            damage_events.append(damage)
            require(damage.get("g05NativeContactAuthority") is True, f"{label}:NATURAL_DAMAGE_WITHOUT_G05_AUTHORITY:{actor_id}")
            require(damage.get("g05ReceiptStatus") == "VERIFIED", f"{label}:NATURAL_DAMAGE_RECEIPT_NOT_VERIFIED:{actor_id}")
            require(damage.get("g05ContactAuthorityModel") == EXPECTED_CONTACT_AUTHORITY, f"{label}:NATURAL_DAMAGE_AUTHORITY_MISMATCH:{actor_id}")
    return {
        "directG05PhysicalTransactions": len(direct),
        "naturalDamageEventCount": len(damage_events),
    }


def transitions(drama: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {
        str(row.get("stage")): row
        for row in (drama.get("transitions") or [])
        if isinstance(row, dict) and row.get("stage")
    }


def validate_drama(drama: dict[str, Any], label: str) -> dict[str, Any]:
    require(drama.get("status") == "COMPLETE", f"{label}:G07_STATUS_NOT_COMPLETE:{drama.get('status')}")
    require(drama.get("candidate") == EXPECTED_RUNTIME, f"{label}:G07_CANDIDATE_MISMATCH:{drama.get('candidate')}")
    require(drama.get("model") == EXPECTED_DRAMA_MODEL, f"{label}:G07_MODEL_MISMATCH:{drama.get('model')}")
    require(drama.get("dominanceModel") == EXPECTED_DOMINANCE_MODEL, f"{label}:G07_DOMINANCE_MODEL_MISMATCH:{drama.get('dominanceModel')}")
    require(drama.get("collisionPlanningAuthority") == EXPECTED_COLLISION_AUTHORITY, f"{label}:COLLISION_AUTHORITY_INVALID:{drama.get('collisionPlanningAuthority')}")
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

    txs = drama.get("directTransactions") or []
    keys = [str(row.get("transactionKey") or "") for row in txs]
    require(len(keys) == len(set(keys)), f"{label}:DUPLICATE_DIRECT_TRANSACTION")
    require(len(txs) >= 3, f"{label}:DIRECT_TRANSACTION_COUNT_LOW:{len(txs)}")
    for row in txs:
        require(row.get("g05ReceiptStatus") == "VERIFIED", f"{label}:TRANSACTION_NOT_G05_VERIFIED:{row.get('eventId')}")
        require(row.get("g05ContactAuthorityModel") == EXPECTED_CONTACT_AUTHORITY, f"{label}:TRANSACTION_AUTHORITY_MISMATCH:{row.get('eventId')}")
        require(row.get("inheritedReciprocalAlias") is False, f"{label}:INHERITED_ALIAS_COUNTED_AS_DIRECT")

    opening = [row for row in txs if str(row.get("phase") or "") == "ESCALATION" and row.get("physicalInitiativeQualified") is True]
    counters = [row for row in txs if str(row.get("phase") or "") == "COUNTERATTACK" and row.get("physicalInitiativeQualified") is True]
    climaxes = [row for row in txs if str(row.get("phase") or "") == "CLIMAX" and row.get("physicalInitiativeQualified") is True]
    require(bool(opening), f"{label}:OPENING_DIRECT_G05_AGGRESSION_MISSING")
    require(bool(counters), f"{label}:COUNTER_DIRECT_G05_AGGRESSION_MISSING")
    require(bool(climaxes), f"{label}:CLIMAX_DIRECT_G05_AGGRESSION_MISSING")
    opening_tx = sorted(opening, key=lambda r: int(r.get("frame") or 0))[0]
    counter_tx = sorted(counters, key=lambda r: int(r.get("frame") or 0))[0]
    climax_tx = sorted(climaxes, key=lambda r: int(r.get("frame") or 0))[0]
    require(opening_tx.get("physicalInitiativeReason") == "DIRECT_G05_OPENING_AGGRESSION", f"{label}:OPENING_REASON_INVALID")
    require(counter_tx.get("attackerPreviouslyTargetedByOpponent") is True, f"{label}:COUNTER_WITHOUT_PRIOR_AGGRESSION")
    require(counter_tx.get("physicalInitiativeReason") == "DIRECT_G05_COUNTER_AFTER_PRIOR_AGGRESSION", f"{label}:COUNTER_REASON_INVALID")
    require(climax_tx.get("physicalInitiativeReason") == "DIRECT_G05_CLIMAX_AFTER_REVERSAL", f"{label}:CLIMAX_REASON_INVALID")

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
    require(xf > rf, f"{label}:CLIMAX_NOT_AFTER_REVERSAL")
    require(pf > xf, f"{label}:PAYOFF_NOT_AFTER_CLIMAX")

    activations = drama.get("eventActivations") or {}
    require((activations.get("evt-counterattack") or {}).get("reason") == "PRIOR_DIRECT_G05_AGGRESSION_FROM_TARGET", f"{label}:COUNTER_GUARD_NOT_PRIOR_AGGRESSION")
    require((activations.get("evt-climax") or {}).get("reason") == "PHYSICAL_DOMINANCE_REVERSAL_OBSERVED", f"{label}:CLIMAX_GUARD_NOT_REVERSAL")
    require((activations.get("evt-payoff") or {}).get("reason") == "CAUSAL_CLIMAX_OBSERVED", f"{label}:PAYOFF_GUARD_NOT_CLIMAX")

    expected_status = {
        "evt-setup": "OBSERVED",
        "evt-escalation": "SUCCEEDED",
        "evt-counterattack": "SUCCEEDED",
        "evt-climax": "SUCCEEDED",
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
        "openingDamageEarnedNaturally": bool(opening_tx.get("damageEarned")),
        "counterDamageEarnedNaturally": bool(counter_tx.get("damageEarned")),
        "climaxDamageEarnedNaturally": bool(climax_tx.get("damageEarned")),
        "escalationFrame": ef,
        "counterattackFrame": cf,
        "reversalFrame": rf,
        "climaxFrame": xf,
        "payoffFrame": pf,
    }


def validate_one(base: dict[str, Any], drama: dict[str, Any], expected_sha: str, label: str) -> dict[str, Any]:
    require(base.get("runtime") == EXPECTED_RUNTIME, f"{label}:RUNTIME_MISMATCH:{base.get('runtime')}")
    require(base.get("success") is True, f"{label}:BASE_RUNTIME_SUCCESS_FALSE")
    asset_sha_check(base, expected_sha, label)
    gates = base.get("gates") or {}
    bad = sorted(name for name, value in gates.items() if value is not True)
    require(not bad, f"{label}:BASE_GATE_FAIL:{','.join(bad)}")
    require((base.get("outcome") or {}).get("allRequiredEventsSucceeded") is True, f"{label}:BASE_OUTCOME_REQUIRED_EVENTS_FALSE")
    return {
        "status": "PASS",
        **validate_g05(base, label),
        **validate_drama(drama, label),
        "finalFrame": int(drama.get("finalFrame") or 0),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--bugatti-evidence", required=True)
    parser.add_argument("--bugatti-drama", required=True)
    parser.add_argument("--generic-evidence", required=True)
    parser.add_argument("--generic-drama", required=True)
    args = parser.parse_args()

    bugatti = validate_one(load(Path(args.bugatti_evidence)), load(Path(args.bugatti_drama)), EXPECTED_BUGATTI_SHA, "EXACT_BUGATTI")
    generic = validate_one(load(Path(args.generic_evidence)), load(Path(args.generic_drama)), EXPECTED_GENERIC_SHA, "GENERIC_HYPERCAR")

    print(json.dumps({
        "marker": "GENERIC_BATTLE_RUNTIME_CANDIDATE442_G07_MACHINE_ACCEPTANCE",
        "status": "PASS",
        "runtime": EXPECTED_RUNTIME,
        "dramaModel": EXPECTED_DRAMA_MODEL,
        "dominanceModel": EXPECTED_DOMINANCE_MODEL,
        "collisionPlanningAuthority": EXPECTED_COLLISION_AUTHORITY,
        "g04Preserved": True,
        "g05Preserved": True,
        "g06Preserved": True,
        "g07BattleStateMachineDramaticCausalProgression": True,
        "storyIntentOnly": True,
        "runtimeChoosesCollisionRealization": True,
        "g07DamageThresholdDependency": False,
        "issR041ScopePreserved": True,
        "issR042ScopePreserved": True,
        "exactBugatti": bugatti,
        "genericHypercar": generic,
        "productionReadyClaimed": False,
    }, sort_keys=True))


if __name__ == "__main__":
    main()
