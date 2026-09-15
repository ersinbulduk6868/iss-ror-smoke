from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

import bpy

from blender import iss_battle_runtime_assets as assets
from blender import run_generic_battle_runtime_v1_candidate34 as candidate34
from blender import run_generic_battle_runtime_v1_candidate39 as candidate39


def args() -> argparse.Namespace:
    argv = sys.argv
    argv = argv[argv.index("--") + 1:] if "--" in argv else []
    p = argparse.ArgumentParser()
    p.add_argument("--bugatti", required=True)
    return p.parse_args(argv)


def clear_scene() -> None:
    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.object.delete(use_global=False)
    for collection in list(bpy.data.collections):
        if collection.users == 0:
            bpy.data.collections.remove(collection)


def normalize(path: Path, binding: dict) -> tuple:
    imported = assets.import_asset(path)
    return candidate39.surface_semantic_normalize(binding, imported)


def close(a: float, b: float, tol: float) -> bool:
    return abs(float(a) - float(b)) <= float(tol)


def main() -> None:
    a = args()
    assets.centroid_for_terms = candidate34.ambiguity_safe_centroid_for_terms

    clear_scene()
    bugatti_binding = {
        "entityId": "bugatti_probe",
        "totalMassKg": 1570.0,
        "semanticBodies": ["front", "rear", "body", "chassis"],
        "runtimeProfile": {"locomotionModel": "GROUND_DIFFERENTIAL"},
    }
    bugatti_dims, bugatti_zones, bugatti_evidence, bugatti_axis = normalize(
        Path(a.bugatti).resolve(), bugatti_binding
    )
    if bugatti_axis != "-Y":
        raise RuntimeError(f"BUGATTI_FORWARD_AXIS_REGRESSION:{bugatti_axis}")
    expected = (4.900918, 2.225155, 1.191855)
    for got, want in zip(bugatti_dims, expected):
        if not close(got, want, 0.035):
            raise RuntimeError(f"BUGATTI_SUPPORTED_ENVELOPE_REGRESSION:{list(bugatti_dims)}")
    if not close(bugatti_zones["front"].x, bugatti_dims.x * 0.5, 0.04):
        raise RuntimeError(f"BUGATTI_FRONT_NOT_ON_SURFACE:{list(bugatti_zones['front'])}")
    if not close(bugatti_zones["rear"].x, -bugatti_dims.x * 0.5, 0.04):
        raise RuntimeError(f"BUGATTI_REAR_NOT_ON_SURFACE:{list(bugatti_zones['rear'])}")
    if bugatti_evidence.get("front") != candidate39.SEMANTIC_SURFACE_MODEL:
        raise RuntimeError("BUGATTI_FRONT_SURFACE_EVIDENCE_MISSING")

    clear_scene()
    generic = REPO_ROOT / "assets" / "generated" / "generic-hypercar-v1" / "generic_hypercar.glb"
    generic_binding = {
        "entityId": "generic_probe",
        "totalMassKg": 1450.0,
        "semanticBodies": ["front", "rear", "body", "chassis"],
        "runtimeProfile": {
            "locomotionModel": "GROUND_DIFFERENTIAL",
            "forwardAxis": "-Y",
        },
    }
    generic_dims, generic_zones, generic_evidence, generic_axis = normalize(
        generic.resolve(), generic_binding
    )
    if generic_axis != "-Y":
        raise RuntimeError(f"GENERIC_FORWARD_AXIS_REGRESSION:{generic_axis}")
    expected_generic = (4.42, 2.06, 1.36)
    for got, want in zip(generic_dims, expected_generic):
        if not close(got, want, 0.035):
            raise RuntimeError(f"GENERIC_ENVELOPE_REGRESSION:{list(generic_dims)}")
    if not close(generic_zones["front"].x, generic_dims.x * 0.5, 0.04):
        raise RuntimeError("GENERIC_FRONT_NOT_ON_SURFACE")
    if generic_evidence.get("front") != candidate39.SEMANTIC_SURFACE_MODEL:
        raise RuntimeError("GENERIC_FRONT_SURFACE_EVIDENCE_MISSING")

    print(json.dumps({
        "marker": "GENERIC_BATTLE_RUNTIME_CANDIDATE39_ASSET_REGRESSION",
        "status": "PASS",
        "bugatti": {
            "dimensions": [round(float(x), 6) for x in bugatti_dims],
            "sourceForwardAxis": bugatti_axis,
            "front": [round(float(x), 6) for x in bugatti_zones["front"]],
            "rear": [round(float(x), 6) for x in bugatti_zones["rear"]],
            "frontEvidence": bugatti_evidence.get("front"),
        },
        "genericHypercar": {
            "dimensions": [round(float(x), 6) for x in generic_dims],
            "sourceForwardAxis": generic_axis,
            "frontEvidence": generic_evidence.get("front"),
        },
        "lockRegression": False,
    }, sort_keys=True), flush=True)


if __name__ == "__main__":
    main()
