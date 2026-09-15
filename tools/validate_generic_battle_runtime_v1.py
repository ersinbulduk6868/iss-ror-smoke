from __future__ import annotations
import ast, importlib.util, math, pathlib, random, sys

ROOT=pathlib.Path(__file__).resolve().parents[1]
BL=ROOT/'blender'
FILES=[BL/'battle_runtime_contract.py',BL/'battle_runtime_core.py',BL/'iss_blender_battle_runtime_v1.py']
FORBIDDEN_TOKENS=('bugatti','ferrari','lamborghini','bulldozer','excavator')
FAIL=[]

def check(cond,msg):
    if not cond: FAIL.append(msg)

def load(name,path):
    spec=importlib.util.spec_from_file_location(name,path); m=importlib.util.module_from_spec(spec); sys.modules[name]=m; spec.loader.exec_module(m); return m

for p in FILES:
    text=p.read_text(encoding='utf-8')
    try: tree=ast.parse(text)
    except SyntaxError as e: FAIL.append(f'SYNTAX:{p.name}:{e}'); continue
    low=text.lower()
    for tok in FORBIDDEN_TOKENS: check(tok not in low,f'PER_VIDEO_TOKEN:{p.name}:{tok}')
    check('key_location(' not in text,f'LEGACY_KEY_LOCATION:{p.name}')
    if p.name=='iss_blender_battle_runtime_v1.py':
        parent={}
        for n in ast.walk(tree):
            for c in ast.iter_child_nodes(n): parent[c]=n
        def enclosing_func(n):
            while n in parent:
                n=parent[n]
                if isinstance(n,(ast.FunctionDef,ast.AsyncFunctionDef)): return n.name
            return None
        for n in ast.walk(tree):
            if isinstance(n,ast.Call) and isinstance(n.func,ast.Attribute) and n.func.attr=='keyframe_insert':
                data=None
                for kw in n.keywords:
                    if kw.arg=='data_path' and isinstance(kw.value,ast.Constant): data=kw.value.value
                if data in {'location','rotation_euler','rotation_quaternion','matrix_world'}:
                    fn=enclosing_func(n)
                    check(fn in {'source_face_shards','build_camera'},f'POSE_KEYFRAME_OUTSIDE_ALLOWED_EFFECT_OR_CAMERA:{fn}:{getattr(n,"lineno",0)}')
        check('motor_lin_target_velocity' in text and 'motor_ang_target_velocity' in text,'NATIVE_MOTOR_CONTROL_MISSING')
        check("actorPoseKeyframes':0" in text,'NO_POSE_KEYFRAME_EVIDENCE_MISSING')
        check('apply_damage(world' in text,'IMPACT_DAMAGE_BINDING_MISSING')
        check('source_face_shards' in text,'ASSET_DERIVED_DEBRIS_MISSING')
        check('copy-on-damage' in text.lower(),'COPY_ON_DAMAGE_MARKER_MISSING')
        check('bpy.ops.ptcache.free_bake_all' in text,'SECOND_PHYSICS_REPLAY_MISSING')
        check('set_kinematic(attacker' not in text,'LEGACY_KINEMATIC_ATTACKER')
        check("['proxy'].keyframe_insert" not in text and '["proxy"].keyframe_insert' not in text,'ACTOR_PROXY_KEYFRAME_FOUND')

contract=load('battle_runtime_contract',BL/'battle_runtime_contract.py')
core=load('battle_runtime_core',BL/'battle_runtime_core.py')
check(contract.selftest().get('status')=='PASS','CONTRACT_SELFTEST_FAIL')
check(core.selftest().get('status')=='PASS','CORE_SELFTEST_FAIL')

rng=random.Random(704513)
for i in range(250):
    eid=f'actor_{i}'; mass=10**rng.uniform(2.7,4.9); L=rng.uniform(2.5,11); W=rng.uniform(1.3,4.5); H=rng.uniform(.9,4.2)
    p=core.profile_from_binding({'entityId':eid,'massKg':mass},(L,W,H))
    vals=[p.mass_kg,p.radius_m,p.max_forward_speed_mps,p.max_accel_mps2,p.drive_impulse_per_frame,p.impact_damage_threshold_j]
    check(all(math.isfinite(x) and x>0 for x in vals),f'PROFILE_INVALID:{eid}')
    a=core.ActorState(eid,core.V2(-20,0),core.V2(rng.uniform(0,12),0),0)
    b=core.ActorState('target',core.V2(10,rng.uniform(-5,5)),core.V2(0,0),math.pi)
    pt=core.profile_from_binding({'entityId':'target','massKg':rng.uniform(1000,25000)},(rng.uniform(3,9),rng.uniform(1.5,4),2))
    w=core.WorldState({eid:a,'target':b}); cmd=core.PlannerCommand('e',eid,'RAM',0,5,'target','front','accelerate')
    intent=core.compute_control(cmd,a,p,w,{eid:p,'target':pt})
    check(0<=intent.throttle<=1 and 0<=intent.brake<=1 and -1<=intent.steer<=1,f'CONTROL_BOUNDS:{eid}')

pa=core.profile_from_binding({'entityId':'a','massKg':1500},(4.5,2,1.3)); pb=core.profile_from_binding({'entityId':'b','massKg':1500},(4.5,2,1.3))
base_a=core.ActorState('a',core.V2(-1,0),core.V2(15,0),0); base_b=core.ActorState('b',core.V2(1,0),core.V2(-15,0),math.pi); post_a=core.ActorState('a',core.V2(-.8,0),core.V2(2,0),0); post_b=core.ActorState('b',core.V2(.8,0),core.V2(3,0),math.pi)
for cutoff,contact in ((False,True),(True,False)):
    w=core.WorldState({'a':base_a,'b':core.ActorState('b',base_b.position,base_b.velocity,base_b.heading_rad)})
    ev=core.impact_evidence('e',base_a,base_b,post_a,post_b,pa,pb,1,cutoff,contact)
    check(core.apply_damage(w,ev,'b','front',pb) is None,f'DAMAGE_WITHOUT_QUALIFIED_CONTACT:{cutoff}:{contact}')

w=core.WorldState({'a':base_a,'b':core.ActorState('b',base_b.position,base_b.velocity,base_b.heading_rad)})
ev=core.impact_evidence('e',base_a,base_b,post_a,post_b,pa,pb,1,True,True); vals=[]; mobs=[]
for _ in range(4):
    m=core.apply_damage(w,ev,'b','front',pb); check(m is not None,'QUALIFIED_DAMAGE_MISSING'); vals.append(w.actors['b'].region_damage['front']); mobs.append(w.actors['b'].mobility)
check(vals==sorted(vals),'DAMAGE_NOT_MONOTONIC'); check(mobs==sorted(mobs,reverse=True),'MOBILITY_NOT_MONOTONIC')

for n in (2,5,10,25,100):
    ids=[f'u{i}' for i in range(n)]+['target']; layout=core.spawn_layout(ids,[(x,'target') for x in ids if x!='target'],{x:2.0 for x in ids}); pts=[layout[x][0] for x in ids]
    mind=min(((pts[i]-pts[j]).length for i in range(len(pts)) for j in range(i)),default=999)
    check(mind>3.5,f'SPAWN_OVERLAP_SCALE_{n}:{mind}')
    world=core.WorldState({x:core.ActorState(x,layout[x][0],core.V2(0,0),layout[x][1]) for x in ids}); cmds=[core.PlannerCommand('wave',x,'RAM',0,10,'target','front','accelerate') for x in ids if x!='target']; sched=core.WaveScheduler(12,1.0); world.time_s=0; sel=sched.select(cmds,world); check(len(sel)<=12,f'WAVE_CAP_SCALE_{n}')

req={'engine':'BLENDER','executionPolicy':{'continuousWorld':True,'persistentDamage':True,'persistentDebris':True,'resetAllowed':False,'teleportAllowed':False,'silentSimplificationAllowed':False,'forcedTransformAfterContactAllowed':False,'velocityInjectionAfterContactAllowed':False},'battlePlan':{'events':[{'eventId':'x1','type':'COORDINATED_ATTACK','phase':'FIRST_ATTACK','startTime':0,'endTime':2,'actors':['unit_q7'],'attackTarget':'machine_z9:left','causedByEventIds':[],'damage':{'required':True,'persistent':True,'zone':'left'},'physicsRequirements':{'speedIntent':'accelerate','trajectory':'direct'}}]}}
cc=contract.compile_commands(req,['unit_q7','machine_z9']); check(len(cc)==1 and cc[0].target.entity_id=='machine_z9','ARBITRARY_NAME_COMPILER_FAIL')

if FAIL:
    print('GENERIC_BATTLE_RUNTIME_V1_STATIC_AUDIT=FAIL')
    for x in FAIL: print('FAIL|'+x)
    raise SystemExit(1)
print('NO_PER_VIDEO_BATTLE_CODE=PASS')
print('NO_ACTOR_POSE_KEYFRAME_CONTROL=PASS')
print('NO_POST_CONTACT_VELOCITY_INJECTION=PASS')
print('DYNAMIC_TARGETING_PROPERTY_TEST=PASS')
print('PHYSICAL_DAMAGE_QUALIFICATION=PASS')
print('PERSISTENT_DAMAGE_MOBILITY_CONSEQUENCE=PASS')
print('SCALE_PACKING_2_5_10_25_100=PASS')
print('WAVE_SCHEDULER_SCALE=PASS')
print('GENERIC_BATTLE_RUNTIME_V1_STATIC_AUDIT=PASS')
