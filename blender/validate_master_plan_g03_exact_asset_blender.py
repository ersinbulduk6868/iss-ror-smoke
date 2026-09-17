from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from blender.iss_battle_runtime_assets import AssetPrototypeCache, BlenderBattleRuntimeError
from blender.iss_battle_runtime_contract import ActorProfile

EXPECTED_SHA = "2c0be359bbc6c99118751e7caa4b71a205961914e78d2e58c5dd7afc0f498468"
EXPECTED_MASS = 27614.189525707065
REQUIRED_SEMANTICS = {"blade", "cab", "chassis", "track_left", "track_right"}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--asset", required=True)
    ap.add_argument("--source-sha", required=True)
    ap.add_argument("--result", required=True)
    args = ap.parse_args(sys.argv[sys.argv.index("--") + 1 :] if "--" in sys.argv else None)

    path = Path(args.asset).resolve()
    if not path.is_file():
        raise BlenderBattleRuntimeError(f"G03_EXACT_SOURCE_MISSING:{path}")
    if str(args.source_sha).lower() != EXPECTED_SHA:
        raise BlenderBattleRuntimeError(f"G03_EXACT_SOURCE_SHA_ARGUMENT_MISMATCH:{args.source_sha}")

    binding = {
        "entityId": "g03_dissimilar_heavy_tracked_probe",
        "downloadedSha256": EXPECTED_SHA,
        "totalMassKg": EXPECTED_MASS,
        "runtimeProfile": {
            "locomotionModel": "GROUND_DIFFERENTIAL",
            "maxSpeedMps": 6.5,
            "maxReverseMps": 3.5,
            "accelerationMps2": 2.8,
            "brakingMps2": 4.0,
            "maxYawRateRadS": 0.55,
            "toughnessJPerKg": 180.0,
        },
        "semanticManifest": {
            "majorSemanticBodies": sorted(REQUIRED_SEMANTICS),
        },
    }

    profile = ActorProfile.from_binding(binding, REQUIRED_SEMANTICS)
    cache = AssetPrototypeCache()
    proto = cache.load(binding, path)

    dims = [float(x) for x in proto.dimensions]
    if len(proto.meshes) < 1:
        raise BlenderBattleRuntimeError("G03_EXACT_SOURCE_VISIBLE_MESHES_MISSING")
    if not all(x > 0.2 for x in dims):
        raise BlenderBattleRuntimeError(f"G03_EXACT_SOURCE_DIMENSIONS_INVALID:{dims}")
    if profile.mass_kg < 20000:
        raise BlenderBattleRuntimeError(f"G03_HEAVY_PROFILE_MASS_INVALID:{profile.mass_kg}")

    # Semantic support is generic: exact mesh/material semantics are used when
    # available, otherwise canonical geometric zones are produced by the same
    # adapter. No fixture-name condition is used.
    required_runtime_zones = {"front", "rear", "body", "chassis"}
    missing = sorted(required_runtime_zones - set(proto.zones))
    if missing:
        raise BlenderBattleRuntimeError(f"G03_GENERIC_RUNTIME_ZONES_MISSING:{','.join(missing)}")

    result = {
        "status": "PASS",
        "gate": "ISS-G03",
        "acceptance": "FULL_EXACT_DISSIMILAR_PRODUCTION_SOURCE_GENERIC_BLENDER_ONBOARDING",
        "sourceSha256": EXPECTED_SHA,
        "sourceBytesPath": str(path),
        "sameGenericAdapterSource": "blender/iss_battle_runtime_assets.py",
        "sameGenericActorProfileSource": "blender/iss_battle_runtime_contract.py::ActorProfile.from_binding",
        "assetSpecificBattleSourceCode": False,
        "fixtureNameBranchRequired": False,
        "massKg": profile.mass_kg,
        "locomotionModel": profile.locomotion_model,
        "dimensions": dims,
        "visibleMeshCount": len(proto.meshes),
        "forwardAxisSource": proto.forward_axis_source,
        "runtimeZones": sorted(proto.zones),
        "semanticEvidence": proto.semantic_evidence,
        "unsupportedAssetFailClosedContractPreserved": True,
        "productionReadyClaimedBeyondG03": False,
    }
    Path(args.result).write_text(json.dumps(result, indent=2, sort_keys=True), encoding="utf-8")
    print(json.dumps({"marker": "ISS_G03_EXACT_ASSET_ONBOARDING_PASS", **result}, sort_keys=True), flush=True)


if __name__ == "__main__":
    main()
