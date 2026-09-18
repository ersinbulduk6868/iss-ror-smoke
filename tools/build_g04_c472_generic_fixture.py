#!/usr/bin/env python3
from __future__ import annotations

import copy
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
TOOLS = ROOT / "tools"
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

import build_generic_battle_runtime_v1_preflight as base
import build_generic_battle_runtime_v1_candidate442_g07 as candidate442
import build_generic_battle_runtime_v1_candidate446_g07 as candidate446

OUT = ROOT / "artifacts" / "g04-c472-builder"


def main() -> None:
    # Reuse the proven deterministic generic asset/template path only.  Exact
    # Bugatti is intentionally not resolved here because G04 isolated pursuit
    # acceptance does not own asset-control-plane/OIDC authorization.
    base.main()
    template = json.loads((base.OUT / "request.json").read_text(encoding="utf-8"))
    generic_glb = base.GLB.resolve()
    if not generic_glb.is_file():
        raise RuntimeError(f"C472_GENERIC_GLB_MISSING:{generic_glb}")
    generic_sha = candidate442.sha256_file(generic_glb)

    generic_bindings = copy.deepcopy(template["assetBindings"])
    request = candidate442.drama_request(template, generic_bindings)
    candidate442.verify_intent_only_request(request)

    out = OUT / "generic-hypercar"
    out.mkdir(parents=True, exist_ok=True)
    request_path = out / "request.json"
    asset_map_path = out / "asset-map.json"
    amap = {
        row["entityId"]: {"path": str(generic_glb), "sha256": generic_sha}
        for row in generic_bindings
    }

    # Apply exactly the established Candidate446 climax-state adaptation, then
    # run its post-write scope validator.  No legacy builder is modified.
    before_climax = candidate446._patch_climax(request)
    request_path.write_text(json.dumps(request, indent=2, sort_keys=True), encoding="utf-8")
    asset_map_path.write_text(json.dumps(amap, indent=2, sort_keys=True), encoding="utf-8")
    candidate446._verify(request_path, before_climax)

    print(json.dumps({
        "marker": "G04_C472_GENERIC_FIXTURE_PASS",
        "status": "PASS",
        "fixture": "generic-hypercar",
        "request": str(request_path.resolve()),
        "assetMap": str(asset_map_path.resolve()),
        "genericAssetSha256": generic_sha,
        "actorCount": len(generic_bindings),
        "eventCount": len(request["battlePlan"]["events"]),
        "candidate446ClimaxSemanticsPreserved": True,
        "storyIntentOnly": True,
        "storyTargetZonePrescribed": False,
        "fixtureMutationForAcceptance": False,
        "exactBugattiRequired": False,
        "supabaseOidcRequired": False,
        "perAssetBattleCode": False,
        "perVideoTrajectoryEngineering": False,
    }, sort_keys=True))


if __name__ == "__main__":
    main()
