from __future__ import annotations

from blender import run_generic_battle_runtime_v1_candidate485_generic_battle as candidate485
from blender import run_generic_battle_runtime_v1_candidate486_generic_battle as candidate486
from blender import run_generic_battle_runtime_v1_candidate487_generic_battle as candidate487


def main() -> None:
    # C487 supersedes C486's mode-blind corridor composition.  Do not execute the
    # C486 main receipt and then claim its mechanism is active.  Reuse C485 as the
    # preserved predecessor while C487 owns the corrected event-scoped lifecycle.
    candidate486.main = candidate485.main
    candidate487.main()


if __name__ == "__main__":
    main()
