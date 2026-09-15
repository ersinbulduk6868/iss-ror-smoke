#!/usr/bin/env python3
from __future__ import annotations

import runpy
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TARGET = Path(__file__).resolve().with_name("iss_blender_battle_runtime_v1_hardened.py")

if not TARGET.is_file():
    raise RuntimeError(f"GENERIC_BATTLE_RUNTIME_ENTRYPOINT_MISSING:{TARGET}")

root_text = str(ROOT)
if root_text not in sys.path:
    sys.path.insert(0, root_text)

if str(sys.path[0]) != root_text:
    raise RuntimeError("GENERIC_BATTLE_RUNTIME_REPO_ROOT_BOOTSTRAP_FAILED")

print(
    f'{{"marker":"GENERIC_BATTLE_RUNTIME_PYTHON_BOOTSTRAP_PASS",'
    f'"repoRoot":"{root_text}"}}',
    flush=True,
)
runpy.run_path(str(TARGET), run_name="__main__")
