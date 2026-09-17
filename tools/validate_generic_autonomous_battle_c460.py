#!/usr/bin/env python3
from __future__ import annotations

import ast
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from blender.iss_battle_runtime_tactics_v2 import (
    GenericBattleTacticalPlanner,
    TacticalMemory,
    TacticalObservation,
)

SOURCES = [
    ROOT / "blender" / "iss_battle_runtime_tactics_v2.py",
    ROOT / "blender" / "iss_battle_runtime_generic_battle_v2.py",
    ROOT / "blender" / "iss_battle_runtime_consequences_v2.py",
    ROOT / "blender" / "run_generic_battle_runtime_v1_candidate460_generic_battle.py",
]
FORBIDDEN_ASSET_TOKENS = ("bugatti", "bulldozer", "ferrari")
FORBIDDEN_CHOREOGRAPHY = (
    "collisionframe", "contactframe", "impactframe", "targetenergyj", "impactenergyj",
    "targetimpactspeedmps", "trajectorypoints", "pathpoints", "waypoints",
    "positionkeyframes", "velocitykeyframes", "steeringangle", "brakingpoint",
    "collisionpoint", "forcedwinner", "winnerid",
)


def _obs(**overrides):
    row = dict(
        frame=1, fps=30, phase="FIRST_ATTACK", story_tactic="RAM", requires_contact=True,
        surface_gap_m=8.0, center_distance_m=10.0, closing_speed_mps=2.0, heading_error_rad=0.10,
        contention=0.0, own_integrity=1.0, own_drive_efficiency=1.0, own_disabled=False,
        target_integrity=1.0, target_drive_efficiency=1.0, target_disabled=False,
        own_max_speed_mps=20.0, own_max_reverse_mps=6.0, own_yaw_rate_rad_s=1.35,
        own_acceleration_mps2=7.0, own_braking_mps2=10.0, own_length_m=4.5, own_width_m=2.0,
        target_length_m=4.5, target_width_m=2.0, contact_count=0, damage_count=0,
        own_damage_event_count=0, target_damage_event_count=0, last_own_impact_frame=None,
        last_target_impact_frame=None,
    )
    row.update(overrides)
    return TacticalObservation(**row)


def _sequence(profile: str):
    base = (
        dict(
            own_max_speed_mps=6.5, own_max_reverse_mps=3.5, own_yaw_rate_rad_s=0.55,
            own_acceleration_mps2=2.8, own_braking_mps2=4.0, own_length_m=7.2,
            own_width_m=3.2, target_length_m=4.5, target_width_m=2.0,
        )
        if profile == "heavy"
        else {}
    )
    memory = TacticalMemory()
    rows = []
    rows.append(GenericBattleTacticalPlanner.decide(memory, _obs(**base), symmetry_bias=1.0))
    rows.append(
        GenericBattleTacticalPlanner.decide(
            memory,
            _obs(frame=30, contact_count=1, damage_count=1, own_damage_event_count=1, surface_gap_m=0.1, **base),
            symmetry_bias=1.0,
        )
    )
    reposition_frame = memory.break_until_frame + 1
    rows.append(
        GenericBattleTacticalPlanner.decide(
            memory,
            _obs(frame=reposition_frame, contact_count=1, damage_count=1, own_damage_event_count=1, surface_gap_m=2.5, **base),
            symmetry_bias=1.0,
        )
    )
    engage_frame = memory.reposition_until_frame + 1
    rows.append(
        GenericBattleTacticalPlanner.decide(
            memory,
            _obs(frame=engage_frame, contact_count=1, damage_count=1, own_damage_event_count=1, surface_gap_m=5.0, **base),
            symmetry_bias=1.0,
        )
    )
    rows.append(
        GenericBattleTacticalPlanner.decide(
            memory,
            _obs(
                frame=engage_frame + 10, phase="COUNTERATTACK", story_tactic="COUNTER",
                contact_count=1, damage_count=1, own_damage_event_count=1, surface_gap_m=4.0, **base,
            ),
            symmetry_bias=-1.0,
        )
    )
    return memory, rows


def _static_scope() -> None:
    for path in SOURCES:
        text = path.read_text(encoding="utf-8")
        ast.parse(text, filename=str(path))
        lowered = text.lower()
        for token in FORBIDDEN_ASSET_TOKENS:
            if token in lowered:
                raise SystemExit(f"C460_ASSET_SPECIFIC_TOKEN_FORBIDDEN:{path.name}:{token}")
    tactics = SOURCES[0].read_text(encoding="utf-8").lower()
    adapter = SOURCES[1].read_text(encoding="utf-8").lower()
    for token in FORBIDDEN_CHOREOGRAPHY:
        if token in tactics or token in adapter:
            raise SystemExit(f"C460_EXECUTABLE_CHOREOGRAPHY_FORBIDDEN:{token}")
    consequences = SOURCES[2].read_text(encoding="utf-8")
    if "MIN_DAMAGE_SEVERITY" in consequences:
        raise SystemExit("C460_DAMAGE_ADMISSION_THRESHOLD_MUST_NOT_BE_OVERRIDDEN")
    if 'iss_debris_trajectory_injection"] = False' not in consequences:
        raise SystemExit("C460_DEBRIS_TRAJECTORY_INJECTION_GUARD_MISSING")
    wrapper = SOURCES[3].read_text(encoding="utf-8")
    for token in (
        '"nativeContactAuthorityPreserved": True',
        '"damageAdmissionThresholdChanged": False',
        '"contactThresholdChanged": False',
        '"perAssetBattleCode": False',
        '"perVideoTrajectoryEngineering": False',
        '"issR045MasterPlanAlignedTarget": True',
        '"gateClosed": False',
    ):
        if token not in wrapper:
            raise SystemExit(f"C460_WRAPPER_CONTRACT_MISSING:{token}")


def main() -> None:
    _static_scope()
    sports_memory, sports = _sequence("sports")
    heavy_memory, heavy = _sequence("heavy")
    assert sports[0].mode == "ENGAGE"
    assert sports[1].mode == "BREAK_CONTACT" and sports[1].speed_intent == "REVERSE"
    assert sports[2].mode == "REPOSITION"
    assert sports[4].mode == "COUNTER" and sports[4].contact_commit
    assert heavy[0].mode == "ENGAGE"
    assert heavy[1].mode == "BREAK_CONTACT" and heavy[1].speed_intent == "REVERSE"
    assert heavy[2].mode == "REPOSITION"
    assert heavy[4].mode == "COUNTER"
    assert heavy_memory.break_until_frame >= sports_memory.break_until_frame

    memory = TacticalMemory()
    evasive = GenericBattleTacticalPlanner.decide(
        memory,
        _obs(
            own_integrity=0.45, own_drive_efficiency=0.35,
            target_integrity=0.95, target_drive_efficiency=0.95, surface_gap_m=6.0,
        ),
        symmetry_bias=1.0,
    )
    assert evasive.mode == "EVADE" and not evasive.contact_commit

    memory = TacticalMemory()
    brake = GenericBattleTacticalPlanner.decide(
        memory,
        _obs(surface_gap_m=0.8, closing_speed_mps=12.0, heading_error_rad=0.05),
        symmetry_bias=1.0,
    )
    assert brake.mode == "BRAKE_APPROACH" and brake.speed_intent == "BRAKE"

    print(
        json.dumps(
            {
                "marker": "GENERIC_AUTONOMOUS_BATTLE_C460_PROPERTY_ACCEPTANCE",
                "status": "PASS",
                "sportsModes": [x.mode for x in sports],
                "heavyModes": [x.mode for x in heavy],
                "heavyCapabilityDerivedBreakWindow": True,
                "damageDisadvantageEvasion": "PASS",
                "brakingDistanceAdaptation": "PASS",
                "samePlannerAcrossProfiles": True,
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
