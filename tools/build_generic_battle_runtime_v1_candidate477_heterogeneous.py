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

OUT = ROOT / "artifacts" / "generic-autonomous-battle-c477"
EXPECTED_GENERIC_SHA = "0b2710a840d128aee53161277edb8cb77e1930d339f53585c6faece3f1dc2b1c"
EXPECTED_BULLDOZER_SHA = "2c0be359bbc6c99118751e7caa4b71a205961914e78d2e58c5dd7afc0f498468"
EXPECTED_BULLDOZER_UID = "b06a715d23a7450babac383b8bb7fb0a"
EXPECTED_BULLDOZER_MASS_KG = 27614.189525707065
BULLDOZER_SEMANTIC_BODIES = ["chassis", "cab", "blade", "track_left", "track_right"]


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


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--bulldozer-primary", required=True)
    a = p.parse_args()

    bulldozer = Path(a.bulldozer_primary).expanduser().resolve()
    if not bulldozer.is_file():
        raise RuntimeError(f"C477_BULLDOZER_PRIMARY_MISSING:{bulldozer}")
    bulldozer_sha = sha256_file(bulldozer)
    if bulldozer_sha != EXPECTED_BULLDOZER_SHA:
        raise RuntimeError(f"C477_BULLDOZER_SHA_MISMATCH:{bulldozer_sha}:{EXPECTED_BULLDOZER_SHA}")

    base.main()
    generic_glb = base.GLB.resolve()
    generic_sha = sha256_file(generic_glb)
    if generic_sha != EXPECTED_GENERIC_SHA:
        raise RuntimeError(f"C477_GENERIC_SHA_MISMATCH:{generic_sha}:{EXPECTED_GENERIC_SHA}")

    template = json.loads((base.OUT / "request.json").read_text(encoding="utf-8"))
    generic_bindings = copy.deepcopy(template["assetBindings"])
    base_request = c442.drama_request(template, generic_bindings)
    before_climax = c446._patch_climax(base_request)

    base_dir = OUT / "base-generic-hypercar"
    base_request_path = base_dir / "request.json"
    base_asset_map_path = base_dir / "asset-map.json"
    base_map = {
        row["entityId"]: {"path": str(generic_glb), "sha256": generic_sha}
        for row in generic_bindings
    }
    write_json(base_request_path, base_request)
    write_json(base_asset_map_path, base_map)
    c446._verify(base_request_path, before_climax)

    hetero = copy.deepcopy(base_request)
    before = copy.deepcopy(hetero)
    beta = next(row for row in hetero["assetBindings"] if row["entityId"] == "actor_beta")
    beta.update({
        "assetId": "production-bulldozer-beta",
        "sourceProvider": "iss_asset_source_library",
        "sourceUid": EXPECTED_BULLDOZER_UID,
        "sourceSha256": EXPECTED_BULLDOZER_SHA,
        "totalMassKg": EXPECTED_BULLDOZER_MASS_KG,
        "semanticBodies": list(BULLDOZER_SEMANTIC_BODIES),
        "semanticManifest": {"majorSemanticBodies": list(BULLDOZER_SEMANTIC_BODIES)},
        "runtimeProfile": {
            "locomotionModel": "GROUND_DIFFERENTIAL",
            "friction": 1.0,
            "restitution": 0.03,
        },
    })

    if canonical_sha(hetero["battlePlan"]) != canonical_sha(before["battlePlan"]):
        raise RuntimeError("C477_BATTLE_PLAN_MUTATED")
    if canonical_sha(hetero["executionPolicy"]) != canonical_sha(before["executionPolicy"]):
        raise RuntimeError("C477_EXECUTION_POLICY_MUTATED")
    if canonical_sha(hetero["scenes"]) != canonical_sha(before["scenes"]):
        raise RuntimeError("C477_SCENES_MUTATED")

    alpha_binding = next(row for row in hetero["assetBindings"] if row["entityId"] == "actor_alpha")
    alpha = ActorProfile.from_binding(alpha_binding)
    heavy = ActorProfile.from_binding(beta)
    if heavy.mass_kg / alpha.mass_kg < 10.0:
        raise RuntimeError("C477_MASS_DISSIMILARITY_INSUFFICIENT")
    if not (
        alpha.max_speed_mps > heavy.max_speed_mps
        and alpha.max_reverse_mps > heavy.max_reverse_mps
        and alpha.acceleration_mps2 > heavy.acceleration_mps2
        and alpha.braking_mps2 > heavy.braking_mps2
        and alpha.max_yaw_rate_rad_s > heavy.max_yaw_rate_rad_s
        and heavy.toughness_j_per_kg > alpha.toughness_j_per_kg
    ):
        raise RuntimeError("C477_ACTORPROFILE_DISSIMILARITY_NOT_REALIZED")

    forbidden = (
        "desiredimpactspeed", "desiredimpactenergy", "collisionframe", "contactframe",
        "impactframe", "trajectorypoints", "waypoints", "forcedwinner", "winnerid",
        "collisionpoint", "contactpoint", "brakingpoint", "steeringangle",
    )
    raw = json.dumps(hetero, sort_keys=True).lower()
    for token in forbidden:
        if token in raw:
            raise RuntimeError(f"C477_FORBIDDEN_ACCEPTANCE_CHOREOGRAPHY:{token}")

    hetero_dir = OUT / "generic-hypercar-production-bulldozer"
    hetero_request = hetero_dir / "request.json"
    hetero_map = hetero_dir / "asset-map.json"
    write_json(hetero_request, hetero)
    write_json(hetero_map, {
        "actor_alpha": {"path": str(generic_glb), "sha256": generic_sha},
        "actor_beta": {"path": str(bulldozer), "sha256": bulldozer_sha},
    })

    print(json.dumps({
        "marker": "GENERIC_AUTONOMOUS_BATTLE_C477_FIXTURE_ACCEPTANCE",
        "status": "PASS",
        "battlePlanSha256": canonical_sha(hetero["battlePlan"]),
        "battlePlanUnchanged": True,
        "executionPolicyUnchanged": True,
        "scenesUnchanged": True,
        "genericSourceSha256": generic_sha,
        "bulldozerSourceSha256": bulldozer_sha,
        "bulldozerSourceUid": EXPECTED_BULLDOZER_UID,
        "massRatioHeavyToLight": heavy.mass_kg / alpha.mass_kg,
        "lightProfile": {
            "massKg": alpha.mass_kg,
            "maxSpeedMps": alpha.max_speed_mps,
            "maxReverseMps": alpha.max_reverse_mps,
            "accelerationMps2": alpha.acceleration_mps2,
            "brakingMps2": alpha.braking_mps2,
            "maxYawRateRadS": alpha.max_yaw_rate_rad_s,
            "toughnessJPerKg": alpha.toughness_j_per_kg,
        },
        "heavyProfile": {
            "massKg": heavy.mass_kg,
            "maxSpeedMps": heavy.max_speed_mps,
            "maxReverseMps": heavy.max_reverse_mps,
            "accelerationMps2": heavy.acceleration_mps2,
            "brakingMps2": heavy.braking_mps2,
            "maxYawRateRadS": heavy.max_yaw_rate_rad_s,
            "toughnessJPerKg": heavy.toughness_j_per_kg,
        },
        "productionSemanticBodies": list(BULLDOZER_SEMANTIC_BODIES),
        "heavyCapabilitiesDerivedByExistingGenericActorProfileRules": True,
        "perAssetBattleCode": False,
        "perAssetTacticalTuning": False,
        "runtimeBehaviorChangedFromC474": False,
        "heteroRequest": str(hetero_request.resolve()),
        "heteroAssetMap": str(hetero_map.resolve()),
        "baseRequest": str(base_request_path.resolve()),
    }, sort_keys=True))


if __name__ == "__main__":
    main()
