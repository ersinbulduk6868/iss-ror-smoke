from __future__ import annotations

from typing import Any

DRIVE_DIRECTION_MODEL = "GENERIC_CHASSIS_FORWARD_TO_BLENDER_MOTOR_SIGN_V1"


def motor_angular_velocity_for_chassis_speed(speed_mps: float, wheel_radius_m: float) -> float:
    """Map canonical chassis-forward speed to Blender motor angular velocity.

    Runtime wheel axes are aligned with chassis lateral +Y. With this exact
    geometry, Blender positive angular motor velocity propels the chassis toward
    canonical -X, so canonical +forward requires the opposite motor sign. The
    mapping is geometric and asset-independent.
    """
    radius = max(float(wheel_radius_m), 1e-4)
    return -float(speed_mps) / radius


def command_drive_rig(
    rig: Any,
    left_mps: float,
    right_mps: float,
    impulse_scale: float = 1.0,
) -> None:
    left_w = motor_angular_velocity_for_chassis_speed(left_mps, rig.wheel_radius)
    right_w = motor_angular_velocity_for_chassis_speed(right_mps, rig.wheel_radius)
    impulse = max(0.0, rig.max_motor_impulse * float(impulse_scale))
    for obj in rig.motors_left:
        c = obj.rigid_body_constraint
        c.motor_ang_target_velocity = left_w
        c.motor_ang_max_impulse = impulse
    for obj in rig.motors_right:
        c = obj.rigid_body_constraint
        c.motor_ang_target_velocity = right_w
        c.motor_ang_max_impulse = impulse
