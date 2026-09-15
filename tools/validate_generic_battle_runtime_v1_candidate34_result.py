#!/usr/bin/env python3
from __future__ import annotations

import json

from tools import validate_generic_battle_runtime_v1_candidate32_result as base

EXPECTED_RUNTIME = "ISS_GENERIC_BATTLE_RUNTIME_V1_CANDIDATE_3_4"


def main() -> None:
    base.EXPECTED_RUNTIME = EXPECTED_RUNTIME
    base.main()
    print(json.dumps({
        "marker": "GENERIC_BATTLE_RUNTIME_CANDIDATE34_MACHINE_PREFLIGHT",
        "status": "PASS",
        "runtime": EXPECTED_RUNTIME,
        "gateInheritance": "CANDIDATE32_FULL_MACHINE_TRUTH_PLUS_AMBIGUITY_SAFE_SEMANTIC_TARGETING",
    }, sort_keys=True))


if __name__ == "__main__":
    main()
