from __future__ import annotations

HANDOFF_READINESS_MODEL = "G04_G05_HANDOFF_READINESS_AND_LIVE_RECOVERY_DIRECTION_V1"


def live_recovery_bias(heading_error_rad: float, fallback_bias: float) -> float:
    """Turn recovery toward the live goal error; use deterministic bias only at zero error."""
    error = float(heading_error_rad)
    if error > 1.0e-6:
        return 1.0
    if error < -1.0e-6:
        return -1.0
    return 1.0 if float(fallback_bias) >= 0.0 else -1.0


def handoff_closing_ready(closing_speed_mps: float, minimum_closing_speed_mps: float) -> bool:
    """Boolean interface readiness only; this does not target an impact speed."""
    return float(closing_speed_mps) >= float(minimum_closing_speed_mps)
