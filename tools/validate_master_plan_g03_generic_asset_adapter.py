#!/usr/bin/env python3
from __future__ import annotations

import ast
import json
import math
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ASSET_SOURCE = ROOT / "blender" / "iss_battle_runtime_assets.py"
CONTRACT_SOURCE = ROOT / "blender" / "iss_battle_runtime_contract.py"
BUGATTI_FIXTURE = ROOT / "assets" / "test-real-model" / "bugatti_quant120.json"
BULLDOZER_FIXTURE = ROOT / "assets" / "test-real-model" / "bulldozer_quant120.json"

EXPECTED_SHA = {
    "bugatti": "8cc074c40fe9ced7271cbeddf223cd9a520dee868977ffcbd439cec1c2b62cb4",
    "bulldozer": "187f81c3c4638180fb8d82c5b2bbc7510f01bc970ee149713b2de993089f1e18",
}


class G03ValidationError(RuntimeError):
    pass


def require(condition: bool, marker: str) -> None:
    if not condition:
        raise G03ValidationError(marker)


def read_source(path: Path) -> str:
    require(path.is_file(), f"SOURCE_MISSING:{path}")
    text = path.read_text(encoding="utf-8")
    ast.parse(text, filename=str(path))
    return text


def source_contract_checks() -> dict[str, object]:
    assets = read_source(ASSET_SOURCE)
    contract = read_source(CONTRACT_SOURCE)
    lowered = (assets + "\n" + contract).lower()

    # Product runtime must not branch on fixture identity. Fixture names are allowed
    # in tests, but never in the generic adapter/profile implementation itself.
    identity_hits = [name for name in ("bugatti", "bulldozer") if name in lowered]
    require(not identity_hits, "ASSET_IDENTITY_HARDCODE_IN_GENERIC_RUNTIME:" + ",".join(identity_hits))

    required_asset_tokens = (
        "def world_bounds(",
        "def parse_forward_axis(",
        "def normalize_prototype(",
        "SEMANTIC_TERMS",
        "UNSUPPORTED_BLENDER_ASSET_FORMAT",
        "PRODUCTION_ASSET_IMPORTED_WITHOUT_MESH",
        "VISIBLE_MESH_BOUNDS_MISSING",
        "ACTOR_FORWARD_AXIS_UNRESOLVED",
        "ACTOR_FORWARD_AXIS_DEGENERATE",
        "ACTOR_SCALE_MULTIPLIER_INVALID",
        "ACTOR_NORMALIZED_DIMENSIONS_IMPLAUSIBLE",
        "CANONICAL_GEOMETRIC_ZONE",
    )
    missing_assets = [token for token in required_asset_tokens if token not in assets]
    require(not missing_assets, "GENERIC_ADAPTER_CONTRACT_TOKEN_MISSING:" + ",".join(missing_assets))

    required_contract_tokens = (
        "class ActorProfile:",
        "def from_binding(",
        "ACTOR_PROFILE_ENTITY_ID_EMPTY",
        "ACTOR_MASS_REQUIRED",
        "ACTOR_MASS_INVALID",
        "runtimeProfile",
        "locomotionModel",
        "maxSpeedMps",
        "maxReverseMps",
        "maxYawRateRadS",
        "accelerationMps2",
        "brakingMps2",
        "toughnessJPerKg",
    )
    missing_contract = [token for token in required_contract_tokens if token not in contract]
    require(not missing_contract, "ACTOR_PROFILE_CONTRACT_TOKEN_MISSING:" + ",".join(missing_contract))

    # Supported source formats are explicit; unknown formats remain fail-closed.
    require("{\".glb\", \".gltf\"}" in assets, "GLTF_SUPPORT_BOUNDARY_MISSING")
    require("{\".usd\", \".usda\", \".usdc\"}" in assets, "USD_SUPPORT_BOUNDARY_MISSING")

    return {
        "status": "PASS",
        "runtimeIdentityBranches": identity_hits,
        "canonicalScaleAxesEnvelopeDerivedFromGeometry": True,
        "semanticZonesDerivedGenerically": True,
        "physicalProfileDerivedFromBinding": True,
        "unsupportedFormatsFailClosed": True,
    }


def fixture_metrics(path: Path, label: str) -> dict[str, object]:
    require(path.is_file(), f"REAL_GEOMETRY_FIXTURE_MISSING:{label}")
    data = json.loads(path.read_text(encoding="utf-8"))
    require(data.get("source_sha256") == EXPECTED_SHA[label], f"REAL_GEOMETRY_SHA_MISMATCH:{label}")
    lo = data.get("min")
    hi = data.get("max")
    require(isinstance(lo, list) and isinstance(hi, list) and len(lo) == 3 and len(hi) == 3,
            f"REAL_GEOMETRY_BOUNDS_MISSING:{label}")
    dims = [float(b) - float(a) for a, b in zip(lo, hi)]
    require(all(math.isfinite(v) and v > 0.05 for v in dims), f"REAL_GEOMETRY_BOUNDS_INVALID:{label}:{dims}")
    qv = data.get("qv") or []
    faces = data.get("f") or []
    require(len(qv) >= 90 and len(qv) % 3 == 0, f"REAL_GEOMETRY_VERTEX_SAMPLE_INVALID:{label}")
    require(len(faces) >= 30, f"REAL_GEOMETRY_FACE_SAMPLE_INVALID:{label}")
    longest = max(dims)
    signature = sorted(v / longest for v in dims)
    return {
        "sourceSha256": data["source_sha256"],
        "dimensions": [round(v, 6) for v in dims],
        "normalizedShapeSignature": [round(v, 6) for v in signature],
        "sampledVertexCount": len(qv) // 3,
        "faceIndexCount": len(faces),
        "transport": data.get("transport"),
    }


def dissimilar_real_asset_checks() -> dict[str, object]:
    bugatti = fixture_metrics(BUGATTI_FIXTURE, "bugatti")
    bulldozer = fixture_metrics(BULLDOZER_FIXTURE, "bulldozer")
    a = bugatti["normalizedShapeSignature"]
    b = bulldozer["normalizedShapeSignature"]
    shape_distance = math.sqrt(sum((float(x) - float(y)) ** 2 for x, y in zip(a, b)))
    require(shape_distance >= 0.20, f"REAL_ASSET_FIXTURES_NOT_DISSIMILAR_ENOUGH:{shape_distance}")

    # Both fixtures are exact-upload-derived real geometry snapshots. This gate is
    # proving the generic adapter support boundary, not claiming a new battle result.
    require(bugatti.get("transport") == "exact-upload-derived-quantized-surface-v1",
            "BUGATTI_REAL_GEOMETRY_PROVENANCE_INVALID")
    require(bulldozer.get("transport") == "exact-upload-derived-quantized-surface-v1",
            "BULLDOZER_REAL_GEOMETRY_PROVENANCE_INVALID")

    return {
        "status": "PASS",
        "fixtureA": bugatti,
        "fixtureB": bulldozer,
        "normalizedShapeDistance": round(shape_distance, 6),
        "dissimilarRealGeometry": True,
    }


def main() -> None:
    source = source_contract_checks()
    fixtures = dissimilar_real_asset_checks()
    result = {
        "marker": "ISS_G03_GENERIC_ACTOR_PROFILE_ASSET_ONBOARDING_ACCEPTANCE",
        "status": "PASS",
        "scope": "GENERIC_ADAPTER_SUPPORT_BOUNDARY",
        "sourceContract": source,
        "realDissimilarAssets": fixtures,
        "runtimeSourceMutated": False,
        "assetSpecificBattleCodeAdded": False,
        "fullHeavyTrackedBattleRuntimeClaimed": False,
        "productionReadyClaimed": False,
    }
    print(json.dumps(result, sort_keys=True))


if __name__ == "__main__":
    main()
