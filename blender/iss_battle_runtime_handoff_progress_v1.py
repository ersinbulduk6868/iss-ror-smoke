from __future__ import annotations

HANDOFF_DEFER_PROGRESS_MODEL = "G04_DEFERRED_HANDOFF_COLLISION_PROXY_PROGRESS_V1"


def deferred_handoff_stalled(
    *,
    handoff_deferred: bool,
    effective_collision_proxy_gap_m: float | None,
    existing_handoff_gap_m: float,
    last_command_speed_mps: float,
    frame: int,
    last_progress_frame: int,
    progress_timeout_frames: int,
    controller_mode: str,
) -> bool:
    """Return whether a deferred contact approach has physically stopped progressing.

    This is intentionally asset-agnostic.  The function does not know vehicle names,
    masses, semantic parts, target damage, desired impact speed/energy, collision
    frames, or world coordinates.  It only reconciles the existing C474 handoff
    proxy with the existing low-level progress/recovery clock.
    """
    if not bool(handoff_deferred):
        return False
    if effective_collision_proxy_gap_m is None:
        return False
    if float(effective_collision_proxy_gap_m) <= float(existing_handoff_gap_m):
        return False
    if abs(float(last_command_speed_mps)) <= 0.25:
        return False
    if str(controller_mode or "").upper().startswith("RECOVER_"):
        return False
    elapsed = int(frame) - int(last_progress_frame)
    return elapsed >= max(2, int(progress_timeout_frames))
