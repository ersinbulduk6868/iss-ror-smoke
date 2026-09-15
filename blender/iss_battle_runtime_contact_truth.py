from __future__ import annotations

import math
from dataclasses import asdict, dataclass
from typing import Iterable

PAIRWISE_RESPONSE_MODEL = "RECIPROCAL_NATIVE_SOLVER_RESPONSE_V1"
OUTER_AUTHORITY_MODEL = "PAIRWISE_CONTACT_OUTER_AUTHORITY_V1"


def _v(value: Iterable[float]) -> tuple[float, float, float]:
    rows = tuple(float(x) for x in value)
    if len(rows) != 3:
        raise ValueError("PAIRWISE_VECTOR_MUST_HAVE_THREE_COMPONENTS")
    return rows  # type: ignore[return-value]


def _sub(a: tuple[float, float, float], b: tuple[float, float, float]) -> tuple[float, float, float]:
    return (a[0] - b[0], a[1] - b[1], a[2] - b[2])


def _scale(a: tuple[float, float, float], s: float) -> tuple[float, float, float]:
    return (a[0] * s, a[1] * s, a[2] * s)


def _dot(a: tuple[float, float, float], b: tuple[float, float, float]) -> float:
    return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]


def _length(a: tuple[float, float, float]) -> float:
    return math.sqrt(max(0.0, _dot(a, a)))


def _unit(a: tuple[float, float, float]) -> tuple[float, float, float]:
    length = _length(a)
    if length <= 1.0e-12:
        return (0.0, 0.0, 0.0)
    return _scale(a, 1.0 / length)


@dataclass(frozen=True)
class PairwiseSolverSample:
    attacker_mass_kg: float
    target_mass_kg: float
    pre_attacker_velocity: tuple[float, float, float]
    pre_target_velocity: tuple[float, float, float]
    post_attacker_velocity: tuple[float, float, float]
    post_target_velocity: tuple[float, float, float]
    collision_normal_attacker_to_target: tuple[float, float, float]

    @staticmethod
    def build(
        *,
        attacker_mass_kg: float,
        target_mass_kg: float,
        pre_attacker_velocity: Iterable[float],
        pre_target_velocity: Iterable[float],
        post_attacker_velocity: Iterable[float],
        post_target_velocity: Iterable[float],
        collision_normal_attacker_to_target: Iterable[float],
    ) -> "PairwiseSolverSample":
        return PairwiseSolverSample(
            attacker_mass_kg=float(attacker_mass_kg),
            target_mass_kg=float(target_mass_kg),
            pre_attacker_velocity=_v(pre_attacker_velocity),
            pre_target_velocity=_v(pre_target_velocity),
            post_attacker_velocity=_v(post_attacker_velocity),
            post_target_velocity=_v(post_target_velocity),
            collision_normal_attacker_to_target=_v(collision_normal_attacker_to_target),
        )


@dataclass(frozen=True)
class PairwiseSolverReceipt:
    qualified: bool
    reason: str
    normal_closing_speed_mps: float
    post_normal_closing_speed_mps: float
    closing_speed_drop_mps: float
    relative_speed_mps: float
    response_attacker_mps: float
    response_target_mps: float
    response_floor_mps: float
    attacker_impulse_ns: float
    target_impulse_ns: float
    impulse_balance_ratio: float
    impulse_opposition_cosine: float
    attacker_normal_alignment: float
    target_normal_alignment: float
    reduced_mass_kg: float

    def as_dict(self) -> dict[str, float | bool | str]:
        return asdict(self)


class PairwiseSolverResponseOracle:
    """Pair-specific physical-response oracle over solver-produced motion only."""

    MIN_CLOSING_SPEED_MPS = 1.25  # identical to existing ImpactModel default
    MIN_IMPULSE_BALANCE_RATIO = 0.25
    MIN_OPPOSITION_COSINE = 0.65
    MIN_NORMAL_ALIGNMENT = 0.55

    @staticmethod
    def evaluate(sample: PairwiseSolverSample) -> PairwiseSolverReceipt:
        ma = max(1.0, float(sample.attacker_mass_kg))
        mt = max(1.0, float(sample.target_mass_kg))
        normal = _unit(sample.collision_normal_attacker_to_target)
        if _length(normal) <= 0.0:
            return PairwiseSolverResponseOracle._receipt(False, "DEGENERATE_PAIR_NORMAL", ma, mt)

        pre_rel = _sub(sample.pre_attacker_velocity, sample.pre_target_velocity)
        post_rel = _sub(sample.post_attacker_velocity, sample.post_target_velocity)
        closing = max(0.0, _dot(pre_rel, normal))
        post_closing = _dot(post_rel, normal)
        closing_drop = closing - post_closing
        relative_speed = _length(pre_rel)
        response_floor = max(0.12, closing * 0.015)

        dva = _sub(sample.post_attacker_velocity, sample.pre_attacker_velocity)
        dvt = _sub(sample.post_target_velocity, sample.pre_target_velocity)
        response_a = _length(dva)
        response_t = _length(dvt)
        impulse_a = _scale(dva, ma)
        impulse_t = _scale(dvt, mt)
        impulse_a_mag = _length(impulse_a)
        impulse_t_mag = _length(impulse_t)
        larger = max(impulse_a_mag, impulse_t_mag)
        smaller = min(impulse_a_mag, impulse_t_mag)
        balance = smaller / larger if larger > 1.0e-9 else 0.0
        opposition = (
            _dot(impulse_a, _scale(impulse_t, -1.0)) / (impulse_a_mag * impulse_t_mag)
            if impulse_a_mag > 1.0e-9 and impulse_t_mag > 1.0e-9
            else -1.0
        )
        attacker_alignment = (
            _dot(_scale(impulse_a, -1.0), normal) / impulse_a_mag
            if impulse_a_mag > 1.0e-9 else -1.0
        )
        target_alignment = (
            _dot(impulse_t, normal) / impulse_t_mag
            if impulse_t_mag > 1.0e-9 else -1.0
        )
        reduced = (ma * mt) / (ma + mt)

        reason = "QUALIFIED"
        qualified = True
        if closing < PairwiseSolverResponseOracle.MIN_CLOSING_SPEED_MPS:
            qualified = False; reason = "CLOSING_SPEED_BELOW_EXISTING_GATE"
        elif max(response_a, response_t) < response_floor:
            qualified = False; reason = "SOLVER_RESPONSE_BELOW_EXISTING_FLOOR"
        elif impulse_a_mag <= 1.0e-9 or impulse_t_mag <= 1.0e-9:
            qualified = False; reason = "UNILATERAL_RESPONSE"
        elif balance < PairwiseSolverResponseOracle.MIN_IMPULSE_BALANCE_RATIO:
            qualified = False; reason = "IMPULSE_BALANCE_INCONSISTENT"
        elif opposition < PairwiseSolverResponseOracle.MIN_OPPOSITION_COSINE:
            qualified = False; reason = "IMPULSES_NOT_RECIPROCAL"
        elif attacker_alignment < PairwiseSolverResponseOracle.MIN_NORMAL_ALIGNMENT:
            qualified = False; reason = "ATTACKER_RESPONSE_NOT_PAIR_NORMAL"
        elif target_alignment < PairwiseSolverResponseOracle.MIN_NORMAL_ALIGNMENT:
            qualified = False; reason = "TARGET_RESPONSE_NOT_PAIR_NORMAL"
        elif closing_drop < response_floor:
            qualified = False; reason = "NO_MEANINGFUL_CLOSING_RESPONSE"

        return PairwiseSolverReceipt(
            qualified=qualified,
            reason=reason,
            normal_closing_speed_mps=closing,
            post_normal_closing_speed_mps=post_closing,
            closing_speed_drop_mps=closing_drop,
            relative_speed_mps=relative_speed,
            response_attacker_mps=response_a,
            response_target_mps=response_t,
            response_floor_mps=response_floor,
            attacker_impulse_ns=impulse_a_mag,
            target_impulse_ns=impulse_t_mag,
            impulse_balance_ratio=balance,
            impulse_opposition_cosine=opposition,
            attacker_normal_alignment=attacker_alignment,
            target_normal_alignment=target_alignment,
            reduced_mass_kg=reduced,
        )

    @staticmethod
    def _receipt(qualified: bool, reason: str, ma: float, mt: float) -> PairwiseSolverReceipt:
        reduced = (ma * mt) / (ma + mt)
        return PairwiseSolverReceipt(
            qualified=qualified,
            reason=reason,
            normal_closing_speed_mps=0.0,
            post_normal_closing_speed_mps=0.0,
            closing_speed_drop_mps=0.0,
            relative_speed_mps=0.0,
            response_attacker_mps=0.0,
            response_target_mps=0.0,
            response_floor_mps=0.12,
            attacker_impulse_ns=0.0,
            target_impulse_ns=0.0,
            impulse_balance_ratio=0.0,
            impulse_opposition_cosine=-1.0,
            attacker_normal_alignment=-1.0,
            target_normal_alignment=-1.0,
            reduced_mass_kg=reduced,
        )


@dataclass(frozen=True)
class ContactOuterAuthoritySample:
    intended_target_id: str
    observed_pair_target_id: str
    controller_handoff: bool
    motor_authority_zero: bool
    locality_gap_m: float
    locality_tolerance_m: float
    semantic_distance_m: float
    semantic_tolerance_m: float


@dataclass(frozen=True)
class ContactOuterAuthorityReceipt:
    qualified: bool
    reason: str
    target_identity_pass: bool
    controller_handoff_pass: bool
    locality_pass: bool
    semantic_pass: bool

    def as_dict(self) -> dict[str, bool | str]:
        return asdict(self)


class ContactOuterAuthorityGate:
    """Pure outer authority gate used by Candidate 4.2 and property acceptance."""

    @staticmethod
    def evaluate(sample: ContactOuterAuthoritySample) -> ContactOuterAuthorityReceipt:
        target_identity = bool(sample.intended_target_id) and (
            sample.intended_target_id == sample.observed_pair_target_id
        )
        handoff = bool(sample.controller_handoff and sample.motor_authority_zero)
        locality = float(sample.locality_gap_m) <= float(sample.locality_tolerance_m)
        semantic = float(sample.semantic_distance_m) <= float(sample.semantic_tolerance_m)

        reason = "QUALIFIED"
        qualified = True
        if not target_identity:
            qualified = False; reason = "TARGET_IDENTITY_MISMATCH"
        elif not handoff:
            qualified = False; reason = "CONTROLLER_AUTHORITY_NOT_RELEASED"
        elif not locality:
            qualified = False; reason = "PAIR_NOT_LOCALLY_ADJACENT"
        elif not semantic:
            qualified = False; reason = "SEMANTIC_ZONE_MISMATCH"

        return ContactOuterAuthorityReceipt(
            qualified=qualified,
            reason=reason,
            target_identity_pass=target_identity,
            controller_handoff_pass=handoff,
            locality_pass=locality,
            semantic_pass=semantic,
        )
