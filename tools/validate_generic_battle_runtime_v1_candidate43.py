#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from blender.iss_battle_runtime_autonomy import (
    AutonomyMemory,
    AutonomyObservation,
    ClosedLoopGoalController,
)
from blender.iss_battle_runtime_contract import ActorState, ImpactEvidence
from blender.iss_battle_runtime_models import DamageAccumulator

EXPECTED_BLOBS = {
    "blender/run_generic_battle_runtime_v1_candidate40.py": "5fac710c646e4609d4b63d0ae23e8612f1c9c81d",
    "blender/iss_battle_runtime_autonomy.py": "d349c51b289266740df7615d37dc645839001641",
    "blender/run_generic_battle_runtime_v1_candidate39.py": "0ecbf33d2825802410faf2d3356ebc1e5a545a40",
    "blender/run_generic_battle_runtime_v1_candidate371.py": "e557e504ffb69c76e4d6b2370fb9f102d6c892d9",
    "blender/run_generic_battle_runtime_v1_candidate37.py": "4ed1301dd3b307773c53e9ce7304f353a5818cbe",
    "blender/run_generic_battle_runtime_v1_candidate42.py": "a6e8f624f1897f965b7fa1c87ea74afab3eaeeff",
    "blender/iss_battle_runtime_contact_truth.py": "9041178dd7d1a3951912e49ee398e8fa423da730",
    "blender/iss_battle_runtime_models.py": "7ba0fe68c3418d83f2d57824bd11721debd53e64",
}


def git_blob_sha(path: Path) -> str:
    data = path.read_bytes()
    return hashlib.sha1(f"blob {len(data)}\0".encode("ascii") + data).hexdigest()


def observation(*, efficiency: float, disabled: bool = False) -> AutonomyObservation:
    return AutonomyObservation(
        frame=100,
        fps=30,
        distance_m=120.0,
        surface_gap_m=100.0,
        heading_error_rad=0.0,
        forward_speed_mps=0.0,
        closing_speed_mps=0.0,
        contention=0.0,
        contact_count=0,
        damage_count=1,
        damage_required=False,
        actor_disabled=disabled,
        requires_contact=True,
        max_speed_mps=20.0,
        max_reverse_mps=6.0,
        max_yaw_rate_rad_s=1.35,
        acceleration_mps2=7.0,
        braking_mps2=10.0,
        drive_efficiency=efficiency,
        characteristic_length_m=4.5,
        speed_intent="ACCELERATE",
    )


def main() -> None:
    preserved = {}
    for rel, expected in EXPECTED_BLOBS.items():
        actual = git_blob_sha(ROOT / rel)
        if actual != expected:
            raise SystemExit(f"G06_PRESERVED_SOURCE_CHANGED:{rel}:{actual}:{expected}")
        preserved[rel] = actual

    hardened = (ROOT / "blender/iss_blender_battle_runtime_v1_hardened.py").read_text(encoding="utf-8")
    if "MIN_DAMAGE_SEVERITY = 0.055" not in hardened:
        raise SystemExit("G06_DAMAGE_THRESHOLD_CHANGED_OR_MISSING")
    if "damage_earned = evidence.severity >= MIN_DAMAGE_SEVERITY" not in hardened:
        raise SystemExit("G06_DAMAGE_EARNED_GATE_MISSING")

    state = ActorState(entity_id="property_actor")
    evidence = ImpactEvidence(
        frame=42,
        attacker_id="attacker",
        target_id="property_actor",
        target_zone="front",
        relative_speed_mps=10.0,
        normal_closing_speed_mps=9.0,
        reduced_mass_kg=725.0,
        impact_energy_j=29362.5,
        target_specific_energy_j_per_kg=20.25,
        severity=0.12,
        contact_point=(1.0, 0.0, 0.5),
        contact_normal=(1.0, 0.0, 0.0),
        response_delta_attacker_mps=2.0,
        response_delta_target_mps=2.0,
        detector="RECIPROCAL_NATIVE_SOLVER_RESPONSE_V1",
    )
    before_identity = id(state)
    receipt = DamageAccumulator.apply(state, evidence)
    if id(state) != before_identity:
        raise SystemExit("G06_ACTOR_STATE_OBJECT_REPLACED")
    if not (state.structural_integrity < 1.0 and state.drive_efficiency < 1.0):
        raise SystemExit("G06_DAMAGE_STATE_NOT_DEGRADED")
    if len(state.damage_events) != 1 or state.last_impact_frame != 42:
        raise SystemExit("G06_DAMAGE_HISTORY_NOT_PERSISTED")
    if receipt.get("detector") != "RECIPROCAL_NATIVE_SOLVER_RESPONSE_V1":
        raise SystemExit("G06_DAMAGE_DETECTOR_PROVENANCE_LOST")

    healthy = ClosedLoopGoalController.update(AutonomyMemory(), observation(efficiency=1.0))
    damaged = ClosedLoopGoalController.update(
        AutonomyMemory(), observation(efficiency=state.drive_efficiency)
    )
    if not (damaged.forward_speed_mps < healthy.forward_speed_mps):
        raise SystemExit(
            f"G06_DAMAGE_DOES_NOT_REDUCE_CONTROLLER_CAPABILITY:{healthy.forward_speed_mps}:{damaged.forward_speed_mps}"
        )
    disabled = ClosedLoopGoalController.update(
        AutonomyMemory(), observation(efficiency=0.08, disabled=True)
    )
    if disabled.mode != "DISABLED" or disabled.motor_authority != "COAST":
        raise SystemExit("G06_DISABLED_ACTOR_RETAINED_MOTOR_AUTHORITY")

    source = (ROOT / "blender/run_generic_battle_runtime_v1_candidate43.py").read_text(encoding="utf-8")
    required = [
        "CAUSAL_DAMAGE_PERSISTENT_STATE_V1",
        "G06_DAMAGE_PATH_WITHOUT_G05_AUTHORITY",
        "g05NativeContactAuthority",
        "G06_DAMAGED_STATE_CONSUMED_BY_LATER_EVENT",
        "g06-persistence-evidence.json",
        '"damageThresholdChanged": False',
        '"contactThresholdChanged": False',
        '"actorPoseOrVelocityMutation": False',
        '"stateResetMechanismIntroduced": False',
    ]
    missing = [token for token in required if token not in source]
    if missing:
        raise SystemExit("G06_C43_REQUIRED_SOURCE_CONTRACT_MISSING:" + ",".join(missing))

    low = source.lower()
    forbidden = [
        "obb_overlap_2d(",
        "convex_sweep_test(",
        ".linear_velocity =",
        ".location =",
        "keyframe_insert(data_path=\"location\"",
        "keyframe_insert(data_path='location'",
        "targetenergyj",
        "targetimpactspeedmps",
        "collisionframe",
        "trajectorypoints",
    ]
    hits = [token for token in forbidden if token in low]
    if hits:
        raise SystemExit("G06_C43_FORBIDDEN_CHEAT_OR_CHOREOGRAPHY:" + ",".join(hits))

    debris_source = (ROOT / "blender/iss_battle_runtime_consequences.py").read_text(encoding="utf-8")
    if 'shard["iss_debris_trajectory_injection"] = False' not in debris_source:
        raise SystemExit("G06_DEBRIS_NO_TRAJECTORY_CONTRACT_MISSING")

    print(json.dumps({
        "marker": "GENERIC_BATTLE_RUNTIME_CANDIDATE43_G06_PROPERTY_ACCEPTANCE",
        "status": "PASS",
        "preservedBlobShas": preserved,
        "damageThreshold": 0.055,
        "damageState": {
            "structuralIntegrityAfter": state.structural_integrity,
            "driveEfficiencyAfter": state.drive_efficiency,
            "damageEventCount": len(state.damage_events),
            "lastImpactFrame": state.last_impact_frame,
        },
        "controllerCapability": {
            "healthyForwardCommandMps": healthy.forward_speed_mps,
            "damagedForwardCommandMps": damaged.forward_speed_mps,
            "damagedCapabilityReduced": damaged.forward_speed_mps < healthy.forward_speed_mps,
            "disabledActorMode": disabled.mode,
            "disabledActorAuthority": disabled.motor_authority,
        },
        "g04SourceChanged": False,
        "g05SourceChanged": False,
        "candidate39SourceChanged": False,
        "candidate371SourceChanged": False,
        "damageThresholdChanged": False,
        "contactThresholdChanged": False,
        "actorPoseOrVelocityMutation": False,
        "productionReadyClaimed": False,
    }, sort_keys=True))


if __name__ == "__main__":
    main()
