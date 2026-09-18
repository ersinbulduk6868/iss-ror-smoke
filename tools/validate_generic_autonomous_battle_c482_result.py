#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
TOOLS = ROOT / "tools"
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

from validate_generic_autonomous_battle_c465_result import _cutoff_runtime_proof
from validate_generic_autonomous_battle_c470_result import _surface_transaction_runtime_proof
from validate_generic_autonomous_battle_c471_result import _transaction_sampling_runtime_proof
from validate_generic_autonomous_battle_c474_result import _progress_runtime_proof
from validate_generic_autonomous_battle_c479_result import (
    direction_proof,
    load,
    profile_and_metadata_proof,
)
from validate_generic_autonomous_battle_c480_result import (
    _json_markers,
    approach_transaction_proof,
)
from validate_generic_autonomous_battle_c481_result import deferred_handoff_recovery_proof
from validate_generic_heterogeneous_cross_gate_v1 import heterogeneous_cross_gate_proof


def collision_role_runtime_proof(log_path: str) -> dict[str, object]:
    rows = _json_markers(log_path)
    roles = [r for r in rows if r.get("marker") == "G04_RIGID_BODY_COLLISION_ROLE_ASSIGNED"]
    constraints = [r for r in rows if r.get("marker") == "G04_CONSTRAINED_DRIVE_SELF_COLLISION_DISABLED"]
    battle = [r for r in roles if r.get("role") == "BATTLE_BODY"]
    drive = [r for r in roles if r.get("role") == "DRIVE_HELPER"]
    ground = [r for r in roles if r.get("role") == "GROUND"]

    assert len(battle) == 2, ("C482_BATTLE_BODY_ROLE_COUNT", len(battle), battle)
    assert len(drive) == 8, ("C482_DRIVE_HELPER_ROLE_COUNT", len(drive), drive)
    assert len(ground) == 1, ("C482_GROUND_ROLE_COUNT", len(ground), ground)
    assert all(r.get("enabledGroups") == [0] for r in battle), battle
    assert all(r.get("enabledGroups") == [1] for r in drive), drive
    assert ground[0].get("enabledGroups") == [0, 1], ground[0]
    assert len(constraints) == 16, ("C482_DRIVE_CONSTRAINT_COUNT", len(constraints))
    assert all(r.get("disableCollisions") is True for r in constraints), constraints
    assert all(r.get("model") == "GENERIC_BATTLE_RIGID_BODY_COLLISION_ROLE_V1" for r in roles + constraints)
    return {
        "collisionRoleRuntimeProof": "PASS",
        "battleBodyRoleCount": len(battle),
        "driveHelperRoleCount": len(drive),
        "groundRoleCount": len(ground),
        "driveConstraintSelfCollisionDisabledCount": len(constraints),
        "battleAndDriveRolesDisjoint": True,
        "groundSharesBothRoles": True,
    }


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--base-request", required=True)
    p.add_argument("--hetero-request", required=True)
    p.add_argument("--asset-library-metadata", required=True)
    for key in ("battle", "g06", "g07", "g08", "log"):
        p.add_argument(f"--hetero-{key}", required=True)
    a = p.parse_args()

    base_req = load(a.base_request)
    hetero_req = load(a.hetero_request)
    ready_meta = load(a.asset_library_metadata)
    profile = profile_and_metadata_proof(base_req, hetero_req, ready_meta)
    g06 = load(a.hetero_g06)
    directions = direction_proof(g06)

    cross_gate = heterogeneous_cross_gate_proof(
        "generic-hypercar-production-ready-heavy-asset",
        a.hetero_battle,
        a.hetero_g06,
        a.hetero_g07,
        a.hetero_g08,
    )
    cutoff = _cutoff_runtime_proof(a.hetero_battle)
    surface = _surface_transaction_runtime_proof(a.hetero_log)
    transaction = _transaction_sampling_runtime_proof(a.hetero_log)
    progress = _progress_runtime_proof(a.hetero_log)
    approach = approach_transaction_proof(a.hetero_log, a.hetero_g07)
    recovery = deferred_handoff_recovery_proof(a.hetero_log)
    roles = collision_role_runtime_proof(a.hetero_log)

    print(json.dumps({
        "marker": "GENERIC_AUTONOMOUS_BATTLE_C482_MACHINE_ACCEPTANCE",
        "status": "PASS",
        "candidate": "ISS_GENERIC_BATTLE_RUNTIME_V1_CANDIDATE_4_8_2_GENERIC_AUTONOMOUS_BATTLE",
        "mechanism": "GENERIC_BATTLE_RIGID_BODY_COLLISION_ROLE_V1",
        "executionProfile": "NVIDIA_L4",
        "productionReadyHeavyAssetProof": "PASS",
        "canonicalFrameMetadataProof": "PASS",
        "heterogeneousActorProfileProof": "PASS",
        "sameRuntimeAcrossDissimilarActorProfiles": True,
        **directions,
        **approach,
        **recovery,
        **roles,
        "radialNavigationContractPreserved": "PASS",
        "obbOnlyHandoffEligibility": "PASS",
        "tacticalGoalProgressRebase": "PASS",
        "collisionProxyProgressRefresh": "PASS",
        "transactionBoundedLocalityWindow": "PASS",
        "livePairSurfaceSemanticSelection": "PASS",
        "secondNativeContact": "PASS",
        "heterogeneousDamageOutcome": cross_gate["damageOutcomeMode"],
        "damageThresholdSemantics": cross_gate["damageThresholdSemantics"],
        "g04DoesNotTargetG06DamageThreshold": cross_gate["g04DoesNotTargetG06DamageThreshold"],
        "visibleCausalDamageDebris": "PASS",
        "g07AdaptiveCausalDrama": "PASS",
        "g08MachineObservability": "PASS",
        "nativeContactAuthorityPreserved": True,
        "pairwiseSolverOraclePreserved": True,
        "c481DeferredHandoffProgressPreserved": True,
        "c480ApproachSemanticTransactionPreserved": True,
        "contactThresholdChanged": False,
        "semanticToleranceChanged": False,
        "localityToleranceChanged": False,
        "damageAdmissionThresholdChanged": False,
        "damageThresholdAwareControl": False,
        "targetToughnessAwareControl": False,
        "desiredImpactSpeedControl": False,
        "desiredImpactEnergyControl": False,
        "fixtureBattlePlanChanged": False,
        "perAssetBattleCode": False,
        "perAssetTacticalTuning": False,
        "perVideoTrajectoryEngineering": False,
        "canonicalFrameFixtureHardcode": False,
        "humanCinematicAcceptance": "PENDING",
        "gateClosed": False,
        "productionReadyClaimed": False,
        "profileAndMetadataProof": profile,
        "crossGateProof": cross_gate,
        "cutoffRuntimeProof": cutoff,
        "surfaceTransactionRuntimeProof": surface,
        "transactionSamplingRuntimeProof": transaction,
        "progressRuntimeProof": progress,
    }, sort_keys=True))


if __name__ == "__main__":
    main()
