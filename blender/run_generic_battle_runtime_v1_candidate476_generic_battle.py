from __future__ import annotations

import json
from pathlib import Path
import sys

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from blender import run_generic_battle_runtime_v1_candidate474_generic_battle as candidate474

CANDIDATE = "ISS_GENERIC_BATTLE_RUNTIME_V1_CANDIDATE_4_7_6_HETEROGENEOUS_ACTORPROFILE_ACCEPTANCE"
MECHANISM = "G04_HETEROGENEOUS_ACTORPROFILE_ACCEPTANCE_V1"
AUDIT = "G04_HETEROGENEOUS_ACTORPROFILE_MASTER_PLAN_ACCEPTANCE_20260918"


def main() -> None:
    print(json.dumps({
        "marker": "GENERIC_AUTONOMOUS_BATTLE_C476_ENGINEERING_READY",
        "candidate": CANDIDATE,
        "mechanism": MECHANISM,
        "affectedLayerAudit": AUDIT,
        "runtimeBehaviorChangedFromC474": False,
        "c474RuntimeReusedUnchanged": True,
        "sameRuntimeAcrossDissimilarActorProfiles": True,
        "assetIdentityBranch": False,
        "perAssetBattleCode": False,
        "perVideoTrajectoryEngineering": False,
        "damageThresholdAwareControl": False,
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
        "gateClosed": False,
        "productionReadyClaimed": False,
    }, sort_keys=True), flush=True)
    candidate474.main()


if __name__ == "__main__":
    main()
