#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from blender.iss_battle_runtime_contact_truth import (
    OUTER_AUTHORITY_MODEL,
    PAIRWISE_RESPONSE_MODEL,
    ContactOuterAuthorityGate,
    ContactOuterAuthoritySample,
    PairwiseSolverResponseOracle,
    PairwiseSolverSample,
)

EXPECTED_BLOBS = {
    "blender/run_generic_battle_runtime_v1_candidate40.py": "5fac710c646e4609d4b63d0ae23e8612f1c9c81d",
    "blender/iss_battle_runtime_autonomy.py": "d349c51b289266740df7615d37dc645839001641",
    "blender/run_generic_battle_runtime_v1_candidate39.py": "0ecbf33d2825802410faf2d3356ebc1e5a545a40",
}


def git_blob_sha(path: Path) -> str:
    data = path.read_bytes()
    return hashlib.sha1(f"blob {len(data)}\0".encode("ascii") + data).hexdigest()


def sample(ma, mt, va0, vt0, va1, vt1, normal=(1.0, 0.0, 0.0)):
    return PairwiseSolverResponseOracle.evaluate(PairwiseSolverSample.build(
        attacker_mass_kg=ma,
        target_mass_kg=mt,
        pre_attacker_velocity=va0,
        pre_target_velocity=vt0,
        post_attacker_velocity=va1,
        post_target_velocity=vt1,
        collision_normal_attacker_to_target=normal,
    ))


def require(label: str, expected: bool, receipt) -> dict:
    if bool(receipt.qualified) is not expected:
        raise SystemExit(f"G05_PAIRWISE_PROPERTY_FAIL:{label}:{receipt.as_dict()}")
    return {"status": "PASS", "qualified": receipt.qualified, "reason": receipt.reason}


def outer(
    *,
    intended="target",
    observed="target",
    handoff=True,
    motor_zero=True,
    gap=0.0,
    gap_tol=0.10,
    semantic=0.05,
    semantic_tol=0.50,
):
    return ContactOuterAuthorityGate.evaluate(ContactOuterAuthoritySample(
        intended_target_id=intended,
        observed_pair_target_id=observed,
        controller_handoff=handoff,
        motor_authority_zero=motor_zero,
        locality_gap_m=gap,
        locality_tolerance_m=gap_tol,
        semantic_distance_m=semantic,
        semantic_tolerance_m=semantic_tol,
    ))


def main() -> None:
    preserved = {}
    for rel, expected in EXPECTED_BLOBS.items():
        actual = git_blob_sha(ROOT / rel)
        if actual != expected:
            raise SystemExit(f"G05_PRESERVED_SOURCE_CHANGED:{rel}:{actual}:{expected}")
        preserved[rel] = actual

    solver_properties = {
        "equalMassNativeCollision": require(
            "equalMassNativeCollision", True,
            sample(1450, 1450, (5,0,0), (-5,0,0), (-1,0,0), (1,0,0)),
        ),
        "asymmetricMassNativeCollision": require(
            "asymmetricMassNativeCollision", True,
            sample(1500, 10000, (8,0,0), (0,0,0), (-2,0,0), (1.5,0,0)),
        ),
        "rollingFrictionRejected": require(
            "rollingFrictionFalsePositive", False,
            sample(1450, 1450, (5,0,0), (-5,0,0), (4.98,0,0), (-4.98,0,0)),
        ),
        "unilateralWallRejected": require(
            "unilateralWallImpact", False,
            sample(1450, 1450, (5,0,0), (0,0,0), (-2,0,0), (0,0,0)),
        ),
        "verticalGroundRejected": require(
            "verticalGroundResponse", False,
            sample(1450, 1450, (5,0,-2), (-5,0,-2), (5,0,2), (-5,0,2)),
        ),
        "sameDirectionExternalImpulseRejected": require(
            "sameDirectionExternalImpulse", False,
            sample(1450, 1450, (5,0,0), (-5,0,0), (3,0,0), (-7,0,0)),
        ),
    }

    outer_properties = {
        "validPair": require("outerValidPair", True, outer()),
        "wrongTargetRejected": require("outerWrongTarget", False, outer(observed="third_actor")),
        "controllerAuthorityRejected": require("outerControllerAuthority", False, outer(handoff=False, motor_zero=False)),
        "nonAdjacentRejected": require("outerNonAdjacent", False, outer(gap=0.25, gap_tol=0.10)),
        "semanticMismatchRejected": require("outerSemanticMismatch", False, outer(semantic=0.75, semantic_tol=0.50)),
    }

    source = (ROOT / "blender/run_generic_battle_runtime_v1_candidate42.py").read_text(encoding="utf-8")
    required = [
        "RECIPROCAL_NATIVE_SOLVER_RESPONSE_V1",
        "PAIRWISE_CONTACT_OUTER_AUTHORITY_V1",
        "PairwiseSolverResponseOracle",
        "ContactOuterAuthorityGate",
        "controllerCutoffObserved",
        "nativeContactAuthority",
        "pairwiseLocalityGapM",
        "semanticDistance",
        "\"obbFinalContactAuthority\": False",
        "\"nativeSweepFinalContactAuthority\": False",
        "\"actorPoseOrVelocityMutation\": False",
    ]
    missing = [token for token in required if token not in source]
    if missing:
        raise SystemExit("G05_C42_REQUIRED_SOURCE_CONTRACT_MISSING:" + ",".join(missing))

    low = source.lower()
    forbidden_runtime_mechanisms = [
        "obb_overlap_2d(",
        "convex_sweep_test(",
        ".linear_velocity =",
        "keyframe_insert(data_path=\"location\"",
        "keyframe_insert(data_path='location'",
        "keyframe_insert(data_path=\"rotation",
        "keyframe_insert(data_path='rotation",
    ]
    mechanism_hits = [token for token in forbidden_runtime_mechanisms if token in low]
    if mechanism_hits:
        raise SystemExit("G05_C42_FORBIDDEN_CONTACT_OR_CHEAT_SOURCE:" + ",".join(mechanism_hits))

    forbidden_executable_inputs = [
        'event.get("targetenergyj")',
        "event.get('targetenergyj')",
        'event.get("targetimpactspeedmps")',
        "event.get('targetimpactspeedmps')",
        'event.get("collisionframe")',
        "event.get('collisionframe')",
        '["targetenergyj"]',
        "['targetenergyj']",
        '["targetimpactspeedmps"]',
        "['targetimpactspeedmps']",
        '["collisionframe"]',
        "['collisionframe']",
    ]
    executable_hits = [token for token in forbidden_executable_inputs if token in low]
    if executable_hits:
        raise SystemExit("G05_C42_FORBIDDEN_EXECUTABLE_CHOREOGRAPHY:" + ",".join(executable_hits))

    print(json.dumps({
        "marker": "GENERIC_BATTLE_RUNTIME_CANDIDATE42_G05_PROPERTY_ACCEPTANCE",
        "status": "PASS",
        "model": PAIRWISE_RESPONSE_MODEL,
        "outerAuthorityModel": OUTER_AUTHORITY_MODEL,
        "preservedBlobShas": preserved,
        "solverProperties": solver_properties,
        "outerAuthorityProperties": outer_properties,
        "g04SourceChanged": False,
        "candidate39SourceChanged": False,
        "obbFinalContactAuthority": False,
        "nativeSweepFinalContactAuthority": False,
        "damageThresholdChanged": False,
        "contactThresholdChanged": False,
        "actorPoseOrVelocityMutation": False,
        "productionReadyClaimed": False,
    }, sort_keys=True))


if __name__ == "__main__":
    main()
