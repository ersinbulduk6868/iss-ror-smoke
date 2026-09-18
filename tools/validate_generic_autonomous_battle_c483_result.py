#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
TOOLS = ROOT / "tools"
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

import validate_generic_autonomous_battle_c482_result as c482
from validate_generic_autonomous_battle_c480_result import _json_markers


def main() -> None:
    p = argparse.ArgumentParser(add_help=False)
    p.add_argument("--hetero-log", required=True)
    a, _ = p.parse_known_args()

    rows = _json_markers(a.hetero_log)
    ready = [r for r in rows if r.get("marker") == "GENERIC_AUTONOMOUS_BATTLE_C483_ENGINEERING_READY"]
    assert len(ready) == 1, ("C483_ENGINEERING_READY_COUNT", len(ready))
    row = ready[0]
    assert row.get("mechanism") == "GENERIC_CANONICAL_DRIVE_DIRECTION_V1", row
    assert row.get("canonicalVehicleForwardAxis") == "+X", row
    assert row.get("blenderWheelMotorPositiveDirectionRealizes") == "CHASSIS_LOCAL_NEGATIVE_X", row
    assert row.get("canonicalLinearCommandSignMappedToMotorSign") == "INVERTED", row
    assert row.get("assetIdentityBranch") is False, row
    assert row.get("perAssetBattleCode") is False, row
    assert row.get("perAssetTacticalTuning") is False, row
    assert row.get("contactThresholdChanged") is False, row
    assert row.get("damageAdmissionThresholdChanged") is False, row

    # Reuse the complete C482 heterogeneous acceptance contract, including
    # machine-proven reciprocal damage semantics and all prior G04/G05/G06/G07/G08 gates.
    c482.main()

    print(json.dumps({
        "marker": "GENERIC_AUTONOMOUS_BATTLE_C483_MACHINE_ACCEPTANCE",
        "status": "PASS",
        "candidate": "ISS_GENERIC_BATTLE_RUNTIME_V1_CANDIDATE_4_8_3_GENERIC_AUTONOMOUS_BATTLE",
        "mechanism": "GENERIC_CANONICAL_DRIVE_DIRECTION_V1",
        "canonicalDriveDirectionRuntimeProof": "PASS",
        "c482HeterogeneousCrossGateAcceptance": "PASS",
        "assetSpecificCode": False,
        "perAssetTacticalTuning": False,
        "thresholdChanged": False,
        "humanCinematicAcceptance": "PENDING",
        "gateClosed": False,
        "productionReadyClaimed": False,
    }, sort_keys=True))


if __name__ == "__main__":
    main()
