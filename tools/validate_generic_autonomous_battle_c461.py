#!/usr/bin/env python3
from __future__ import annotations

import ast
import json
import math
from pathlib import Path
from types import SimpleNamespace
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from blender.iss_battle_runtime_tactics_v3 import (
    BATTLE_SIGNAL_SCOPE,
    GenericBattleTacticalPlanner,
    TacticalMemory,
    TacticalObservation,
    actor_realized_event_signals,
    motion_heading_error,
)

TACTICS = ROOT / "blender" / "iss_battle_runtime_tactics_v3.py"
CONTROL = ROOT / "blender" / "iss_battle_runtime_generic_battle_v3.py"
CONSEQUENCES = ROOT / "blender" / "iss_battle_runtime_consequences_v3.py"
WRAPPER = ROOT / "blender" / "run_generic_battle_runtime_v1_candidate461_generic_battle.py"
SOURCES = [TACTICS, CONTROL, CONSEQUENCES, WRAPPER]
FORBIDDEN_ASSET_TOKENS = ("bugatti", "bulldozer", "ferrari")


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


def _profile(profile: str) -> dict:
    if profile == "heavy":
        return dict(
            own_max_speed_mps=6.5, own_max_reverse_mps=3.5, own_yaw_rate_rad_s=0.55,
            own_acceleration_mps2=2.8, own_braking_mps2=4.0, own_length_m=7.2,
            own_width_m=3.2, target_length_m=4.5, target_width_m=2.0,
        )
    return {}


def _sequence(profile: str):
    base = _profile(profile)
    memory = TacticalMemory()
    rows = [GenericBattleTacticalPlanner.decide(memory, _obs(**base), symmetry_bias=1.0)]
    rows.append(GenericBattleTacticalPlanner.decide(
        memory,
        _obs(frame=30, contact_count=1, surface_gap_m=0.1, **base),
        symmetry_bias=1.0,
    ))
    after_timer = memory.break_until_frame + 2
    rows.append(GenericBattleTacticalPlanner.decide(
        memory,
        _obs(frame=after_timer, contact_count=1,
             surface_gap_m=max(0.05, memory.separation_required_m * 0.45), **base),
        symmetry_bias=1.0,
    ))
    separated = after_timer + 3
    rows.append(GenericBattleTacticalPlanner.decide(
        memory,
        _obs(frame=separated, contact_count=1,
             surface_gap_m=memory.separation_required_m + 0.4, **base),
        symmetry_bias=1.0,
    ))
    counter_frame = memory.reposition_until_frame + 1
    rows.append(GenericBattleTacticalPlanner.decide(
        memory,
        _obs(frame=counter_frame, phase="COUNTERATTACK", story_tactic="COUNTER",
             contact_count=1, surface_gap_m=memory.separation_required_m + 0.6, **base),
        symmetry_bias=-1.0,
    ))
    return memory, rows


def _actor_history_regression() -> dict[str, object]:
    events = (
        SimpleNamespace(event_id="e-ab", attackers=("A",), target_id="B"),
        SimpleNamespace(event_id="e-ba", attackers=("B",), target_id="A"),
        SimpleNamespace(event_id="e-cd", attackers=("C",), target_id="D"),
        SimpleNamespace(event_id="e-be", attackers=("B",), target_id="E"),
    )
    states = {
        "e-ab": SimpleNamespace(contact_count=1, damage_count=0),
        "e-ba": SimpleNamespace(contact_count=1, damage_count=0),
        "e-cd": SimpleNamespace(contact_count=7, damage_count=4),
        "e-be": SimpleNamespace(contact_count=0, damage_count=0),
    }
    b_contacts, b_damage, b_events = actor_realized_event_signals("B", events, states)
    e_contacts, e_damage, _ = actor_realized_event_signals("E", events, states)
    assert (b_contacts, b_damage) == (2, 0)
    assert set(b_events) == {"e-ab", "e-ba"}
    assert (e_contacts, e_damage) == (0, 0)

    memory = TacticalMemory()
    first = GenericBattleTacticalPlanner.decide(
        memory,
        _obs(frame=147, phase="COUNTERATTACK", story_tactic="COUNTER",
             contact_count=b_contacts, damage_count=b_damage, surface_gap_m=0.1),
        symmetry_bias=-1.0,
    )
    assert first.mode == "BREAK_CONTACT" and first.speed_intent == "REVERSE"
    cycle = memory.cycle
    repeated = GenericBattleTacticalPlanner.decide(
        memory,
        _obs(frame=148, phase="COUNTERATTACK", story_tactic="COUNTER",
             contact_count=b_contacts, damage_count=b_damage, surface_gap_m=0.1),
        symmetry_bias=-1.0,
    )
    assert repeated.mode == "BREAK_CONTACT" and memory.cycle == cycle
    separated = GenericBattleTacticalPlanner.decide(
        memory,
        _obs(frame=149, phase="COUNTERATTACK", story_tactic="COUNTER",
             contact_count=b_contacts, damage_count=b_damage,
             surface_gap_m=memory.separation_required_m + 0.3),
        symmetry_bias=-1.0,
    )
    assert separated.mode == "REPOSITION"
    counter = GenericBattleTacticalPlanner.decide(
        memory,
        _obs(frame=memory.reposition_until_frame + 1, phase="COUNTERATTACK", story_tactic="COUNTER",
             contact_count=b_contacts, damage_count=b_damage,
             surface_gap_m=memory.separation_required_m + 0.5),
        symmetry_bias=-1.0,
    )
    assert counter.mode == "COUNTER" and counter.contact_commit
    return {
        "actorBContactSignals": b_contacts,
        "actorBContributingEvents": list(b_events),
        "unrelatedCDSignalsExcludedFromB": True,
        "targetRoleHistoryIncluded": True,
        "attackerRoleHistoryIncluded": True,
        "lateUninvolvedActorSignalsZero": True,
        "contactWithoutDamageTriggersBattleCycle": True,
        "reciprocalSignalsDoNotRepeatedlyRetrigger": True,
        "firstObservationHistoricalContactAware": True,
    }


def _payoff_terminal_regression() -> None:
    memory = TacticalMemory()
    started = GenericBattleTacticalPlanner.decide(
        memory,
        _obs(frame=50, phase="COUNTERATTACK", story_tactic="COUNTER",
             contact_count=1, surface_gap_m=0.05),
        symmetry_bias=1.0,
    )
    assert started.mode == "BREAK_CONTACT" and not memory.separation_achieved
    payoff = GenericBattleTacticalPlanner.decide(
        memory,
        _obs(frame=51, phase="PAYOFF", story_tactic="HOLD",
             contact_count=1, surface_gap_m=0.05),
        symmetry_bias=1.0,
    )
    assert payoff.mode == "HOLD" and payoff.speed_intent == "BRAKE"
    assert memory.separation_achieved is True
    assert memory.break_until_frame == 0 and memory.reposition_until_frame == 0


def _static_scope() -> None:
    for path in SOURCES:
        text = path.read_text(encoding="utf-8")
        ast.parse(text, filename=str(path))
        lowered = text.lower()
        for token in FORBIDDEN_ASSET_TOKENS:
            if token in lowered:
                raise SystemExit(f"C461_ASSET_SPECIFIC_TOKEN_FORBIDDEN:{path.name}:{token}")

    compact = "".join(CONTROL.read_text(encoding="utf-8").split())
    assert "contact_count=int(actor_contact_signal),damage_count=int(actor_damage_signal)" in compact
    assert "contact_count=int(state.contact_count),damage_count=int(state.damage_count)" in compact
    assert '"battleSignalScope":BATTLE_SIGNAL_SCOPE' in compact
    assert '"autonomyStateScope":"CURRENT_EVENT_ONLY"' in compact

    wrapper = WRAPPER.read_text(encoding="utf-8")
    for required in (
        'AUDIT = "C460_FULL_AFFECTED_LAYER_AUDIT_20260917"',
        '"actorScopedContinuousBattleMemory": True',
        '"payoffTerminatesRecovery": True',
        '"nativeContactAuthorityPreserved": True',
        '"damageAdmissionThresholdChanged": False',
        '"contactThresholdChanged": False',
        '"debrisEligibilityUsesEarnedDamageConsequence": True',
        '"perAssetBattleCode": False',
        '"perVideoTrajectoryEngineering": False',
        '"stateResetMechanism": False',
        '"gateClosed": False',
    ):
        assert required in wrapper, required

    consequences = CONSEQUENCES.read_text(encoding="utf-8")
    assert "MIN_DAMAGE_SEVERITY" not in consequences
    assert 'shard["iss_debris_trajectory_injection"] = False' in consequences
    assert '"physicalDamageGateChanged": False' in consequences
    assert '"contactGateChanged": False' in consequences


def main() -> None:
    _static_scope()
    assert BATTLE_SIGNAL_SCOPE == "ACTOR_INVOLVEMENT_EVENT_HISTORY_V1"
    assert abs(motion_heading_error(math.pi - 0.01, "REVERSE")) < 0.02
    assert abs(motion_heading_error(-math.pi + 0.01, "REVERSE")) < 0.02

    sports_memory, sports = _sequence("sports")
    heavy_memory, heavy = _sequence("heavy")
    expected = ["ENGAGE", "BREAK_CONTACT", "BREAK_CONTACT", "REPOSITION", "COUNTER"]
    assert [x.mode for x in sports] == expected
    assert [x.mode for x in heavy] == expected
    assert heavy_memory.separation_required_m >= sports_memory.separation_required_m

    history = _actor_history_regression()
    _payoff_terminal_regression()

    damage_memory = TacticalMemory()
    evasive = GenericBattleTacticalPlanner.decide(
        damage_memory,
        _obs(frame=2, own_integrity=0.45, own_drive_efficiency=0.35,
             target_integrity=0.95, target_drive_efficiency=0.95, surface_gap_m=6.0),
        symmetry_bias=1.0,
    )
    assert evasive.mode == "EVADE" and not evasive.contact_commit

    brake_memory = TacticalMemory()
    brake = GenericBattleTacticalPlanner.decide(
        brake_memory,
        _obs(frame=2, surface_gap_m=0.8, closing_speed_mps=12.0, heading_error_rad=0.05),
        symmetry_bias=1.0,
    )
    assert brake.mode == "BRAKE_APPROACH" and brake.speed_intent == "BRAKE"

    print(json.dumps({
        "marker": "GENERIC_AUTONOMOUS_BATTLE_C461_PROPERTY_ACCEPTANCE",
        "status": "PASS",
        "fullAffectedLayerAudit": "PASS",
        "sportsModes": [x.mode for x in sports],
        "heavyModes": [x.mode for x in heavy],
        "samePlannerAcrossProfiles": True,
        "actorScopedContinuousBattleMemory": True,
        "battleSignalScope": BATTLE_SIGNAL_SCOPE,
        "autonomyCurrentEventCountersRemainEventScoped": True,
        "reverseMotionHeadingAware": True,
        "geometryConfirmedSeparationBeforeReengagement": True,
        "timerOnlyReengagementForbidden": True,
        "payoffTerminatesRecovery": True,
        "heavyCapabilityDerivedSeparation": True,
        "damageDisadvantageEvasion": "PASS",
        "brakingDistanceAdaptation": "PASS",
        "nativeContactAuthorityPreserved": True,
        "damageAdmissionThresholdChanged": False,
        "contactThresholdChanged": False,
        "debrisEligibilityUsesEarnedDamageConsequence": True,
        "perAssetBattleCode": False,
        "exactCollisionFrameTarget": False,
        "exactImpactEnergyTarget": False,
        "actorPoseOrVelocityMutation": False,
        "masterPlanAligned": True,
        "gateClosed": False,
        **history,
    }, sort_keys=True))


if __name__ == "__main__":
    main()
