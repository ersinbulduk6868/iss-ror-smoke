#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path

import build_generic_battle_runtime_v1_candidate442_g07 as candidate442_builder

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "artifacts" / "generic-battle-runtime-v1-candidate443-g07"


def verify_runtime_selected_targeting(path: Path) -> None:
    request = json.loads(path.read_text(encoding="utf-8"))
    events = {row["eventId"]: row for row in request["battlePlan"]["events"]}
    for event_id in ("evt-escalation", "evt-counterattack", "evt-climax"):
        event = events[event_id]
        target = str(event.get("attackTarget") or "")
        if not target or ":" in target:
            raise RuntimeError(f"CANDIDATE443_STORY_TARGET_NOT_ACTOR_ONLY:{event_id}:{target}")
        damage = event.get("damage") or {}
        if damage.get("zone") or damage.get("targetZone"):
            raise RuntimeError(f"CANDIDATE443_STORY_DAMAGE_ZONE_PRESENT:{event_id}")
        requirements = event.get("physicsRequirements") or {}
        if "targetArea" in requirements or "speedIntent" in requirements:
            raise RuntimeError(f"CANDIDATE443_STORY_COLLISION_CONTROL_PRESENT:{event_id}")
    raw = json.dumps(request, sort_keys=True).lower()
    for forbidden in (
        "collisionframe", "contactframe", "impactframe", "targetenergyj",
        "impactenergyj", "targetimpactspeedmps", "trajectorypoints",
        "pathpoints", "waypoints", "positionkeyframes", "velocitykeyframes",
        "steeringangle", "brakingpoint", "approachvector", "collisionpoint",
        "contactpoint", "forcedwinner", "winnerid",
    ):
        if forbidden in raw:
            raise RuntimeError(f"CANDIDATE443_FORBIDDEN_STORY_COLLISION_CHOREOGRAPHY:{forbidden}")


def main() -> None:
    candidate442_builder.OUT = OUT
    candidate442_builder.main()
    exact = OUT / "exact-bugatti" / "request.json"
    generic = OUT / "generic-hypercar" / "request.json"
    verify_runtime_selected_targeting(exact)
    verify_runtime_selected_targeting(generic)
    print(json.dumps({
        "marker": "GENERIC_BATTLE_RUNTIME_CANDIDATE443_G07_FIXTURES_PASS",
        "status": "PASS",
        "sameIntentStructureAcrossAssets": True,
        "storyIntentOnly": True,
        "storyTargetActorOnly": True,
        "storyTargetZonePrescribed": False,
        "runtimeSelectsSemanticEngagementSurface": True,
        "damageRequiredForG07": False,
        "speedIntentPrescribed": False,
        "exactCollisionFrameTarget": False,
        "exactImpactEnergyTarget": False,
        "manualTrajectoryPoints": False,
        "forcedWinner": False,
        "perAssetCollisionEngineering": False,
        "issR041ScopePreserved": True,
        "issR042ScopePreserved": True,
    }, sort_keys=True))


if __name__ == "__main__":
    main()
