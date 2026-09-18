from __future__ import annotations

HANDOFF_ELIGIBILITY_MODEL = "G04_COLLISION_PROXY_HANDOFF_ELIGIBILITY_V1"
TACTICAL_PROGRESS_OWNERSHIP_MODEL = "G04_TACTICAL_GOAL_PROGRESS_OWNERSHIP_V1"
COLLISION_PROXY_PROGRESS_MODEL = "G04_COLLISION_PROXY_PROGRESS_V1"


def progress_epsilon_m(characteristic_length_m: float) -> float:
    """Exact progress epsilon already used by ClosedLoopGoalController V1."""
    return max(0.025, max(0.0, float(characteristic_length_m)) * 0.008)


def should_defer_contact_handoff(
    *,
    requires_contact: bool,
    effective_collision_proxy_gap_m: float,
    existing_handoff_gap_m: float,
) -> bool:
    """Keep motor authority while rigid-body proxies are outside existing handoff gap.

    This adds no new threshold. The established controller handoff gap remains the
    sole distance budget; OBB/SAT only determines whether the rigid proxies satisfy it.
    """
    return bool(
        requires_contact
        and float(effective_collision_proxy_gap_m) > float(existing_handoff_gap_m)
    )


def should_rebase_progress_for_tactical_goal(
    *,
    previous_tactical_mode: str | None,
    current_tactical_mode: str,
    tactical_transition: bool,
) -> bool:
    previous = str(previous_tactical_mode or "").strip().upper()
    current = str(current_tactical_mode or "").strip().upper()
    return bool(tactical_transition and previous and current and previous != current)


def collision_proxy_progressed(
    *,
    previous_effective_gap_m: float | None,
    current_effective_gap_m: float,
    closing_speed_mps: float,
    characteristic_length_m: float,
    requires_contact: bool,
) -> bool:
    if not requires_contact or previous_effective_gap_m is None:
        return False
    epsilon = progress_epsilon_m(characteristic_length_m)
    return bool(
        float(closing_speed_mps) > 0.0
        and float(current_effective_gap_m)
        < float(previous_effective_gap_m) - epsilon
    )
