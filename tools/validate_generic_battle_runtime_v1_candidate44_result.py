#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

EXPECTED_RUNTIME = "ISS_GENERIC_BATTLE_RUNTIME_V1_CANDIDATE_4_4_G07"
EXPECTED_BUGATTI_SHA = "8cc074c40fe9ced7271cbeddf223cd9a520dee868977ffcbd439cec1c2b62cb4"
EXPECTED_GENERIC_SHA = "0b2710a840d128aee53161277edb8cb77e1930d339f53585c6faece3f1dc2b1c"
EXPECTED_CONTACT_AUTHORITY = "RECIPROCAL_NATIVE_SOLVER_RESPONSE_V1"
EXPECTED_PERSISTENCE_MODEL = "CAUSAL_DAMAGE_PERSISTENT_STATE_V1"
EXPECTED_DRAMA_MODEL = "PHYSICAL_CAUSAL_DRAMA_STATE_MACHINE_V1"
EXPECTED_DOMINANCE_MODEL = "LATEST_UNIQUE_DIRECT_G05_DAMAGE_INITIATIVE_V1"


class ValidationError(RuntimeError):
    pass


def load(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValidationError(f"EVIDENCE_NOT_OBJECT:{path}")
    return data


def require(condition: bool, code: str) -> None:
    if not condition:
        raise ValidationError(code)


def asset_sha_check(base: dict[str, Any], expected_sha: str, label: str) -> None:
    assets = base.get("resolvedAssets") or {}
    require(set(assets) == {"actor_alpha", "actor_beta"}, f"{label}:ACTOR_SET_INVALID:{sorted(assets)}")
    for actor_id, row in assets.items():
        actual = str((row or {}).get("sha256") or "").lower()
        require(actual == expected_sha, f"{label}:ASSET_SHA_MISMATCH:{actor_id}:{actual}")


def all_damage_events(base: dict[str, Any]) -> list[tuple[str, dict[str, Any]]]:
    rows: list[tuple[str, dict[str, Any]]] = []
    for actor_id, actor in (base.get("actors") or {}).items():
        state = (actor or {}).get("state") or {}
        for damage in state.get("damageEvents") or []:
            if isinstance(damage, dict):
                rows.append((str(actor_id), damage))
    return rows


def validate_g05_and_damage(base: dict[str, Any], label: str) -> tuple[int, int]:
    impacts = base.get("impacts") or []
    require(bool(impacts), f"{label}:IMPACTS_EMPTY")
    direct = 0
    for row in impacts:
        require(row.get("nativeContactAuthority") is True, f"{label}:IMPACT_WITHOUT_G05_AUTHORITY:{row.get('eventId')}")
        receipt = row.get("nativeContactReceipt")
        require(isinstance(receipt, dict), f"{label}:G05_RECEIPT_MISSING:{row.get('eventId')}")
        require(receipt.get("status") == "VERIFIED", f"{label}:G05_RECEIPT_NOT_VERIFIED:{row.get('eventId')}")
        model = str(row.get("contactAuthorityModel") or receipt.get("model") or "")
        require(model == EXPECTED_CONTACT_AUTHORITY, f"{label}:CONTACT_AUTHORITY_MODEL_MISMATCH:{model}")
        require(receipt.get("actorPoseOrVelocityMutation") is False, f"{label}:G05_POSE_VELOCITY_MUTATION")
        require(receipt.get("obbFinalContactAuthority") is False, f"{label}:OBB_FINAL_AUTHORITY_REGRESSION")
        require(receipt.get("nativeSweepFinalContactAuthority") is False, f"{label}:SWEEP_FINAL_AUTHORITY_REGRESSION")
        if row.get("nativeContactInheritedFromPhysicalTransaction") is not True:
            direct += 1
    require(direct >= 3, f"{label}:DIRECT_G05_TRANSACTION_COVERAGE_LOW:{direct}")

    damage = all_damage_events(base)
    require(bool(damage), f"{label}:DAMAGE_EVENTS_EMPTY")
    for actor_id, row in damage:
        require(row.get("g05NativeContactAuthority") is True, f"{label}:DAMAGE_WITHOUT_G05_PROVENANCE:{actor_id}:{row.get('frame')}")
        require(row.get("g05ReceiptStatus") == "VERIFIED", f"{label}:DAMAGE_G05_RECEIPT_NOT_VERIFIED:{actor_id}:{row.get('frame')}")
        require(row.get("g05ContactAuthorityModel") == EXPECTED_CONTACT_AUTHORITY, f"{label}:DAMAGE_AUTHORITY_MODEL_MISMATCH:{actor_id}")
        require(row.get("detector") == EXPECTED_CONTACT_AUTHORITY, f"{label}:DAMAGE_DETECTOR_PROVENANCE_MISMATCH:{actor_id}:{row.get('detector')}")
    return direct, len(damage)


def validate_g06_persistence(persistence: dict[str, Any], label: str) -> dict[str, Any]:
    require(persistence.get("status") == "OBSERVED", f"{label}:G06_PERSISTENCE_STATUS_INVALID:{persistence.get('status')}")
    require(persistence.get("candidate") == EXPECTED_RUNTIME, f"{label}:G06_CANDIDATE_MISMATCH:{persistence.get('candidate')}")
    require(persistence.get("model") == EXPECTED_PERSISTENCE_MODEL, f"{label}:G06_PERSISTENCE_MODEL_MISMATCH:{persistence.get('model')}")
    for flag in (
        "actorPoseOrVelocityMutation",
        "damageThresholdChanged",
        "contactThresholdChanged",
        "stateResetMechanismIntroduced",
        "debrisTrajectoryInjectionIntroduced",
        "productionReadyClaimed",
    ):
        require(persistence.get(flag) is False, f"{label}:G06_FORBIDDEN_FLAG:{flag}:{persistence.get(flag)}")

    require(int(persistence.get("g05DamageProvenanceBoundCount") or 0) >= 2, f"{label}:G06_G05_PROVENANCE_BINDINGS_LOW")
    require(bool(persistence.get("g05BoundImpacts") or []), f"{label}:G06_BOUND_IMPACTS_EMPTY")
    final_actors = persistence.get("finalActors") or {}
    require(set(final_actors) == {"actor_alpha", "actor_beta"}, f"{label}:G06_FINAL_ACTOR_SET_INVALID:{sorted(final_actors)}")

    damaged_actor_count = 0
    shape_keys = 0
    debris = 0
    for actor_id, actor in final_actors.items():
        state = (actor or {}).get("state") or {}
        visual = (actor or {}).get("visual") or {}
        if int(state.get("damageEventCount") or 0) <= 0:
            continue
        damaged_actor_count += 1
        require(float(state.get("structuralIntegrity", 1.0)) < 1.0, f"{label}:{actor_id}:G06_STRUCTURAL_NOT_DEGRADED")
        require(float(state.get("driveEfficiency", 1.0)) < 1.0, f"{label}:{actor_id}:G06_DRIVE_NOT_DEGRADED")
        require(visual.get("realizedRootPresent") is True, f"{label}:{actor_id}:G06_REALIZED_ROOT_MISSING")
        require(int(visual.get("realizedMeshCount") or 0) >= 1, f"{label}:{actor_id}:G06_REALIZED_MESH_MISSING")
        active_keys = [row for row in (visual.get("damageShapeKeys") or []) if float(row.get("value") or 0.0) > 0.0]
        require(bool(active_keys), f"{label}:{actor_id}:G06_ACTIVE_DAMAGE_SHAPE_KEY_MISSING")
        actor_debris = visual.get("debris") or []
        require(bool(actor_debris), f"{label}:{actor_id}:G06_PERSISTENT_DEBRIS_MISSING")
        for row in actor_debris:
            require(row.get("trajectoryInjection") is False, f"{label}:{actor_id}:G06_DEBRIS_TRAJECTORY_INJECTION")
            require(row.get("rigidBodyPresent") is True, f"{label}:{actor_id}:G06_DEBRIS_RIGID_BODY_MISSING")
            require(row.get("kinematic") is not True, f"{label}:{actor_id}:G06_DEBRIS_KINEMATIC")
        shape_keys += len(active_keys)
        debris += len(actor_debris)
    require(damaged_actor_count >= 1, f"{label}:G06_NO_DAMAGED_ACTOR")
    require(debris >= 1, f"{label}:G06_NO_PERSISTENT_DEBRIS")

    later = persistence.get("laterDamagedEventObservations") or []
    require(bool(later), f"{label}:G06_LATER_DAMAGED_EVENT_OBSERVATION_MISSING")
    consumed = []
    for row in later:
        state = row.get("state") or {}
        capability = row.get("effectiveCapability") or {}
        efficiency = float(state.get("driveEfficiency", 1.0))
        profile = float(capability.get("profileMaxSpeedMps") or 0.0)
        effective = float(capability.get("effectiveMaxSpeedMps") or 0.0)
        if efficiency < 1.0 and profile > 0.0 and effective < profile and row.get("controlSample") is not None:
            consumed.append(row)
    require(bool(consumed), f"{label}:G06_DEGRADED_CAPABILITY_NOT_CONSUMED")
    return {
        "persistentDamageShapeKeyCount": shape_keys,
        "persistentDebrisCount": debris,
        "laterDamagedEventObservationCount": len(consumed),
    }


def transition_map(drama: dict[str, Any]) -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    for row in drama.get("transitions") or []:
        if isinstance(row, dict) and row.get("stage"):
            out[str(row["stage"])] = row
    return out


def validate_g07_drama(drama: dict[str, Any], label: str) -> dict[str, Any]:
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
    earned = [row for row in transactions if row.get("damageEarned") is True]
    require(len(earned) >= 3, f"{label}:G07_DIRECT_DAMAGE_TRANSACTION_COUNT_LOW:{len(earned)}")
    for row in transactions:
        require(row.get("g05ReceiptStatus") == "VERIFIED", f"{label}:G07_TRANSACTION_G05_UNVERIFIED:{row.get('eventId')}")
        require(row.get("g05ContactAuthorityModel") == EXPECTED_CONTACT_AUTHORITY, f"{label}:G07_TRANSACTION_AUTHORITY_MISMATCH:{row.get('eventId')}")
        require(row.get("inheritedReciprocalAlias") is False, f"{label}:G07_INHERITED_ALIAS_COUNTED_AS_DIRECT")

    by_phase: dict[str, list[dict[str, Any]]] = {}
    for row in earned:
        by_phase.setdefault(str(row.get("phase") or ""), []).append(row)
    for phase in ("ESCALATION", "COUNTERATTACK", "CLIMAX"):
        require(bool(by_phase.get(phase)), f"{label}:G07_{phase}_DIRECT_DAMAGE_MISSING")
    counter_tx = by_phase["COUNTERATTACK"][0]
    require(counter_tx.get("attackerPreviouslyDamagedByTarget") is True, f"{label}:G07_COUNTERATTACK_NOT_CAUSED_BY_PRIOR_DAMAGE")

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
    require(counter_frame > escalation_frame, f"{label}:G07_COUNTERATTACK_NOT_AFTER_ESCALATION")
    require(reversal_frame >= counter_frame, f"{label}:G07_REVERSAL_NOT_FROM_COUNTERATTACK")
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
    require(int(counter_activation.get("frame") or -1) > escalation_frame, f"{label}:G07_COUNTER_ACTIVATED_BEFORE_ESCALATION_DAMAGE")
    require(climax_activation.get("reason") == "PHYSICAL_DOMINANCE_REVERSAL_OBSERVED", f"{label}:G07_CLIMAX_GUARD_NOT_REVERSAL_DRIVEN:{climax_activation.get('reason')}")
    require(int(climax_activation.get("frame") or -1) >= reversal_frame, f"{label}:G07_CLIMAX_ACTIVATED_BEFORE_REVERSAL")
    require(payoff_activation.get("reason") == "CAUSAL_CLIMAX_OBSERVED", f"{label}:G07_PAYOFF_GUARD_NOT_CLIMAX_DRIVEN:{payoff_activation.get('reason')}")
    require(int(payoff_activation.get("frame") or -1) >= climax_frame, f"{label}:G07_PAYOFF_ACTIVATED_BEFORE_CLIMAX")

    event_states = drama.get("eventStates") or {}
    expected_status = {
        "evt-setup": "OBSERVED",
        "evt-escalation": "SUCCEEDED",
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
        "directDamageTransactions": len(earned),
        "initialDominantActor": initial_actor,
        "reversalToActor": str(reversal.get("toActorId") or ""),
        "escalationFrame": escalation_frame,
        "counterattackFrame": counter_frame,
        "reversalFrame": reversal_frame,
        "climaxFrame": climax_frame,
        "payoffFrame": payoff_frame,
    }


def validate_one(
    base: dict[str, Any],
    persistence: dict[str, Any],
    drama: dict[str, Any],
    *,
    expected_sha: str,
    label: str,
) -> dict[str, Any]:
    require(base.get("runtime") == EXPECTED_RUNTIME, f"{label}:RUNTIME_MISMATCH:{base.get('runtime')}")
    require(base.get("success") is True, f"{label}:BASE_RUNTIME_SUCCESS_FALSE")
    asset_sha_check(base, expected_sha, label)
    gates = base.get("gates") or {}
    bad = sorted(name for name, value in gates.items() if value is not True)
    require(not bad, f"{label}:BASE_GATE_FAIL:{','.join(bad)}")
    require((base.get("outcome") or {}).get("allRequiredEventsSucceeded") is True, f"{label}:BASE_OUTCOME_REQUIRED_EVENTS_FALSE")
    require(bool(base.get("debrisObjects") or []), f"{label}:BASE_DEBRIS_EMPTY")

    direct, damage = validate_g05_and_damage(base, label)
    g06 = validate_g06_persistence(persistence, label)
    g07 = validate_g07_drama(drama, label)
    return {
        "status": "PASS",
        "directG05PhysicalTransactions": direct,
        "damageEventsWithG05Provenance": damage,
        **g06,
        **g07,
        "finalFrame": int(drama.get("finalFrame") or 0),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--bugatti-evidence", required=True)
    parser.add_argument("--bugatti-persistence", required=True)
    parser.add_argument("--bugatti-drama", required=True)
    parser.add_argument("--generic-evidence", required=True)
    parser.add_argument("--generic-persistence", required=True)
    parser.add_argument("--generic-drama", required=True)
    args = parser.parse_args()

    bugatti = validate_one(
        load(Path(args.bugatti_evidence)),
        load(Path(args.bugatti_persistence)),
        load(Path(args.bugatti_drama)),
        expected_sha=EXPECTED_BUGATTI_SHA,
        label="EXACT_BUGATTI",
    )
    generic = validate_one(
        load(Path(args.generic_evidence)),
        load(Path(args.generic_persistence)),
        load(Path(args.generic_drama)),
        expected_sha=EXPECTED_GENERIC_SHA,
        label="GENERIC_HYPERCAR",
    )

    print(json.dumps({
        "marker": "GENERIC_BATTLE_RUNTIME_CANDIDATE44_G07_MACHINE_ACCEPTANCE",
        "status": "PASS",
        "runtime": EXPECTED_RUNTIME,
        "dramaModel": EXPECTED_DRAMA_MODEL,
        "dominanceModel": EXPECTED_DOMINANCE_MODEL,
        "g04Preserved": True,
        "g05Preserved": True,
        "g06Preserved": True,
        "g07BattleStateMachineDramaticCausalProgression": True,
        "exactBugatti": bugatti,
        "genericHypercar": generic,
        "productionReadyClaimed": False,
    }, sort_keys=True))


if __name__ == "__main__":
    main()
