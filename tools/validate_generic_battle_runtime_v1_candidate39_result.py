#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path

EXPECTED_RUNTIME = "ISS_GENERIC_BATTLE_RUNTIME_V1_CANDIDATE_3_9"
EXPECTED_CONTROL = "DIFFERENTIAL_RIGID_BODY_MOTOR_V1_1"
EXPECTED_CONSEQUENCE = "ISS_IMPACT_CONSEQUENCE_V1_1_SURFACE_AWARE"
EXPECTED_ASSET_SHA = "8cc074c40fe9ced7271cbeddf223cd9a520dee868977ffcbd439cec1c2b62cb4"
EXPECTED_DIMS = (4.900918, 2.225155, 1.191855)
MIN_DAMAGE_SEVERITY = 0.055


class ValidationError(RuntimeError):
    pass


def require(condition: bool, marker: str) -> None:
    if not condition:
        raise ValidationError(marker)


def close(a: float, b: float, tol: float) -> bool:
    return abs(float(a) - float(b)) <= float(tol)


def args() -> argparse.Namespace:
    p = argparse.ArgumentParser()
    p.add_argument("--evidence", required=True)
    return p.parse_args()


def main() -> None:
    path = Path(args().evidence).resolve()
    require(path.is_file(), f"EVIDENCE_FILE_MISSING:{path}")
    d = json.loads(path.read_text(encoding="utf-8"))

    require(d.get("runtime") == EXPECTED_RUNTIME, "RUNTIME_VERSION_MISMATCH")
    require(d.get("success") is True, "EVIDENCE_SUCCESS_NOT_TRUE")
    models = d.get("models") or {}
    require(models.get("control") == EXPECTED_CONTROL, "CONTROL_MODEL_MISMATCH")
    require(models.get("consequence") == EXPECTED_CONSEQUENCE, "CONSEQUENCE_MODEL_MISMATCH")

    program = d.get("program") or {}
    require(int(program.get("actorCount") or 0) == 2, "ACTOR_COUNT_NOT_TWO")
    require(int(program.get("eventCount") or 0) == 4, "EVENT_COUNT_NOT_FOUR")
    require(int(program.get("totalFrames") or 0) > 30, "FRAME_COUNT_IMPLAUSIBLE")

    gates = d.get("gates") or {}
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
    failed = [name for name in required_gates if gates.get(name) is not True]
    require(not failed, "GATES_FAILED:" + ",".join(failed))

    resolved = d.get("resolvedAssets") or {}
    require(set(resolved) == {"actor_alpha", "actor_beta"}, "RESOLVED_ASSETS_INVALID")
    for actor_id, row in resolved.items():
        require(row.get("sha256") == EXPECTED_ASSET_SHA, f"ASSET_SHA_MISMATCH:{actor_id}")
        require(int(row.get("visibleMeshCount") or 0) >= 50, f"VISIBLE_GEOMETRY_TOO_LOW:{actor_id}")
        dims = row.get("dimensions") or []
        require(len(dims) == 3, f"ASSET_DIMENSIONS_MISSING:{actor_id}")
        require(
            all(close(got, want, 0.04) for got, want in zip(dims, EXPECTED_DIMS)),
            f"SUPPORTED_ENVELOPE_MISMATCH:{actor_id}:{dims}",
        )

    mass = d.get("massReceipts") or {}
    for actor_id in ("actor_alpha", "actor_beta"):
        row = mass.get(actor_id) or {}
        require(close(row.get("declaredMassKg", 0), 1570.0, 1e-4), f"DECLARED_MASS_MISMATCH:{actor_id}")
        require(close(row.get("reconciledMassKg", 0), 1570.0, 1e-4), f"MASS_NOT_RECONCILED:{actor_id}")

    events = d.get("events") or {}
    event_actor = {
        "evt-impact-alpha": "actor_alpha",
        "evt-impact-beta": "actor_beta",
    }
    for event_id in event_actor:
        row = events.get(event_id) or {}
        require(row.get("status") == "SUCCEEDED", f"IMPACT_EVENT_NOT_SUCCEEDED:{event_id}")
        require(int(row.get("contactCount") or 0) >= 1, f"CONTACT_COUNT_ZERO:{event_id}")
        require(int(row.get("damageCount") or 0) >= 1, f"DAMAGE_COUNT_ZERO:{event_id}")
    payoff = events.get("evt-payoff") or {}
    require(payoff.get("status") in {"SETTLED", "OBSERVED", "SUCCEEDED"}, "PAYOFF_NOT_COMPLETED")

    impacts = d.get("impacts") or []
    earned = [
        row for row in impacts
        if row.get("controllerCutoffObserved") is True
        and row.get("damageEarned") is True
        and float((row.get("evidence") or {}).get("severity") or 0.0) >= MIN_DAMAGE_SEVERITY
        and float((row.get("evidence") or {}).get("impact_energy_j") or 0.0) > 0.0
        and float((row.get("evidence") or {}).get("normal_closing_speed_mps") or 0.0) > 1.25
    ]
    require(earned, "NO_EARNED_NATIVE_IMPACT")
    require(
        {row.get("eventId") for row in earned} >= {"evt-impact-alpha", "evt-impact-beta"},
        "RECIPROCAL_EVENT_EVIDENCE_INCOMPLETE",
    )
    physical = [row for row in earned if row.get("coalescedPhysicalImpact") is not True]
    coalesced = [row for row in earned if row.get("coalescedPhysicalImpact") is True]
    require(physical, "PHYSICAL_TRANSACTION_MISSING")
    require(coalesced, "RECIPROCAL_INTENT_NOT_COALESCED")
    for row in coalesced:
        require(bool(row.get("physicalTransactionEventId")), "COALESCED_PHYSICAL_TRANSACTION_REF_MISSING")
        require(row.get("targetDamage") is None, "COALESCED_DAMAGE_DOUBLE_APPLY_DETECTED")
        require(row.get("attackerEvidence") is None, "COALESCED_SECOND_MIRROR_EVIDENCE_DETECTED")
        require(row.get("attackerVisual") is None, "COALESCED_SECOND_MIRROR_VISUAL_DETECTED")

    first_physical_frame = min(
        int((row.get("evidence") or {}).get("frame") or 10**9)
        for row in physical
    )
    samples = d.get("controlSamples") or []
    convergence = {}
    for event_id, actor_id in event_actor.items():
        rows = [
            row for row in samples
            if row.get("eventId") == event_id and row.get("actorId") == actor_id
        ]
        motors = [
            row for row in rows
            if row.get("controllerAuthority") == "MOTOR"
            and int(row.get("frame") or 10**9) < first_physical_frame
            and float((row.get("telemetry") or {}).get("distance") or 0.0) > 0.0
        ]
        require(len(motors) >= 2, f"MOTOR_SAMPLES_INSUFFICIENT:{actor_id}")
        motors.sort(key=lambda row: int(row.get("frame") or 0))
        distances = [float((row.get("telemetry") or {}).get("distance") or 0.0) for row in motors]
        require(min(distances[1:]) < distances[0] - 0.25, f"TARGET_DID_NOT_CONVERGE:{actor_id}:{distances}")
        coasts = [
            row for row in rows
            if row.get("controllerAuthority") == "COAST"
            and float((row.get("telemetry") or {}).get("controllerCutoff") or 0.0) >= 0.5
            and int(row.get("frame") or 10**9) <= first_physical_frame
        ]
        require(coasts, f"PRE_IMPACT_COAST_MISSING:{actor_id}")
        convergence[actor_id] = distances

    actors = d.get("actors") or {}
    for actor_id in ("actor_alpha", "actor_beta"):
        state = ((actors.get(actor_id) or {}).get("state") or {})
        require(state.get("damageEvents"), f"PERSISTENT_DAMAGE_MISSING:{actor_id}")
        require(float(state.get("structuralIntegrity", 1.0)) < 1.0, f"STRUCTURAL_DAMAGE_MISSING:{actor_id}")
        visual = (actors.get(actor_id) or {}).get("visualEvidence") or []
        require(visual, f"VISUAL_DAMAGE_EVIDENCE_MISSING:{actor_id}")
        require(any(row.get("model") == EXPECTED_CONSEQUENCE for row in visual), f"VISUAL_MODEL_MISMATCH:{actor_id}")

    debris = d.get("debrisObjects") or []
    require(len(debris) >= 4, "DEBRIS_COUNT_TOO_LOW")

    previews = d.get("previews") or []
    require([row.get("label") for row in previews] == ["approach", "impact", "aftermath"], "PREVIEW_SEQUENCE_INVALID")
    frames = [int(row.get("frame") or 0) for row in previews]
    require(frames[0] < frames[1] < frames[2], f"PREVIEW_FRAME_ORDER_INVALID:{frames}")
    for row in previews:
        p = Path(str(row.get("path") or ""))
        require(p.is_file(), f"PREVIEW_FILE_MISSING:{row.get('label')}")
        require(int(row.get("bytes") or 0) >= 5000, f"PREVIEW_TOO_SMALL:{row.get('label')}")
        require(len(str(row.get("sha256") or "")) == 64, f"PREVIEW_SHA_INVALID:{row.get('label')}")

    print(json.dumps({
        "marker": "GENERIC_BATTLE_RUNTIME_CANDIDATE39_MACHINE_PREFLIGHT",
        "status": "PASS",
        "runtime": EXPECTED_RUNTIME,
        "exactBugattiSha256": EXPECTED_ASSET_SHA,
        "physicalImpactTransactions": len(physical),
        "coalescedReciprocalIntentReceipts": len(coalesced),
        "firstPhysicalImpactFrame": first_physical_frame,
        "debrisCount": len(debris),
        "preImpactDistanceSamples": convergence,
        "previewFrames": frames,
        "reciprocalDamageDoubleApply": False,
        "nextGate": "HUMAN_VISUAL_REVIEW",
    }, sort_keys=True))


if __name__ == "__main__":
    main()
