from __future__ import annotations

import json
import math
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from blender import iss_battle_runtime_physics as physics
from blender import iss_blender_battle_runtime_v1_hardened as hardened

CANDIDATE = "ISS_GENERIC_BATTLE_RUNTIME_V1_CANDIDATE_3_2"
MOTOR_ROLLING_SIGN = -1.0


def calibrated_command(
    self: physics.DriveRig,
    left_mps: float,
    right_mps: float,
    impulse_scale: float = 1.0,
) -> None:
    """Map canonical +forward linear speed to Blender/Bullet wheel angular velocity.

    The real Blender 4.5.13 diagnostic proved the previous +omega convention drives
    the chassis opposite its canonical +X forward axis. Rolling kinematics for the
    rig's axle orientation therefore require a single engine-level -1 sign. This is
    generic: no actor name, target coordinate, trajectory, or scenario data enters
    this conversion.
    """
    radius = max(float(self.wheel_radius), 1e-4)
    left_w = MOTOR_ROLLING_SIGN * float(left_mps) / radius
    right_w = MOTOR_ROLLING_SIGN * float(right_mps) / radius
    impulse = max(0.0, float(self.max_motor_impulse) * float(impulse_scale))
    if not all(math.isfinite(x) for x in (left_w, right_w, impulse)):
        raise RuntimeError("MOTOR_COMMAND_NONFINITE")
    for obj in self.motors_left:
        constraint = obj.rigid_body_constraint
        constraint.motor_ang_target_velocity = left_w
        constraint.motor_ang_max_impulse = impulse
    for obj in self.motors_right:
        constraint = obj.rigid_body_constraint
        constraint.motor_ang_target_velocity = right_w
        constraint.motor_ang_max_impulse = impulse


def main() -> None:
    physics.DriveRig.command = calibrated_command
    print(
        json.dumps(
            {
                "marker": "GENERIC_BATTLE_RUNTIME_CANDIDATE32_PROPULSION_CALIBRATION_PASS",
                "candidate": CANDIDATE,
                "motorRollingSign": MOTOR_ROLLING_SIGN,
                "scope": "GENERIC_ENGINE_LEVEL_NO_SCENARIO_TRAJECTORY",
            },
            sort_keys=True,
        ),
        flush=True,
    )
    hardened.RUNTIME_VERSION = CANDIDATE
    hardened.main()


if __name__ == "__main__":
    main()
