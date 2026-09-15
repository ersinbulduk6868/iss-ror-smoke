#!/usr/bin/env python3
from __future__ import annotations

import argparse
import copy
import hashlib
import json
from pathlib import Path

import build_generic_battle_runtime_v1_preflight as base

EXPECTED_SHA = "8cc074c40fe9ced7271cbeddf223cd9a520dee868977ffcbd439cec1c2b62cb4"
EXPECTED_BYTES = 31576440
SOURCE_UID = "4af92c51ecdd4efa9b1c19a1163d9f46"
MASS_KG = 1570.0
OUT = base.ROOT / "artifacts" / "generic-battle-runtime-v1-bugatti-preflight"


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--bugatti-primary", required=True)
    a = p.parse_args()
    glb = Path(a.bugatti_primary).expanduser().resolve()
    if not glb.is_file():
        raise RuntimeError(f"BUGATTI_PRIMARY_MISSING:{glb}")
    sha = sha256_file(glb)
    if sha != EXPECTED_SHA or glb.stat().st_size != EXPECTED_BYTES:
        raise RuntimeError("BUGATTI_EXACT_IDENTITY_FAIL")

    base.main()
    template = base.OUT
    request = json.loads((template / "request.json").read_text(encoding="utf-8"))

    common = {
        "sourceUid": SOURCE_UID,
        "sourceProvider": "exact_full_source",
        "sourceSha256": sha,
        "totalMassKg": MASS_KG,
        "semanticBodies": ["front", "rear", "body", "chassis"],
        "runtimeProfile": {
            "locomotionModel": "GROUND_DIFFERENTIAL",
            "friction": 1.0,
            "restitution": 0.03,
        },
    }
    request["assetBindings"] = [
        {**common, "entityId": "actor_alpha", "assetId": "bugatti-alpha"},
        {**common, "entityId": "actor_beta", "assetId": "bugatti-beta"},
    ]
    request["battlePlan"]["objective"] = "Generic two-sided solver-driven exact Bugatti impact."
    request["battlePlan"]["finalOutcome"] = "Preserve physically earned two-sided aftermath."

    events = request["battlePlan"]["events"]
    first = next(e for e in events if e["eventId"] == "evt-impact")
    first["eventId"] = "evt-impact-alpha"
    first["actors"] = ["actor_alpha"]
    first["attackTarget"] = "actor_beta:front"
    second = copy.deepcopy(first)
    second["eventId"] = "evt-impact-beta"
    second["actors"] = ["actor_beta"]
    second["attackTarget"] = "actor_alpha:front"
    payoff = next(e for e in events if e["eventId"] == "evt-payoff")
    payoff["causedByEventIds"] = ["evt-impact-alpha", "evt-impact-beta"]
    request["battlePlan"]["events"] = [events[0], first, second, payoff]

    for scene in request["scenes"]:
        scene["eventIds"] = [
            x for x in scene["eventIds"] if x != "evt-impact"
        ] + ["evt-impact-alpha", "evt-impact-beta"]

    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "request.json").write_text(json.dumps(request, indent=2, sort_keys=True), encoding="utf-8")
    amap = {
        "actor_alpha": {"path": str(glb), "sha256": sha},
        "actor_beta": {"path": str(glb), "sha256": sha},
    }
    (OUT / "asset-map.json").write_text(json.dumps(amap, indent=2, sort_keys=True), encoding="utf-8")
    print(json.dumps({
        "marker": "GENERIC_BATTLE_RUNTIME_BUGATTI_FIXTURE_PASS",
        "assetSha256": sha,
        "assetBytes": glb.stat().st_size,
        "sourceUid": SOURCE_UID,
        "sourceForwardAxis": "RUNTIME_SEMANTIC_RESOLUTION_REQUIRED",
        "actorCount": 2,
        "eventCount": 4,
        "twoSidedControllerIntent": True,
        "scenarioTrajectoryHardcode": False,
        "request": str((OUT / "request.json").resolve()),
        "assetMap": str((OUT / "asset-map.json").resolve()),
    }, sort_keys=True))


if __name__ == "__main__":
    main()
