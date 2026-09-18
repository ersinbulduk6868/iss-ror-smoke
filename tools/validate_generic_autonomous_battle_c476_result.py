#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(ROOT / "tools") not in sys.path:
    sys.path.insert(0, str(ROOT / "tools"))

from blender.iss_battle_runtime_contract import ActorProfile
from validate_generic_autonomous_battle_c465_result import _cutoff_runtime_proof
from validate_generic_autonomous_battle_c470_result import _surface_transaction_runtime_proof
from validate_generic_autonomous_battle_c471_result import _transaction_sampling_runtime_proof
from validate_generic_autonomous_battle_c474_result import (
    _ownership_aware_cross_gate_validate,
    _progress_runtime_proof,
)

EXPECTED_BUGATTI_MASS_KG = 1570.0
EXPECTED_BULLDOZER_MASS_KG = 27614.189525707065
EXPECTED_BULLDOZER_SOURCE_SHA = "2c0be359bbc6c99118751e7caa4b71a205961914e78d2e58c5dd7afc0f498468"
EXPECTED_BULLDOZER_UID = "b06a715d23a7450babac383b8bb7fb0a"


def _load(path: str) -> dict:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def _canonical_sha(value: object) -> str:
    raw = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def _binding_by_entity(request: dict, entity_id: str) -> dict:
    for binding in request.get("assetBindings") or []:
        if str(binding.get("entityId") or "") == entity_id:
            return dict(binding)
    raise AssertionError(("C476_BINDING_MISSING", entity_id))


def _profile_contract(base_request: dict, hetero_request: dict) -> dict[str, object]:
    base_plan_sha = _canonical_sha(base_request.get("battlePlan"))
    hetero_plan_sha = _canonical_sha(hetero_request.get("battlePlan"))
    assert base_plan_sha == hetero_plan_sha, (
        "C476_BATTLE_PLAN_MUTATED_FOR_HETEROGENEOUS_ACCEPTANCE",
        base_plan_sha,
        hetero_plan_sha,
    )
    assert _canonical_sha(base_request.get("executionPolicy")) == _canonical_sha(hetero_request.get("executionPolicy")), (
        "C476_EXECUTION_POLICY_MUTATED_FOR_HETEROGENEOUS_ACCEPTANCE"
    )
    assert _canonical_sha(base_request.get("scenes")) == _canonical_sha(hetero_request.get("scenes")), (
        "C476_SCENES_MUTATED_FOR_HETEROGENEOUS_ACCEPTANCE"
    )

    alpha_binding = _binding_by_entity(hetero_request, "actor_alpha")
    beta_binding = _binding_by_entity(hetero_request, "actor_beta")
    alpha_mass = float(alpha_binding.get("totalMassKg") or alpha_binding.get("massKg") or 0.0)
    beta_mass = float(beta_binding.get("totalMassKg") or beta_binding.get("massKg") or 0.0)
    assert abs(alpha_mass - EXPECTED_BUGATTI_MASS_KG) < 1.0e-6, ("C476_BUGATTI_MASS_DRIFT", alpha_mass)
    assert abs(beta_mass - EXPECTED_BULLDOZER_MASS_KG) < 1.0e-6, ("C476_BULLDOZER_MASS_DRIFT", beta_mass)
    mass_ratio = beta_mass / alpha_mass
    assert mass_ratio >= 10.0, ("C476_MASS_DISSIMILARITY_INSUFFICIENT", mass_ratio)

    assert str(beta_binding.get("sourceUid") or "") == EXPECTED_BULLDOZER_UID, (
        "C476_BULLDOZER_SOURCE_UID_DRIFT", beta_binding.get("sourceUid")
    )
    assert str(beta_binding.get("sourceSha256") or "").lower() == EXPECTED_BULLDOZER_SOURCE_SHA, (
        "C476_BULLDOZER_SOURCE_SHA_DRIFT", beta_binding.get("sourceSha256")
    )

    alpha = ActorProfile.from_binding(alpha_binding)
    beta = ActorProfile.from_binding(beta_binding)

    assert alpha.mass_kg < 8000.0 <= beta.mass_kg
    assert alpha.max_speed_mps > beta.max_speed_mps
    assert alpha.max_reverse_mps > beta.max_reverse_mps
    assert alpha.acceleration_mps2 > beta.acceleration_mps2
    assert alpha.braking_mps2 > beta.braking_mps2
    assert alpha.max_yaw_rate_rad_s > beta.max_yaw_rate_rad_s
    assert beta.toughness_j_per_kg > alpha.toughness_j_per_kg

    forbidden_profile_fields = {
        "desiredImpactSpeedMps",
        "desiredImpactEnergyJ",
        "collisionFrame",
        "contactFrame",
        "trajectoryPoints",
        "waypoints",
        "forcedWinner",
    }
    for label, binding in (("alpha", alpha_binding), ("beta", beta_binding)):
        raw = json.dumps(binding, sort_keys=True)
        for key in forbidden_profile_fields:
            assert key.lower() not in raw.lower(), ("C476_FORBIDDEN_PROFILE_TUNING", label, key)

    return {
        "battlePlanSha256": base_plan_sha,
        "battlePlanUnchanged": True,
        "massRatioBulldozerToBugatti": mass_ratio,
        "bugattiProfile": {
            "massKg": alpha.mass_kg,
            "maxSpeedMps": alpha.max_speed_mps,
            "maxReverseMps": alpha.max_reverse_mps,
            "accelerationMps2": alpha.acceleration_mps2,
            "brakingMps2": alpha.braking_mps2,
            "maxYawRateRadS": alpha.max_yaw_rate_rad_s,
            "toughnessJPerKg": alpha.toughness_j_per_kg,
        },
        "bulldozerProfile": {
            "massKg": beta.mass_kg,
            "maxSpeedMps": beta.max_speed_mps,
            "maxReverseMps": beta.max_reverse_mps,
            "accelerationMps2": beta.acceleration_mps2,
            "brakingMps2": beta.braking_mps2,
            "maxYawRateRadS": beta.max_yaw_rate_rad_s,
            "toughnessJPerKg": beta.toughness_j_per_kg,
        },
        "actorProfileCapabilityDissimilarity": True,
        "perAssetControlTuning": False,
    }


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--base-request", required=True)
    p.add_argument("--hetero-request", required=True)
    for key in ("battle", "g06", "g07", "g08", "log"):
        p.add_argument(f"--hetero-{key}", required=True)
    a = p.parse_args()

    base_request = _load(a.base_request)
    hetero_request = _load(a.hetero_request)
    profiles = _profile_contract(base_request, hetero_request)

    cross_gate = _ownership_aware_cross_gate_validate(
        "bugatti-bulldozer",
        a.hetero_battle,
        a.hetero_g06,
        a.hetero_g07,
        a.hetero_g08,
    )
    cutoff = _cutoff_runtime_proof(a.hetero_battle)
    surface = _surface_transaction_runtime_proof(a.hetero_log)
    transaction = _transaction_sampling_runtime_proof(a.hetero_log)
    progress = _progress_runtime_proof(a.hetero_log)

    print(json.dumps({
        "marker": "GENERIC_AUTONOMOUS_BATTLE_C476_MACHINE_ACCEPTANCE",
        "status": "PASS",
        "candidate": "ISS_GENERIC_BATTLE_RUNTIME_V1_CANDIDATE_4_7_6_HETEROGENEOUS_ACTORPROFILE_ACCEPTANCE",
        "mechanism": "G04_HETEROGENEOUS_ACTORPROFILE_ACCEPTANCE_V1",
        "sameC474RuntimeSource": True,
        "runtimeBehaviorChangedFromC474": False,
        "heterogeneousActorProfileProof": "PASS",
        "battlePlanUnchanged": True,
        "sameRuntimeAcrossDissimilarActorProfiles": True,
        "lightToHeavyNativeContact": "PASS",
        "heavyToLightNativeContact": "PASS",
        "radialNavigationContractPreserved": "PASS",
        "obbOnlyHandoffEligibility": "PASS",
        "tacticalGoalProgressRebase": "PASS",
        "collisionProxyProgressRefresh": "PASS",
        "transactionBoundedLocalityWindow": "PASS",
        "livePairSurfaceSemanticSelection": "PASS",
        "secondNativeContact": "PASS",
        "twoSidedDamage": "PASS",
        "damageThresholdSemantics": "PASS",
        "visibleCausalDamageDebris": "PASS",
        "g07AdaptiveCausalDrama": "PASS",
        "g08MachineObservability": "PASS",
        "nativeContactAuthorityPreserved": True,
        "pairwiseSolverOraclePreserved": True,
        "contactThresholdChanged": False,
        "damageAdmissionThresholdChanged": False,
        "damageThresholdAwareControl": False,
        "desiredImpactSpeedControl": False,
        "desiredImpactEnergyControl": False,
        "fixtureBattlePlanChanged": False,
        "perAssetBattleCode": False,
        "perVideoTrajectoryEngineering": False,
        "humanCinematicAcceptance": "PENDING",
        "gateClosed": False,
        "productionReadyClaimed": False,
        "profileProof": profiles,
        "crossGateProof": cross_gate,
        "cutoffRuntimeProof": cutoff,
        "surfaceTransactionRuntimeProof": surface,
        "transactionSamplingRuntimeProof": transaction,
        "progressRuntimeProof": progress,
    }, sort_keys=True))


if __name__ == "__main__":
    main()
