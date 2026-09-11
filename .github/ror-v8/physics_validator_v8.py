import math,re,sys
from pathlib import Path
text=Path(sys.argv[1]).read_text(errors='replace')
tele=[]
pat=re.compile(r'ISS_BATTLE_TELEM seq=(\d+) ax=([-+0-9.eE]+) ay=([-+0-9.eE]+) az=([-+0-9.eE]+) aspeed=([-+0-9.eE]+) bx=([-+0-9.eE]+) by=([-+0-9.eE]+) bz=([-+0-9.eE]+) bspeed=([-+0-9.eE]+) centerDist=([-+0-9.eE]+) accel=([01]) ai=([01]) breaks=(\d+) contactBreaks=(\d+) resets=(\d+) teleports=(\d+) actors=(\d+)')
for m in pat.finditer(text):
    g=m.groups(); tele.append(dict(seq=int(g[0]),ax=float(g[1]),ay=float(g[2]),az=float(g[3]),aspeed=float(g[4]),bx=float(g[5]),by=float(g[6]),bz=float(g[7]),bspeed=float(g[8]),dist=float(g[9]),accel=int(g[10]),ai=int(g[11]),breaks=int(g[12]),contactBreaks=int(g[13]),resets=int(g[14]),teleports=int(g[15]),actors=int(g[16])))
if len(tele)<10: raise SystemExit(f'BATTLE_TELEMETRY_FAIL samples={len(tele)}')
if any(t['actors']<2 for t in tele if t['ai']==1): raise SystemExit('ACTOR_PERSISTENCE_FAIL')
if max(t['aspeed'] for t in tele)<1.0: raise SystemExit('PLAYER_MOTION_FAIL')
if max(t['bspeed'] for t in tele)<1.0: raise SystemExit('AI_MOTION_FAIL')
active=[t for t in tele if t['ai']==1]
start=active[0]; end=active[-1]
def hd(a,b,px='a'):
    if px=='a': return math.hypot(a['ax']-b['ax'],a['az']-b['az'])
    return math.hypot(a['bx']-b['bx'],a['bz']-b['bz'])
a_move=hd(start,end,'a'); b_move=hd(start,end,'b')
if a_move<2.0: raise SystemExit(f'PLAYER_DISPLACEMENT_FAIL {a_move}')
if b_move<2.0: raise SystemExit(f'AI_DISPLACEMENT_FAIL {b_move}')
if max(t['breaks'] for t in tele)<1: raise SystemExit('BEAM_BREAK_TELEMETRY_FAIL')
if max(t['contactBreaks'] for t in tele)<1: raise SystemExit('QUALIFIED_CONTACT_DAMAGE_FAIL')
if max(t['resets'] for t in tele)!=0 or max(t['teleports'] for t in tele)!=0: raise SystemExit('FORBIDDEN_LIFECYCLE_EVENT_FAIL')

node_pat=re.compile(r'ISS_NODE label=(BASE1|BASE2|IMPACT|POST) actor=([AB]) idx=(\d+) x=([-+0-9.eE]+) y=([-+0-9.eE]+) z=([-+0-9.eE]+)')
nodes={}
for m in node_pat.finditer(text):
    label,actor,idx,x,y,z=m.groups(); nodes.setdefault((label,actor),{})[int(idx)]=(float(x),float(y),float(z))
for label in ('BASE1','BASE2','POST'):
  for actor in ('A','B'):
    if len(nodes.get((label,actor),{}))<4: raise SystemExit(f'NODE_SNAPSHOT_MISSING {label} {actor}')

def signature(d):
    ids=sorted(d)
    # deterministic evenly spaced sample, capped at 14 nodes
    if len(ids)>14:
        ids=sorted(set(ids[round(i*(len(ids)-1)/13)] for i in range(14)))
    out=[]
    for i,a in enumerate(ids):
        for b in ids[i+1:]:
            pa,pb=d[a],d[b]
            out.append(math.dist(pa,pb))
    return out

def delta(a,b):
    sa,sb=signature(a),signature(b)
    if len(sa)!=len(sb) or not sa: raise SystemExit('SIGNATURE_SHAPE_FAIL')
    ds=[abs(x-y) for x,y in zip(sa,sb)]
    return max(ds), math.sqrt(sum(x*x for x in ds)/len(ds))
results=[]
for actor in ('A','B'):
    idle_max,idle_rms=delta(nodes[('BASE1',actor)],nodes[('BASE2',actor)])
    post_max,post_rms=delta(nodes[('BASE2',actor)],nodes[('POST',actor)])
    threshold=max(0.03,idle_max*5.0+0.01)
    damaged=post_max>threshold
    results.append((actor,idle_max,idle_rms,post_max,post_rms,threshold,damaged))
if not any(r[-1] for r in results):
    raise SystemExit('PERSISTENT_DEFORMATION_FAIL '+repr(results))

print(f'TELEMETRY_SAMPLES={len(tele)}')
print(f'PLAYER_MAX_SPEED_MPS={max(t["aspeed"] for t in tele):.6f}')
print(f'AI_MAX_SPEED_MPS={max(t["bspeed"] for t in tele):.6f}')
print(f'PLAYER_HORIZONTAL_DISPLACEMENT_M={a_move:.6f}')
print(f'AI_HORIZONTAL_DISPLACEMENT_M={b_move:.6f}')
print(f'MIN_CENTER_DISTANCE_M={min(t["dist"] for t in tele):.6f}')
print(f'BEAM_BREAK_COUNT={max(t["breaks"] for t in tele)}')
print(f'QUALIFIED_CONTACT_BREAK_COUNT={max(t["contactBreaks"] for t in tele)}')
for actor,idle_max,idle_rms,post_max,post_rms,threshold,damaged in results:
    print(f'{actor}_IDLE_SIGNATURE_MAX_DELTA_M={idle_max:.6f}')
    print(f'{actor}_POST_SIGNATURE_MAX_DELTA_M={post_max:.6f}')
    print(f'{actor}_DAMAGE_THRESHOLD_M={threshold:.6f}')
    print(f'{actor}_PERSISTENT_DEFORMATION_PASS={str(damaged).upper()}')
print('MULTI_ACTOR_MOTION_GATE=PASS')
print('DIRECT_BEAM_BREAK_GATE=PASS')
print('QUALIFIED_CONTACT_DAMAGE_GATE=PASS')
print('NO_RESET_TELEPORT_GATE=PASS')
print('PERSISTENT_DEFORMATION_GATE=PASS')
print('CONTINUOUS_WORLD_GATE=PASS')
