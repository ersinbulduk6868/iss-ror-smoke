#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

EXPECTED_RUNTIME = "ISS_GENERIC_BATTLE_RUNTIME_V1_CANDIDATE_4_3_G06"
EXPECTED_BUGATTI_SHA = "8cc074c40fe9ced7271cbeddf223cd9a520dee868977ffcbd439cec1c2b62cb4"
EXPECTED_GENERIC_SHA = "0b2710a840d128aee53161277edb8cb77e1930d339f53585c6faece3f1dc2b1c"
EXPECTED_CONTACT_AUTHORITY = "RECIPROCAL_NATIVE_SOLVER_RESPONSE_V1"
EXPECTED_PERSISTENCE_MODEL = "CAUSAL_DAMAGE_PERSISTENT_STATE_V1"


class ValidationError(RuntimeError):
    pass


def load(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValidationError(f"EVIDENCE_NOT_OBJECT:{path}")
    return data


def _asset_sha_check(base: dict[str, Any], expected_sha: str, label: str) -> None:
    assets = base.get("resolvedAssets") or {}
    if set(assets) != {"actor_alpha", "actor_beta"}:
        raise ValidationError(f"{label}:ACTOR_SET_INVALID:{sorted(assets)}")
    for actor_id, row in assets.items():
        actual = str((row or {}).get("sha256") or "").lower()
        if actual != expected_sha:
            raise ValidationError(f"{label}:ASSET_SHA_MISMATCH:{actor_id}:{actual}")


def _validate_g05_truth(base: dict[str, Any], label: str) -> tuple[int, int]:
    impacts = base.get("impacts") or []
    direct = 0
    inherited = 0
    if not impacts:
        raise ValidationError(f"{label}:IMPACTS_EMPTY")
    for row in impacts:
        if row.get("nativeContactAuthority") is not True:
            raise ValidationError(f"{label}:IMPACT_WITHOUT_G05_AUTHORITY:{row.get('eventId')}")
        receipt = row.get("nativeContactReceipt")
        if not isinstance(receipt, dict) or receipt.get("status") != "VERIFIED":
            raise ValidationError(f"{label}:G05_RECEIPT_INVALID:{row.get('eventId')}")
        model = str(row.get("contactAuthorityModel") or receipt.get("model") or "")
        if model != EXPECTED_CONTACT_AUTHORITY:
            raise ValidationError(f"{label}:CONTACT_AUTHORITY_MODEL_MISMATCH:{model}")
        if receipt.get("actorPoseOrVelocityMutation") is not False:
            raise ValidationError(f"{label}:G05_RECEIPT_POSE_VELOCITY_MUTATION")
        if receipt.get("obbFinalContactAuthority") is not False:
            raise ValidationError(f"{label}:OBB_FINAL_AUTHORITY_REGRESSION")
        if receipt.get("nativeSweepFinalContactAuthority") is not False:
            raise ValidationError(f"{label}:SWEEP_FINAL_AUTHORITY_REGRESSION")
        if row.get("nativeContactInheritedFromPhysicalTransaction") is True:
            inherited += 1
        else:
            direct += 1
    if direct < 1 or inherited < 1:
        raise ValidationError(f"{label}:G05_TRANSACTION_COVERAGE_INVALID:{direct}:{inherited}")
    return direct, inherited


def _all_damage_events(base: dict[str, Any]) -> list[tuple[str, dict[str, Any]]]:
    rows: list[tuple[str, dict[str, Any]]] = []
    for actor_id, actor in (base.get("actors") or {}).items():
        state = (actor or {}).get("state") or {}
        for damage in state.get("damageEvents") or []:
            if isinstance(damage, dict):
                rows.append((str(actor_id), damage))
    return rows


def _validate_damage_provenance(base: dict[str, Any], label: str) -> int:
    damage = _all_damage_events(base)
    if not damage:
        raise ValidationError(f"{label}:DAMAGE_EVENTS_EMPTY")
    for actor_id, row in damage:
        if row.get("g05NativeContactAuthority") is not True:
            raise ValidationError(f"{label}:DAMAGE_WITHOUT_G05_PROVENANCE:{actor_id}:{row.get('frame')}")
        if row.get("g05ReceiptStatus") != "VERIFIED":
            raise ValidationError(f"{label}:DAMAGE_G05_RECEIPT_NOT_VERIFIED:{actor_id}:{row.get('frame')}")
        if row.get("g05ContactAuthorityModel") != EXPECTED_CONTACT_AUTHORITY:
            raise ValidationError(f"{label}:DAMAGE_AUTHORITY_MODEL_MISMATCH:{actor_id}")
        if row.get("detector") != EXPECTED_CONTACT_AUTHORITY:
            raise ValidationError(f"{label}:DAMAGE_DETECTOR_PROVENANCE_MISMATCH:{actor_id}:{row.get('detector')}")
    return len(damage)


def _validate_required_events(base: dict[str, Any], label: str) -> None:
    events = base.get("events") or {}
    for event_id in ("evt-first-alpha", "evt-first-beta"):
        row = events.get(event_id) or {}
        if row.get("status") != "SUCCEEDED":
            raise ValidationError(f"{label}:{event_id}:NOT_SUCCEEDED:{row.get('status')}")
        if int(row.get("contactCount") or 0) < 1 or int(row.get("damageCount") or 0) < 1:
            raise ValidationError(f"{label}:{event_id}:CONTACT_OR_DAMAGE_MISSING")
    follow = events.get("evt-damaged-followup") or {}
    if follow.get("status") != "SUCCEEDED":
        raise ValidationError(f"{label}:FOLLOWUP_NOT_SUCCEEDED:{follow.get('status')}")
    if int(follow.get("contactCount") or 0) < 1:
        raise ValidationError(f"{label}:FOLLOWUP_CONTACT_MISSING")
    payoff = events.get("evt-payoff") or {}
    if payoff.get("status") != "SETTLED":
        raise ValidationError(f"{label}:PAYOFF_NOT_SETTLED:{payoff.get('status')}")


def _visual_persistence(final_actor: dict[str, Any], label: str, actor_id: str) -> tuple[int, int]:
    visual = final_actor.get("visual") or {}
    if visual.get("realizedRootPresent") is not True:
        raise ValidationError(f"{label}:{actor_id}:REALIZED_DAMAGE_ROOT_MISSING")
    if int(visual.get("realizedMeshCount") or 0) < 1:
        raise ValidationError(f"{label}:{actor_id}:REALIZED_DAMAGE_MESHES_MISSING")
    if visual.get("originalVisualHiddenRender") is not True:
        raise ValidationError(f"{label}:{actor_id}:ORIGINAL_VISUAL_NOT_REPLACED")
    shape_keys = visual.get("damageShapeKeys") or []
    if not shape_keys or not any(float(row.get("value") or 0.0) > 0.0 for row in shape_keys):
        raise ValidationError(f"{label}:{actor_id}:ACTIVE_DAMAGE_SHAPE_KEY_MISSING")
    if not (visual.get("damageVisualEvidence") or []):
        raise ValidationError(f"{label}:{actor_id}:DAMAGE_VISUAL_EVIDENCE_MISSING")
    debris = visual.get("debris") or []
    if not debris:
        raise ValidationError(f"{label}:{actor_id}:PERSISTENT_DEBRIS_MISSING")
    for row in debris:
        if row.get("trajectoryInjection") is not False:
            raise ValidationError(f"{label}:{actor_id}:DEBRIS_TRAJECTORY_INJECTION")
        if row.get("rigidBodyPresent") is not True:
            raise ValidationError(f"{label}:{actor_id}:DEBRIS_RIGID_BODY_MISSING")
        if row.get("kinematic") is True:
            raise ValidationError(f"{label}:{actor_id}:DEBRIS_KINEMATIC")
        if row.get("hideRender") is True or row.get("hideViewport") is True:
            raise ValidationError(f"{label}:{actor_id}:DEBRIS_HIDDEN")
    return len(shape_keys), len(debris)


def validate_one(
    base: dict[str, Any],
    persistence: dict[str, Any],
    *,
    expected_sha: str,
    label: str,
) -> dict[str, Any]:
    if base.get("runtime") != EXPECTED_RUNTIME:
        raise ValidationError(f"{label}:RUNTIME_MISMATCH:{base.get('runtime')}")
    if base.get("success") is not True:
        raise ValidationError(f"{label}:RUNTIME_SUCCESS_FALSE")
    _asset_sha_check(base, expected_sha, label)

    gates = base.get("gates") or {}
    bad = [name for name, value in gates.items() if value is not True]
    if bad:
        raise ValidationError(f"{label}:BASE_RUNTIME_GATE_FAIL:" + ",".join(sorted(bad)))
    if not (base.get("outcome") or {}).get("allRequiredEventsSucceeded"):
        raise ValidationError(f"{label}:REQUIRED_EVENTS_OUTCOME_FALSE")
    if not (base.get("debrisObjects") or []):
        raise ValidationError(f"{label}:BASE_DEBRIS_OBJECTS_EMPTY")

    _validate_required_events(base, label)
    direct, inherited = _validate_g05_truth(base, label)
    damage_count = _validate_damage_provenance(base, label)

    if persistence.get("status") != "OBSERVED":
        raise ValidationError(f"{label}:PERSISTENCE_STATUS_INVALID:{persistence.get('status')}")
    if persistence.get("candidate") != EXPECTED_RUNTIME:
        raise ValidationError(f"{label}:PERSISTENCE_CANDIDATE_MISMATCH:{persistence.get('candidate')}")
    if persistence.get("model") != EXPECTED_PERSISTENCE_MODEL:
        raise ValidationError(f"{label}:PERSISTENCE_MODEL_MISMATCH:{persistence.get('model')}")
    for flag in (
        "actorPoseOrVelocityMutation",
        "damageThresholdChanged",
        "contactThresholdChanged",
        "stateResetMechanismIntroduced",
        "debrisTrajectoryInjectionIntroduced",
        "productionReadyClaimed",
    ):
        if persistence.get(flag) is not False:
            raise ValidationError(f"{label}:FORBIDDEN_FLAG_NOT_FALSE:{flag}:{persistence.get(flag)}")

    first = persistence.get("firstDamageState") or {}
    final = persistence.get("finalActors") or {}
    if set(first) != {"actor_alpha", "actor_beta"}:
        raise ValidationError(f"{label}:FIRST_DAMAGE_ACTOR_SET_INVALID:{sorted(first)}")
    if set(final) != {"actor_alpha", "actor_beta"}:
        raise ValidationError(f"{label}:FINAL_ACTOR_SET_INVALID:{sorted(final)}")
    if int(persistence.get("g05DamageProvenanceBoundCount") or 0) < 2:
        raise ValidationError(f"{label}:G05_DAMAGE_PROVENANCE_BOUND_COUNT_LOW")
    if not (persistence.get("g05BoundImpacts") or []):
        raise ValidationError(f"{label}:G05_BOUND_IMPACTS_EMPTY")

    shape_key_count = 0
    debris_count = 0
    for actor_id in ("actor_alpha", "actor_beta"):
        first_state = (first[actor_id] or {}).get("state") or {}
        final_state = (final[actor_id] or {}).get("state") or {}
        first_damage_events = int(first_state.get("damageEventCount") or 0)
        final_damage_events = int(final_state.get("damageEventCount") or 0)
        if first_damage_events < 1 or final_damage_events < first_damage_events:
            raise ValidationError(f"{label}:{actor_id}:DAMAGE_HISTORY_RESET")
        if float(first_state.get("structuralIntegrity", 1.0)) >= 1.0:
            raise ValidationError(f"{label}:{actor_id}:FIRST_DAMAGE_STRUCTURAL_UNCHANGED")
        if float(first_state.get("driveEfficiency", 1.0)) >= 1.0:
            raise ValidationError(f"{label}:{actor_id}:FIRST_DAMAGE_DRIVE_UNCHANGED")
        if float(final_state.get("structuralIntegrity", 1.0)) > float(first_state.get("structuralIntegrity", 1.0)) + 1.0e-9:
            raise ValidationError(f"{label}:{actor_id}:STRUCTURAL_STATE_HEALED_OR_RESET")
        if float(final_state.get("driveEfficiency", 1.0)) > float(first_state.get("driveEfficiency", 1.0)) + 1.0e-9:
            raise ValidationError(f"{label}:{actor_id}:DRIVE_STATE_HEALED_OR_RESET")
        shapes, debris = _visual_persistence(final[actor_id], label, actor_id)
        shape_key_count += shapes
        debris_count += debris

    later = persistence.get("laterDamagedEventObservations") or []
    beta_rows = [
        row for row in later
        if row.get("actorId") == "actor_beta" and row.get("eventId") == "evt-damaged-followup"
    ]
    if not beta_rows:
        raise ValidationError(f"{label}:DAMAGED_FOLLOWUP_OBSERVATION_MISSING")
    follow = beta_rows[0]
    if int(follow.get("priorImpactFrame") or -1) >= int(follow.get("eventStartFrame") or -1):
        raise ValidationError(f"{label}:FOLLOWUP_NOT_AFTER_PRIOR_IMPACT")
    state = follow.get("state") or {}
    capability = follow.get("effectiveCapability") or {}
    efficiency = float(state.get("driveEfficiency", 1.0))
    if efficiency >= 1.0:
        raise ValidationError(f"{label}:FOLLOWUP_DID_NOT_CONSUME_DEGRADED_STATE")
    if float(capability.get("effectiveMaxSpeedMps") or 0.0) >= float(capability.get("profileMaxSpeedMps") or 0.0):
        raise ValidationError(f"{label}:FOLLOWUP_CAPABILITY_NOT_REDUCED")
    if follow.get("controlSample") is None:
        raise ValidationError(f"{label}:FOLLOWUP_CONTROL_SAMPLE_MISSING")
    if bool(state.get("disabled")):
        sample = follow.get("controlSample") or {}
        if sample.get("mode") != "DISABLED" or sample.get("motorAuthority") != "COAST":
            raise ValidationError(f"{label}:DISABLED_ACTOR_RETAINED_CONTROL_AUTHORITY")

    return {
        "status": "PASS",
        "directG05PhysicalTransactions": direct,
        "inheritedReciprocalTransactions": inherited,
        "damageEventsWithG05Provenance": damage_count,
        "g05DamageProvenanceBoundCount": int(persistence.get("g05DamageProvenanceBoundCount") or 0),
        "laterDamagedEventObservationCount": len(beta_rows),
        "followupDriveEfficiency": efficiency,
        "followupEffectiveMaxSpeedMps": float(capability.get("effectiveMaxSpeedMps") or 0.0),
        "followupProfileMaxSpeedMps": float(capability.get("profileMaxSpeedMps") or 0.0),
        "persistentDamageShapeKeyCount": shape_key_count,
        "persistentDebrisCount": debris_count,
        "finalFrame": int(persistence.get("finalFrame") or 0),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--bugatti-evidence", required=True)
    parser.add_argument("--bugatti-persistence", required=True)
    parser.add_argument("--generic-evidence", required=True)
    parser.add_argument("--generic-persistence", required=True)
    args = parser.parse_args()

    bugatti = validate_one(
        load(Path(args.bugatti_evidence)),
        load(Path(args.bugatti_persistence)),
        expected_sha=EXPECTED_BUGATTI_SHA,
        label="EXACT_BUGATTI",
    )
    generic = validate_one(
        load(Path(args.generic_evidence)),
        load(Path(args.generic_persistence)),
        expected_sha=EXPECTED_GENERIC_SHA,
        label="GENERIC_HYPERCAR",
    )
    print(json.dumps({
        "marker": "GENERIC_BATTLE_RUNTIME_CANDIDATE43_G06_MACHINE_ACCEPTANCE",
        "status": "PASS",
        "runtime": EXPECTED_RUNTIME,
        "persistenceModel": EXPECTED_PERSISTENCE_MODEL,
        "g04Preserved": True,
        "g05Preserved": True,
        "g06CausalDamagePersistentState": True,
        "exactBugatti": bugatti,
        "genericHypercar": generic,
        "g07DramaClaimed": False,
        "productionReadyClaimed": False,
    }, sort_keys=True))


if __name__ == "__main__":
    main()
