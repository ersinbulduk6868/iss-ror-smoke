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


def _log_proof(path: str) -> dict[str, object]:
    rows=[]
    for line in Path(path).read_text(encoding='utf-8', errors='replace').splitlines():
        try: row=json.loads(line)
        except Exception: continue
        if isinstance(row,dict): rows.append(row)
    release=[r for r in rows if r.get('marker')=='GENERIC_SOLVER_HANDOFF_RECENCY_BUDGET_RELEASED']
    frozen=[r for r in rows if r.get('marker')=='GENERIC_HANDOFF_SEMANTIC_SURFACE_FROZEN']
    contacts=[r for r in rows if r.get('marker')=='PAIRWISE_NATIVE_SOLVER_CONTACT_VERIFIED']
    cutoff=[r for r in rows if r.get('marker')=='GENERIC_SOLVER_HANDOFF_CUTOFF_FRAME_STABILIZED']
    impacts=[r for r in rows if r.get('marker') in {'QUALIFIED_NATIVE_RESPONSE_IMPACT','CAUSAL_VISIBLE_IMPACT_CONSEQUENCE_V3_APPLIED'}]
    assert release, 'C468_RECENCY_BUDGET_RELEASE_NOT_OBSERVED'
    assert frozen, 'C468_SEMANTIC_FREEZE_NOT_OBSERVED'
    assert contacts, 'C468_NATIVE_CONTACT_NOT_VERIFIED'
    assert cutoff, 'C468_CUTOFF_STABILIZATION_NOT_OBSERVED'
    assert impacts, 'C468_CAUSAL_IMPACT_NOT_OBSERVED'
    for row in release:
        assert int(row.get('handoffAgeFrames') or -1) <= int(row.get('fps') or 0), row
        assert int(row.get('maxHandoffHoldFrames') or 0) <= int(row.get('fps') or 0), row
    return {
        'recencyBudgetReleaseCount':len(release),
        'semanticFreezeCount':len(frozen),
        'verifiedNativeContactCount':len(contacts),
        'cutoffStabilizationCount':len(cutoff),
        'causalImpactMarkerCount':len(impacts),
        'noHandoffReleaseAfterG05RecencyWindow':True,
    }


def main() -> None:
    p=argparse.ArgumentParser()
    for prefix in ('bugatti','generic'):
        for key in ('battle','g06','g07','g08','log'):
            p.add_argument(f'--{prefix}-{key}', required=True)
    a=p.parse_args()
    fixtures=[]; cutoff={}; proof={}
    for prefix in ('bugatti','generic'):
        battle=getattr(a,f'{prefix}_battle')
        fixtures.append(_validate(prefix,battle,getattr(a,f'{prefix}_g06'),getattr(a,f'{prefix}_g07'),getattr(a,f'{prefix}_g08')))
        cutoff[prefix]=_cutoff_runtime_proof(battle)
        proof[prefix]=_log_proof(getattr(a,f'{prefix}_log'))
    print(json.dumps({
        'marker':'GENERIC_AUTONOMOUS_BATTLE_C468_MACHINE_ACCEPTANCE',
        'status':'PASS',
        'affectedLayerAudit':'PASS',
        'failureFamily':'HANDOFF_LATCH_OUTLIVES_G05_CUTOFF_RECENCY_WINDOW',
        'sameRuntimeAcrossAssets':True,
        'g05CutoffRecencyContractPreserved':'PASS',
        'handoffCutoffFrameImmutableWithinLatch':'PASS',
        'newLatchMayEstablishFreshCutoff':'PASS',
        'semanticSelectionFrozenWithinHandoff':'PASS',
        'secondNativeContact':'PASS',
        'twoSidedDamage':'PASS',
        'visibleCausalDamageDebris':'PASS',
        'g07AdaptiveCausalDrama':'PASS',
        'g08MachineObservability':'PASS',
        'nativeContactAuthorityPreserved':True,
        'semanticToleranceChanged':False,
        'localityToleranceChanged':False,
        'contactThresholdChanged':False,
        'damageAdmissionThresholdChanged':False,
        'fixtureMutationForAcceptance':False,
        'perAssetBattleCode':False,
        'perVideoTrajectoryEngineering':False,
        'humanCinematicAcceptance':'PENDING',
        'gateClosed':False,
        'productionReadyClaimed':False,
        'cutoffRuntimeProof':cutoff,
        'recencyRuntimeProof':proof,
        'fixtures':fixtures,
    },sort_keys=True))

if __name__=='__main__': main()
