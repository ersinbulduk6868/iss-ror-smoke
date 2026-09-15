#!/usr/bin/env python3
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

import validate_generic_battle_runtime_v1_candidate32_result as base

EXPECTED_RUNTIME = "ISS_GENERIC_BATTLE_RUNTIME_V1_CANDIDATE_3_5"


def main() -> None:
    base.EXPECTED_RUNTIME = EXPECTED_RUNTIME
    base.main()
    print(json.dumps({
        "marker": "GENERIC_BATTLE_RUNTIME_CANDIDATE35_MACHINE_PREFLIGHT",
        "status": "PASS",
        "runtime": EXPECTED_RUNTIME,
        "gateInheritance": "CANDIDATE32_FULL_MACHINE_TRUTH_PLUS_SEMANTIC_AND_PHYSICAL_DRIVE_AUTHORITY_HARDENING",
    }, sort_keys=True))


if __name__ == "__main__":
    main()
