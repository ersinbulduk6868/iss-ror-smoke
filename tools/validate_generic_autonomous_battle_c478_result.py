#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
TOOLS = ROOT / "tools"
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

from blender.iss_battle_runtime_contract import ActorProfile
from validate_generic_autonomous_battle_c465_result import _cutoff_runtime_proof
from validate_generic_autonomous_battle_c470_result import _surface_transaction_runtime_proof
from validate_generic_autonomous_battle_c471_result import _transaction_sampling_runtime_proof
from validate_generic_autonomous_battle_c474_result import (
    _ownership_aware_cross_gate_validate,
    _progress_runtime_proof,
)

EXPECTED_GENERIC_MASS_KG = 1450.0
EXPECTED_GENERIC_SHA = "0b2710a840d128aee53161277edb8cb77e1930d339f53585c6faece3f1dc2b1c"
EXPECTED_BULLDOZER_MASS_KG = 27614.189525707065
EXPECTED_BULLDOZER_SOURCE_SHA = "2c0be359bbc6c99118751e7caa4b71a205961914e78d2e58c5dd7afc0f498468"
EXPECTED_BULLDOZER_DYNAMIC_MASTER_SHA = "8ab94079ad22974f037bb01732365ffafdf2e107edd19865d145b9e33cc763c6"
EXPECTED_BULLDOZER_READY_PACKAGE_MANIFEST_SHA = "b2399a2e1b6944faefb458a6408adc385fe0f4376b125ae8f0a6b859adbcc623"
EXPECTED_BULLDOZER_READY_ASSET_ID = "2153aaa0-b922-40a6-a340-e286807bc44b"
EXPECTED_BULLDOZER_UID = "b06a715d23a7450babac383b8bb7fb0a"


def load(path: str) -> dict:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def canonical_sha(value: object) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def binding(req: dict, entity_id: str) -> dict:
    for row in req.get("assetBindings") or []:
        if str(row.get("entityId") or "") == entity_id:
            return dict(row)
    raise AssertionError(("C478_BINDING_MISSING", entity_id))


def profile_proof(base_req: dict, hetero_req: dict) -> dict[str, object]:
    assert canonical_sha(base_req.get("battlePlan")) == canonical_sha(hetero_req.get("battlePlan")), "C478_BATTLE_PLAN_DRIFT"
    assert canonical_sha(base_req.get("executionPolicy")) == canonical_sha(hetero_req.get("executionPolicy")), "C478_EXECUTION_POLICY_DRIFT"
    assert canonical_sha(base_req.get("scenes")) == canonical_sha(hetero_req.get("scenes")), "C478_SCENES_DRIFT"

    a = binding(hetero_req, "actor_alpha")
    b = binding(hetero_req, "actor_beta")
    assert str(a.get("sourceSha256") or "").lower() == EXPECTED_GENERIC_SHA, a
    assert abs(float(a.get("totalMassKg") or 0.0) - EXPECTED_GENERIC_MASS_KG) < 1e-6, a
    assert str(b.get("sourceUid") or "") == EXPECTED_BULLDOZER_UID, b
    assert str(b.get("sourceSha256") or "").lower() == EXPECTED_BULLDOZER_SOURCE_SHA, b
    assert str(b.get("readyAssetId") or "") == EXPECTED_BULLDOZER_READY_ASSET_ID, b
    assert str(b.get("dynamicMasterSha256") or "").lower() == EXPECTED_BULLDOZER_DYNAMIC_MASTER_SHA, b
    assert str(b.get("readyPackageManifestSha256") or "").lower() == EXPECTED_BULLDOZER_READY_PACKAGE_MANIFEST_SHA, b
    assert str(b.get("assetProfile") or "") == "DYNAMIC_ACTOR", b
    assert abs(float(b.get("totalMassKg") or 0.0) - EXPECTED_BULLDOZER_MASS_KG) < 1e-6, b

    sem = b.get("semanticManifest") or {}
    assert sem.get("canonicalization") == "RC1.1_REAL_L4_PASS", sem
    assert set(sem.get("majorSemanticBodies") or []) >= {"chassis", "cab", "blade", "track_left", "track_right"}, sem

    alpha = ActorProfile.from_binding(a)
    beta = ActorProfile.from_binding(b)
    ratio = beta.mass_kg / alpha.mass_kg
    assert ratio >= 10.0, ratio
    assert alpha.mass_kg < 8000.0 <= beta.mass_kg
    assert alpha.max_speed_mps > beta.max_speed_mps
    assert alpha.max_reverse_mps > beta.max_reverse_mps
    assert alpha.acceleration_mps2 > beta.acceleration_mps2
    assert alpha.braking_mps2 > beta.braking_mps2
    assert alpha.max_yaw_rate_rad_s > beta.max_yaw_rate_rad_s
    assert beta.toughness_j_per_kg > alpha.toughness_j_per_kg

    beta_rp = b.get("runtimeProfile") or {}
    for forbidden in (
        "maxSpeedMps", "maxReverseMps", "accelerationMps2", "brakingMps2",
        "maxYawRateRadS", "toughnessJPerKg", "desiredImpactSpeedMps",
        "desiredImpactEnergyJ", "collisionFrame", "contactFrame", "trajectoryPoints",
        "waypoints", "forcedWinner", "forwardAxis",
    ):
        assert forbidden not in beta_rp, ("C478_HEAVY_PROFILE_ACCEPTANCE_TUNING_FORBIDDEN", forbidden)

    return {
        "battlePlanSha256": canonical_sha(hetero_req.get("battlePlan")),
        "battlePlanUnchanged": True,
        "executionPolicyUnchanged": True,
        "scenesUnchanged": True,
        "massRatioHeavyToLight": ratio,
        "productionReadyHeavyAssetProof": "PASS",
        "readyAssetId": EXPECTED_BULLDOZER_READY_ASSET_ID,
        "sourceSnapshotSha256": EXPECTED_BULLDOZER_SOURCE_SHA,
        "dynamicMasterSha256": EXPECTED_BULLDOZER_DYNAMIC_MASTER_SHA,
        "readyPackageManifestSha256": EXPECTED_BULLDOZER_READY_PACKAGE_MANIFEST_SHA,
        "lightProfile": {
            "massKg": alpha.mass_kg,
            "maxSpeedMps": alpha.max_speed_mps,
            "maxReverseMps": alpha.max_reverse_mps,
            "accelerationMps2": alpha.acceleration_mps2,
            "brakingMps2": alpha.braking_mps2,
            "maxYawRateRadS": alpha.max_yaw_rate_rad_s,
            "toughnessJPerKg": alpha.toughness_j_per_kg,
        },
        "heavyProfile": {
            "massKg": beta.mass_kg,
            "maxSpeedMps": beta.max_speed_mps,
            "maxReverseMps": beta.max_reverse_mps,
            "accelerationMps2": beta.acceleration_mps2,
            "brakingMps2": beta.braking_mps2,
            "maxYawRateRadS": beta.max_yaw_rate_rad_s,
            "toughnessJPerKg": beta.toughness_j_per_kg,
        },
        "heavyCapabilitiesDerivedByExistingGenericActorProfileRules": True,
        "forwardAxisHardCoded": False,
        "perAssetControlTuning": False,
    }


def direction_proof(g06: dict) -> dict[str, object]:
    direct = [r for r in (g06.get("g05BoundImpacts") or []) if not r.get("inherited")]
    by_event = {str(r.get("eventId") or ""): r for r in direct}
    esc = by_event.get("evt-escalation")
    ctr = by_event.get("evt-counterattack")
    assert esc is not None, "C478_ESCALATION_NATIVE_CONTACT_MISSING"
    assert ctr is not None, "C478_COUNTERATTACK_NATIVE_CONTACT_MISSING"
    er = esc.get("nativeContactReceipt") or {}
    cr = ctr.get("nativeContactReceipt") or {}
    assert er.get("status") == "VERIFIED" and er.get("attackerId") == "actor_alpha" and er.get("targetId") == "actor_beta", er
    assert cr.get("status") == "VERIFIED" and cr.get("attackerId") == "actor_beta" and cr.get("targetId") == "actor_alpha", cr
    assert er.get("model") == "RECIPROCAL_NATIVE_SOLVER_RESPONSE_V1", er
    assert cr.get("model") == "RECIPROCAL_NATIVE_SOLVER_RESPONSE_V1", cr
    return {
        "lightToHeavyNativeContact": "PASS",
        "heavyToLightNativeContact": "PASS",
        "escalationContactFrame": er.get("contactFrame"),
        "counterattackContactFrame": cr.get("contactFrame"),
        "nativeContactAuthority": "RECIPROCAL_NATIVE_SOLVER_RESPONSE_V1",
    }


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--base-request", required=True)
    p.add_argument("--hetero-request", required=True)
    for key in ("battle", "g06", "g07", "g08", "log"):
        p.add_argument(f"--hetero-{key}", required=True)
    a = p.parse_args()

    base_req = load(a.base_request)
    hetero_req = load(a.hetero_request)
    profiles = profile_proof(base_req, hetero_req)
    g06 = load(a.hetero_g06)
    directions = direction_proof(g06)

    cross_gate = _ownership_aware_cross_gate_validate(
        "generic-hypercar-production-ready-bulldozer",
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
        "marker": "GENERIC_AUTONOMOUS_BATTLE_C478_MACHINE_ACCEPTANCE",
        "status": "PASS",
        "candidate": "ISS_GENERIC_BATTLE_RUNTIME_V1_CANDIDATE_4_7_8_PRODUCTION_READY_HETEROGENEOUS_ACCEPTANCE",
        "mechanism": "G04_PRODUCTION_READY_HETEROGENEOUS_ACTORPROFILE_ACCEPTANCE_V1",
        "executionProfile": "NVIDIA_L4",
        "sameC474RuntimeSource": True,
        "runtimeBehaviorChangedFromC474": False,
        "productionReadyHeavyAssetProof": "PASS",
        "heterogeneousActorProfileProof": "PASS",
        "sameRuntimeAcrossDissimilarActorProfiles": True,
        "battlePlanUnchanged": True,
        **directions,
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
        "targetToughnessAwareControl": False,
        "desiredImpactSpeedControl": False,
        "desiredImpactEnergyControl": False,
        "fixtureBattlePlanChanged": False,
        "perAssetBattleCode": False,
        "perVideoTrajectoryEngineering": False,
        "forwardAxisHardCoded": False,
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
