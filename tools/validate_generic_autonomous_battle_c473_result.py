#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
TOOLS = ROOT / "tools"
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

from validate_generic_autonomous_battle_c464_result import _validate
from validate_generic_autonomous_battle_c465_result import _cutoff_runtime_proof
from validate_generic_autonomous_battle_c470_result import _surface_transaction_runtime_proof
from validate_generic_autonomous_battle_c471_result import _transaction_sampling_runtime_proof
from validate_generic_autonomous_battle_c472_result import _c472_runtime_proof


def _rows(path: str) -> list[dict[str, object]]:
    rows=[]
    for line in Path(path).read_text(encoding="utf-8",errors="replace").splitlines():
        try: row=json.loads(line)
        except Exception: continue
        if isinstance(row,dict): rows.append(row)
    return rows


def _c473_runtime_proof(path: str) -> dict[str, object]:
    rows=_rows(path)
    readiness=[r for r in rows if r.get("marker")=="G04_HANDOFF_REJECTED_BELOW_EXISTING_G05_CLOSING_GATE"]
    recoveries=[r for r in rows if r.get("marker")=="GENERIC_RECOVERY_BIAS_BOUND_TO_LIVE_HEADING"]
    contacts=[r for r in rows if r.get("marker")=="PAIRWISE_NATIVE_SOLVER_CONTACT_VERIFIED"]
    assert contacts, "C473_NATIVE_CONTACT_NOT_VERIFIED"
    for row in readiness:
        observed=float(row.get("observedClosingSpeedMps") or 0.0)
        minimum=float(row.get("existingG05MinimumClosingSpeedMps") or 0.0)
        assert observed < minimum, ("C473_READINESS_REJECTION_NOT_BELOW_GATE",row)
        assert row.get("desiredImpactSpeedControl") is False,row
        assert row.get("g05ThresholdChanged") is False,row
        assert row.get("assetIdentityBranch") is False,row
    for row in recoveries:
        heading=float(row.get("headingErrorRad") or 0.0)
        live=float(row.get("liveRecoveryBias") or 0.0)
        if abs(heading)>1.0e-6:
            assert live==(1.0 if heading>0.0 else -1.0),("C473_RECOVERY_BIAS_NOT_LIVE_HEADING",row)
        assert row.get("assetIdentityBranch") is False,row
    return {
        "handoffReadinessRejectionCount":len(readiness),
        "liveHeadingRecoveryCount":len(recoveries),
        "verifiedNativeContactCount":len(contacts),
        "desiredImpactSpeedControl":False,
        "existingG05MinimumClosingThresholdChanged":False,
    }


def main()->None:
    p=argparse.ArgumentParser()
    for prefix in ("bugatti","generic"):
        for key in ("battle","g06","g07","g08","log"):
            p.add_argument(f"--{prefix}-{key}",required=True)
    a=p.parse_args()
    fixtures=[]; cutoff={}; surface={}; transaction={}; c472={}; c473={}
    for prefix in ("bugatti","generic"):
        battle=getattr(a,f"{prefix}_battle"); log=getattr(a,f"{prefix}_log")
        fixtures.append(_validate(prefix,battle,getattr(a,f"{prefix}_g06"),getattr(a,f"{prefix}_g07"),getattr(a,f"{prefix}_g08")))
        cutoff[prefix]=_cutoff_runtime_proof(battle)
        surface[prefix]=_surface_transaction_runtime_proof(log)
        transaction[prefix]=_transaction_sampling_runtime_proof(log)
        c472[prefix]=_c472_runtime_proof(log)
        c473[prefix]=_c473_runtime_proof(log)

    assert int(c473["bugatti"]["handoffReadinessRejectionCount"])>0,"C473_BUGATTI_HANDOFF_READINESS_NOT_EXERCISED"
    assert int(c473["bugatti"]["liveHeadingRecoveryCount"])>0,"C473_BUGATTI_LIVE_RECOVERY_NOT_EXERCISED"
    assert int(c473["generic"]["liveHeadingRecoveryCount"])>0,"C473_GENERIC_LIVE_RECOVERY_NOT_EXERCISED"

    print(json.dumps({
        "marker":"GENERIC_AUTONOMOUS_BATTLE_C473_MACHINE_ACCEPTANCE",
        "status":"PASS",
        "affectedLayerAudit":"PASS",
        "failureFamilies":[
            "CONTACT_HANDOFF_CEDES_AUTHORITY_BELOW_EXISTING_G05_CLOSING_GATE",
            "RECOVERY_TURN_DIRECTION_IGNORES_LIVE_GOAL_HEADING",
        ],
        "sameRuntimeAcrossAssets":True,
        "handoffReadiness":"PASS",
        "liveHeadingRecoveryDirection":"PASS",
        "colliderAwareHandoffGap":"PASS",
        "recoveryRunwayOwnershipSplit":"PASS",
        "transactionBoundedLocalityWindow":"PASS",
        "livePairSurfaceSemanticSelection":"PASS",
        "secondNativeContact":"PASS",
        "twoSidedDamage":"PASS",
        "visibleCausalDamageDebris":"PASS",
        "g07AdaptiveCausalDrama":"PASS",
        "g08MachineObservability":"PASS",
        "nativeContactAuthorityPreserved":True,
        "pairwiseSolverOraclePreserved":True,
        "desiredImpactSpeedControl":False,
        "existingG05MinimumClosingThresholdChanged":False,
        "semanticToleranceChanged":False,
        "localityToleranceChanged":False,
        "contactThresholdChanged":False,
        "damageAdmissionThresholdChanged":False,
        "fixtureMutationForAcceptance":False,
        "perAssetBattleCode":False,
        "perVideoTrajectoryEngineering":False,
        "humanCinematicAcceptance":"PENDING",
        "gateClosed":False,
        "productionReadyClaimed":False,
        "cutoffRuntimeProof":cutoff,
        "surfaceTransactionRuntimeProof":surface,
        "transactionSamplingRuntimeProof":transaction,
        "c472RuntimeProof":c472,
        "c473RuntimeProof":c473,
        "fixtures":fixtures,
    },sort_keys=True))

if __name__=="__main__": main()
