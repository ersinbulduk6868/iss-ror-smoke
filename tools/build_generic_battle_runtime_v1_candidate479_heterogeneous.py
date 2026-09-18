#!/usr/bin/env python3
from __future__ import annotations

import argparse
import copy
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
TOOLS = ROOT / "tools"
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

import build_generic_battle_runtime_v1_preflight as base
import build_generic_battle_runtime_v1_candidate442_g07 as c442
import build_generic_battle_runtime_v1_candidate446_g07 as c446
from blender.iss_battle_runtime_contract import ActorProfile

OUT = ROOT / "artifacts" / "generic-autonomous-battle-c479"
EXPECTED_GENERIC_SHA = "0b2710a840d128aee53161277edb8cb77e1930d339f53585c6faece3f1dc2b1c"
EXPECTED_READY_ASSET_ID = "2153aaa0-b922-40a6-a340-e286807bc44b"
EXPECTED_SOURCE_UID = "b06a715d23a7450babac383b8bb7fb0a"
EXPECTED_SOURCE_SHA = "2c0be359bbc6c99118751e7caa4b71a205961914e78d2e58c5dd7afc0f498468"
EXPECTED_DYNAMIC_MASTER_SHA = "8ab94079ad22974f037bb01732365ffafdf2e107edd19865d145b9e33cc763c6"
EXPECTED_READY_PACKAGE_MANIFEST_SHA = "b2399a2e1b6944faefb458a6408adc385fe0f4376b125ae8f0a6b859adbcc623"
EXPECTED_CANONICAL_FRAME_EVIDENCE_SHA = "8bf19015283d786142ea387bb7076e0681975387457cab4c3304c0e05ba08069"
EXPECTED_MASS_KG = 27614.189525707065
ALLOWED_FORWARD = {"X", "-X", "Y", "-Y"}


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def canonical_sha(value: object) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True), encoding="utf-8")


def load_ready_metadata(path: Path) -> dict:
    d = json.loads(path.read_text(encoding="utf-8"))
    if d.get("metadataSource") != "iss_asset_ready_library":
        raise RuntimeError("C479_READY_METADATA_SOURCE_INVALID")
    if d.get("status") != "PRODUCTION_READY":
        raise RuntimeError("C479_READY_METADATA_STATUS_INVALID")
    if d.get("readyAssetId") != EXPECTED_READY_ASSET_ID:
        raise RuntimeError("C479_READY_ASSET_ID_DRIFT")
    if d.get("sourceUid") != EXPECTED_SOURCE_UID:
        raise RuntimeError("C479_SOURCE_UID_DRIFT")
    if d.get("sourceSha256Snapshot") != EXPECTED_SOURCE_SHA:
        raise RuntimeError("C479_SOURCE_SHA_DRIFT")
    if d.get("dynamicMasterSha256") != EXPECTED_DYNAMIC_MASTER_SHA:
        raise RuntimeError("C479_DYNAMIC_MASTER_SHA_METADATA_DRIFT")
    if d.get("readyPackageManifestSha256") != EXPECTED_READY_PACKAGE_MANIFEST_SHA:
        raise RuntimeError("C479_READY_MANIFEST_SHA_METADATA_DRIFT")
    if d.get("canonicalFrameEvidenceSha256") != EXPECTED_CANONICAL_FRAME_EVIDENCE_SHA:
        raise RuntimeError("C479_CANONICAL_FRAME_EVIDENCE_SHA_DRIFT")
    if abs(float(d.get("totalMassKg") or 0.0) - EXPECTED_MASS_KG) > 1e-6:
        raise RuntimeError("C479_READY_MASS_DRIFT")
    cf = d.get("canonicalFrame") or {}
    if set(cf) != {"forward", "up", "units", "grounded"}:
        raise RuntimeError(f"C479_CANONICAL_FRAME_SCHEMA_INVALID:{sorted(cf)}")
    if str(cf.get("forward")) not in ALLOWED_FORWARD:
        raise RuntimeError("C479_CANONICAL_FORWARD_INVALID")
    if cf.get("up") != "Z" or cf.get("units") != "meters" or cf.get("grounded") is not True:
        raise RuntimeError("C479_CANONICAL_FRAME_NON_FORWARD_CONTRACT_INVALID")
    return d


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--bulldozer-ready-primary", required=True)
    p.add_argument("--asset-library-metadata", required=True)
    a = p.parse_args()

    ready_meta = load_ready_metadata(Path(a.asset_library_metadata).expanduser().resolve())
    canonical_frame = dict(ready_meta["canonicalFrame"])
    semantic_manifest = dict(ready_meta.get("semanticManifest") or {})

    bulldozer = Path(a.bulldozer_ready_primary).expanduser().resolve()
    if not bulldozer.is_file() or bulldozer.name != "master_asset_rc2_dynamic.usda":
        raise RuntimeError("C479_BULLDOZER_READY_ENTRYPOINT_INVALID")
    if sha256_file(bulldozer) != EXPECTED_DYNAMIC_MASTER_SHA:
        raise RuntimeError("C479_BULLDOZER_DYNAMIC_MASTER_SHA_MISMATCH")

    base.main()
    generic_glb = base.GLB.resolve()
    generic_sha = sha256_file(generic_glb)
    if generic_sha != EXPECTED_GENERIC_SHA:
        raise RuntimeError("C479_GENERIC_SHA_MISMATCH")

    template = json.loads((base.OUT / "request.json").read_text(encoding="utf-8"))
    generic_bindings = copy.deepcopy(template["assetBindings"])
    base_request = c442.drama_request(template, generic_bindings)
    before_climax = c446._patch_climax(base_request)

    base_dir = OUT / "base-generic-hypercar"
    base_request_path = base_dir / "request.json"
    write_json(base_request_path, base_request)
    write_json(base_dir / "asset-map.json", {
        row["entityId"]: {"path": str(generic_glb), "sha256": generic_sha}
        for row in generic_bindings
    })
    c446._verify(base_request_path, before_climax)

    hetero = copy.deepcopy(base_request)
    before = copy.deepcopy(hetero)
    beta = next(row for row in hetero["assetBindings"] if row["entityId"] == "actor_beta")
    beta.update({
        "assetId": "production-ready-bulldozer-beta",
        "sourceProvider": "iss_asset_ready_library",
        "sourceUid": EXPECTED_SOURCE_UID,
        "sourceSha256": EXPECTED_SOURCE_SHA,
        "readyAssetId": EXPECTED_READY_ASSET_ID,
        "dynamicMasterSha256": EXPECTED_DYNAMIC_MASTER_SHA,
        "readyPackageManifestSha256": EXPECTED_READY_PACKAGE_MANIFEST_SHA,
        "canonicalFrameEvidenceSha256": EXPECTED_CANONICAL_FRAME_EVIDENCE_SHA,
        "canonicalFrame": canonical_frame,
        "assetProfile": "DYNAMIC_ACTOR",
        "totalMassKg": EXPECTED_MASS_KG,
        "semanticBodies": list(semantic_manifest.get("majorSemanticBodies") or []),
        "semanticManifest": semantic_manifest,
        "runtimeProfile": {
            "locomotionModel": "GROUND_DIFFERENTIAL",
            "friction": 1.0,
            "restitution": 0.03,
        },
    })

    if canonical_sha(hetero["battlePlan"]) != canonical_sha(before["battlePlan"]):
        raise RuntimeError("C479_BATTLE_PLAN_MUTATED")
    if canonical_sha(hetero["executionPolicy"]) != canonical_sha(before["executionPolicy"]):
        raise RuntimeError("C479_EXECUTION_POLICY_MUTATED")
    if canonical_sha(hetero["scenes"]) != canonical_sha(before["scenes"]):
        raise RuntimeError("C479_SCENES_MUTATED")

    alpha_binding = next(row for row in hetero["assetBindings"] if row["entityId"] == "actor_alpha")
    alpha = ActorProfile.from_binding(alpha_binding)
    heavy = ActorProfile.from_binding(beta)
    if heavy.mass_kg / alpha.mass_kg < 10.0:
        raise RuntimeError("C479_MASS_DISSIMILARITY_INSUFFICIENT")
    if not (
        alpha.max_speed_mps > heavy.max_speed_mps
        and alpha.max_reverse_mps > heavy.max_reverse_mps
        and alpha.acceleration_mps2 > heavy.acceleration_mps2
        and alpha.braking_mps2 > heavy.braking_mps2
        and alpha.max_yaw_rate_rad_s > heavy.max_yaw_rate_rad_s
        and heavy.toughness_j_per_kg > alpha.toughness_j_per_kg
    ):
        raise RuntimeError("C479_ACTORPROFILE_DISSIMILARITY_NOT_REALIZED")

    beta_rp = beta.get("runtimeProfile") or {}
    for forbidden in (
        "forwardAxis", "maxSpeedMps", "maxReverseMps", "accelerationMps2",
        "brakingMps2", "maxYawRateRadS", "toughnessJPerKg",
        "desiredImpactSpeedMps", "desiredImpactEnergyJ", "collisionFrame",
        "contactFrame", "trajectoryPoints", "waypoints", "forcedWinner",
    ):
        if forbidden in beta_rp:
            raise RuntimeError(f"C479_RUNTIME_PROFILE_TUNING_FORBIDDEN:{forbidden}")

    raw_plan = json.dumps(hetero["battlePlan"], sort_keys=True).lower()
    for token in (
        "desiredimpactspeed", "desiredimpactenergy", "collisionframe", "contactframe",
        "impactframe", "trajectorypoints", "waypoints", "forcedwinner", "winnerid",
        "collisionpoint", "contactpoint", "brakingpoint", "steeringangle",
    ):
        if token in raw_plan:
            raise RuntimeError(f"C479_FORBIDDEN_BATTLE_CHOREOGRAPHY:{token}")

    hetero_dir = OUT / "generic-hypercar-production-ready-bulldozer"
    write_json(hetero_dir / "request.json", hetero)
    write_json(hetero_dir / "asset-map.json", {
        "actor_alpha": {"path": str(generic_glb), "sha256": generic_sha},
        "actor_beta": {"path": str(bulldozer), "sha256": EXPECTED_DYNAMIC_MASTER_SHA},
    })
    write_json(OUT / "asset-library-metadata-snapshot.json", ready_meta)

    print(json.dumps({
        "marker": "GENERIC_AUTONOMOUS_BATTLE_C479_FIXTURE_ACCEPTANCE",
        "status": "PASS",
        "battlePlanSha256": canonical_sha(hetero["battlePlan"]),
        "battlePlanUnchanged": True,
        "executionPolicyUnchanged": True,
        "scenesUnchanged": True,
        "genericSourceSha256": generic_sha,
        "readyAssetId": EXPECTED_READY_ASSET_ID,
        "dynamicMasterSha256": EXPECTED_DYNAMIC_MASTER_SHA,
        "canonicalFrame": canonical_frame,
        "canonicalFrameSource": "iss_asset_ready_library",
        "canonicalFrameEvidenceSha256": EXPECTED_CANONICAL_FRAME_EVIDENCE_SHA,
        "canonicalFrameFixtureHardcode": False,
        "massRatioHeavyToLight": heavy.mass_kg / alpha.mass_kg,
        "perAssetBattleCode": False,
        "perAssetTacticalTuning": False,
        "runtimeBehaviorChangedFromC474": False,
        "heteroRequest": str((hetero_dir / "request.json").resolve()),
        "heteroAssetMap": str((hetero_dir / "asset-map.json").resolve()),
        "baseRequest": str(base_request_path.resolve()),
    }, sort_keys=True))


if __name__ == "__main__":
    main()
