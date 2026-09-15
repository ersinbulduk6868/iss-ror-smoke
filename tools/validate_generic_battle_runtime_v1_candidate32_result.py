#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path

EXPECTED_RUNTIME = "ISS_GENERIC_BATTLE_RUNTIME_V1_CANDIDATE_3_2"
EXPECTED_CONTROL = "DIFFERENTIAL_RIGID_BODY_MOTOR_V1_1"
EXPECTED_ASSET_SHA = "0b2710a840d128aee53161277edb8cb77e1930d339f53585c6faece3f1dc2b1c"
MIN_DAMAGE_SEVERITY = 0.055


class ResultValidationError(RuntimeError):
    pass


def args() -> argparse.Namespace:
    p = argparse.ArgumentParser()
    p.add_argument(
        "--evidence",
        default="artifacts/generic-battle-runtime-v1-preflight/generic-battle-runtime-v1-evidence.json",
    )
    return p.parse_args()


def require(condition: bool, marker: str) -> None:
    if not condition:
        raise ResultValidationError(marker)


def main() -> None:
    path = Path(args().evidence).resolve()
    require(path.is_file(), f"EVIDENCE_FILE_MISSING:{path}")
    evidence = json.loads(path.read_text(encoding="utf-8"))

    require(evidence.get("runtime") == EXPECTED_RUNTIME, "RUNTIME_VERSION_MISMATCH")
    require(evidence.get("success") is True, "EVIDENCE_SUCCESS_NOT_TRUE")
    models = evidence.get("models") or {}
    require(models.get("control") == EXPECTED_CONTROL, "CONTROL_MODEL_MISMATCH")

    program = evidence.get("program") or {}
    require(program.get("actorCount") == 2, "ACTOR_COUNT_NOT_TWO")
    require(program.get("eventCount") == 3, "EVENT_COUNT_NOT_THREE")
    require(program.get("totalFrames", 0) > 30, "FRAME_COUNT_IMPLAUSIBLE")

    gates = evidence.get("gates") or {}
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
    missing_or_false = [name for name in required_gates if gates.get(name) is not True]
    require(not missing_or_false, "GATES_FAILED:" + ",".join(missing_or_false))

    assets = evidence.get("resolvedAssets") or {}
    require(set(assets) == {"actor_alpha", "actor_beta"}, "RESOLVED_ASSET_IDENTITIES_INVALID")
    for actor_id, row in assets.items():
        require(row.get("sha256") == EXPECTED_ASSET_SHA, f"ASSET_SHA_MISMATCH:{actor_id}")
        require(int(row.get("visibleMeshCount") or 0) >= 1, f"VISIBLE_GEOMETRY_MISSING:{actor_id}")

    impacts = evidence.get("impacts") or []
    qualified = [row for row in impacts if row.get("eventId") == "evt-impact"]
    require(bool(qualified), "QUALIFIED_IMPACT_EVENT_MISSING")
    earned = [
        row
        for row in qualified
        if row.get("controllerCutoffObserved") is True
        and row.get("damageEarned") is True
        and float((row.get("evidence") or {}).get("severity") or 0.0) >= MIN_DAMAGE_SEVERITY
        and float((row.get("evidence") or {}).get("impact_energy_j") or 0.0) > 0.0
        and float((row.get("evidence") or {}).get("normal_closing_speed_mps") or 0.0) > 1.25
    ]
    require(bool(earned), "NO_EARNED_DAMAGE_WITH_CONTROLLER_CUTOFF")
    first_impact_frame = min(int((row.get("evidence") or {}).get("frame") or 10**9) for row in earned)

    events = evidence.get("events") or {}
    impact_event = events.get("evt-impact") or {}
    payoff_event = events.get("evt-payoff") or {}
    require(impact_event.get("status") == "SUCCEEDED", "IMPACT_EVENT_NOT_SUCCEEDED")
    require(int(impact_event.get("contactCount") or 0) >= 1, "IMPACT_CONTACT_COUNT_ZERO")
    require(int(impact_event.get("damageCount") or 0) >= 1, "IMPACT_DAMAGE_COUNT_ZERO")
    require(payoff_event.get("status") in {"SETTLED", "OBSERVED", "SUCCEEDED"}, "PAYOFF_NOT_COMPLETED")

    samples = evidence.get("controlSamples") or []
    impact_samples = [
        row for row in samples
        if row.get("eventId") == "evt-impact" and row.get("actorId") == "actor_alpha"
    ]
    motor_samples = [
        row for row in impact_samples
        if row.get("controllerAuthority") == "MOTOR"
        and int(row.get("frame") or 10**9) < first_impact_frame
        and float((row.get("telemetry") or {}).get("distance") or 0.0) > 0.0
    ]
    require(len(motor_samples) >= 2, "PROPULSION_MOTOR_SAMPLES_INSUFFICIENT")
    motor_samples.sort(key=lambda row: int(row.get("frame") or 0))
    distances = [float((row.get("telemetry") or {}).get("distance") or 0.0) for row in motor_samples]
    require(min(distances[1:]) < distances[0] - 0.25, f"TARGET_DISTANCE_DID_NOT_CONVERGE:{distances}")

    coast_samples = [
        row
        for row in impact_samples
        if row.get("controllerAuthority") == "COAST"
        and float((row.get("telemetry") or {}).get("controllerCutoff") or 0.0) >= 0.5
        and int(row.get("frame") or 10**9) <= first_impact_frame
    ]
    require(bool(coast_samples), "NO_PRE_IMPACT_CONTROLLER_COAST_EVIDENCE")

    actors = evidence.get("actors") or {}
    target_state = ((actors.get("actor_beta") or {}).get("state") or {})
    require(len(target_state.get("damageEvents") or []) >= 1, "TARGET_DAMAGE_EVENT_MISSING")
    require(float(target_state.get("structuralIntegrity", 1.0)) < 1.0, "TARGET_STRUCTURAL_DAMAGE_NOT_PERSISTENT")

    debris = evidence.get("debrisObjects") or []
    require(len(debris) >= 2, "DEBRIS_COUNT_TOO_LOW")

    previews = evidence.get("previews") or []
    require([row.get("label") for row in previews] == ["approach", "impact", "aftermath"], "PREVIEW_LABEL_SEQUENCE_INVALID")
    frames = [int(row.get("frame") or 0) for row in previews]
    require(frames[0] < frames[1] < frames[2], f"PREVIEW_FRAME_ORDER_INVALID:{frames}")
    for row in previews:
        preview_path = Path(str(row.get("path") or ""))
        require(preview_path.is_file(), f"PREVIEW_FILE_MISSING:{row.get('label')}")
        require(int(row.get("bytes") or 0) >= 5000, f"PREVIEW_FILE_TOO_SMALL:{row.get('label')}")
        require(len(str(row.get("sha256") or "")) == 64, f"PREVIEW_SHA_INVALID:{row.get('label')}")

    print(json.dumps({
        "marker": "GENERIC_BATTLE_RUNTIME_CANDIDATE32_MACHINE_PREFLIGHT",
        "status": "PASS",
        "runtime": EXPECTED_RUNTIME,
        "impactCount": len(impacts),
        "earnedImpactCount": len(earned),
        "firstImpactFrame": first_impact_frame,
        "debrisCount": len(debris),
        "preImpactDistanceSamples": distances,
        "previewFrames": frames,
        "nextGate": "HUMAN_VISUAL_REVIEW",
    }, sort_keys=True))


if __name__ == "__main__":
    main()
