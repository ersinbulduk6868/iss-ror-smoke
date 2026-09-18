from __future__ import annotations

import json
from pathlib import Path
import sys

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from blender import run_generic_battle_runtime_v1_candidate474_generic_battle as candidate474

CANDIDATE = "ISS_GENERIC_BATTLE_RUNTIME_V1_CANDIDATE_4_7_9_ASSET_METADATA_CANONICAL_FRAME_ACCEPTANCE"
MECHANISM = "G04_ASSET_METADATA_CANONICAL_FRAME_INTEGRATION_V1"
AUDIT = "G04_CANONICAL_FRAME_ASSET_METADATA_FULL_AFFECTED_LAYER_AUDIT_20260918"


def main() -> None:
    print(json.dumps({
        "marker": "GENERIC_AUTONOMOUS_BATTLE_C479_ENGINEERING_READY",
        "candidate": CANDIDATE,
        "mechanism": MECHANISM,
        "affectedLayerAudit": AUDIT,
        "runtimeBehaviorChangedFromC474": False,
        "c474RuntimeReusedUnchanged": True,
        "canonicalFrameAuthority": "ISS_ASSET_READY_LIBRARY_METADATA",
        "canonicalFrameFixtureHardcode": False,
        "acceptanceExecutionProfile": "NVIDIA_L4",
        "sameRuntimeAcrossDissimilarActorProfiles": True,
        "assetIdentityBranch": False,
        "perAssetBattleCode": False,
        "perVideoTrajectoryEngineering": False,
        "damageThresholdAwareControl": False,
        "targetToughnessAwareControl": False,
        "desiredImpactSpeedControl": False,
        "desiredImpactEnergyControl": False,
        "fixedWorldCoordinates": False,
        "exactCollisionFrameTarget": False,
        "actorPoseOrVelocityMutation": False,
        "g05NativeSolverFinalAuthorityPreserved": True,
        "pairwiseSolverOraclePreserved": True,
        "contactThresholdChanged": False,
        "damageAdmissionThresholdChanged": False,
        "fixtureBattlePlanChanged": False,
        "g01ToG03Changed": False,
        "frozenNineServiceArchitectureChanged": False,
        "gateClosed": False,
        "productionReadyClaimed": False,
    }, sort_keys=True), flush=True)
    candidate474.main()


if __name__ == "__main__":
    main()
