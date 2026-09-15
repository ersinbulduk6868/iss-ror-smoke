#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

EXPECTED_BLOBS = {
    "blender/run_generic_battle_runtime_v1_candidate40.py": "5fac710c646e4609d4b63d0ae23e8612f1c9c81d",
    "blender/iss_battle_runtime_autonomy.py": "d349c51b289266740df7615d37dc645839001641",
    "blender/run_generic_battle_runtime_v1_candidate39.py": "0ecbf33d2825802410faf2d3356ebc1e5a545a40",
}


def git_blob_sha(path: Path) -> str:
    data = path.read_bytes()
    header = f"blob {len(data)}\0".encode("ascii")
    return hashlib.sha1(header + data).hexdigest()


def main() -> None:
    preserved = {}
    for rel, expected in EXPECTED_BLOBS.items():
        actual = git_blob_sha(ROOT / rel)
        if actual != expected:
            raise SystemExit(f"G05_PRESERVED_SOURCE_CHANGED:{rel}:{actual}:{expected}")
        preserved[rel] = actual

    path = ROOT / "blender/run_generic_battle_runtime_v1_candidate41.py"
    source = path.read_text(encoding="utf-8")
    required = [
        "RigidBodyWorld.convex_sweep_test",
        "BLENDER_NATIVE_ACTUAL_STEP_SWEEP_PLUS_SOLVER_RESPONSE_V1",
        "ACTUAL_SOLVER_STEP_ONLY",
        "native_detect_contacts",
        "native_resolve_pending_contacts",
        "targetIdentityUnique",
        "predictiveExtensionUsed\": False",
        "obbFinalContactAuthority\": False",
        "actorPoseOrVelocityMutation\": False",
    ]
    missing = [token for token in required if token not in source]
    if missing:
        raise SystemExit("G05_REQUIRED_SOURCE_CONTRACT_MISSING:" + ",".join(missing))

    forbidden = [
        "obb_overlap_2d(",
        "seed_velocity",
        "targetenergyj",
        "targetimpactspeedmps",
        "location.keyframe_insert",
        "rotation_euler.keyframe_insert",
        "linear_velocity =",
    ]
    hits = [token for token in forbidden if token in source.lower()]
    if hits:
        raise SystemExit("G05_FORBIDDEN_CONTACT_OR_CHEAT_SOURCE:" + ",".join(hits))

    result = {
        "marker": "GENERIC_BATTLE_RUNTIME_CANDIDATE41_G05_STATIC_ACCEPTANCE",
        "status": "PASS",
        "preservedBlobShas": preserved,
        "nativeApi": "RigidBodyWorld.convex_sweep_test",
        "pathAuthority": "ACTUAL_SOLVER_STEP_ONLY",
        "obbFinalContactAuthority": False,
        "predictiveSweepExtension": False,
        "g04AutonomySourceChanged": False,
        "candidate39AssetSemanticSourceChanged": False,
        "damageThresholdChanged": False,
        "contactThresholdChanged": False,
        "actorPoseOrVelocityMutation": False,
        "productionReadyClaimed": False,
    }
    print(json.dumps(result, sort_keys=True))


if __name__ == "__main__":
    main()
