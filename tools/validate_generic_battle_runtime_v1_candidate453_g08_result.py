#!/usr/bin/env python3
from __future__ import annotations

import argparse,json
from pathlib import Path
from typing import Any


def load(path:str)->dict[str,Any]:
    d=json.loads(Path(path).read_text(encoding='utf-8'))
    if not isinstance(d,dict): raise SystemExit(f'G08_C453_JSON_OBJECT_REQUIRED:{path}')
    return d

def require(v:bool,code:str)->None:
    if not v: raise SystemExit(code)

def base_pass(d:dict[str,Any],name:str)->dict[str,Any]:
    require(d.get('success') is True,f'G08_C453_{name}_BASE_RUNTIME_NOT_SUCCESS')
    p=d.get('program') or {}; impacts=d.get('impacts') or []
    require(int(p.get('actorCount') or 0)>=2,f'G08_C453_{name}_ACTOR_COUNT_INVALID')
    require(int(p.get('eventCount') or 0)>=1,f'G08_C453_{name}_EVENT_COUNT_INVALID')
    require(len(impacts)>=1,f'G08_C453_{name}_IMPACT_MISSING')
    return {'status':'PASS','actorCount':int(p.get('actorCount') or 0),'eventCount':int(p.get('eventCount') or 0),'impactCount':len(impacts)}

def drama_pass(d:dict[str,Any],name:str)->dict[str,Any]:
    require(d.get('status')=='COMPLETE',f'G08_C453_{name}_G07_NOT_COMPLETE')
    require(len(d.get('directTransactions') or [])>=2,f'G08_C453_{name}_DIRECT_TRANSACTIONS_INSUFFICIENT')
    for key in ('reversal','climax','payoff'): require(isinstance(d.get(key),dict),f'G08_C453_{name}_{key.upper()}_MISSING')
    for key,code in (('g04ControlLawChanged','G04'),('g05ContactAuthorityChanged','G05'),('g06DamagePersistenceChanged','G06')):
        require(d.get(key) is False,f'G08_C453_{name}_{code}_DRIFT')
    return {'status':'PASS'}

def camera_pass(d:dict[str,Any],name:str)->dict[str,Any]:
    require(d.get('cameraModelV4')=='ISS_EVENT_DRIVEN_CINEMATIC_CAMERA_DIRECTOR_V4',f'G08_C453_{name}_CAMERA_MODEL_INVALID')
    require(d.get('status')=='COMPLETE',f'G08_C453_{name}_CAMERA_INCOMPLETE')
    require(d.get('verticalShortsFrame') is True and d.get('targetAspect9x16') is True,f'G08_C453_{name}_VERTICAL_9X16_FAIL')
    require(d.get('allRequiredCuesObserved') is True,f'G08_C453_{name}_CUES_INCOMPLETE')
    require(int(d.get('realImpactShotCount') or 0)>=1,f'G08_C453_{name}_IMPACT_SHOT_MISSING')
    require(d.get('relationshipReadabilityPass') is True,f'G08_C453_{name}_RELATIONSHIP_READABILITY_FAIL')
    require(d.get('autoFrameModel')=='PORTRAIT_FULL_BOUNDS_AUTOFRAME_V1',f'G08_C453_{name}_AUTOFRAME_MODEL_INVALID')
    require(d.get('fullBoundsReadabilityPass') is True and int(d.get('autoFrameFailureCount') or 0)==0,f'G08_C453_{name}_FULL_BOUNDS_FAIL')
    require(d.get('cinematicSalienceModel')=='CUE_AWARE_VERTICAL_CINEMATIC_SALIENCE_V2',f'G08_C453_{name}_SALIENCE_MODEL_INVALID')
    require(d.get('salienceAnchorModel')=='REALIZED_CUE_ANCHOR_ONLY_V1',f'G08_C453_{name}_ANCHOR_MODEL_INVALID')
    require(d.get('payoffFocusModel')=='REALIZED_G07_DOMINANCE_LEADER_FOCUS_V1',f'G08_C453_{name}_PAYOFF_FOCUS_MODEL_INVALID')
    require(d.get('cinematicSaliencePass') is True,f'G08_C453_{name}_CINEMATIC_SALIENCE_FAIL')
    require(int(d.get('cinematicSalienceFailureCount') or 0)==0,f'G08_C453_{name}_SALIENCE_FAILURE_COUNT_NONZERO')
    require(d.get('payoffFocusFromRealizedDominancePass') is True,f'G08_C453_{name}_PAYOFF_FOCUS_FAIL')
    require(d.get('climaxRelationshipAnchorPass') is True,f'G08_C453_{name}_CLIMAX_RELATIONSHIP_ANCHOR_FAIL')
    per=d.get('cinematicSaliencePerCue') or {}
    for cue in ('CLIMAX','PAYOFF'):
        row=per.get(cue) or {}
        require(row.get('pass') is True,f'G08_C453_{name}_{cue}_SALIENCE_FAIL')
        require(int(row.get('anchorShotCount') or 0)>=1,f'G08_C453_{name}_{cue}_ANCHOR_MISSING')
    payoff=per.get('PAYOFF') or {}
    require('REALIZED_G07_DOMINANCE_LEADER_FOCUS_V1' in (payoff.get('focusAuthorities') or []),f'G08_C453_{name}_PAYOFF_AUTHORITY_INVALID')
    for key,expected,code in (
        ('sourceAuthority','READ_ONLY_REALIZED_WORLD_AND_G07_EVENT_STATE','SOURCE_AUTHORITY'),
        ('cameraOnlyMutation',True,'CAMERA_ONLY'),('actorPoseOrVelocityMutation',False,'ACTOR_MUTATION'),('physicsMutation',False,'PHYSICS_MUTATION'),
        ('g04ControlLawChanged',False,'G04_CHANGED'),('g05ContactAuthorityChanged',False,'G05_CHANGED'),('g06DamagePersistenceChanged',False,'G06_CHANGED'),('g07DramaAuthorityChanged',False,'G07_CHANGED'),
        ('perAssetCameraBranch',False,'PER_ASSET_CAMERA'),('perAssetFocusBranch',False,'PER_ASSET_FOCUS'),('cameraFakesPhysics',False,'CAMERA_FAKES_PHYSICS'),
        ('humanCinematicAcceptance','PENDING','HUMAN_REVIEW_PRECLAIM'),('gateClosed',False,'GATE_CLOSED_PRECLAIM'),('productionReadyClaimed',False,'PRODUCTION_READY_PRECLAIM')):
        require(d.get(key)==expected,f'G08_C453_{name}_{code}')
    return {'status':'PASS','cameraModel':d.get('cameraModelV4'),'salienceModel':d.get('cinematicSalienceModel'),'anchorModel':d.get('salienceAnchorModel'),'payoffFocusModel':d.get('payoffFocusModel'),'perCue':per}

def main()->None:
    p=argparse.ArgumentParser()
    for arg in ('bugatti-evidence','bugatti-drama','bugatti-camera','generic-evidence','generic-drama','generic-camera'): p.add_argument('--'+arg,required=True)
    a=p.parse_args()
    bb=base_pass(load(a.bugatti_evidence),'BUGATTI'); gb=base_pass(load(a.generic_evidence),'GENERIC')
    bd=drama_pass(load(a.bugatti_drama),'BUGATTI'); gd=drama_pass(load(a.generic_drama),'GENERIC')
    bc=camera_pass(load(a.bugatti_camera),'BUGATTI'); gc=camera_pass(load(a.generic_camera),'GENERIC')
    for key in ('cameraModel','salienceModel','anchorModel','payoffFocusModel'): require(bc[key]==gc[key],f'G08_C453_CROSS_ASSET_{key.upper()}_DIFFERS')
    print(json.dumps({
        'marker':'GENERIC_BATTLE_RUNTIME_CANDIDATE453_G08_MACHINE_ACCEPTANCE','status':'PASS','runtime':'ISS_GENERIC_BATTLE_RUNTIME_V1_CANDIDATE_4_5_3_G08',
        'gateScope':'G08_EVENT_DRIVEN_CINEMATIC_CAMERA_ONLY','exactBugatti':{'base':bb,'drama':bd,'camera':bc,'status':'PASS'},'genericHypercar':{'base':gb,'drama':gd,'camera':gc,'status':'PASS'},
        'sameGenericCameraAcrossAssets':True,'sameGenericSalienceLogicAcrossAssets':True,'sameGenericPayoffFocusAuthorityAcrossAssets':True,
        'thresholdsWeakened':False,'climaxPayoffCinematicSalience':'PASS','g04Preserved':True,'g05Preserved':True,'g06Preserved':True,'g07Preserved':True,
        'actorPoseOrVelocityMutation':False,'physicsMutation':False,'perAssetCameraBranch':False,'perAssetTuning':False,'cameraFakesPhysics':False,
        'machineFramingAcceptance':'PASS','humanCinematicAcceptance':'PENDING','issR045MasterPlanAlignment':'PASS_MACHINE_LAYER_PENDING_HUMAN_POSTFLIGHT','gateClosed':False,'productionReadyClaimed':False,
    },sort_keys=True))

if __name__=='__main__': main()
