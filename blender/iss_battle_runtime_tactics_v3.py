from __future__ import annotations

from dataclasses import asdict, dataclass
import math
from typing import Any, Iterable

TACTICAL_MODEL = "ISS_GENERIC_ADAPTIVE_BATTLE_TACTICS_V3"
BATTLE_SIGNAL_SCOPE = "ACTOR_INVOLVEMENT_EVENT_HISTORY_V1"


def clamp(value: float, lo: float, hi: float) -> float:
    return max(float(lo), min(float(hi), float(value)))


def wrap_pi(angle_rad: float) -> float:
    return (float(angle_rad) + math.pi) % (2.0 * math.pi) - math.pi


def motion_heading_error(heading_error_rad: float, speed_intent: str) -> float:
    """Heading error relative to the commanded direction of travel."""
    error = wrap_pi(heading_error_rad)
    if str(speed_intent or "").upper() == "REVERSE":
        return wrap_pi(error - math.pi)
    return error


def actor_realized_event_signals(
    actor_id: str,
    events: Iterable[Any],
    states: dict[str, Any],
) -> tuple[int, int, tuple[str, ...]]:
    """Return monotonic contact/damage signals for events involving one actor.

    The counters are deliberately *signals*, not unique physical-transaction
    counts: reciprocal story intents may each inherit one verified physical
    transaction. The tactical planner only needs to know whether the actor's
    realized battle history advanced. Events involving only other actors are
    excluded so multi-actor battles cannot contaminate this actor's memory.
    """
    entity = str(actor_id)
    contact_signal = 0
    damage_signal = 0
    contributing: list[str] = []
    for event in events:
        attackers = tuple(str(x) for x in (getattr(event, "attackers", ()) or ()))
        target_id = str(getattr(event, "target_id", "") or "")
        if entity not in attackers and entity != target_id:
            continue
        event_id = str(getattr(event, "event_id", "") or "")
        state = states.get(event_id)
        if state is None:
            continue
        contacts = max(0, int(getattr(state, "contact_count", 0) or 0))
        damages = max(0, int(getattr(state, "damage_count", 0) or 0))
        contact_signal += contacts
        damage_signal += damages
        if contacts or damages:
            contributing.append(event_id)
    return contact_signal, damage_signal, tuple(contributing)


@dataclass(slots=True)
class TacticalObservation:
    frame: int
    fps: int
    phase: str
    story_tactic: str
    requires_contact: bool
    surface_gap_m: float
    center_distance_m: float
    closing_speed_mps: float
    heading_error_rad: float
    contention: float
    own_integrity: float
    own_drive_efficiency: float
    own_disabled: bool
    target_integrity: float
    target_drive_efficiency: float
    target_disabled: bool
    own_max_speed_mps: float
    own_max_reverse_mps: float
    own_yaw_rate_rad_s: float
    own_acceleration_mps2: float
    own_braking_mps2: float
    own_length_m: float
    own_width_m: float
    target_length_m: float
    target_width_m: float
    contact_count: int
    damage_count: int
    own_damage_event_count: int
    target_damage_event_count: int
    last_own_impact_frame: int | None
    last_target_impact_frame: int | None


@dataclass(slots=True)
class TacticalMemory:
    mode: str = "ENGAGE"
    reason: str = "INIT"
    cycle: int = 0
    last_contact_count: int = 0
    last_damage_count: int = 0
    last_own_damage_count: int = 0
    break_until_frame: int = 0
    reposition_until_frame: int = 0
    reposition_duration_frames: int = 0
    separation_required_m: float = 0.0
    separation_achieved: bool = True
    flank_bias: float = 1.0
    transitions: int = 0
    initialized: bool = False

    def snapshot(self) -> dict[str, object]:
        return asdict(self)


@dataclass(slots=True)
class TacticalGoal:
    mode: str
    reason: str
    speed_intent: str
    speed_scale: float
    forward_offset_scale: float
    lateral_offset_scale: float
    contact_commit: bool
    brake_strength: float
    transition: bool
    cycle: int


class GenericBattleTacticalPlanner:
    """Asset-agnostic battle decision policy over live state and capabilities."""

    @staticmethod
    def _set_mode(memory: TacticalMemory, mode: str, reason: str) -> bool:
        changed = memory.mode != mode or memory.reason != reason
        if changed:
            memory.mode = mode
            memory.reason = reason
            memory.transitions += 1
        return changed

    @staticmethod
    def _break_frames(obs: TacticalObservation) -> tuple[int, int]:
        reverse_time = clamp(
            0.45 + obs.own_length_m / max(1.0, obs.own_max_reverse_mps) * 0.22,
            0.55,
            1.60,
        )
        turn_time = clamp(
            0.55 + 0.70 / max(0.15, obs.own_yaw_rate_rad_s),
            0.75,
            2.50,
        )
        fps = max(1, int(obs.fps))
        return max(2, round(reverse_time * fps)), max(2, round(turn_time * fps))

    @staticmethod
    def _separation_required(obs: TacticalObservation) -> float:
        length_term = 0.18 * (max(0.25, obs.own_length_m) + max(0.25, obs.target_length_m))
        width_term = 0.30 * max(max(0.25, obs.own_width_m), max(0.25, obs.target_width_m))
        return clamp(max(0.45, length_term, width_term), 0.45, 3.50)

    @staticmethod
    def _health_pressure(obs: TacticalObservation) -> float:
        own = 0.58 * clamp(obs.own_integrity, 0.0, 1.0) + 0.42 * clamp(obs.own_drive_efficiency, 0.0, 1.0)
        target = 0.58 * clamp(obs.target_integrity, 0.0, 1.0) + 0.42 * clamp(obs.target_drive_efficiency, 0.0, 1.0)
        return clamp(target - own, -1.0, 1.0)

    @staticmethod
    def _capability_speed_scale(obs: TacticalObservation) -> float:
        integrity = clamp(obs.own_integrity, 0.0, 1.0)
        drive = clamp(obs.own_drive_efficiency, 0.0, 1.0)
        braking_ratio = clamp(
            obs.own_braking_mps2 / max(0.25, obs.own_acceleration_mps2 + obs.own_braking_mps2),
            0.20,
            0.85,
        )
        return clamp((0.45 + 0.35 * drive + 0.20 * integrity) * (0.85 + 0.20 * braking_ratio), 0.20, 1.0)

    @staticmethod
    def decide(
        memory: TacticalMemory,
        obs: TacticalObservation,
        *,
        symmetry_bias: float = 1.0,
    ) -> TacticalGoal:
        phase = str(obs.phase or "").upper()
        story = str(obs.story_tactic or "").upper()
        bias = 1.0 if symmetry_bias >= 0.0 else -1.0
        memory.flank_bias = bias

        # V3 intentionally does not baseline away already-realized actor history.
        # A target can receive a verified contact before it later becomes the
        # attacker of a counter-event, so its first tactical observation must
        # still react to that prior physical fact.
        if not memory.initialized:
            new_contact = int(obs.contact_count) > 0
            new_damage = int(obs.damage_count) > 0
            own_new_damage = int(obs.own_damage_event_count) > 0
            memory.initialized = True
        else:
            new_contact = int(obs.contact_count) > int(memory.last_contact_count)
            new_damage = int(obs.damage_count) > int(memory.last_damage_count)
            own_new_damage = int(obs.own_damage_event_count) > int(memory.last_own_damage_count)
        memory.last_contact_count = max(memory.last_contact_count, int(obs.contact_count))
        memory.last_damage_count = max(memory.last_damage_count, int(obs.damage_count))
        memory.last_own_damage_count = max(memory.last_own_damage_count, int(obs.own_damage_event_count))

        base_scale = GenericBattleTacticalPlanner._capability_speed_scale(obs)
        health_pressure = GenericBattleTacticalPlanner._health_pressure(obs)
        transition = False

        if obs.own_disabled:
            transition = GenericBattleTacticalPlanner._set_mode(memory, "DISABLED", "ACTOR_DISABLED")
            return TacticalGoal("DISABLED", memory.reason, "COAST", 0.0, 0.0, 0.0, False, 0.0, transition, memory.cycle)

        if new_contact or own_new_damage or new_damage:
            reverse_frames, turn_frames = GenericBattleTacticalPlanner._break_frames(obs)
            memory.cycle += 1
            memory.break_until_frame = max(int(memory.break_until_frame), int(obs.frame) + reverse_frames)
            memory.reposition_duration_frames = turn_frames
            memory.reposition_until_frame = memory.break_until_frame + turn_frames
            memory.separation_required_m = GenericBattleTacticalPlanner._separation_required(obs)
            memory.separation_achieved = False
            transition = GenericBattleTacticalPlanner._set_mode(memory, "BREAK_CONTACT", "REALIZED_CONTACT_OR_DAMAGE")

        if memory.cycle > 0 and not memory.separation_achieved:
            if obs.surface_gap_m >= memory.separation_required_m:
                memory.separation_achieved = True
                memory.reposition_until_frame = int(obs.frame) + max(2, int(memory.reposition_duration_frames))
                transition = GenericBattleTacticalPlanner._set_mode(memory, "REPOSITION", "SEPARATION_CONFIRMED") or transition
            else:
                transition = GenericBattleTacticalPlanner._set_mode(memory, "BREAK_CONTACT", "SEPARATION_NOT_YET_CONFIRMED") or transition
                return TacticalGoal(
                    "BREAK_CONTACT", memory.reason, "REVERSE", clamp(base_scale * 0.72, 0.18, 0.75),
                    0.0, bias * 0.18, False, 0.0, transition, memory.cycle,
                )

        if memory.cycle > 0 and memory.separation_achieved and obs.frame <= memory.reposition_until_frame:
            transition = GenericBattleTacticalPlanner._set_mode(memory, "REPOSITION", "POST_CONTACT_SPACING") or transition
            return TacticalGoal(
                "REPOSITION", memory.reason, "ACCELERATE", clamp(base_scale * 0.52, 0.18, 0.68),
                -0.30, bias * 1.05, False, 0.0, transition, memory.cycle,
            )

        if story in {"HOLD", "SETTLE"} or phase == "PAYOFF":
            transition = GenericBattleTacticalPlanner._set_mode(memory, "HOLD", "STORY_HIGH_LEVEL_HOLD") or transition
            return TacticalGoal("HOLD", memory.reason, "BRAKE", 0.0, 0.0, 0.0, False, 1.0, transition, memory.cycle)

        if story in {"EVADE", "REGROUP", "REVERSE"}:
            transition = GenericBattleTacticalPlanner._set_mode(memory, "EVADE", "STORY_HIGH_LEVEL_EVASION") or transition
            return TacticalGoal(
                "EVADE", memory.reason, "REVERSE" if abs(obs.heading_error_rad) < 0.75 else "ACCELERATE",
                clamp(base_scale * 0.62, 0.18, 0.72), -1.15, bias * 0.65, False, 0.0, transition, memory.cycle,
            )

        if health_pressure > 0.28 and phase not in {"CLIMAX", "COUNTERATTACK"}:
            transition = GenericBattleTacticalPlanner._set_mode(memory, "EVADE", "DAMAGE_STATE_DISADVANTAGE") or transition
            return TacticalGoal(
                "EVADE", memory.reason, "ACCELERATE", clamp(base_scale * 0.58, 0.16, 0.66),
                -1.00, bias * 0.85, False, 0.0, transition, memory.cycle,
            )

        if phase == "COUNTERATTACK" or story == "COUNTER":
            transition = GenericBattleTacticalPlanner._set_mode(memory, "COUNTER", "CAUSAL_COUNTERATTACK_WINDOW") or transition
            return TacticalGoal(
                "COUNTER", memory.reason, "ACCELERATE", clamp(base_scale * 0.90, 0.30, 1.0),
                -0.10, bias * 0.38, True, 0.0, transition, memory.cycle,
            )

        if story in {"FLANK", "SURROUND"} or obs.contention >= 0.48 or abs(obs.heading_error_rad) > 0.95:
            transition = GenericBattleTacticalPlanner._set_mode(memory, "FLANK", "GEOMETRY_OR_CONTENTION") or transition
            lateral = 0.90 if story != "SURROUND" else 1.20
            return TacticalGoal(
                "FLANK", memory.reason, "ACCELERATE", clamp(base_scale * 0.78, 0.24, 0.92),
                -0.18, bias * lateral, False, 0.0, transition, memory.cycle,
            )

        stopping_distance = max(0.0, obs.closing_speed_mps) ** 2 / max(0.5, 2.0 * obs.own_braking_mps2)
        geometric_buffer = max(0.35, 0.18 * (obs.own_length_m + obs.target_length_m))
        if obs.requires_contact and obs.surface_gap_m > 0.0 and stopping_distance > obs.surface_gap_m + geometric_buffer:
            transition = GenericBattleTacticalPlanner._set_mode(memory, "BRAKE_APPROACH", "BRAKING_DISTANCE") or transition
            strength = clamp(stopping_distance / max(0.2, obs.surface_gap_m + geometric_buffer), 0.5, 1.8)
            return TacticalGoal(
                "BRAKE_APPROACH", memory.reason, "BRAKE", 0.0, 0.0, 0.0, False, strength, transition, memory.cycle,
            )

        transition = GenericBattleTacticalPlanner._set_mode(memory, "ENGAGE", "LIVE_STATE_ENGAGEMENT") or transition
        contact_commit = bool(obs.requires_contact and abs(obs.heading_error_rad) <= 0.70 and obs.contention < 0.80)
        return TacticalGoal(
            "ENGAGE", memory.reason, "ACCELERATE", clamp(base_scale, 0.25, 1.0),
            -0.22, bias * 0.22, contact_commit, 0.0, transition, memory.cycle,
        )
