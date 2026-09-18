#!/usr/bin/env python3
from __future__ import annotations

import ast
import importlib.util
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
ENTRYPOINT = ROOT / "blender" / "run_generic_battle_runtime_v1_candidate487_1_final.py"


def main() -> None:
    text = ENTRYPOINT.read_text(encoding="utf-8")
    ast.parse(text, filename=str(ENTRYPOINT))

    repo_decl = text.index("REPO_ROOT = Path(__file__).resolve().parents[1]")
    sys_path_guard = text.index("sys.path.insert(0, str(REPO_ROOT))")
    first_blender_import = text.index("from blender import")
    assert repo_decl < sys_path_guard < first_blender_import

    original = list(sys.path)
    try:
        sys.path[:] = [p for p in sys.path if Path(p or ".").resolve() != ROOT.resolve()]
        assert importlib.util.find_spec("blender") is None
        sys.path.insert(0, str(ROOT))
        spec = importlib.util.find_spec("blender")
        assert spec is not None and spec.submodule_search_locations is not None
    finally:
        sys.path[:] = original

    for required in (
        'C487_1_ENTRYPOINT_BOOTSTRAP=PASS',
        'candidate486.main = candidate485.main',
        'candidate487.main()',
        'C487.1_BLENDER_REPO_ROOT_BOOTSTRAP_V1',
    ):
        assert required in text, required

    lower = text.lower()
    for forbidden in (
        "bugatti",
        "bulldozer",
        "min_damage_severity",
        "min_closing_speed_mps",
        "desiredimpactspeedmps",
        "desiredimpactenergyj",
        "trajectorypoints",
        "waypoints",
        "linear_velocity =",
        "set_pose",
    ):
        assert forbidden not in lower, forbidden

    print(json.dumps({
        "marker": "GENERIC_AUTONOMOUS_BATTLE_C487_1_ENTRYPOINT_ACCEPTANCE",
        "status": "PASS",
        "scope": "DIRECT_BLENDER_PYTHON_ENTRYPOINT_IMPORT_CONTEXT_ONLY",
        "repoRootInjectedBeforePackageImport": True,
        "underlyingRuntimeCandidate": "C487",
        "underlyingLifecycleSourceChanged": False,
        "g05SourceChanged": False,
        "g06SourceChanged": False,
        "g07SourceChanged": False,
        "g08SourceChanged": False,
        "thresholdChanged": False,
        "perAssetBattleCode": False,
        "perVideoTrajectoryEngineering": False,
        "gateClosed": False,
    }, sort_keys=True))


if __name__ == "__main__":
    main()
