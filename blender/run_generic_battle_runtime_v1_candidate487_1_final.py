from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from blender import run_generic_battle_runtime_v1_candidate485_generic_battle as candidate485
from blender import run_generic_battle_runtime_v1_candidate486_generic_battle as candidate486
from blender import run_generic_battle_runtime_v1_candidate487_generic_battle as candidate487

ENTRYPOINT = "C487.1_BLENDER_REPO_ROOT_BOOTSTRAP_V1"


def main() -> None:
    # Preserve C487 runtime behavior exactly.  C487.1 fixes only the direct Blender
    # --python execution context so the repository package can be imported before
    # the preserved C487 final composition is entered.
    print("C487_1_ENTRYPOINT_BOOTSTRAP=PASS", flush=True)
    candidate486.main = candidate485.main
    candidate487.main()


if __name__ == "__main__":
    main()
