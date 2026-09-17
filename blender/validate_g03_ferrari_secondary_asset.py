from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from blender.iss_battle_runtime_assets import AssetPrototypeCache, BlenderBattleRuntimeError
from blender.iss_battle_runtime_contract import ActorProfile


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--asset", required=True)
    ap.add_argument("--result", required=True)
    args = ap.parse_args(sys.argv[sys.argv.index("--") + 1 :] if "--" in sys.argv else None)

    path = Path(args.asset).resolve()
    if not path.is_file():
        raise BlenderBattleRuntimeError(f"G03_FERRARI_SOURCE_MISSING:{path}")

    source_sha = sha256_file(path)

    # Diagnostic-only generic passenger-sports-car binding. These values are not
    # a production Ferrari physics profile and are not used to close G03.
    binding = {
        "entityId": "g03_secondary_real_sports_car_probe",
        "downloadedSha256": source_sha,
        "totalMassKg": 1200.0,
        "runtimeProfile": {
            "locomotionModel": "GROUND_STEERED",
            "maxSpeedMps": 45.0,
            "maxReverseMps": 8.0,
            "accelerationMps2": 6.0,
            "brakingMps2": 9.0,
            "maxYawRateRadS": 1.2,
            "toughnessJPerKg": 70.0,
        },
        "semanticManifest": {"majorSemanticBodies": ["body", "front", "rear"]},
    }

    profile = ActorProfile.from_binding(binding, {"body", "front", "rear"})
    cache = AssetPrototypeCache()
    proto = cache.load(binding, path)

    dims = [float(x) for x in proto.dimensions]
    if len(proto.meshes) < 1:
        raise BlenderBattleRuntimeError("G03_FERRARI_VISIBLE_MESHES_MISSING")
    if not all(x > 0.2 for x in dims):
        raise BlenderBattleRuntimeError(f"G03_FERRARI_DIMENSIONS_INVALID:{dims}")

    required_runtime_zones = {"front", "rear", "body", "chassis"}
    missing = sorted(required_runtime_zones - set(proto.zones))
    if missing:
        raise BlenderBattleRuntimeError(f"G03_FERRARI_GENERIC_RUNTIME_ZONES_MISSING:{','.join(missing)}")

    result = {
        "status": "PASS",
        "test": "G03_SECONDARY_REAL_ASSET_GENERICITY",
        "gateClosureEligible": False,
        "gateClosureClaimed": False,
        "sourceSha256": source_sha,
        "sourceBytes": path.stat().st_size,
        "sameGenericAdapterSource": "blender/iss_battle_runtime_assets.py",
        "sameGenericActorProfileSource": "blender/iss_battle_runtime_contract.py::ActorProfile.from_binding",
        "assetSpecificBattleSourceCode": False,
        "fixtureNameBranchRequired": False,
        "diagnosticProfileOnly": True,
        "productionFerrariPhysicsProfileClaimed": False,
        "massKgDiagnostic": profile.mass_kg,
        "dimensions": dims,
        "visibleMeshCount": len(proto.meshes),
        "forwardAxisSource": proto.forward_axis_source,
        "runtimeZones": sorted(proto.zones),
        "semanticEvidence": proto.semantic_evidence,
        "productionReadyClaimed": False,
    }
    Path(args.result).write_text(json.dumps(result, indent=2, sort_keys=True), encoding="utf-8")
    print(json.dumps({"marker": "ISS_G03_FERRARI_SECONDARY_GENERICITY_PASS", **result}, sort_keys=True), flush=True)


if __name__ == "__main__":
    main()
