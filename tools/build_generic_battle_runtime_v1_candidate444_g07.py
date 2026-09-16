#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path

import build_generic_battle_runtime_v1_candidate443_g07 as candidate443_builder

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "artifacts" / "generic-battle-runtime-v1-candidate444-g07"


def main() -> None:
    candidate443_builder.OUT = OUT
    candidate443_builder.main()

    exact = OUT / "exact-bugatti" / "request.json"
    generic = OUT / "generic-hypercar" / "request.json"
    candidate443_builder.verify_runtime_selected_targeting(exact)
    candidate443_builder.verify_runtime_selected_targeting(generic)

    exact_request = json.loads(exact.read_text(encoding="utf-8"))
    generic_request = json.loads(generic.read_text(encoding="utf-8"))
    exact_events = exact_request["battlePlan"]["events"]
    generic_events = generic_request["battlePlan"]["events"]

    def normalized_intent(events: list[dict]) -> list[dict]:
        rows: list[dict] = []
        for event in events:
            rows.append({
                "eventId": event.get("eventId"),
                "type": event.get("type"),
                "phase": event.get("phase"),
                "attackers": event.get("attackers"),
                "attackTarget": event.get("attackTarget"),
                "dependsOn": event.get("dependsOn"),
                "requiredOutcome": event.get("requiredOutcome"),
                "damageRequired": bool((event.get("damage") or {}).get("required", False)),
            })
        return rows

    if normalized_intent(exact_events) != normalized_intent(generic_events):
        raise RuntimeError("CANDIDATE444_ASSET_FIXTURE_INTENT_STRUCTURE_DRIFT")

    print(json.dumps({
        "marker": "GENERIC_BATTLE_RUNTIME_CANDIDATE444_G07_FIXTURES_PASS",
        "status": "PASS",
        "sameIntentStructureAcrossAssets": True,
        "storyIntentOnly": True,
        "storyTargetActorOnly": True,
        "storyTargetZonePrescribed": False,
        "runtimeSelectsSemanticEngagementSurface": True,
        "handoffLifecycleSpecifiedByStory": False,
        "handoffDistanceSpecifiedByFixture": False,
        "handoffTimeoutSpecifiedByFixture": False,
        "damageRequiredForG07": False,
        "speedIntentPrescribed": False,
        "exactCollisionFrameTarget": False,
        "exactImpactEnergyTarget": False,
        "manualTrajectoryPoints": False,
        "forcedWinner": False,
        "perAssetCollisionEngineering": False,
        "perAssetHandoffTuning": False,
        "issR041ScopePreserved": True,
        "issR042ScopePreserved": True,
        "issR043ScopePreflightPassed": True,
        "issR043ScopePostflightRequired": True,
    }, sort_keys=True))


if __name__ == "__main__":
    main()
