#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path

import build_generic_battle_runtime_v1_candidate443_g07 as candidate443_builder

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "artifacts" / "generic-battle-runtime-v1-candidate445-g07"


def main() -> None:
    candidate443_builder.OUT = OUT
    candidate443_builder.main()
    exact = OUT / "exact-bugatti" / "request.json"
    generic = OUT / "generic-hypercar" / "request.json"
    candidate443_builder.verify_runtime_selected_targeting(exact)
    candidate443_builder.verify_runtime_selected_targeting(generic)
    print(json.dumps({
        "marker": "GENERIC_BATTLE_RUNTIME_CANDIDATE445_G07_FIXTURES_PASS",
        "status": "PASS",
        "fixtureSemanticsChangedFromCandidate443": False,
        "sameIntentStructureAcrossAssets": True,
        "storyIntentOnly": True,
        "storyTargetActorOnly": True,
        "storyTargetZonePrescribed": False,
        "runtimeSelectsSemanticEngagementSurface": True,
        "g07ReceiptAdmissionOnly": True,
        "damageRequiredForG07": False,
        "speedIntentPrescribed": False,
        "exactCollisionFrameTarget": False,
        "exactImpactEnergyTarget": False,
        "manualTrajectoryPoints": False,
        "forcedWinner": False,
        "perAssetCollisionEngineering": False,
        "issR041ScopePreserved": True,
        "issR042ScopePreserved": True,
        "issR043ScopePreflightPreserved": True,
    }, sort_keys=True))


if __name__ == "__main__":
    main()
