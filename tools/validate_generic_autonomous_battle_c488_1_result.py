#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
TOOLS = ROOT / "tools"
if str(ROOT) not in sys.path: sys.path.insert(0, str(ROOT))
if str(TOOLS) not in sys.path: sys.path.insert(0, str(TOOLS))

import validate_generic_autonomous_battle_c483_result as c483
from validate_generic_autonomous_battle_c480_result import _json_markers
from blender.iss_battle_runtime_precontact_realization_v1 import PRECONTACT_REALIZATION_MODEL

CANDIDATE = "ISS_GENERIC_BATTLE_RUNTIME_V1_CANDIDATE_4_8_8_1_GENERIC_AUTONOMOUS_BATTLE"


def _frame(row: dict[str, Any]) -> int:
    return int(row.get("frame") or -1)


def c488_1_runtime_proof(log_path: str) -> dict[str, object]:
    rows = _json_markers(log_path)
    ready = [r for r in rows if r.get("marker") == "GENERIC_AUTONOMOUS_BATTLE_C488_1_ENGINEERING_READY"]
    assert len(ready) == 1, ("C488_1_ENGINEERING_READY_COUNT", len(ready))
    receipt = ready[0]
    assert receipt.get("candidate") == CANDIDATE, receipt
    assert receipt.get("mechanism") == PRECONTACT_REALIZATION_MODEL, receipt
    assert receipt.get("affectedLayerAuditStatus") == "PASS", receipt
    for field in (
        "c488RejectedBySourceAudit","previousFrameOnlyEvidence","eventActorTargetScopedEvidence",
        "staleEvidenceRejected","recoveryEvidenceRejected","currentNonNegativeClosingRequired",
        "precontactOutsideExistingHandoffGapRequired","c487LifecyclePreserved",
        "c485CapabilityFloorPreserved","c484AlignmentSemanticsPreserved",
        "c465CutoffFrameStabilityPreserved","g05NativeSolverFinalAuthorityPreserved",
    ):
        assert receipt.get(field) is True, (field, receipt.get(field))
    for field in (
        "g05SourceChanged","g06SourceChanged","g07SourceChanged","g08SourceChanged",
        "g05ThresholdImported","contactThresholdChanged","semanticToleranceChanged",
        "localityToleranceChanged","damageAdmissionThresholdChanged","assetIdentityBranch",
        "perAssetBattleCode","perAssetTacticalTuning","perVideoTrajectoryEngineering",
        "fixedWorldCoordinates","exactCollisionFrameTarget","exactImpactEnergyTarget",
        "actorPoseOrVelocityMutation","fixtureBattlePlanChanged","frozenNineServiceArchitectureChanged",
        "gateClosed","productionReadyClaimed",
    ):
        assert receipt.get(field) is False, (field, receipt.get(field))
    assert receipt.get("runtimeFrameOrderVerified") == "PHYSICS_SAMPLE_THEN_G05_DETECT_THEN_G04_CONTROLS", receipt
    assert not any(r.get("marker") == "GENERIC_AUTONOMOUS_BATTLE_C488_ENGINEERING_READY" for r in rows), "SUPERSEDED_C488_EXECUTED"

    armed = [r for r in rows if r.get("marker") == "G04_PRECONTACT_REALIZATION_SAMPLE_ARMED"]
    carried = [r for r in rows if r.get("marker") == "G04_PRECONTACT_REALIZATION_CARRIED_TO_HANDOFF"]
    handoffs = [r for r in rows if r.get("marker") == "GENERIC_SOLVER_HANDOFF_LATCHED"]
    contacts = [r for r in rows if r.get("marker") == "PAIRWISE_NATIVE_SOLVER_CONTACT_VERIFIED"]
    assert armed and carried and handoffs and contacts

    armed_keys = {(str(r.get("eventId") or ""),str(r.get("attackerId") or ""),str(r.get("targetId") or ""),_frame(r)) for r in armed}
    valid: list[tuple[str,str,str]] = []
    for carry in carried:
        key=(str(carry.get("eventId") or ""),str(carry.get("attackerId") or ""),str(carry.get("targetId") or ""))
        assert all(key), carry
        assert carry.get("model") == PRECONTACT_REALIZATION_MODEL, carry
        frame=_frame(carry); evidence_frame=int(carry.get("evidenceFrame") or -1); age=int(carry.get("evidenceAgeFrames") or -1)
        assert age == 1 and evidence_frame == frame - 1, carry
        assert float(carry.get("currentClosingSpeedMps")) >= 0.0, carry
        assert float(carry.get("evidenceForwardSpeedMps")) >= float(carry.get("evidenceCapabilityFloorMps")), carry
        assert float(carry.get("evidenceClosingSpeedMps")) >= float(carry.get("evidenceCapabilityFloorMps")), carry
        assert (key[0],key[1],key[2],evidence_frame) in armed_keys, carry
        hs=[r for r in handoffs if str(r.get("eventId") or "")==key[0] and str(r.get("actorId") or "")==key[1] and _frame(r)>=frame]
        assert hs, ("NO_SAME_TRANSACTION_HANDOFF",key)
        hf=min(_frame(r) for r in hs); assert hf == frame, (key,frame,hf)
        ns=[r for r in contacts if str(r.get("eventId") or "")==key[0] and str(r.get("attackerId") or "")==key[1] and str(r.get("targetId") or "")==key[2] and _frame(r)>=hf]
        assert ns, ("NO_SAME_TRANSACTION_NATIVE_CONTACT",key,hf)
        valid.append(key)
    assert valid
    return {
        "precontactSampleRuntimeReceipt":"PASS",
        "previousFrameCarryRuntimeReceipt":"PASS",
        "sameTransactionCarryToHandoffToNativeContact":"PASS",
        "carriedTransactionCount":len(set(valid)),
        "currentNonNegativeClosingAtCarry":True,
        "supersededBroadC488NotExecuted":True,
    }


def main() -> None:
    p=argparse.ArgumentParser()
    p.add_argument("--base-request",required=True); p.add_argument("--hetero-request",required=True); p.add_argument("--asset-library-metadata",required=True)
    for key in ("battle","g06","g07","g08","log"): p.add_argument(f"--hetero-{key}",required=True)
    a=p.parse_args()
    base_req=c483.load(a.base_request); hetero_req=c483.load(a.hetero_request); ready_meta=c483.load(a.asset_library_metadata)
    profile=c483.profile_and_metadata_proof(base_req,hetero_req,ready_meta)
    g06=c483.load(a.hetero_g06); directions=c483.direction_proof(g06)
    cross_gate=c483.heterogeneous_cross_gate_proof("generic-hypercar-production-ready-heavy-asset",a.hetero_battle,a.hetero_g06,a.hetero_g07,a.hetero_g08)
    cutoff=c483._cutoff_runtime_proof(a.hetero_battle)
    surface=c483._surface_transaction_runtime_proof(a.hetero_log)
    transaction=c483._transaction_sampling_runtime_proof(a.hetero_log)
    progress=c483._progress_runtime_proof(a.hetero_log)
    approach=c483.approach_transaction_proof(a.hetero_log,a.hetero_g07)
    recovery=c483.deferred_handoff_recovery_proof(a.hetero_log)
    roles=c483.collision_role_runtime_proof(a.hetero_log)
    drive=c483.drive_direction_runtime_proof(a.hetero_log)
    proof=c488_1_runtime_proof(a.hetero_log)
    print(json.dumps({
        "marker":"GENERIC_AUTONOMOUS_BATTLE_C488_1_MACHINE_ACCEPTANCE","status":"PASS","candidate":CANDIDATE,
        "mechanism":PRECONTACT_REALIZATION_MODEL,"executionProfile":"NVIDIA_L4",
        "productionReadyHeavyAssetProof":"PASS","canonicalFrameMetadataProof":"PASS","heterogeneousActorProfileProof":"PASS",
        "sameRuntimeAcrossDissimilarActorProfiles":True,**directions,**approach,**recovery,**roles,**drive,**proof,
        "radialNavigationContractPreserved":"PASS","obbHandoffEligibilityPreserved":"PASS",
        "translationDominantHandoffEligibility":"PASS","tacticalGoalProgressRebase":"PASS",
        "collisionProxyProgressRefresh":"PASS","transactionBoundedLocalityWindow":"PASS",
        "livePairSurfaceSemanticSelection":"PASS","secondNativeContact":"PASS","damageThresholdSemantics":"PASS",
        "physicsThresholdDrivenDamageOutcome":"PASS","visibleCausalDamageDebris":"PASS","g07AdaptiveCausalDrama":"PASS",
        "g08MachineObservability":"PASS","nativeContactAuthorityPreserved":True,"pairwiseSolverOraclePreserved":True,
        "g05ThresholdImported":False,"contactThresholdChanged":False,"semanticToleranceChanged":False,
        "localityToleranceChanged":False,"damageAdmissionThresholdChanged":False,"fixtureBattlePlanChanged":False,
        "perAssetBattleCode":False,"perAssetTacticalTuning":False,"perVideoTrajectoryEngineering":False,
        "canonicalFrameFixtureHardcode":False,"humanCinematicAcceptance":"PENDING","gateClosed":False,"productionReadyClaimed":False,
        "profileAndMetadataProof":profile,"crossGateProof":cross_gate,"cutoffRuntimeProof":cutoff,
        "surfaceTransactionRuntimeProof":surface,"transactionSamplingRuntimeProof":transaction,"progressRuntimeProof":progress,
    },sort_keys=True))


if __name__ == "__main__": main()
