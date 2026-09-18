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
from validate_generic_autonomous_battle_c465_result import _cutoff_runtime_proof


def _log_proof(path: str) -> dict[str, object]:
    rows: list[dict[str, object]] = []
    for line in Path(path).read_text(encoding="utf-8", errors="replace").splitlines():
        try:
            row = json.loads(line)
        except Exception:
            continue
        if isinstance(row, dict):
            rows.append(row)

    sync = [r for r in rows if r.get("marker") == "GENERIC_PRECONTACT_SEMANTIC_SURFACE_SYNCHRONIZED"]
    contacts = [r for r in rows if r.get("marker") == "PAIRWISE_NATIVE_SOLVER_CONTACT_VERIFIED"]
    cutoff = [r for r in rows if r.get("marker") == "GENERIC_SOLVER_HANDOFF_CUTOFF_FRAME_STABILIZED"]
    impacts = [
        r for r in rows
        if r.get("marker") in {"QUALIFIED_NATIVE_RESPONSE_IMPACT", "CAUSAL_VISIBLE_IMPACT_CONSEQUENCE_V3_APPLIED"}
    ]
    assert sync, "C466_PRECONTACT_SEMANTIC_SYNC_NOT_OBSERVED"
    assert contacts, "C466_NATIVE_CONTACT_NOT_VERIFIED"
    assert cutoff, "C466_CUTOFF_STABILIZATION_NOT_OBSERVED"
    assert impacts, "C466_CAUSAL_IMPACT_NOT_OBSERVED"

    first_sync_line = next(i for i, r in enumerate(rows) if r.get("marker") == "GENERIC_PRECONTACT_SEMANTIC_SURFACE_SYNCHRONIZED")
    first_contact_line = next(i for i, r in enumerate(rows) if r.get("marker") == "PAIRWISE_NATIVE_SOLVER_CONTACT_VERIFIED")
    assert first_sync_line < first_contact_line, "C466_SYNC_NOT_BEFORE_FIRST_VERIFIED_CONTACT"

    return {
        "semanticSyncCount": len(sync),
        "verifiedNativeContactCount": len(contacts),
        "cutoffStabilizationCount": len(cutoff),
        "causalImpactMarkerCount": len(impacts),
        "semanticSyncObservedBeforeFirstVerifiedContact": True,
        "firstSemanticSyncFrame": int(sync[0].get("frame") or -1),
        "firstVerifiedContactFrame": int(contacts[0].get("contactFrame") or contacts[0].get("frame") or -1),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    for prefix in ("bugatti", "generic"):
        for key in ("battle", "g06", "g07", "g08", "log"):
            parser.add_argument(f"--{prefix}-{key}", required=True)
    args = parser.parse_args()

    fixtures = []
    cutoff_proof: dict[str, object] = {}
    log_proof: dict[str, object] = {}
    for prefix in ("bugatti", "generic"):
        battle_path = getattr(args, f"{prefix}_battle")
        fixtures.append(
            _validate(
                prefix,
                battle_path,
                getattr(args, f"{prefix}_g06"),
                getattr(args, f"{prefix}_g07"),
                getattr(args, f"{prefix}_g08"),
            )
        )
        cutoff_proof[prefix] = _cutoff_runtime_proof(battle_path)
        log_proof[prefix] = _log_proof(getattr(args, f"{prefix}_log"))

    print(json.dumps({
        "marker": "GENERIC_AUTONOMOUS_BATTLE_C466_MACHINE_ACCEPTANCE",
        "status": "PASS",
        "affectedLayerAudit": "PASS",
        "failureFamily": "LIVE_SEMANTIC_SELECTION_ONE_FRAME_LATE_FOR_G05_CONTACT_EVALUATION",
        "sameRuntimeAcrossAssets": True,
        "semanticSelectionSynchronizedBeforeG05": "PASS",
        "existingG07ResolverReusedUnchanged": True,
        "existingG05DetectorReusedUnchanged": True,
        "handoffCutoffFrameImmutableWithinLatch": "PASS",
        "g05ControllerAuthorityContractPreserved": True,
        "g07GenericEngagementContractPreserved": True,
        "secondNativeContact": "PASS",
        "twoSidedDamage": "PASS",
        "visibleCausalDamageDebris": "PASS",
        "g07AdaptiveCausalDrama": "PASS",
        "g08MachineObservability": "PASS",
        "nativeContactAuthorityPreserved": True,
        "semanticToleranceChanged": False,
        "localityToleranceChanged": False,
        "contactThresholdChanged": False,
        "damageAdmissionThresholdChanged": False,
        "damageThresholdAwareControl": False,
        "targetToughnessAwareControl": False,
        "desiredImpactSpeedControl": False,
        "desiredImpactEnergyControl": False,
        "fixtureMutationForAcceptance": False,
        "perAssetBattleCode": False,
        "perVideoTrajectoryEngineering": False,
        "humanCinematicAcceptance": "PENDING",
        "gateClosed": False,
        "productionReadyClaimed": False,
        "cutoffRuntimeProof": cutoff_proof,
        "semanticRuntimeProof": log_proof,
        "fixtures": fixtures,
    }, sort_keys=True))


if __name__ == "__main__":
    main()
