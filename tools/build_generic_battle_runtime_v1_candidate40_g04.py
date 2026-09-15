#!/usr/bin/env python3
from __future__ import annotations

import argparse
import copy
import hashlib
import json
from pathlib import Path

import build_generic_battle_runtime_v1_preflight as base

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "artifacts" / "generic-battle-runtime-v1-candidate40-g04"
EXPECTED_BUGATTI_SHA = "8cc074c40fe9ced7271cbeddf223cd9a520dee868977ffcbd439cec1c2b62cb4"
EXPECTED_BUGATTI_BYTES = 31576440
BUGATTI_SOURCE_UID = "4af92c51ecdd4efa9b1c19a1163d9f46"


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def motion_request(template: dict, bindings: list[dict]) -> dict:
    request = copy.deepcopy(template)
    request["durationSeconds"] = 8
    request["assetBindings"] = copy.deepcopy(bindings)
    request["requiredEvidence"]["visibleDamage"] = False
    request["requiredEvidence"]["persistentDebris"] = False
    request["battlePlan"]["objective"] = (
        "Autonomously acquire a moving semantic target and physically converge without exact trajectory, impact-speed, collision-frame or Joule choreography."
    )
    request["battlePlan"]["finalOutcome"] = (
        "Both contact intents are physically resolved in one continuous world; final product contact/damage authority remains downstream G05/G06."
    )

    setup = {
        "eventId": "evt-setup",
        "type": "BATTLE_HOOK",
        "phase": "HOOK",
        "startTime": 0.0,
        "endTime": 0.5,
        "actors": ["actor_alpha", "actor_beta"],
        "attackTarget": "",
        "causedByEventIds": [],
        "damage": {"required": False},
        "physicsRequirements": {
            "speedIntent": "hold",
            "trajectory": "setup",
            "targetArea": "none",
        },
        "requiredOutcome": "Actors remain in one continuous physical world.",
        "usesPersistentWorldState": True,
    }
    alpha = {
        "eventId": "evt-contact-alpha",
        "type": "COORDINATED_ATTACK",
        "phase": "FIRST_ATTACK",
        "startTime": 0.5,
        "endTime": 6.5,
        "actors": ["actor_alpha"],
        "attackTarget": "actor_beta:front",
        "causedByEventIds": ["evt-setup"],
        "damage": {"required": False, "persistent": True, "zone": "front"},
        "physicsRequirements": {
            "speedIntent": "accelerate",
            "trajectory": "direct converging approach",
            "targetArea": "front",
            "minQualifiedContacts": 1,
            "minDistinctAttackers": 1,
        },
        "requiredOutcome": "Closed-loop control resolves the current moving front target through physical convergence.",
        "usesPersistentWorldState": True,
    }
    beta = copy.deepcopy(alpha)
    beta["eventId"] = "evt-contact-beta"
    beta["actors"] = ["actor_beta"]
    beta["attackTarget"] = "actor_alpha:front"
    payoff = {
        "eventId": "evt-payoff",
        "type": "OUTCOME",
        "phase": "PAYOFF",
        "startTime": 6.5,
        "endTime": 8.0,
        "actors": ["actor_alpha", "actor_beta"],
        "attackTarget": "",
        "causedByEventIds": ["evt-contact-alpha", "evt-contact-beta"],
        "damage": {"required": False, "persistent": True},
        "physicsRequirements": {
            "speedIntent": "settle",
            "trajectory": "natural physical aftermath",
            "targetArea": "none",
        },
        "requiredOutcome": "Final physical state remains continuous.",
        "usesPersistentWorldState": True,
    }
    request["battlePlan"]["events"] = [setup, alpha, beta, payoff]
    request["scenes"] = [
        {
            "sceneNumber": 1,
            "startSecond": 0.0,
            "endSecond": 4.0,
            "eventIds": ["evt-setup", "evt-contact-alpha", "evt-contact-beta"],
            "cameraIntent": "Track autonomous acquisition and convergence.",
        },
        {
            "sceneNumber": 2,
            "startSecond": 4.0,
            "endSecond": 8.0,
            "eventIds": ["evt-contact-alpha", "evt-contact-beta", "evt-payoff"],
            "cameraIntent": "Track physical completion and continuous aftermath.",
        },
    ]
    return request


def write_fixture(name: str, request: dict, amap: dict) -> dict:
    out = OUT / name
    out.mkdir(parents=True, exist_ok=True)
    request_path = out / "request.json"
    asset_map_path = out / "asset-map.json"
    request_path.write_text(json.dumps(request, indent=2, sort_keys=True), encoding="utf-8")
    asset_map_path.write_text(json.dumps(amap, indent=2, sort_keys=True), encoding="utf-8")
    return {
        "request": str(request_path.resolve()),
        "assetMap": str(asset_map_path.resolve()),
        "actorCount": len(request["assetBindings"]),
        "eventCount": len(request["battlePlan"]["events"]),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--bugatti-primary", required=True)
    args = parser.parse_args()

    base.main()
    template = json.loads((base.OUT / "request.json").read_text(encoding="utf-8"))

    generic_glb = base.GLB.resolve()
    generic_sha = sha256_file(generic_glb)
    generic_bindings = copy.deepcopy(template["assetBindings"])
    generic_request = motion_request(template, generic_bindings)
    generic_map = {
        row["entityId"]: {"path": str(generic_glb), "sha256": generic_sha}
        for row in generic_bindings
    }
    generic = write_fixture("generic-hypercar", generic_request, generic_map)

    bugatti = Path(args.bugatti_primary).expanduser().resolve()
    if not bugatti.is_file():
        raise RuntimeError(f"BUGATTI_PRIMARY_MISSING:{bugatti}")
    bugatti_sha = sha256_file(bugatti)
    if bugatti_sha != EXPECTED_BUGATTI_SHA or bugatti.stat().st_size != EXPECTED_BUGATTI_BYTES:
        raise RuntimeError("CANDIDATE40_BUGATTI_EXACT_IDENTITY_FAIL")
    common = {
        "sourceUid": BUGATTI_SOURCE_UID,
        "sourceProvider": "exact_full_source",
        "sourceSha256": bugatti_sha,
        "totalMassKg": 1570.0,
        "semanticBodies": ["front", "rear", "body", "chassis"],
        "runtimeProfile": {
            "locomotionModel": "GROUND_DIFFERENTIAL",
            "friction": 1.0,
            "restitution": 0.03,
        },
    }
    bugatti_bindings = [
        {**common, "entityId": "actor_alpha", "assetId": "bugatti-alpha"},
        {**common, "entityId": "actor_beta", "assetId": "bugatti-beta"},
    ]
    bugatti_request = motion_request(template, bugatti_bindings)
    bugatti_map = {
        row["entityId"]: {"path": str(bugatti), "sha256": bugatti_sha}
        for row in bugatti_bindings
    }
    exact = write_fixture("exact-bugatti", bugatti_request, bugatti_map)

    print(json.dumps({
        "marker": "GENERIC_BATTLE_RUNTIME_CANDIDATE40_G04_FIXTURES_PASS",
        "generic": {**generic, "sha256": generic_sha},
        "exactBugatti": {**exact, "sha256": bugatti_sha, "bytes": bugatti.stat().st_size},
        "damageRequired": False,
        "exactCollisionFrameTarget": False,
        "exactImpactEnergyTarget": False,
        "manualTrajectoryPoints": False,
    }, sort_keys=True))


if __name__ == "__main__":
    main()
