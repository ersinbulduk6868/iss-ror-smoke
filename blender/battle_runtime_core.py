from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any, Dict, Mapping, Optional, Sequence, Tuple, List
import math

EPS=1e-9

def clamp(v,lo,hi): return max(lo,min(hi,v))
def wrap_pi(a):
    while a>math.pi: a-=2*math.pi
    while a<-math.pi: a+=2*math.pi
    return a

@dataclass(frozen=True)
class V2:
    x: float; y: float
    def __add__(self,o): return V2(self.x+o.x,self.y+o.y)
    def __sub__(self,o): return V2(self.x-o.x,self.y-o.y)
    def __mul__(self,s): return V2(self.x*s,self.y*s)
    __rmul__=__mul__
    def __truediv__(self,s): return V2(self.x/s,self.y/s)
    def dot(self,o): return self.x*o.x+self.y*o.y
    @property
    def length(self): return math.hypot(self.x,self.y)
    def normalized(self,fallback=None): return self/self.length if self.length>EPS else (fallback or V2(1,0))
    def rotated(self,a):
        c,s=math.cos(a),math.sin(a); return V2(c*self.x-s*self.y,s*self.x+c*self.y)
    def perp_left(self): return V2(-self.y,self.x)

@dataclass(frozen=True)
class ActorProfile:
    entity_id:str; mass_kg:float; radius_m:float; length_m:float; width_m:float
    max_forward_speed_mps:float; max_reverse_speed_mps:float; max_accel_mps2:float; max_brake_mps2:float
    max_yaw_rate_rad_s:float; drive_impulse_per_frame:float; brake_impulse_per_frame:float; yaw_impulse_per_frame:float
    controller_cutoff_m:float; impact_damage_threshold_j:float; severe_damage_energy_j:float; disable_damage:float
    region_offsets:Mapping[str,Tuple[float,float]]=field(default_factory=dict)

@dataclass
class ActorState:
    entity_id:str; position:V2; velocity:V2; heading_rad:float; angular_velocity_rad_s:float=0
    region_damage:Dict[str,float]=field(default_factory=dict); total_damage:float=0; mobility:float=1; disabled:bool=False
    contact_count:int=0; last_contact_time:Optional[float]=None; stalled_seconds:float=0
    @property
    def speed(self): return self.velocity.length
    @property
    def forward(self): return V2(math.cos(self.heading_rad),math.sin(self.heading_rad))

@dataclass(frozen=True)
class PlannerCommand:
    event_id:str; actor_id:str; command:str; start_time:float; end_time:float
    target_entity_id:Optional[str]=None; target_region:Optional[str]=None; speed_intent:str=''; caused_by:Tuple[str,...]=(); damage_required:bool=False

@dataclass(frozen=True)
class ControlIntent:
    actor_id:str; event_id:str; command:str; target_entity_id:Optional[str]; target_region:Optional[str]; target_point:Optional[V2]
    desired_speed_mps:float; throttle:float; brake:float; steer:float; reverse:bool; controller_enabled:bool; reason:str

@dataclass(frozen=True)
class ImpactEvidence:
    event_id:str; actor_a:str; actor_b:str; time_s:float; position:V2; normal_a_to_b:V2
    closing_speed_mps:float; relative_speed_mps:float; reduced_mass_kg:float; energy_proxy_j:float; response_delta_mps:float
    solver_response_observed:bool; contact_geometry_observed:bool; controller_cutoff_observed:bool
    @property
    def physically_qualified(self):
        return self.contact_geometry_observed and self.solver_response_observed and self.controller_cutoff_observed and self.closing_speed_mps>.05 and self.energy_proxy_j>0

@dataclass(frozen=True)
class DamageMutation:
    entity_id:str; region:str; increment:float; accumulated:float; total_damage:float; mobility_after:float; disabled:bool; energy_proxy_j:float; severity_class:str

@dataclass
class EventRuntimeState:
    event_id:str; started:bool=False; completed:bool=False; physically_resolved:bool=False; contact_count:int=0; damage_mutations:int=0; replan_count:int=0; failure_reason:Optional[str]=None

@dataclass
class WorldState:
    actors:Dict[str,ActorState]; events:Dict[str,EventRuntimeState]=field(default_factory=dict); impacts:List[ImpactEvidence]=field(default_factory=list); damage_log:List[DamageMutation]=field(default_factory=list); debris_ids:List[str]=field(default_factory=list); time_s:float=0


def profile_from_binding(binding:Mapping[str,Any],dims_xyz:Sequence[float],fps:float=30)->ActorProfile:
    eid=str(binding.get('entityId') or '').strip()
    if not eid or len(dims_xyz)<3: raise ValueError('INVALID_ACTOR_BINDING')
    d=[max(.05,abs(float(x))) for x in dims_xyz[:3]]; L,W=sorted(d[:2],reverse=True); R=.5*math.hypot(L,W)
    m=float(binding.get('totalMassKg') or binding.get('massKg') or 1500)
    if not math.isfinite(m) or m<=0: raise ValueError('INVALID_MASS')
    cfg=binding.get('runtimeProfile') or {}; mr=clamp(m/1500,.3,30); sr=clamp(L/4.5,.5,4)
    vmax=clamp(float(cfg.get('maxForwardSpeedMps',34/(mr**.18))),6,55); rev=clamp(float(cfg.get('maxReverseSpeedMps',max(2,vmax*.28))),1,vmax)
    acc=clamp(float(cfg.get('maxAccelMps2',8/(mr**.22))),1,14); brake=clamp(float(cfg.get('maxBrakeMps2',10/(mr**.12))),1.2,18); yaw=clamp(float(cfg.get('maxYawRateRadS',1.45/sr)),.18,2.5)
    I=m*(L*L+W*W)/12; yaw_acc=clamp(float(cfg.get('maxYawAccelRadS2',yaw*3)),.2,8)
    base=.5*m*min(vmax,15)**2; th=max(2500,float(cfg.get('impactDamageThresholdJ',base*.035))); severe=max(th*2,float(cfg.get('severeDamageEnergyJ',base*.28)))
    off={'center':(0,0),'chassis':(0,0),'front':(L*.47,0),'rear':(-L*.47,0),'left':(0,W*.46),'right':(0,-W*.46),'cab':(L*.08,0),'cabin':(L*.08,0),'blade':(L*.48,0),'left_track':(0,W*.43),'right_track':(0,-W*.43)}
    for k,v in (binding.get('semanticRegionOffsets') or {}).items():
        if isinstance(v,Sequence) and len(v)>=2: off[str(k).lower()]=(float(v[0]),float(v[1]))
    return ActorProfile(eid,m,R,L,W,vmax,rev,acc,brake,yaw,m*acc/fps,m*brake/fps,I*yaw_acc/fps,max(.25,R*.12),th,severe,clamp(float(cfg.get('disableDamage',.92)),.5,1),off)

def semantic_target_point(target:ActorState,profile:ActorProfile,region:Optional[str])->V2:
    loc=profile.region_offsets.get((region or 'center').lower(),profile.region_offsets['center'])
    return target.position+V2(*loc).rotated(target.heading_rad)

def _speed_fraction(x:str)->float:
    return {'hold':0,'settle':0,'crawl':.28,'slow':.28,'sustain':.58,'cruise':.58,'accelerate':.82,'attack':.82,'fast':.9}.get((x or '').lower(),.65)

def compute_control(cmd:PlannerCommand,actor:ActorState,profile:ActorProfile,world:WorldState,profiles:Mapping[str,ActorProfile])->ControlIntent:
    name=cmd.command.upper()
    if actor.disabled: return ControlIntent(actor.entity_id,cmd.event_id,name,cmd.target_entity_id,cmd.target_region,None,0,0,1,0,False,False,'ACTOR_DISABLED')
    if name in {'HOLD','SETTLE','BRAKE'}: return ControlIntent(actor.entity_id,cmd.event_id,name,cmd.target_entity_id,cmd.target_region,None,0,0,1 if actor.speed>.15 else 0,0,False,True,'BRAKE_TO_HOLD')
    target=world.actors.get(cmd.target_entity_id) if cmd.target_entity_id else None; tp=profiles.get(cmd.target_entity_id) if cmd.target_entity_id else None
    reverse=name=='REVERSE'
    if target and tp:
        point=semantic_target_point(target,tp,cmd.target_region); direction=(point-actor.position).normalized(actor.forward); lateral=direction.perp_left(); fd=max(tp.radius_m*1.15,tp.width_m*.75)
        if name=='FLANK_LEFT': point=point+lateral*fd
        elif name=='FLANK_RIGHT': point=point-lateral*fd
        elif name=='EVADE': point=actor.position-direction*max(12,actor.speed*1.5)
    else: point=actor.position+actor.forward*(-20 if reverse else 20)
    delta=point-actor.position; dist=delta.length; desired_heading=math.atan2(delta.y,delta.x)+(math.pi if reverse else 0); errh=wrap_pi(desired_heading-actor.heading_rad)
    steer=clamp(errh/max(profile.max_yaw_rate_rad_s*.45,.15),-1,1)
    vmax=profile.max_reverse_speed_mps if reverse else profile.max_forward_speed_mps; desired=vmax*_speed_fraction(cmd.speed_intent)*clamp(actor.mobility,.08,1)
    if name in {'RAM','PRESSURE'}: desired=max(desired,vmax*.72*actor.mobility)
    if name.startswith('FLANK'): desired=min(desired,vmax*.64*actor.mobility)
    cutoff=(tp.radius_m if tp else 0)+profile.radius_m+profile.controller_cutoff_m; enabled=not(target and dist<=cutoff)
    signed=actor.velocity.dot(actor.forward)*(-1 if reverse else 1); errs=desired-signed
    throttle=clamp(errs/max(profile.max_accel_mps2*1.2,.5),0,1) if enabled else 0; brake=clamp((-errs)/max(profile.max_brake_mps2,.5),0,1) if errs<-.5 and enabled else 0
    return ControlIntent(actor.entity_id,cmd.event_id,name,cmd.target_entity_id,cmd.target_region,point,desired if enabled else 0,throttle,brake,steer if enabled else 0,reverse,enabled,'TRACK_DYNAMIC_TARGET' if enabled else 'CONTACT_APPROACH_CUTOFF')

def impact_evidence(event_id:str,a0:ActorState,b0:ActorState,a1:ActorState,b1:ActorState,pa:ActorProfile,pb:ActorProfile,time_s:float,cutoff:bool,contact:bool)->ImpactEvidence:
    normal=(b0.position-a0.position).normalized(V2(1,0)); rel0=b0.velocity-a0.velocity; closing=max(0,-rel0.dot(normal)); reduced=pa.mass_kg*pb.mass_kg/max(pa.mass_kg+pb.mass_kg,EPS); energy=.5*reduced*closing*closing; rel1=b1.velocity-a1.velocity; response=(rel1-rel0).length
    return ImpactEvidence(event_id,a0.entity_id,b0.entity_id,time_s,(a1.position+b1.position)*.5,normal,closing,rel0.length,reduced,energy,response,response>=max(.12,closing*.03),contact,cutoff)

def apply_damage(world:WorldState,ev:ImpactEvidence,target_id:str,region:Optional[str],p:ActorProfile)->Optional[DamageMutation]:
    if not ev.physically_qualified or ev.energy_proxy_j<p.impact_damage_threshold_j: return None
    a=world.actors[target_id]; key=(region or 'chassis').lower(); span=max(p.severe_damage_energy_j-p.impact_damage_threshold_j,EPS); n=clamp((ev.energy_proxy_j-p.impact_damage_threshold_j)/span,0,2.5); prev=clamp(a.region_damage.get(key,0),0,1); inc=clamp(.06+.38*(1-math.exp(-n)),0,.5); acc=clamp(prev+inc*(1-.35*prev),0,1); a.region_damage[key]=acc
    worst=max(a.region_damage.values()); mean=sum(a.region_damage.values())/len(a.region_damage); a.total_damage=clamp(.72*worst+.28*mean,0,1); drivetrain=1.35 if any(t in key for t in ('wheel','track','axle','steer','suspension')) else 1; a.mobility=clamp(1-a.total_damage*.68-acc*.18*drivetrain,.04,1); a.disabled=a.total_damage>=p.disable_damage or a.mobility<=.06; a.contact_count+=1; a.last_contact_time=ev.time_s
    ratio=ev.energy_proxy_j/max(p.severe_damage_energy_j,EPS); sev='LIGHT' if ratio<.35 else 'MEDIUM' if ratio<.75 else 'HEAVY' if ratio<1.6 else 'CATASTROPHIC'; m=DamageMutation(target_id,key,inc,acc,a.total_damage,a.mobility,a.disabled,ev.energy_proxy_j,sev); world.damage_log.append(m); return m

class BattleStateMachine:
    def __init__(self,commands:Sequence[PlannerCommand]):
        self.commands=list(commands); self.by_event={}
        for c in self.commands: self.by_event.setdefault(c.event_id,[]).append(c)
    def active(self,world:WorldState,now:float)->List[PlannerCommand]:
        out=[]
        for c in self.commands:
            e=world.events.setdefault(c.event_id,EventRuntimeState(c.event_id)); deps=all(world.events.get(d,EventRuntimeState(d)).completed for d in c.caused_by)
            if deps and c.start_time<=now<c.end_time and not e.completed: e.started=True; out.append(c)
        return out
    def note_impact(self,world:WorldState,ev:ImpactEvidence,mutations:Sequence[DamageMutation]):
        e=world.events.setdefault(ev.event_id,EventRuntimeState(ev.event_id)); e.contact_count+=1; e.physically_resolved|=ev.physically_qualified; e.damage_mutations+=len(mutations); world.impacts.append(ev)
    def close_expired(self,world:WorldState,now:float,grace_s:float=.20):
        for eid,cs in self.by_event.items():
            e=world.events.setdefault(eid,EventRuntimeState(eid)); end=max(c.end_time for c in cs)
            if e.completed or now+1e-6<end+max(0.0,grace_s): continue
            dr=any(c.damage_required for c in cs); cr=any(c.target_entity_id for c in cs if c.command in {'RAM','PRESSURE','FLANK_LEFT','FLANK_RIGHT'})
            if dr and e.damage_mutations<=0: e.failure_reason='REQUIRED_DAMAGE_NOT_PHYSICALLY_EARNED'
            elif cr and not e.physically_resolved: e.failure_reason='REQUIRED_CONTACT_NOT_PHYSICALLY_RESOLVED'
            else: e.completed=True

def replan_if_stalled(world:WorldState,cmd:PlannerCommand,profile:ActorProfile,dt:float,distance_to_target:Optional[float])->PlannerCommand:
    actor=world.actors[cmd.actor_id]
    if cmd.command not in {'RAM','PRESSURE','FLANK_LEFT','FLANK_RIGHT'} or distance_to_target is None:
        actor.stalled_seconds=0; return cmd
    far=distance_to_target>profile.radius_m*1.8; slow=actor.speed<max(.35,profile.max_forward_speed_mps*.03)
    actor.stalled_seconds=actor.stalled_seconds+dt if far and slow else max(0,actor.stalled_seconds-2*dt)
    if actor.stalled_seconds<1.25: return cmd
    e=world.events.setdefault(cmd.event_id,EventRuntimeState(cmd.event_id)); e.replan_count+=1; actor.stalled_seconds=0
    replacement='FLANK_LEFT' if e.replan_count%2 else 'FLANK_RIGHT'
    return PlannerCommand(cmd.event_id,cmd.actor_id,replacement,cmd.start_time,cmd.end_time,cmd.target_entity_id,cmd.target_region,cmd.speed_intent,cmd.caused_by,cmd.damage_required)

class WaveScheduler:
    def __init__(self,max_active_attackers=12,wave_seconds=1.5):
        self.max_active_attackers=max(1,int(max_active_attackers)); self.wave_seconds=max(.25,float(wave_seconds))
    def select(self,commands:Sequence[PlannerCommand],world:WorldState)->List[PlannerCommand]:
        atk=[c for c in commands if c.command in {'RAM','PRESSURE','FLANK_LEFT','FLANK_RIGHT'}]; oth=[c for c in commands if c not in atk]
        atk.sort(key=lambda c:(world.actors[c.actor_id].disabled,world.actors[c.actor_id].contact_count,world.actors[c.actor_id].total_damage,c.actor_id))
        healthy=[c for c in atk if not world.actors[c.actor_id].disabled]
        if len(healthy)<=self.max_active_attackers:return oth+healthy
        bucket=int(world.time_s/self.wave_seconds); start=(bucket*self.max_active_attackers)%len(healthy); selected=[healthy[(start+i)%len(healthy)] for i in range(self.max_active_attackers)]
        return oth+selected

def resolve_outcome(world:WorldState)->Dict[str,Any]:
    a=list(world.actors.values())
    if not a:return {'status':'NO_ACTORS','winner':None}
    r=sorted(a,key=lambda x:(x.disabled,x.total_damage,-x.mobility,-x.contact_count,x.entity_id)); best,worst=r[0],r[-1]; decisive=(worst.disabled and not best.disabled) or (worst.total_damage-best.total_damage>=.35)
    return {'status':'DECISIVE' if decisive else 'UNRESOLVED','winner':best.entity_id if decisive else None,'actors':[{'entityId':x.entity_id,'disabled':x.disabled,'totalDamage':round(x.total_damage,6),'mobility':round(x.mobility,6),'contacts':x.contact_count} for x in sorted(a,key=lambda y:y.entity_id)]}

def spawn_layout(actor_ids:Sequence[str],target_edges:Sequence[Tuple[str,str]],radii:Mapping[str,float])->Dict[str,Tuple[V2,float]]:
    ids=list(actor_ids)
    if len(ids)!=len(set(ids)): raise ValueError('DUPLICATE_ACTOR_ID')
    incoming={x:0 for x in ids}
    for src,dst in target_edges:
        if src in incoming and dst in incoming and src!=dst: incoming[dst]+=1
    order=sorted(ids,key=lambda x:(-incoming[x],x))
    if not order:return {}
    mr=max([float(radii.get(x,1)) for x in ids] or [1]); spacing=max(2.4*mr,3.0)
    core=[x for x in order if incoming[x]>0]
    if not core: core=[order[0]]
    out:Dict[str,Tuple[V2,float]]={}
    if len(core)==1: out[core[0]]=(V2(0,0),0.0); core_extent=mr
    else:
        r=max(spacing*len(core)/(2*math.pi),spacing*.8)
        for i,e in enumerate(core):
            a=2*math.pi*i/len(core); p=V2(math.cos(a)*r,math.sin(a)*r); out[e]=(p,math.atan2(-p.y,-p.x))
        core_extent=r+mr
    rem=[x for x in order if x not in out]; radius=max(core_extent+spacing*1.5,spacing*2)
    idx=0
    while idx<len(rem):
        capacity=max(6,int((2*math.pi*radius)//spacing)); take=min(capacity,len(rem)-idx)
        for j in range(take):
            e=rem[idx+j]; a=2*math.pi*j/take + (0.37*(idx//max(1,capacity))); p=V2(math.cos(a)*radius,math.sin(a)*radius); out[e]=(p,math.atan2(-p.y,-p.x))
        idx+=take; radius+=spacing
    return out

def selftest()->dict:
    pa=profile_from_binding({'entityId':'alpha','massKg':1500},(4.5,1.9,1.2)); pb=profile_from_binding({'entityId':'beta','massKg':1800},(4.8,2,1.4)); w=WorldState({'alpha':ActorState('alpha',V2(-8,0),V2(10,0),0),'beta':ActorState('beta',V2(8,0),V2(-8,0),math.pi)})
    c=PlannerCommand('e1','alpha','RAM',0,3,'beta','front','accelerate'); i=compute_control(c,w.actors['alpha'],pa,w,{'alpha':pa,'beta':pb}); assert i.target_point and i.throttle>=0 and -1<=i.steer<=1
    p0=i.target_point; w.actors['beta'].position=V2(8,3); p1=compute_control(c,w.actors['alpha'],pa,w,{'alpha':pa,'beta':pb}).target_point; assert p0!=p1
    a0=ActorState('alpha',V2(-1,0),V2(10,0),0); b0=ActorState('beta',V2(1,0),V2(-8,0),math.pi); a1=ActorState('alpha',V2(-.8,0),V2(2,0),0); b1=ActorState('beta',V2(.8,0),V2(3,0),math.pi); ev=impact_evidence('e1',a0,b0,a1,b1,pa,pb,1,True,True); assert ev.physically_qualified
    w.actors['beta']=b0; m1=apply_damage(w,ev,'beta','front',pb); m2=apply_damage(w,ev,'beta','front',pb); assert m1 and m2 and m2.accumulated>m1.accumulated and w.actors['beta'].mobility<1
    ids=[f'a{i}' for i in range(100)]+['boss']; edges=[(x,'boss') for x in ids if x!='boss']; layout=spawn_layout(ids,edges,{x:2 for x in ids}); assert len(layout)==101; pts=[layout[x][0] for x in ids]; assert min((pts[i]-pts[j]).length for i in range(len(pts)) for j in range(i))>3.5
    ww=WorldState({x:ActorState(x,layout[x][0],V2(0,0),layout[x][1]) for x in ids}); cmds=[PlannerCommand('wave',x,'RAM',0,5,'boss','front','accelerate') for x in ids if x!='boss']; sched=WaveScheduler(12,1.0); s0=sched.select(cmds,ww); assert len(s0)==12; ww.time_s=1.1; s1=sched.select(cmds,ww); assert len(s1)==12 and {c.actor_id for c in s0}!={c.actor_id for c in s1}
    return {'status':'PASS','dynamicTarget':True,'persistentDamage':round(m2.accumulated,6),'actorsScaled':101,'waveCap':12,'impactEnergyJ':round(ev.energy_proxy_j,3)}

if __name__=='__main__': print(selftest())
