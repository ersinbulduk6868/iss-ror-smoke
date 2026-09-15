from __future__ import annotations

import json
import math
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from blender import iss_battle_runtime_assets as assets
from blender import iss_battle_runtime_physics as physics
from blender import run_generic_battle_runtime_v1_candidate34 as candidate34

CANDIDATE = "ISS_GENERIC_BATTLE_RUNTIME_V1_CANDIDATE_3_5"
DRIVE_AUTHORITY_MODEL = "MASS_ACCEL_RADIUS_TRACTION_CALIBRATED_V1"

_original_create_drive_rig = physics.create_drive_rig


def calibrated_create_drive_rig(
    entity: str,
    chassis,
    dimensions,
    profile,
    yaw: float,
):
    rig = _original_create_drive_rig(entity, chassis, dimensions, profile, yaw)
    driven_wheels = list(rig.wheels_left) + list(rig.wheels_right)
    driven_count = max(1, len(driven_wheels))
    wheel_mass_kg = sum(float(w.rigid_body.mass) for w in driven_wheels)

    # Rolling wheels add I/r^2 to the effective translational mass. The generated drive
    # wheels are cylinders, so 0.5 * wheel mass is the corresponding solid-cylinder term.
    effective_mass_kg = float(profile.mass_kg) + 0.5 * wheel_mass_kg

    # Respect the actor's requested acceleration, but never request more longitudinal
    # force than a conservative Coulomb-traction envelope can carry.
    requested_accel = max(0.0, float(profile.acceleration_mps2))
    traction_accel = max(0.5, float(profile.friction) * 9.81 * 0.85)
    calibrated_accel = min(requested_accel, traction_accel)

    torque_per_wheel = (
        effective_mass_kg
        * calibrated_accel
        * float(rig.wheel_radius)
        / float(driven_count)
    )
    if not math.isfinite(torque_per_wheel) or torque_per_wheel <= 0.0:
        raise RuntimeError(f"DRIVE_AUTHORITY_CALIBRATION_INVALID:{entity}:{torque_per_wheel}")

    rig.max_motor_impulse = torque_per_wheel
    for motor in rig.motors_left + rig.motors_right:
        motor.rigid_body_constraint.motor_ang_max_impulse = torque_per_wheel

    assets.marker(
        "DRIVE_RIG_AUTHORITY_CALIBRATED",
        entityId=entity,
        model=DRIVE_AUTHORITY_MODEL,
        drivenWheelCount=driven_count,
        wheelRadiusM=round(float(rig.wheel_radius), 6),
        declaredMassKg=round(float(profile.mass_kg), 6),
        rollingWheelMassKg=round(wheel_mass_kg, 6),
        effectiveMassKg=round(effective_mass_kg, 6),
        requestedAccelerationMps2=round(requested_accel, 6),
        tractionLimitedAccelerationMps2=round(calibrated_accel, 6),
        motorAuthorityPerWheel=round(torque_per_wheel, 6),
    )
    return rig


def main() -> None:
    # Preserve the proven Candidate 3.4 fixes.
    assets.centroid_for_terms = candidate34.ambiguity_safe_centroid_for_terms
    physics.DriveRig.command = candidate34.calibrated_command

    # Fix the generic underpowered drive-rig failure family without changing story intent,
    # actor trajectories, damage thresholds, contact gates, or acceptance criteria.
    physics.create_drive_rig = calibrated_create_drive_rig

    from blender import iss_blender_battle_runtime_v1_hardened as hardened

    hardened.RUNTIME_VERSION = CANDIDATE
    print(
        json.dumps(
            {
                "marker": "GENERIC_BATTLE_RUNTIME_CANDIDATE35_ENGINE_HARDENING_PASS",
                "candidate": CANDIDATE,
                "motorRollingSign": candidate34.MOTOR_ROLLING_SIGN,
                "semanticLocator": candidate34.SEMANTIC_LOCATOR,
                "driveAuthorityModel": DRIVE_AUTHORITY_MODEL,
                "damageThresholdChanged": False,
                "contactThresholdChanged": False,
                "scenarioTrajectoryHardcode": False,
            },
            sort_keys=True,
        ),
        flush=True,
    )
    hardened.main()


if __name__ == "__main__":
    main()
