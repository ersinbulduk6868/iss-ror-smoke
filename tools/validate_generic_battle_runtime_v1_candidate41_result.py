#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path

EXPECTED_RUNTIME = "ISS_GENERIC_BATTLE_RUNTIME_V1_CANDIDATE_4_1_G05"
EXPECTED_CONTACT_MODEL = "BLENDER_NATIVE_ACTUAL_STEP_SWEEP_PLUS_SOLVER_RESPONSE_V1"
EXPECTED_API = "RigidBodyWorld.convex_sweep_test"
EXPECTED_PATH_AUTHORITY = "ACTUAL_SOLVER_STEP_ONLY"
EXPECTED_BUGATTI_SHA = "8cc074c40fe9ced7271cbeddf223cd9a520dee868977ffcbd439cec1c2b62cb4"
EXPECTED_GENERIC_SHA = "0b2710a840d128aee53161277edb8cb77e1930d339f53585c6faece3f1dc2b1c"


class ValidationError(RuntimeError):
    pass


def load(path: Path) -> dict:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValidationError(f"EVIDENCE_NOT_OBJECT:{path}")
    return value


def validate_one(data: dict, *, label: str, expected_sha: str) -> dict[str, object]:
    if data.get("runtime") != EXPECTED_RUNTIME:
        raise ValidationError(f"{label}:RUNTIME_MISMATCH:{data.get('runtime')}")
    if data.get("success") is not True:
        raise ValidationError(f"{label}:RUNTIME_SUCCESS_FALSE")
    models = data.get("models") or {}
    if models.get("contact") != EXPECTED_CONTACT_MODEL:
        raise ValidationError(f"{label}:CONTACT_MODEL_MISMATCH:{models.get('contact')}")

    gates = data.get("gates") or {}
    inherited = (
        "continuousWorld",
        "noActorPoseKeyframes",
        "assetIdentityVerified",
        "massReconciled",
        "solverCorrelatedImpactEvidence",
        "damageCausallyImpactGated",
        "allRequiredEventsSucceeded",
    )
    bad = [name for name in inherited if gates.get(name) is not True]
    if bad:
        raise ValidationError(f"{label}:INHERITED_GATE_FAIL:" + ",".join(bad))

    assets = data.get("resolvedAssets") or {}
    if set(assets) != {"actor_alpha", "actor_beta"}:
        raise ValidationError(f"{label}:ACTOR_SET_INVALID:{sorted(assets)}")
    for entity, row in assets.items():
        if str(row.get("sha256") or "").lower() != expected_sha:
            raise ValidationError(f"{label}:ASSET_SHA_MISMATCH:{entity}")

    events = data.get("events") or {}
    contact_events = {
        event_id: row for event_id, row in events.items()
        if event_id.startswith("evt-contact-")
    }
    if set(contact_events) != {"evt-contact-alpha", "evt-contact-beta"}:
        raise ValidationError(f"{label}:CONTACT_EVENT_SET_INVALID:{sorted(contact_events)}")
    for event_id, row in contact_events.items():
        if row.get("status") != "SUCCEEDED" or int(row.get("contactCount") or 0) < 1:
            raise ValidationError(f"{label}:CONTACT_EVENT_NOT_SUCCEEDED:{event_id}")

    impacts = data.get("impacts") or []
    by_event = {str(row.get("eventId") or ""): row for row in impacts}
    if not set(contact_events).issubset(by_event):
        raise ValidationError(f"{label}:CONTACT_IMPACT_ROWS_MISSING")

    direct_native = 0
    inherited_native = 0
    for event_id in sorted(contact_events):
        row = by_event[event_id]
        if row.get("nativeContactAuthority") is not True:
            raise ValidationError(f"{label}:NATIVE_AUTHORITY_FALSE:{event_id}")
        receipt = row.get("nativeContactReceipt") or {}
        if receipt.get("status") != "VERIFIED":
            raise ValidationError(f"{label}:NATIVE_RECEIPT_NOT_VERIFIED:{event_id}")
        if receipt.get("model") != EXPECTED_CONTACT_MODEL:
            raise ValidationError(f"{label}:NATIVE_MODEL_MISMATCH:{event_id}")
        if receipt.get("api") != EXPECTED_API:
            raise ValidationError(f"{label}:NATIVE_API_MISMATCH:{event_id}")
        if receipt.get("pathAuthority") != EXPECTED_PATH_AUTHORITY:
            raise ValidationError(f"{label}:PATH_AUTHORITY_MISMATCH:{event_id}")
        if receipt.get("targetIdentityUnique") is not True or receipt.get("semanticPass") is not True:
            raise ValidationError(f"{label}:TARGET_OR_SEMANTIC_AUTHORITY_FAIL:{event_id}")
        if receipt.get("controllerCutoffObserved") is not True or receipt.get("motorAuthorityZero") is not True:
            raise ValidationError(f"{label}:CONTROLLER_HANDOFF_FAIL:{event_id}")
        if receipt.get("obbUsed") is not False:
            raise ValidationError(f"{label}:OBB_FINAL_AUTHORITY_PRESENT:{event_id}")
        if receipt.get("predictiveExtensionUsed") is not False:
            raise ValidationError(f"{label}:PREDICTIVE_EXTENSION_PRESENT:{event_id}")
        if receipt.get("actorPoseOrVelocityMutation") is not False:
            raise ValidationError(f"{label}:POSE_VELOCITY_MUTATION_PRESENT:{event_id}")
        if float(receipt.get("sweepDistanceM") or 0.0) <= 0.0:
            raise ValidationError(f"{label}:ACTUAL_STEP_SWEEP_DISTANCE_INVALID:{event_id}")

        evidence = row.get("evidence") or {}
        if float(evidence.get("normal_closing_speed_mps") or 0.0) < 1.25:
            raise ValidationError(f"{label}:SOLVER_CLOSING_RESPONSE_INVALID:{event_id}")
        response = max(
            float(evidence.get("response_delta_attacker_mps") or 0.0),
            float(evidence.get("response_delta_target_mps") or 0.0),
        )
        if response <= 0.0:
            raise ValidationError(f"{label}:SOLVER_RESPONSE_DELTA_MISSING:{event_id}")

        if row.get("nativeContactInheritedFromPhysicalTransaction") is True:
            inherited_native += 1
        else:
            direct_native += 1

    if direct_native < 1:
        raise ValidationError(f"{label}:DIRECT_NATIVE_PHYSICAL_TRANSACTION_MISSING")

    samples = data.get("controlSamples") or []
    contact_samples = [
        row for row in samples
        if str(row.get("eventId") or "").startswith("evt-contact-")
    ]
    if not contact_samples:
        raise ValidationError(f"{label}:G04_CONTROL_SAMPLES_MISSING")
    modes = {str(row.get("mode") or "") for row in contact_samples}
    if not {"TRACK", "CONTACT_HANDOFF"}.issubset(modes):
        raise ValidationError(f"{label}:G04_MODES_REGRESSED:{sorted(modes)}")
    max_refresh = max(int(row.get("targetRefreshCount") or 0) for row in contact_samples)
    if max_refresh < 5:
        raise ValidationError(f"{label}:G04_TARGET_REFRESH_REGRESSED:{max_refresh}")

    return {
        "status": "PASS",
        "directNativeTransactions": direct_native,
        "inheritedReciprocalTransactions": inherited_native,
        "impactCount": len(impacts),
        "maxTargetRefreshCount": max_refresh,
        "g04Modes": sorted(modes),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--bugatti-evidence", required=True)
    parser.add_argument("--generic-evidence", required=True)
    args = parser.parse_args()

    bugatti = validate_one(
        load(Path(args.bugatti_evidence)),
        label="EXACT_BUGATTI",
        expected_sha=EXPECTED_BUGATTI_SHA,
    )
    generic = validate_one(
        load(Path(args.generic_evidence)),
        label="GENERIC_HYPERCAR",
        expected_sha=EXPECTED_GENERIC_SHA,
    )
    print(json.dumps({
        "marker": "GENERIC_BATTLE_RUNTIME_CANDIDATE41_G05_MACHINE_ACCEPTANCE",
        "status": "PASS",
        "runtime": EXPECTED_RUNTIME,
        "nativeContactModel": EXPECTED_CONTACT_MODEL,
        "exactBugatti": bugatti,
        "genericHypercar": generic,
        "g04Preserved": True,
        "g05NativeContactTruth": True,
        "g06DamagePersistentStateClaimed": False,
        "productionReadyClaimed": False,
    }, sort_keys=True))


if __name__ == "__main__":
    main()
