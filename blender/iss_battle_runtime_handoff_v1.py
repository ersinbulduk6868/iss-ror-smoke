from __future__ import annotations

from dataclasses import dataclass

SOLVER_HANDOFF_LATCH_MODEL = "EVENT_LOCAL_SOLVER_AUTHORITY_HANDOFF_LATCH_V1"


@dataclass(slots=True)
class SolverHandoffLatch:
    start_frame: int
    contact_count_at_latch: int
    handoff_gap_m: float
    last_surface_gap_m: float


@dataclass(slots=True, frozen=True)
class SolverHandoffDecision:
    hold: bool
    reason: str
    release_gap_m: float


def release_gap_m(handoff_gap_m: float, characteristic_length_m: float) -> float:
    return max(
        0.15,
        float(handoff_gap_m) * 2.5,
        max(0.25, float(characteristic_length_m)) * 0.06,
    )


def decide_solver_handoff(
    latch: SolverHandoffLatch,
    *,
    current_contact_count: int,
    surface_gap_m: float,
    closing_speed_mps: float,
    characteristic_length_m: float,
) -> SolverHandoffDecision:
    """Keep motor authority released while native solver contact is imminent.

    Release occurs only after G05 has verified a contact (observable through the
    event contact counter) or after the pair has physically separated enough and
    is moving apart, which represents a genuine miss. No contact threshold,
    target toughness, asset identity, world coordinate or impact target is used.
    """
    release_gap = release_gap_m(latch.handoff_gap_m, characteristic_length_m)
    if int(current_contact_count) > int(latch.contact_count_at_latch):
        return SolverHandoffDecision(False, "VERIFIED_CONTACT_OBSERVED", release_gap)

    gap = float(surface_gap_m)
    closing = float(closing_speed_mps)
    if gap >= release_gap and closing < -0.10:
        return SolverHandoffDecision(False, "PHYSICAL_MISS_SEPARATING", release_gap)

    latch.last_surface_gap_m = gap
    return SolverHandoffDecision(True, "SOLVER_AUTHORITY_LATCHED", release_gap)
