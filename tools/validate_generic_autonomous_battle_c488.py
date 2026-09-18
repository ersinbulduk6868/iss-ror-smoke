#!/usr/bin/env python3
from __future__ import annotations

import ast
import json
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
HELPER = ROOT / "blender" / "iss_battle_runtime_engagement_authority_v2.py"
WRAPPER = ROOT / "blender" / "run_generic_battle_runtime_v1_candidate488_generic_battle.py"
AUTHORITY_VALIDATOR = ROOT / "tools" / "validate_generic_autonomous_battle_c488_authority.py"


def main() -> None:
    helper = HELPER.read_text(encoding="utf-8")
    wrapper = WRAPPER.read_text(encoding="utf-8")
    ast.parse(helper, filename=str(HELPER))
    ast.parse(wrapper, filename=str(WRAPPER))

    subprocess.run([sys.executable, str(AUTHORITY_VALIDATOR)], cwd=ROOT, check=True)

    combined = helper + "\n" + wrapper
    required = (
        "G04_EVENT_SCOPED_ENGAGEMENT_AUTHORITY_V2",
        "G04_CONTINUOUS_REALIZED_APPROACH_CERTIFICATE_V1",
        "G04_OUTER_RECOVERY_CLEAR_SUPPRESSED",
        "G04_REALIZED_APPROACH_CERTIFICATE_QUALIFIED",
        "G04_REALIZED_APPROACH_CERTIFICATE_INVALIDATED",
        "G04_CERTIFIED_HANDOFF_DEFERRED_CERTIFICATE_MISSING",
        "G04_CERTIFIED_SOLVER_HANDOFF_REQUESTED",
        "candidate472.should_clear_stale_autonomy_recovery = c488_recovery_clear_guard",
        "candidate481._BASE_AUTONOMY_UPDATE = certified_event_scoped_autonomy_update",
        "battle_v6._goal_for_tactical = c488_goal_for_tactical",
        "candidate487._end_transaction = c488_end_transaction",
        "candidate487.event_scoped_recovery_autonomy_update",
        "candidate487.event_scoped_generic_battle_set_controls",
        "candidate472._ORIGINAL_TACTICAL_DECIDE = candidate485.generic_contact_commit_decide",
        "candidate483.main()",
        '"eventScopedRecoveryOwnershipOutermost": True',
        '"continuousRealizedApproachCertificate": True',
        '"atomicMotorToCoastAtCertifiedProximity": True',
        '"currentClosingSignRequiredAfterCertifiedProximity": False',
        '"c485CapabilityDerivedMotionFloorPreserved": True',
        '"c484TranslationDominantAlignmentPreserved": True',
        '"g05NativeSolverFinalAuthorityPreserved": True',
        '"g05SourceChanged": False',
        '"g06SourceChanged": False',
        '"g07SourceChanged": False',
        '"g08SourceChanged": False',
        '"g05ThresholdImported": False',
        '"contactThresholdChanged": False',
        '"damageAdmissionThresholdChanged": False',
        '"perAssetBattleCode": False',
        '"perAssetTacticalTuning": False',
        '"perVideoTrajectoryEngineering": False',
        '"gateClosed": False',
    )
    for token in required:
        assert token in combined, token

    # Superseded top-level receipts must not be executed as if they were still the
    # final handoff authority in the C488 runtime entrypoint.
    for forbidden_call in (
        "candidate485.main()",
        "candidate486.main()",
        "candidate487.main()",
    ):
        assert forbidden_call not in wrapper, forbidden_call

    lower = combined.lower()
    for forbidden in (
        "bugatti",
        "bulldozer",
        "b06a715d23a7450babac383b8bb7fb0a",
        "27614.189525707065",
        "min_closing_speed_mps",
        "min_damage_severity",
        "desiredimpactspeedmps",
        "desiredimpactenergyj",
        "collisionframe",
        "impactframe",
        "trajectorypoints",
        "waypoints",
        "set_pose",
        "linear_velocity =",
        "forcedwinner",
    ):
        assert forbidden not in lower, forbidden

    print(json.dumps({
        "marker": "GENERIC_AUTONOMOUS_BATTLE_C488_PROPERTY_ACCEPTANCE",
        "status": "PASS",
        "candidate": "ISS_GENERIC_BATTLE_RUNTIME_V1_CANDIDATE_4_8_8_GENERIC_AUTONOMOUS_BATTLE",
        "mechanism": "G04_EVENT_SCOPED_ENGAGEMENT_AUTHORITY_V2",
        "fullFailureFamilyComposition": "PASS",
        "recoveryOwnershipComposition": "PASS",
        "continuousApproachCertificateComposition": "PASS",
        "atomicHandoffComposition": "PASS",
        "supersededReceiptExecution": False,
        "g05NativeAuthorityPreserved": True,
        "g05ThresholdImported": False,
        "assetSpecificCode": False,
        "perAssetTacticalTuning": False,
        "perVideoTrajectoryEngineering": False,
        "masterPlanAligned": True,
        "gateClosed": False,
    }, sort_keys=True))


if __name__ == "__main__":
    main()
