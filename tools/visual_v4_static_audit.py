from __future__ import annotations

import ast
import subprocess
from pathlib import Path

SAFE_BASE = "84cb9305f34dd38198d6627b5ed866ccb43c16fe"
ALLOWED_EXACT = {
    ".github/workflows/blender-visual-v4-preflight.yml",
    "tools/visual_v4_static_audit.py",
    "tools/visual_v4_asset_preflight.py",
    "blender/visual_v4_scene.py",
    "ISS_BATTLE_VIDEO_VISUAL_ACCEPTANCE_V4.md",
}


def fail(msg: str) -> None:
    raise SystemExit("STATIC_AUDIT_FAIL|" + msg)


def main() -> None:
    workflow_path = Path(".github/workflows/blender-visual-v4-preflight.yml")
    scene_path = Path("blender/visual_v4_scene.py")
    asset_path = Path("tools/visual_v4_asset_preflight.py")
    for p in (workflow_path, scene_path, asset_path):
        if not p.is_file():
            fail(f"MISSING:{p}")

    workflow = workflow_path.read_text(encoding="utf-8")
    scene = scene_path.read_text(encoding="utf-8")
    asset = asset_path.read_text(encoding="utf-8")

    failures: list[str] = []

    # Candidate isolation: no locked/proven service files may be touched.
    changed = subprocess.check_output(
        ["git", "diff", "--name-only", f"{SAFE_BASE}...HEAD"], text=True
    ).splitlines()
    unexpected = sorted(p for p in changed if p not in ALLOWED_EXACT)
    if unexpected:
        failures.append("LOCKED_OR_OUT_OF_SCOPE_CHANGE:" + ",".join(unexpected))

    # Workflow is read-only and branch-isolated.
    if "permissions:\n  contents: read" not in workflow:
        failures.append("WORKFLOW_CONTENTS_READ_PERMISSION_MISSING")
    if "contents: write" in workflow:
        failures.append("WORKFLOW_CONTENTS_WRITE_FORBIDDEN")
    if "iss-test/visual-v4-preflight" not in workflow:
        failures.append("CANDIDATE_BRANCH_FILTER_MISSING")
    for raw in workflow.splitlines():
        cmd = raw.strip().lower()
        if cmd.startswith("git push") or cmd.startswith("git commit") or cmd.startswith("gh workflow run"):
            failures.append("WORKFLOW_MUTATING_COMMAND:" + cmd[:120])

    # Visible-geometry and renderer fail-closed rules.
    for label, text in (("scene", scene), ("asset", asset)):
        for banned in (
            "assets/test-real-model",
            "_quant120.json",
            "BLENDER_WORKBENCH",
            "generic_hypercar.glb",
        ):
            if banned in text:
                failures.append(f"{label}:FORBIDDEN:{banned}")
    if "BLENDER_EEVEE_NEXT" not in scene:
        failures.append("EEVEE_NEXT_REQUIRED_MARKER_MISSING")
    if "FULL_SOURCE_GLTF" not in scene:
        failures.append("FULL_SOURCE_GLTF_MARKER_MISSING")
    if "damagePhysicalSolver" not in scene or "False" not in scene:
        failures.append("DAMAGE_TRUTH_MARKER_MISSING")

    # Acceptance results must be expressions, never literal True.
    tree = ast.parse(scene)
    for node in ast.walk(tree):
        if not isinstance(node, ast.Dict):
            continue
        for k, v in zip(node.keys, node.values):
            if isinstance(k, ast.Constant) and isinstance(k.value, str) and k.value.startswith("A"):
                if isinstance(v, ast.Constant) and v.value is True:
                    failures.append(f"HARDCODED_ACCEPTANCE_TRUE:{k.value}")

    # Preflight workflow must never invoke final render mode.
    if "--mode final" in workflow:
        failures.append("FINAL_RENDER_IN_PREFLIGHT_WORKFLOW_FORBIDDEN")
    if "--mode preflight" not in workflow:
        failures.append("PREFLIGHT_MODE_MARKER_MISSING")

    if failures:
        fail("|".join(failures))

    print("LOCKED_SERVICE_MUTATION=NO")
    print("CANDIDATE_ISOLATION=PASS")
    print("VISIBLE_QUANT120_REFERENCE=NO")
    print("GENERIC_VISIBLE_FALLBACK=NO")
    print("WORKBENCH_FALLBACK=NO")
    print("HARDCODED_ACCEPTANCE_PASS=NO")
    print("WORKFLOW_REPO_WRITE=NO")
    print("FINAL_RENDER_IN_PREFLIGHT=NO")
    print("STATIC_CANDIDATE_AUDIT=PASS")


if __name__ == "__main__":
    main()
