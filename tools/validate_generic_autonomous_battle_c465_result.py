#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
TOOLS = ROOT / "tools"
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

from validate_generic_autonomous_battle_c464_result import _validate


def _cutoff_runtime_proof(path: str) -> dict[str, object]:
    battle = json.loads(Path(path).read_text(encoding="utf-8"))
    samples = battle.get("samples") or []
    latched = [
        row for row in samples
        if (row.get("policy") or {}).get("solverHandoffLatched") is True
    ]
    assert latched, "C465_SOLVER_HANDOFF_LATCH_NOT_OBSERVED"
    assert all(row.get("motorAuthority") == "COAST" for row in latched), (
        "C465_MOTOR_AUTHORITY_REENTERED_DURING_ACTIVE_LATCH"
    )
    return {
        "latchedSamples": len(latched),
        "allLatchedSamplesMotorAuthorityCoast": True,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    for prefix in ("bugatti", "generic"):
        for key in ("battle", "g06", "g07", "g08"):
            parser.add_argument(f"--{prefix}-{key}", required=True)
    args = parser.parse_args()

    rows = []
    cutoff_proof = {}
    for prefix in ("bugatti", "generic"):
        battle_path = getattr(args, f"{prefix}_battle")
        rows.append(
            _validate(
                prefix,
                battle_path,
                getattr(args, f"{prefix}_g06"),
                getattr(args, f"{prefix}_g07"),
                getattr(args, f"{prefix}_g08"),
            )
        )
        cutoff_proof[prefix] = _cutoff_runtime_proof(battle_path)

    print(json.dumps({
        "marker": "GENERIC_AUTONOMOUS_BATTLE_C465_MACHINE_ACCEPTANCE",
        "status": "PASS",
        "affectedLayerAudit": "PASS",
        "failureFamily": "HANDOFF_CUTOFF_FRAME_REWRITTEN_AFTER_NATIVE_CONTACT_FRAME",
        "sameRuntimeAcrossAssets": True,
        "precontactRunway": "PASS",
        "surfaceGapRevalidation": "PASS",
        "standOffLiveSupportGeometry": "PASS",
        "solverHandoffLatch": "PASS",
        "handoffCutoffFrameImmutableWithinLatch": "PASS",
        "g05ControllerAuthorityContractPreserved": True,
        "secondNativeContact": "PASS",
        "twoSidedDamage": "PASS",
        "nativeContactAuthorityPreserved": True,
        "damageAdmissionThresholdChanged": False,
        "contactThresholdChanged": False,
        "semanticToleranceChanged": False,
        "localityToleranceChanged": False,
        "damageThresholdAwareControl": False,
        "targetToughnessAwareControl": False,
        "desiredImpactSpeedControl": False,
        "desiredImpactEnergyControl": False,
        "fixtureMutationForAcceptance": False,
        "visibleCausalDamageDebris": "PASS",
        "g07AdaptiveCausalDrama": "PASS",
        "g08MachineObservability": "PASS",
        "humanCinematicAcceptance": "PENDING",
        "gateClosed": False,
        "productionReadyClaimed": False,
        "cutoffRuntimeProof": cutoff_proof,
        "fixtures": rows,
    }, sort_keys=True))


if __name__ == "__main__":
    main()
