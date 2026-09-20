from __future__ import annotations

import math
from typing import Any

from blender.iss_battle_runtime_contract import (
    ActorState, BattleProgram, EventState, ImpactEvidence, RuntimeEvent, clamp, norm, stable_unit
)

class SpawnPlanner:
    @staticmethod
    def plan(program: BattleProgram) -> dict[str, tuple[float, float, float]]:
        target_counts = {a: 0 for a in program.actor_ids}
        attack_counts = {a: 0 for a in program.actor_ids}
        for e in program.events:
            if e.target_id:
                target_counts[e.target_id] = target_counts.get(e.target_id, 0) + 1
            for a in e.attackers:
                attack_counts[a] = attack_counts.get(a, 0) + 1
        ranked = sorted(program.actor_ids, key=lambda a: (-target_counts.get(a, 0), attack_counts.get(a, 0), a))
        anchors = [a for a in ranked if target_counts.get(a, 0) > 0][: max(1, min(3, len(ranked)))]
        positions: dict[str, tuple[float, float, float]] = {}
        if anchors:
            if len(anchors) == 1:
                positions[anchors[0]] = (0.0, 0.0, 0.0)
            else:
                for i, actor in enumerate(anchors):
                    angle = 2.0 * math.pi * i / len(anchors)
                    positions[actor] = (3.0 * math.cos(angle), 3.0 * math.sin(angle), 0.0)

        others = [a for a in program.actor_ids if a not in positions]
        golden = math.pi * (3.0 - math.sqrt(5.0))
        for i, actor in enumerate(others):
            ring = i // 18
            r = 10.0 + ring * 4.5
            angle = i * golden + stable_unit(actor) * 0.8
            positions[actor] = (r * math.cos(angle), r * math.sin(angle), 0.0)
        return positions


class WaveScheduler:
    @staticmethod
    def active_attackers(event: RuntimeEvent, frame: int, max_concurrent: int | None = None) -> tuple[str, ...]:
        attackers = event.attackers
        if len(attackers) <= 1:
            return attackers
        cap = max_concurrent or (12 if len(attackers) > 40 else 8 if len(attackers) > 16 else len(attackers))
        cap = max(1, min(cap, len(attackers)))
        if cap >= len(attackers):
            return attackers
        span = max(1, event.end_frame - event.start_frame + 1)
        wave_count = math.ceil(len(attackers) / cap)
        wave_span = max(1, span // wave_count)
        wave = min(wave_count - 1, max(0, (frame - event.start_frame) // wave_span))
        start = wave * cap
        return attackers[start : start + cap]


class TargetingPlanner:
    @staticmethod
    def approach_offset(
        tactic: str,
        attacker_index: int,
        attacker_count: int,
        target_length: float,
        target_width: float,
    ) -> tuple[float, float]:
        tactic = tactic.upper()
        count = max(1, attacker_count)
        idx = max(0, attacker_index)
        centered = idx - (count - 1) * 0.5
        lane = clamp(centered * max(0.65, target_width * 0.28), -target_width * 2.2, target_width * 2.2)
        if tactic == "FLANK":
            side = -1.0 if idx % 2 else 1.0
            return (-target_length * 0.10, side * (target_width * 0.75 + abs(lane) * 0.35))
        if tactic == "SURROUND":
            angle = 2.0 * math.pi * idx / count
            return (math.cos(angle) * target_length * 0.5, math.sin(angle) * max(target_width, target_length * 0.35))
        if tactic == "COUNTER":
            return (-target_length * 0.15, lane * 0.55)
        if tactic in {"EVADE", "REGROUP"}:
            return (-target_length * 1.2, lane)
        return (-target_length * 0.38, lane)


class ImpactModel:
    @staticmethod
    def estimate(
        *,
        frame: int,
        attacker_id: str,
        target_id: str,
        target_zone: str | None,
        attacker_mass_kg: float,
        target_mass_kg: float,
        relative_speed_mps: float,
        normal_closing_speed_mps: float,
        contact_point: tuple[float, float, float],
        contact_normal: tuple[float, float, float],
        response_delta_attacker_mps: float,
        response_delta_target_mps: float,
        target_toughness_j_per_kg: float,
    ) -> ImpactEvidence:
        ma = max(1.0, float(attacker_mass_kg))
        mt = max(1.0, float(target_mass_kg))
        reduced = (ma * mt) / (ma + mt)
        closing = max(0.0, float(normal_closing_speed_mps))
        energy = 0.5 * reduced * closing * closing
        specific = energy / mt
        toughness = max(1.0, float(target_toughness_j_per_kg))
        severity = clamp(1.0 - math.exp(-specific / toughness), 0.0, 1.0)
        return ImpactEvidence(
            frame=int(frame), attacker_id=attacker_id, target_id=target_id,
            target_zone=norm(target_zone) or None,
            relative_speed_mps=max(0.0, float(relative_speed_mps)),
            normal_closing_speed_mps=closing, reduced_mass_kg=reduced,
            impact_energy_j=energy, target_specific_energy_j_per_kg=specific,
            severity=severity, contact_point=tuple(float(x) for x in contact_point),
            contact_normal=tuple(float(x) for x in contact_normal),
            response_delta_attacker_mps=max(0.0, float(response_delta_attacker_mps)),
            response_delta_target_mps=max(0.0, float(response_delta_target_mps)),
        )

    @staticmethod
    def qualifies(evidence: ImpactEvidence, *, min_closing_speed: float = 1.25) -> bool:
        response_floor = max(0.12, evidence.normal_closing_speed_mps * 0.015)
        return (
            evidence.normal_closing_speed_mps >= min_closing_speed
            and evidence.impact_energy_j > 0.0
            and (
                evidence.response_delta_attacker_mps >= response_floor
                or evidence.response_delta_target_mps >= response_floor
            )
        )


class DamageAccumulator:
    DRIVE_ZONES = {
        "left_track", "right_track", "track", "wheel", "left_wheel", "right_wheel",
        "front_left_wheel", "front_right_wheel", "rear_left_wheel", "rear_right_wheel",
    }

    @staticmethod
    def apply(state: ActorState, evidence: ImpactEvidence) -> dict[str, Any]:
        zone = norm(evidence.target_zone) or "body"
        before_zone = state.zone_integrity.get(zone, 1.0)
        decrement = clamp(0.01 + 0.62 * (evidence.severity ** 0.85), 0.0, 0.72)
        after_zone = clamp(before_zone - decrement, 0.0, 1.0)
        state.zone_integrity[zone] = after_zone
        structural_drop = decrement * (0.42 if zone in DamageAccumulator.DRIVE_ZONES else 0.62)
        before_structural = state.structural_integrity
        state.structural_integrity = clamp(state.structural_integrity - structural_drop, 0.0, 1.0)
        if zone in DamageAccumulator.DRIVE_ZONES:
            state.drive_efficiency = clamp(state.drive_efficiency * (0.90 - evidence.severity * 0.45), 0.08, 1.0)
        else:
            state.drive_efficiency = clamp(state.drive_efficiency * (0.98 - evidence.severity * 0.18), 0.08, 1.0)
        state.disabled = state.structural_integrity <= 0.12 or state.drive_efficiency <= 0.10
        state.last_impact_frame = evidence.frame
        receipt = {
            "frame": evidence.frame, "zone": zone, "severity": evidence.severity,
            "impactEnergyJ": evidence.impact_energy_j,
            "specificEnergyJPerKg": evidence.target_specific_energy_j_per_kg,
            "attackerId": evidence.attacker_id, "targetId": evidence.target_id,
            "contactPoint": list(evidence.contact_point), "contactNormal": list(evidence.contact_normal),
            "relativeSpeedMps": evidence.relative_speed_mps,
            "normalClosingSpeedMps": evidence.normal_closing_speed_mps,
            "detector": evidence.detector,
            "zoneIntegrityBefore": before_zone, "zoneIntegrityAfter": after_zone,
            "structuralIntegrityBefore": before_structural,
            "structuralIntegrityAfter": state.structural_integrity,
            "driveEfficiencyAfter": state.drive_efficiency, "disabled": state.disabled,
        }
        state.damage_events.append(receipt)
        return receipt


class OutcomeResolver:
    @staticmethod
    def resolve(states: dict[str, ActorState], events: dict[str, EventState]) -> dict[str, Any]:
        ranking = sorted(
            states.values(),
            key=lambda s: (s.disabled, -s.structural_integrity, -s.drive_efficiency, s.entity_id),
        )
        disabled = sorted(s.entity_id for s in states.values() if s.disabled)
        event_failures = sorted(eid for eid, es in events.items() if es.status not in {"SUCCEEDED", "OBSERVED", "SETTLED"})
        return {
            "mostOperationalActors": [s.entity_id for s in ranking[: min(3, len(ranking))]],
            "disabledActors": disabled,
            "allRequiredEventsSucceeded": not event_failures,
            "failedOrIncompleteEvents": event_failures,
            "actorState": {
                s.entity_id: {
                    "structuralIntegrity": round(s.structural_integrity, 6),
                    "driveEfficiency": round(s.drive_efficiency, 6),
                    "disabled": s.disabled,
                    "zoneIntegrity": {k: round(v, 6) for k, v in sorted(s.zone_integrity.items())},
                    "damageEventCount": len(s.damage_events),
                }
                for s in states.values()
            },
        }
