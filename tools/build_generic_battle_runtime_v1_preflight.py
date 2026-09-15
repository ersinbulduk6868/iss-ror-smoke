#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ASSET_DIR = ROOT / "assets" / "generated" / "generic-hypercar-v1"
GLB = ASSET_DIR / "generic_hypercar.glb"
MANIFEST = ASSET_DIR / "manifest.json"
OUT = ROOT / "artifacts" / "generic-battle-runtime-v1-preflight"
EXPECTED_ENGINE = "BLENDER"
EXPECTED_ENGINE_VERSION = "4.5.13"
SOURCE_FORWARD_AXIS = "-Y"


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def main() -> None:
    if not GLB.is_file() or not MANIFEST.is_file():
        raise RuntimeError("GENERIC_PREFLIGHT_ASSET_MISSING")
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    if manifest.get("engine") != EXPECTED_ENGINE:
        raise RuntimeError("GENERIC_PREFLIGHT_ASSET_ENGINE_MISMATCH")
    if manifest.get("engineVersion") != EXPECTED_ENGINE_VERSION:
        raise RuntimeError("GENERIC_PREFLIGHT_ASSET_ENGINE_VERSION_MISMATCH")
    if manifest.get("productionAcceptance") != "ASSET_LEVEL_ONLY":
        raise RuntimeError("GENERIC_PREFLIGHT_FIXTURE_SCOPE_DRIFT")
    expected_sha = str(manifest.get("sha256") or "").lower()
    actual_sha = sha256_file(GLB)
    if not expected_sha or actual_sha != expected_sha:
        raise RuntimeError(
            f"GENERIC_PREFLIGHT_ASSET_SHA_MISMATCH:{actual_sha}:{expected_sha}"
        )
    if manifest.get("noBrandPass") is not True:
        raise RuntimeError("GENERIC_PREFLIGHT_ASSET_BRAND_GATE_FAIL")

    OUT.mkdir(parents=True, exist_ok=True)
    actor_ids = ("actor_alpha", "actor_beta")
    binding_common = {
        "sourceUid": "generic-hypercar-v1",
        "sourceProvider": "iss_original_blender",
        "sourceSha256": actual_sha,
        "totalMassKg": float(manifest.get("massKg") or 1450.0),
        "semanticBodies": ["front", "rear", "body", "chassis"],
        "runtimeProfile": {
            "forwardAxis": SOURCE_FORWARD_AXIS,
            "maxSpeedMps": 18.0,
            "maxReverseMps": 5.0,
            "accelerationMps2": 7.0,
            "brakingMps2": 10.0,
            "maxYawRateRadS": 1.35,
            "toughnessJPerKg": 72.0,
            "friction": 1.0,
            "restitution": 0.03,
        },
    }
    bindings = [
        {**binding_common, "entityId": actor_ids[0], "assetId": "generic-alpha"},
        {**binding_common, "entityId": actor_ids[1], "assetId": "generic-beta"},
    ]

    request = {
        "engine": EXPECTED_ENGINE,
        "engineVersion": EXPECTED_ENGINE_VERSION,
        "executionMode": "BATTLE",
        "durationSeconds": 6,
        "physicsFps": 120,
        "renderSpec": {
            "fps": 30,
            "renderer": "BLENDER_EEVEE_NEXT",
            "resolution": {"width": 960, "height": 540},
            "aspectRatio": "16:9",
        },
        "executionPolicy": {
            "resetAllowed": False,
            "continuousWorld": True,
            "teleportAllowed": False,
            "persistentDamage": True,
            "persistentDebris": True,
            "silentSimplificationAllowed": False,
            "replanOnPhysicalImpossibility": True,
            "forcedTransformAfterContactAllowed": False,
            "velocityInjectionAfterContactAllowed": False,
        },
        "requiredEvidence": {
            "noReset": True,
            "noTeleport": True,
            "causeEffect": True,
            "visibleDamage": True,
            "physicsFidelity": True,
            "persistentDebris": True,
            "noForcedTransform": True,
            "noSilentSimplification": True,
        },
        "battlePlan": {
            "world": {"simulationContinuous": True},
            "objective": "Resolve a generic solver-driven two-actor impact without scenario-specific code.",
            "finalOutcome": "Preserve the physically earned aftermath state.",
            "events": [
                {
                    "eventId": "evt-setup",
                    "type": "BATTLE_HOOK",
                    "phase": "HOOK",
                    "startTime": 0.0,
                    "endTime": 0.5,
                    "actors": list(actor_ids),
                    "attackTarget": "",
                    "causedByEventIds": [],
                    "damage": {"required": False},
                    "physicsRequirements": {
                        "speedIntent": "hold",
                        "trajectory": "setup",
                        "targetArea": "none",
                    },
                    "requiredOutcome": "Both actors remain in one continuous world.",
                    "usesPersistentWorldState": True,
                },
                {
                    "eventId": "evt-impact",
                    "type": "COORDINATED_ATTACK",
                    "phase": "FIRST_ATTACK",
                    "startTime": 0.5,
                    "endTime": 4.0,
                    "actors": ["actor_alpha"],
                    "attackTarget": "actor_beta:front",
                    "causedByEventIds": ["evt-setup"],
                    "damage": {
                        "required": True,
                        "persistent": True,
                        "zone": "front",
                    },
                    "physicsRequirements": {
                        "speedIntent": "accelerate",
                        "trajectory": "direct converging approach",
                        "targetArea": "front",
                        "momentumIntent": "mass-aware forward momentum",
                        "structuralResponse": "contact-driven persistent deformation",
                        "minQualifiedContacts": 1,
                        "minDistinctAttackers": 1,
                    },
                    "requiredOutcome": "A solver-qualified impact physically earns persistent front damage.",
                    "usesPersistentWorldState": True,
                },
                {
                    "eventId": "evt-payoff",
                    "type": "OUTCOME",
                    "phase": "PAYOFF",
                    "startTime": 4.0,
                    "endTime": 6.0,
                    "actors": list(actor_ids),
                    "attackTarget": "",
                    "causedByEventIds": ["evt-impact"],
                    "damage": {"required": False, "persistent": True},
                    "physicsRequirements": {
                        "speedIntent": "settle",
                        "trajectory": "natural post-contact motion",
                        "targetArea": "none",
                    },
                    "requiredOutcome": "Final positions, damage and debris remain physically earned and persistent.",
                    "usesPersistentWorldState": True,
                },
            ],
        },
        "scenes": [
            {
                "sceneNumber": 1,
                "startSecond": 0.0,
                "endSecond": 3.0,
                "eventIds": ["evt-setup", "evt-impact"],
                "cameraIntent": "Track approach and physical impact.",
            },
            {
                "sceneNumber": 2,
                "startSecond": 3.0,
                "endSecond": 6.0,
                "eventIds": ["evt-impact", "evt-payoff"],
                "cameraIntent": "Track persistent consequence and aftermath.",
            },
        ],
        "assetBindings": bindings,
    }

    asset_map = {
        actor_id: {"path": str(GLB.resolve()), "sha256": actual_sha}
        for actor_id in actor_ids
    }
    (OUT / "request.json").write_text(
        json.dumps(request, indent=2, sort_keys=True), encoding="utf-8"
    )
    (OUT / "asset-map.json").write_text(
        json.dumps(asset_map, indent=2, sort_keys=True), encoding="utf-8"
    )
    print(
        json.dumps(
            {
                "marker": "GENERIC_BATTLE_RUNTIME_PREFLIGHT_FIXTURE_PASS",
                "assetSha256": actual_sha,
                "sourceForwardAxis": SOURCE_FORWARD_AXIS,
                "actorCount": 2,
                "eventCount": 3,
                "request": str((OUT / "request.json").resolve()),
                "assetMap": str((OUT / "asset-map.json").resolve()),
            },
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
