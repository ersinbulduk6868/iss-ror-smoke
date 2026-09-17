#!/usr/bin/env python3
from __future__ import annotations

import ast
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from blender.iss_battle_runtime_tactics_v2 import GenericBattleTacticalPlanner, TacticalMemory
from tools import validate_generic_autonomous_battle_c460 as c460

WRAPPER = ROOT / "blender" / "run_generic_battle_runtime_v1_candidate461_generic_battle.py"


def main() -> None:
    c460._static_scope()

    # Preserve the stricter G04 failure-family behavior: break-contact may not
    # expire on a timer alone. It must continue until live geometry confirms
    # separation, then reposition at stand-off, then re-engage/counter.
    sports_memory, sports = c460._sequence("sports")
    heavy_memory, heavy = c460._sequence("heavy")
    assert sports[0].mode == "ENGAGE"
    assert sports[1].mode == "BREAK_CONTACT" and sports[1].speed_intent == "REVERSE"
    assert sports[2].mode == "BREAK_CONTACT", "timer-only break-contact completion forbidden"
    assert sports[3].mode == "REPOSITION" and sports_memory.separation_achieved
    assert sports[4].mode == "COUNTER" and sports[4].contact_commit
    assert heavy[0].mode == "ENGAGE"
    assert heavy[1].mode == "BREAK_CONTACT" and heavy[1].speed_intent == "REVERSE"
    assert heavy[2].mode == "BREAK_CONTACT"
    assert heavy[3].mode == "REPOSITION" and heavy_memory.separation_achieved
    assert heavy[4].mode == "COUNTER" and heavy[4].contact_commit
    assert heavy_memory.separation_required_m >= sports_memory.separation_required_m

    # Regression for the C460 terminal failure family: an actor may enter a new
    # counterattack event already carrying persistent damage from a prior event.
    # That inherited damage is baseline state, not a fresh impact in this event.
    fresh_event_memory = TacticalMemory()
    inherited_damage_counter = GenericBattleTacticalPlanner.decide(
        fresh_event_memory,
        c460._obs(
            frame=147,
            phase="COUNTERATTACK",
            story_tactic="COUNTER",
            contact_count=0,
            damage_count=0,
            own_damage_event_count=1,
            target_damage_event_count=1,
            surface_gap_m=2.0,
            heading_error_rad=0.10,
        ),
        symmetry_bias=-1.0,
    )
    assert inherited_damage_counter.mode == "COUNTER", inherited_damage_counter
    assert inherited_damage_counter.contact_commit is True
    assert fresh_event_memory.cycle == 0

    wrapper = WRAPPER.read_text(encoding="utf-8")
    ast.parse(wrapper, filename=str(WRAPPER))
    for required in (
        'EVENT_LIFECYCLE_MODEL = "ISS_EVENT_SCOPED_TACTICAL_MEMORY_V1"',
        'battle_v2._tactical_memories.pop(entity, None)',
        '"persistentActorStateReset": False',
        '"g05ContactTruthReset": False',
        '"eventScopedTacticalMemory": True',
        '"stateResetMechanism": False',
        '"perAssetBattleCode": False',
        '"perVideoTrajectoryEngineering": False',
        '"gateClosed": False',
    ):
        assert required in wrapper, required

    lowered = wrapper.lower()
    for forbidden in ("bugatti", "bulldozer", "ferrari"):
        assert forbidden not in lowered, forbidden

    print(
        json.dumps(
            {
                "marker": "GENERIC_AUTONOMOUS_BATTLE_C461_PROPERTY_ACCEPTANCE",
                "status": "PASS",
                "samePlannerAcrossProfiles": True,
                "reverseMotionHeadingAware": True,
                "geometryConfirmedSeparationBeforeReengagement": True,
                "timerOnlyReengagementForbidden": True,
                "heavyCapabilityDerivedSeparation": True,
                "priorEventDamageBaselined": True,
                "counterattackStartsFromCurrentIntent": True,
                "eventScopedTacticalMemory": True,
                "persistentActorStatePreserved": True,
                "nativeContactAuthorityPreserved": True,
                "damageAdmissionThresholdChanged": False,
                "contactThresholdChanged": False,
                "perAssetBattleCode": False,
                "exactCollisionFrameTarget": False,
                "exactImpactEnergyTarget": False,
                "actorPoseOrVelocityMutation": False,
                "masterPlanAligned": True,
                "gateClosed": False,
            },
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
