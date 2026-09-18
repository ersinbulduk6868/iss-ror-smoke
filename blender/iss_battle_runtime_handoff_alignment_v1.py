from __future__ import annotations

HANDOFF_ALIGNMENT_MODEL = "G04_TRANSLATION_DOMINANT_CONTACT_HANDOFF_V1"


def rotational_nose_speed_mps(
    *,
    yaw_rate_rad_s: float,
    characteristic_length_m: float,
) -> float:
    """Return lateral speed of the chassis nose induced by current yaw.

    The lever arm is half the live chassis characteristic length.  This is a
    geometry-derived rigid-body quantity: no asset identity, impact target,
    collision frame, contact threshold, or desired impact energy is involved.
    """
    half_length = max(0.0, float(characteristic_length_m)) * 0.5
    return abs(float(yaw_rate_rad_s)) * half_length


def translation_dominates_rotation(
    *,
    forward_speed_mps: float,
    yaw_rate_rad_s: float,
    characteristic_length_m: float,
) -> bool:
    """True when the prospective contact approach is translation-dominant.

    Solver authority should not be handed off while the chassis nose is sweeping
    laterally faster from yaw than the controller is translating forward.  The
    equality boundary has a direct rigid-body meaning and introduces no tuned
    angular or speed threshold.
    """
    translation = float(forward_speed_mps)
    if translation <= 0.0:
        return False
    rotational = rotational_nose_speed_mps(
        yaw_rate_rad_s=yaw_rate_rad_s,
        characteristic_length_m=characteristic_length_m,
    )
    return translation >= rotational


def should_defer_handoff_for_alignment(
    *,
    contact_handoff_requested: bool,
    prospective_motor_authority: str,
    forward_speed_mps: float,
    yaw_rate_rad_s: float,
    characteristic_length_m: float,
) -> bool:
    if not contact_handoff_requested:
        return False
    if str(prospective_motor_authority).strip().upper() != "MOTOR":
        return False
    return not translation_dominates_rotation(
        forward_speed_mps=forward_speed_mps,
        yaw_rate_rad_s=yaw_rate_rad_s,
        characteristic_length_m=characteristic_length_m,
    )
