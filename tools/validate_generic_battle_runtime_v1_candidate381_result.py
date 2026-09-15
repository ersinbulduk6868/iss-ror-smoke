#!/usr/bin/env python3
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

import validate_generic_battle_runtime_v1_candidate371_result as inherited

EXPECTED_RUNTIME = "ISS_GENERIC_BATTLE_RUNTIME_V1_CANDIDATE_3_8_1"


def main() -> None:
    inherited.EXPECTED_RUNTIME = EXPECTED_RUNTIME
    inherited.main()
    path = inherited.evidence_path()
    evidence = json.loads(path.read_text(encoding="utf-8"))
    runtime = str((evidence.get("runtime") or evidence.get("runtimeVersion") or ""))
    if runtime and runtime != EXPECTED_RUNTIME:
        raise RuntimeError(f"CANDIDATE381_RUNTIME_MISMATCH:{runtime}")
    print(json.dumps({
        "marker": "GENERIC_BATTLE_RUNTIME_CANDIDATE381_MACHINE_PREFLIGHT",
        "status": "PASS",
        "runtime": EXPECTED_RUNTIME,
        "gateInheritance": "CANDIDATE371_FULL_MACHINE_TRUTH_PLUS_GENERIC_PRESENTATION_AND_DIRECTIONAL_SEMANTIC_HARDENING",
        "nextGate": "HUMAN_VISUAL_REVIEW",
    }, sort_keys=True))


if __name__ == "__main__":
    main()
