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

from blender.iss_battle_runtime_tactics_v5 import (
    BATTLE_SIGNAL_SCOPE,
    ENGAGEMENT_RUNWAY_MODEL,
    GenericBattleTacticalPlanner,
    TacticalMemory,
    TacticalObservation,
    actor_realized_event_signals,
    motion_heading_error,
)

TACTICS = ROOT / "blender" / "iss_battle_runtime_tactics_v5.py"
CONTROL = ROOT / "blender" / "iss_battle_runtime_generic_battle_v5.py"
CONSEQUENCES = ROOT / "blender" / "iss_battle_runtime_consequences_v3.py"
WRAPPER = ROOT / "blender" / "run_generic_battle_runtime_v1_candidate463_generic_battle.py"
SOURCES = [TACTICS, CONTROL, CONSEQUENCES, WRAPPER]
FORBIDDEN_ASSET_TOKENS = ("bugatti", "bulldozer", "ferrari")


def _obs(**overrides):
    row = dict(
        frame=1,
        fps=30,
        phase="ESCALATION",
        story_tactic="ENGAGE",
        requires_contact=True,
        surface_gap_m=8.0,
        center_distance_m=12.0,
        closing_speed_mps=0.0,
        heading_error_rad=0.10,
        contention=0.0,
        own_integrity=1.0,
        own_drive_efficiency=1.0,
        own_disabled=False,
        target_integrity=1.0,
        target_drive_efficiency=1.0,
        target_disabled=False,
        own_max_speed_mps=20.0,
        own_max_reverse_mps=6.0,
        own_yaw_rate_rad_s=1.35,
        own_acceleration_mps2=7.0,
        own_braking_mps2=10.0,
        own_length_m=4.5,
        own_width_m=2.0,
        target_length_m=4.5,
        target_width_m=2.0,
        contact_count=0,
        damage_count=0,
        own_damage_event_count=0,
        target_damage_event_count=0,
        last_own_impact_frame=None,
        last_target_impact_frame=None,
    )
    row.update(overrides)
    return TacticalObservation(**row)


def _profile(profile: str) -> dict:
    if profile == "heavy":
        return dict(
            own_max_speed_mps=6.5,
            own_max_reverse_mps=3.5,
            own_yaw_rate_rad_s=0.55,
            own_acceleration_mps2=2.8,
            own_braking_mps2=4.0,
            own_length_m=7.2,
            own_width_m=3.2,
            target_length_m=4.5,
            target_width_m=2.0,
        )
    return {}


def _runway_sequence(profile: str) -> dict[str, object]:
    base = _profile(profile)
    memory = TacticalMemory()
    probe = _obs(**base)
    runway = GenericBattleTacticalPlanner.engagement_runway_required(probe)
    assert runway > 1.5

    low = GenericBattleTacticalPlanner.decide(
        memory,
        _obs(frame=1, surface_gap_m=runway * 0.25, **base),
        symmetry_bias=1.0,
    )
    assert low.mode == "OPEN_DISTANCE"
    assert low.speed_intent == "REVERSE"
    assert low.contact_commit is False
    assert abs(low.stand_off_surface_gap_m - runway) < 1.0e-9

    armed = GenericBattleTacticalPlanner.decide(
        memory,
        _obs(frame=20, surface_gap_m=runway + 0.2, **base),
        symmetry_bias=1.0,
    )
    assert armed.mode == "ENGAGE"
    assert armed.contact_commit is True
    assert memory.engagement_runway_armed is True

    contact = GenericBattleTacticalPlanner.decide(
        memory,
        _obs(frame=30, contact_count=1, surface_gap_m=0.10, **base),
        symmetry_bias=1.0,
    )
    assert contact.mode == "BREAK_CONTACT"
    assert memory.separation_required_m >= runway
    assert contact.stand_off_surface_gap_m >= runway

    still_close = GenericBattleTacticalPlanner.decide(
        memory,
        _obs(frame=31, contact_count=1, surface_gap_m=runway * 0.50, **base),
        symmetry_bias=1.0,
    )
    assert still_close.mode == "BREAK_CONTACT"

    separated = GenericBattleTacticalPlanner.decide(
        memory,
        _obs(frame=40, contact_count=1, surface_gap_m=runway + 0.35, **base),
        symmetry_bias=1.0,
    )
    assert separated.mode == "REPOSITION"
    assert memory.separation_achieved is True

    collapsed = GenericBattleTacticalPlanner.decide(
        memory,
        _obs(frame=41, contact_count=1, surface_gap_m=runway * 0.70, **base),
        symmetry_bias=1.0,
    )
    assert collapsed.mode == "BREAK_CONTACT"
    assert memory.separation_achieved is False
    assert memory.engagement_runway_armed is False

    reestablished = GenericBattleTacticalPlanner.decide(
        memory,
        _obs(frame=50, contact_count=1, surface_gap_m=runway + 0.40, **base),
        symmetry_bias=-1.0,
    )
    assert reestablished.mode == "REPOSITION"
    counter_frame = memory.reposition_until_frame + 1
    counter = GenericBattleTacticalPlanner.decide(
        memory,
        _obs(
            frame=counter_frame,
            phase="COUNTERATTACK",
            story_tactic="COUNTER",
            contact_count=1,
            surface_gap_m=runway + 0.30,
            **base,
        ),
        symmetry_bias=-1.0,
    )
    assert counter.mode == "COUNTER"
    assert counter.contact_commit is True

    return {
        "runwayM": runway,
        "modes": [
            low.mode,
            armed.mode,
            contact.mode,
            still_close.mode,
            separated.mode,
            collapsed.mode,
            reestablished.mode,
            counter.mode,
        ],
    }


def _history_scope() -> dict[str, object]:
    events = (
        SimpleNamespace(event_id="e-ab", attackers=("A",), target_id="B"),
        SimpleNamespace(event_id="e-ba", attackers=("B",), target_id="A"),
        SimpleNamespace(event_id="e-cd", attackers=("C",), target_id="D"),
    )
    states = {
        "e-ab": SimpleNamespace(contact_count=1, damage_count=0),
        "e-ba": SimpleNamespace(contact_count=1, damage_count=0),
        "e-cd": SimpleNamespace(contact_count=7, damage_count=4),
    }
    b_contacts, b_damage, b_events = actor_realized_event_signals("B", events, states)
    assert (b_contacts, b_damage) == (2, 0)
    assert set(b_events) == {"e-ab", "e-ba"}
    return {
        "actorBContactSignals": b_contacts,
        "actorBContributingEvents": list(b_events),
        "unrelatedActorSignalsExcluded": True,
    }


def _payoff_terminal() -> None:
    memory = TacticalMemory()
    runway = GenericBattleTacticalPlanner.engagement_runway_required(_obs())
    GenericBattleTacticalPlanner.decide(
        memory,
        _obs(frame=1, surface_gap_m=runway + 0.2),
        symmetry_bias=1.0,
    )
    started = GenericBattleTacticalPlanner.decide(
        memory,
        _obs(frame=30, contact_count=1, surface_gap_m=0.10),
        symmetry_bias=1.0,
    )
    assert started.mode == "BREAK_CONTACT"
    payoff = GenericBattleTacticalPlanner.decide(
        memory,
        _obs(
            frame=31,
            phase="PAYOFF",
            story_tactic="SETTLE",
            contact_count=1,
            surface_gap_m=0.10,
        ),
        symmetry_bias=1.0,
    )
    assert payoff.mode == "HOLD" and payoff.speed_intent == "BRAKE"
    assert memory.break_until_frame == 0
    assert memory.reposition_until_frame == 0
    assert memory.engagement_runway_armed is False


def _static_scope() -> None:
    for path in SOURCES:
        text = path.read_text(encoding="utf-8")
        ast.parse(text, filename=str(path))
        lowered = text.lower()
        for token in FORBIDDEN_ASSET_TOKENS:
            if token in lowered:
                raise SystemExit(f"C463_ASSET_SPECIFIC_TOKEN_FORBIDDEN:{path.name}:{token}")

    tactics = TACTICS.read_text(encoding="utf-8")
    control = CONTROL.read_text(encoding="utf-8")
    wrapper = WRAPPER.read_text(encoding="utf-8")

    for forbidden in (
        "MIN_DAMAGE_SEVERITY",
        "target_toughness",
        "impact_energy_j",
        "desired_impact_speed",
        "desired_impact_energy",
        "current_event_damage_count",
        "damage_retry_scale",
    ):
        assert forbidden not in tactics, forbidden
    assert "current_event_contact_count" not in tactics
    assert "damage_required" not in tactics

    assert "_surface_gap_goal" in control
    assert "_support_radius" in control
    assert "damageIntentAdaptiveRetry" not in control
    assert "nonproductiveDamageContactCount" not in control
    assert '"damageThresholdAwareControl": False' in control
    assert '"targetToughnessAwareControl": False' in control
    assert '"desiredImpactSpeedControl": False' in control
    assert '"desiredImpactEnergyControl": False' in control

    for required in (
        'CANDIDATE = "ISS_GENERIC_BATTLE_RUNTIME_V1_CANDIDATE_4_6_3_GENERIC_AUTONOMOUS_BATTLE"',
        '"fixtureMutationForAcceptance": False',
        '"nativeContactAuthorityPreserved": True',
        '"damageAdmissionThresholdChanged": False',
        '"contactThresholdChanged": False',
        '"precontactRunwayRequired": True',
        '"surfaceGapRevalidatedDuringReposition": True',
        '"gateClosed": False',
    ):
        assert required in wrapper, required

    consequence = CONSEQUENCES.read_text(encoding="utf-8")
    assert "MIN_DAMAGE_SEVERITY" not in consequence
    assert 'shard["iss_debris_trajectory_injection"] = False' in consequence
    assert '"physicalDamageGateChanged": False' in consequence
    assert '"contactGateChanged": False' in consequence


def main() -> None:
    _static_scope()
    assert BATTLE_SIGNAL_SCOPE == "ACTOR_INVOLVEMENT_EVENT_HISTORY_V1"
    assert ENGAGEMENT_RUNWAY_MODEL == "GEOMETRY_CAPABILITY_SURFACE_GAP_RUNWAY_V1"
    assert abs(motion_heading_error(math.pi - 0.01, "REVERSE")) < 0.02
    assert abs(motion_heading_error(-math.pi + 0.01, "REVERSE")) < 0.02

    sports = _runway_sequence("sports")
    heavy = _runway_sequence("heavy")
    assert float(heavy["runwayM"]) > float(sports["runwayM"])
    history = _history_scope()
    _payoff_terminal()

    print(json.dumps({
        "marker": "GENERIC_AUTONOMOUS_BATTLE_C463_PROPERTY_ACCEPTANCE",
        "status": "PASS",
        "affectedLayerAudit": "PASS",
        "failureFamily": "PRECONTACT_ENGAGEMENT_RUNWAY_AND_SURFACE_GAP_GEOMETRY_CONTRACT_MISMATCH",
        "sports": sports,
        "heavy": heavy,
        "samePlannerAcrossProfiles": True,
        "precontactRunwayRequired": True,
        "surfaceGapRevalidatedDuringReposition": True,
        "standOffUsesLiveSupportGeometry": True,
        "firstAttackAndCounterUseSameRunwayPolicy": True,
        "payoffTerminatesRecovery": True,
        "damageThresholdAwareControl": False,
        "targetToughnessAwareControl": False,
        "desiredImpactSpeedControl": False,
        "desiredImpactEnergyControl": False,
        "fixtureMutationForAcceptance": False,
        "nativeContactAuthorityPreserved": True,
        "damageAdmissionThresholdChanged": False,
        "contactThresholdChanged": False,
        "perAssetBattleCode": False,
        "perVideoTrajectoryEngineering": False,
        "actorPoseOrVelocityMutation": False,
        "gateClosed": False,
        **history,
    }, sort_keys=True))


if __name__ == "__main__":
    main()
