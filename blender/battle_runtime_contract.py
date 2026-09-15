from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any, Iterable, Mapping, Optional, Sequence, Tuple, List
import math, re

RUNTIME_CONTRACT = 'iss-generic-battle-runtime-v1'
SUPPORTED_COMMANDS = {
    'HOLD','ACCELERATE','BRAKE','REVERSE','RAM','FLANK_LEFT','FLANK_RIGHT',
    'EVADE','REGROUP','PRESSURE','SETTLE'
}

class ContractError(RuntimeError):
    pass

def norm(v: Any) -> str:
    return re.sub(r'[^a-z0-9]+','_',str(v or '').lower()).strip('_')

@dataclass(frozen=True)
class TargetSpec:
    entity_id: Optional[str]
    region: Optional[str]

@dataclass(frozen=True)
class RuntimeCommand:
    event_id: str
    actor_id: str
    command: str
    start_time: float
    end_time: float
    target: TargetSpec
    speed_intent: str = ''
    trajectory_intent: str = ''
    momentum_intent: str = ''
    structural_response: str = ''
    phase: str = ''
    caused_by: Tuple[str, ...] = ()
    damage_required: bool = False
    persistent_damage: bool = False
    metadata: Mapping[str, Any] = field(default_factory=dict)

def parse_attack_target(value: Any) -> TargetSpec:
    raw = str(value or '').strip()
    if not raw or norm(raw) in {'none','null'}:
        return TargetSpec(None,None)
    entity, sep, region = raw.partition(':')
    return TargetSpec(entity.strip() or None, norm(region) if sep and region.strip() else None)

def _damage(event: Mapping[str,Any]) -> tuple[bool,bool,Optional[str]]:
    d = event.get('damage')
    if isinstance(d, Mapping):
        return bool(d.get('required')), bool(d.get('persistent')), norm(d.get('zone')) or None
    if isinstance(d, Sequence) and not isinstance(d,(str,bytes)):
        req=pers=False; zone=None
        for row in d:
            if not isinstance(row, Mapping): continue
            if row.get('stateChanges'): req=pers=True
            zone = zone or norm(row.get('zone')) or None
        return req,pers,zone
    return False,False,None

def _infer(event: Mapping[str,Any], target: TargetSpec) -> str:
    req = event.get('physicsRequirements') or {}
    text = '_'.join(filter(None,[norm(event.get('type')),norm(event.get('phase')),norm(req.get('trajectory')),norm(req.get('speedIntent')),norm(event.get('tacticalPurpose')),norm(event.get('action'))]))
    if any(x in text for x in ('payoff','outcome','settle')): return 'SETTLE'
    if 'reverse' in text: return 'REVERSE'
    if any(x in text for x in ('brake','deceler')): return 'BRAKE'
    if any(x in text for x in ('evade','avoid')): return 'EVADE'
    if 'regroup' in text: return 'REGROUP'
    if 'flank' in text: return 'FLANK_RIGHT' if 'right' in text else 'FLANK_LEFT'
    if 'pressure' in text: return 'PRESSURE'
    if target.entity_id: return 'RAM'
    if norm(req.get('speedIntent')) in {'accelerate','sustain'}: return 'ACCELERATE'
    return 'HOLD'

def validate_request(request: Mapping[str,Any]) -> None:
    engine = str(request.get('engine') or 'BLENDER').upper()
    if engine != 'BLENDER': raise ContractError('ENGINE_MUST_BE_BLENDER')
    p = request.get('executionPolicy') or {}
    for k in ('continuousWorld','persistentDamage','persistentDebris'):
        if p.get(k) is not True: raise ContractError(f'EXECUTION_POLICY_REQUIRED_TRUE:{k}')
    for k in ('resetAllowed','teleportAllowed','silentSimplificationAllowed','forcedTransformAfterContactAllowed','velocityInjectionAfterContactAllowed'):
        if p.get(k) is True: raise ContractError(f'EXECUTION_POLICY_FORBIDDEN_TRUE:{k}')
    events = (request.get('battlePlan') or {}).get('events') or []
    if not events: raise ContractError('BATTLE_EVENTS_REQUIRED')
    seen=set()
    for i,e in enumerate(events):
        if not isinstance(e,Mapping): raise ContractError(f'EVENT_NOT_OBJECT:{i}')
        eid=str(e.get('eventId') or '').strip()
        if not eid: raise ContractError(f'EVENT_ID_REQUIRED:{i}')
        if eid in seen: raise ContractError(f'EVENT_ID_DUPLICATE:{eid}')
        try: st=float(e.get('startTime')); en=float(e.get('endTime'))
        except Exception as ex: raise ContractError(f'EVENT_TIME_INVALID:{eid}') from ex
        if not all(math.isfinite(x) for x in (st,en)) or st<0 or en<=st: raise ContractError(f'EVENT_TIME_RANGE_INVALID:{eid}')
        actors=e.get('actors') or []
        if not isinstance(actors,Sequence) or isinstance(actors,(str,bytes)) or not actors: raise ContractError(f'EVENT_ACTORS_REQUIRED:{eid}')
        for dep in e.get('causedByEventIds') or []:
            if dep not in seen: raise ContractError(f'EVENT_DEPENDENCY_NOT_PRIOR:{eid}:{dep}')
        seen.add(eid)

def compile_commands(request: Mapping[str,Any], actor_ids: Iterable[str]) -> List[RuntimeCommand]:
    validate_request(request)
    aset={str(x) for x in actor_ids}
    out=[]
    for e in (request.get('battlePlan') or {}).get('events') or []:
        eid=str(e['eventId']); target=parse_attack_target(e.get('attackTarget'))
        if target.entity_id and target.entity_id not in aset: raise ContractError(f'TARGET_ACTOR_MISSING:{eid}:{target.entity_id}')
        required,persistent,zone=_damage(e)
        if zone and not target.region: target=TargetSpec(target.entity_id,zone)
        req=e.get('physicsRequirements') or {}; cmd=_infer(e,target)
        if cmd not in SUPPORTED_COMMANDS: raise ContractError(f'UNSUPPORTED_COMMAND:{cmd}')
        for actor in [str(x) for x in (e.get('actors') or [])]:
            if actor not in aset: raise ContractError(f'EVENT_ACTOR_MISSING:{eid}:{actor}')
            if target.entity_id and actor==target.entity_id: continue
            out.append(RuntimeCommand(
                eid,actor,cmd,float(e['startTime']),float(e['endTime']),target,
                norm(req.get('speedIntent')),norm(req.get('trajectory')),norm(req.get('momentumIntent')),norm(req.get('structuralResponse')),
                norm(e.get('phase')),tuple(str(x) for x in (e.get('causedByEventIds') or [])),required,persistent,
                {'eventType':str(e.get('type') or ''),'requiredOutcome':str(e.get('requiredOutcome') or ''),'tacticalPurpose':str(e.get('tacticalPurpose') or '')}
            ))
    return sorted(out,key=lambda c:(c.start_time,c.end_time,c.event_id,c.actor_id))

def selftest() -> dict:
    req={'engine':'BLENDER','executionPolicy':{'continuousWorld':True,'persistentDamage':True,'persistentDebris':True,'resetAllowed':False,'teleportAllowed':False,'silentSimplificationAllowed':False,'forcedTransformAfterContactAllowed':False,'velocityInjectionAfterContactAllowed':False},'battlePlan':{'events':[
        {'eventId':'e1','type':'BATTLE_HOOK','phase':'HOOK','startTime':0,'endTime':1,'actors':['alpha','beta'],'causedByEventIds':[],'physicsRequirements':{'speedIntent':'hold'}},
        {'eventId':'e2','type':'COORDINATED_ATTACK','phase':'FIRST_ATTACK','startTime':1,'endTime':4,'actors':['alpha'],'attackTarget':'beta:front','causedByEventIds':['e1'],'damage':{'required':True,'persistent':True,'zone':'front'},'physicsRequirements':{'speedIntent':'accelerate','trajectory':'direct approach'}},
        {'eventId':'e3','type':'OUTCOME','phase':'PAYOFF','startTime':4,'endTime':5,'actors':['alpha','beta'],'causedByEventIds':['e2'],'physicsRequirements':{'speedIntent':'settle'}}]}}
    c=compile_commands(req,['alpha','beta'])
    assert any(x.command=='RAM' and x.target.entity_id=='beta' and x.target.region=='front' for x in c)
    assert any(x.command=='SETTLE' for x in c)
    bad=dict(req); bad['executionPolicy']=dict(req['executionPolicy']); bad['executionPolicy']['teleportAllowed']=True
    try: validate_request(bad); raise AssertionError('teleport policy not rejected')
    except ContractError: pass
    return {'status':'PASS','commands':len(c),'contract':RUNTIME_CONTRACT}

if __name__=='__main__': print(selftest())
