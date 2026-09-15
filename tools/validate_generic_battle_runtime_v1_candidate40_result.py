#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path

EXPECTED_RUNTIME = "ISS_GENERIC_BATTLE_RUNTIME_V1_CANDIDATE_4_0_G04"
EXPECTED_BUGATTI_SHA = "8cc074c40fe9ced7271cbeddf223cd9a520dee868977ffcbd439cec1c2b62cb4"
EXPECTED_GENERIC_SHA = "0b2710a840d128aee53161277edb8cb77e1930d339f53585c6faece3f1dc2b1c"


class ValidationError(RuntimeError):
    pass


def load(path: Path) -> dict:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValidationError(f"EVIDENCE_NOT_OBJECT:{path}")
    return data


def validate_one(data: dict, *, expected_sha: str, label: str) -> dict[str, object]:
    if data.get("runtime") != EXPECTED_RUNTIME:
        raise ValidationError(f"{label}:RUNTIME_MISMATCH:{data.get('runtime')}")
    if data.get("success") is not True:
        raise ValidationError(f"{label}:RUNTIME_SUCCESS_FALSE")

    gates = data.get("gates") or {}
    required_gates = (
        "continuousWorld",
        "noActorPoseKeyframes",
        "assetIdentityVerified",
        "massReconciled",
        "solverCorrelatedImpactEvidence",
        "damageCausallyImpactGated",
        "persistentDebrisMaterialized",
        "allRequiredEventsSucceeded",
    )
    bad = [name for name in required_gates if gates.get(name) is not True]
    if bad:
        raise ValidationError(f"{label}:G04_RUNTIME_GATE_FAIL:" + ",".join(bad))

    assets = data.get("resolvedAssets") or {}
    if len(assets) != 2:
        raise ValidationError(f"{label}:EXPECTED_TWO_ACTORS")
    for entity, row in assets.items():
        if str(row.get("sha256") or "").lower() != expected_sha:
            raise ValidationError(f"{label}:ASSET_SHA_MISMATCH:{entity}")

    events = data.get("events") or {}
    contact_events = [
        row for event_id, row in events.items()
        if event_id.startswith("evt-contact-")
    ]
    if len(contact_events) != 2:
        raise ValidationError(f"{label}:CONTACT_EVENT_COUNT_INVALID:{len(contact_events)}")
    for row in contact_events:
        if row.get("status") != "SUCCEEDED":
            raise ValidationError(f"{label}:CONTACT_EVENT_NOT_SUCCEEDED")
        if int(row.get("contactCount") or 0) < 1:
            raise ValidationError(f"{label}:CONTACT_EVIDENCE_MISSING")
        if int(row.get("damageCount") or 0) != 0:
            raise ValidationError(f"{label}:G04_MOTION_FIXTURE_UNEXPECTED_DAMAGE")

    impacts = data.get("impacts") or []
    if len(impacts) < 2:
        raise ValidationError(f"{label}:QUALIFIED_IMPACT_EVIDENCE_MISSING")

    samples = data.get("controlSamples") or []
    if not samples:
        raise ValidationError(f"{label}:CONTROL_SAMPLES_EMPTY")
    attack_samples = [row for row in samples if str(row.get("eventId") or "").startswith("evt-contact-")]
    if not attack_samples:
        raise ValidationError(f"{label}:AUTONOMY_ATTACK_SAMPLES_EMPTY")
    actors = {row.get("actorId") for row in attack_samples}
    if actors != {"actor_alpha", "actor_beta"}:
        raise ValidationError(f"{label}:AUTONOMY_BOTH_ACTORS_NOT_OBSERVED:{sorted(str(x) for x in actors)}")
    max_refresh = max(int(row.get("targetRefreshCount") or 0) for row in attack_samples)
    if max_refresh < 5:
        raise ValidationError(f"{label}:TARGET_REFRESH_NOT_CONTINUOUS:{max_refresh}")
    modes = {str(row.get("mode") or "") for row in attack_samples}
    if "TRACK" not in modes:
        raise ValidationError(f"{label}:TRACK_MODE_MISSING")
    if "CONTACT_HANDOFF" not in modes:
        raise ValidationError(f"{label}:CONTACT_HANDOFF_MODE_MISSING")
    if any(str(row.get("reason") or "") == "ACTOR_DISABLED" for row in attack_samples):
        raise ValidationError(f"{label}:ACTOR_DISABLED_UNEXPECTED")

    damage_rows = [
        damage
        for actor in (data.get("actors") or {}).values()
        for damage in ((actor.get("state") or {}).get("damageEvents") or [])
    ]
    if damage_rows:
        raise ValidationError(f"{label}:MOTION_GATE_MUST_NOT_REQUIRE_DAMAGE")

    return {
        "status": "PASS",
        "actorCount": len(assets),
        "impactCount": len(impacts),
        "controlSampleCount": len(attack_samples),
        "maxTargetRefreshCount": max_refresh,
        "modes": sorted(modes),
        "replanCountObserved": max(int(row.get("replanCount") or 0) for row in attack_samples),
    }


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--bugatti-evidence", required=True)
    p.add_argument("--generic-evidence", required=True)
    args = p.parse_args()
    bugatti = validate_one(load(Path(args.bugatti_evidence)), expected_sha=EXPECTED_BUGATTI_SHA, label="EXACT_BUGATTI")
    generic = validate_one(load(Path(args.generic_evidence)), expected_sha=EXPECTED_GENERIC_SHA, label="GENERIC_HYPERCAR")
    print(json.dumps({
        "marker": "GENERIC_BATTLE_RUNTIME_CANDIDATE40_G04_MACHINE_ACCEPTANCE",
        "status": "PASS",
        "runtime": EXPECTED_RUNTIME,
        "exactBugatti": bugatti,
        "genericHypercar": generic,
        "g04ClosedLoopMotionOnly": True,
        "g05NativeContactTruthClaimed": False,
        "g06DamageClaimed": False,
        "productionReadyClaimed": False,
    }, sort_keys=True))


if __name__ == "__main__":
    main()
