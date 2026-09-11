import math,re,sys
from pathlib import Path
text=Path(sys.argv[1]).read_text(errors='replace')
pat=re.compile(r'ISS_BATTLE_TELEM_V81 seq=(\d+) ax=([-+0-9.eE]+) ay=([-+0-9.eE]+) az=([-+0-9.eE]+) aspeed=([-+0-9.eE]+) bx=([-+0-9.eE]+) by=([-+0-9.eE]+) bz=([-+0-9.eE]+) bspeed=([-+0-9.eE]+) centerDist=([-+0-9.eE]+) stageMoved=([-+0-9.eE]+) laneOffset=([-+0-9.eE]+) accel=([01]) stage=([01]) blocker=([01]) breaks=(\d+) contactBreaks=(\d+) resets=(\d+) teleports=(\d+) actors=(\d+)')
tele=[]
for m in pat.finditer(text):
    g=m.groups(); tele.append(dict(seq=int(g[0]),ax=float(g[1]),ay=float(g[2]),az=float(g[3]),aspeed=float(g[4]),bx=float(g[5]),by=float(g[6]),bz=float(g[7]),bspeed=float(g[8]),dist=float(g[9]),stageMoved=float(g[10]),laneOffset=float(g[11]),accel=int(g[12]),stage=int(g[13]),blocker=int(g[14]),breaks=int(g[15]),contactBreaks=int(g[16]),resets=int(g[17]),teleports=int(g[18]),actors=int(g[19])))
if len(tele)<10: raise SystemExit(f'BATTLE_TELEMETRY_FAIL samples={len(tele)}')
if 'ISS_BATTLE_BLOCKER_READY ' not in text: raise SystemExit('BLOCKER_READY_MISSING')
if 'ISS_BATTLE_PLAYER_DRIVE_ACTIVE accel_ack=1' not in text: raise SystemExit('PLAYER_DRIVE_ACK_MISSING')
if 'ISS_BATTLE_CONTACT_DAMAGE_PASS ' not in text: raise SystemExit('CONTACT_DAMAGE_MARKER_MISSING')
if any(t['actors']<2 for t in tele): raise SystemExit('ACTOR_PERSISTENCE_FAIL')
block=[t for t in tele if t['blocker']==1]
if not block: raise SystemExit('BLOCKER_TELEMETRY_MISSING')
if min(t['laneOffset'] for t in block)>2.0: raise SystemExit('BLOCKER_LANE_GEOMETRY_FAIL')
if max(t['stageMoved'] for t in block)<2.0: raise SystemExit('BLOCKER_STAGE_MOTION_FAIL')
if max(t['bspeed'] for t in tele if t['stage']==1)<1.0: raise SystemExit('AI_STAGE_SPEED_FAIL')
drive=[t for t in tele if t['blocker']==1 and t['accel']==1]
if len(drive)<2: raise SystemExit('PLAYER_DRIVE_TELEMETRY_FAIL')
def hd(a,b,p='a'):
    return math.hypot((a['ax'] if p=='a' else a['bx'])-(b['ax'] if p=='a' else b['bx']), (a['az'] if p=='a' else a['bz'])-(b['az'] if p=='a' else b['bz']))
a_move=hd(drive[0],drive[-1],'a')
if a_move<2.0: raise SystemExit(f'PLAYER_DISPLACEMENT_FAIL {a_move}')
if max(t['aspeed'] for t in drive)<1.0: raise SystemExit('PLAYER_SPEED_FAIL')
if max(t['contactBreaks'] for t in tele)<1: raise SystemExit('QUALIFIED_CONTACT_DAMAGE_FAIL')
if max(t['breaks'] for t in tele)<1: raise SystemExit('BEAM_BREAK_FAIL')
if max(t['resets'] for t in tele)!=0 or max(t['teleports'] for t in tele)!=0: raise SystemExit('FORBIDDEN_LIFECYCLE_EVENT_FAIL')

node_pat=re.compile(r'ISS_NODE label=(BASE1|BASE2|STAGE1|STAGE2|IMPACT|POST) actor=([AB]) idx=(\d+) x=([-+0-9.eE]+) y=([-+0-9.eE]+) z=([-+0-9.eE]+)')
nodes={}
for m in node_pat.finditer(text):
    label,actor,idx,x,y,z=m.groups(); nodes.setdefault((label,actor),{})[int(idx)]=(float(x),float(y),float(z))
for label,actor in [('BASE1','A'),('BASE2','A'),('STAGE1','B'),('STAGE2','B'),('POST','A'),('POST','B')]:
    if len(nodes.get((label,actor),{}))<4: raise SystemExit(f'NODE_SNAPSHOT_MISSING {label} {actor}')

def signature(d):
    ids=sorted(d)
    if len(ids)>14: ids=sorted(set(ids[round(i*(len(ids)-1)/13)] for i in range(14)))
    out=[]
    for i,a in enumerate(ids):
        for b in ids[i+1:]: out.append(math.dist(d[a],d[b]))
    return out

def delta(a,b):
    sa,sb=signature(a),signature(b)
    if len(sa)!=len(sb) or not sa: raise SystemExit('SIGNATURE_SHAPE_FAIL')
    ds=[abs(x-y) for x,y in zip(sa,sb)]
    return max(ds),math.sqrt(sum(d*d for d in ds)/len(ds))

checks=[]
for actor,noise_pair,post_pair in [
    ('A',(('BASE1','A'),('BASE2','A')),(('BASE2','A'),('POST','A'))),
    ('B',(('STAGE1','B'),('STAGE2','B')),(('STAGE2','B'),('POST','B'))),
]:
    noise_max,noise_rms=delta(nodes[noise_pair[0]],nodes[noise_pair[1]])
    post_max,post_rms=delta(nodes[post_pair[0]],nodes[post_pair[1]])
    threshold=max(0.03,noise_max*5.0+0.01)
    damaged=post_max>threshold
    checks.append((actor,noise_max,noise_rms,post_max,post_rms,threshold,damaged))
if not any(x[-1] for x in checks): raise SystemExit('PERSISTENT_DEFORMATION_FAIL '+repr(checks))
print(f'TELEMETRY_SAMPLES={len(tele)}')
print(f'BLOCKER_STAGE_MOVED_MAX_M={max(t["stageMoved"] for t in tele):.6f}')
print(f'BLOCKER_LANE_NODE_OFFSET_MIN_M={min(t["laneOffset"] for t in block):.6f}')
print(f'PLAYER_HORIZONTAL_DISPLACEMENT_M={a_move:.6f}')
print(f'PLAYER_MAX_SPEED_MPS={max(t["aspeed"] for t in drive):.6f}')
print(f'MIN_CENTER_DISTANCE_M={min(t["dist"] for t in tele):.6f}')
print(f'BEAM_BREAK_COUNT={max(t["breaks"] for t in tele)}')
print(f'QUALIFIED_CONTACT_BREAK_COUNT={max(t["contactBreaks"] for t in tele)}')
for actor,noise_max,noise_rms,post_max,post_rms,threshold,damaged in checks:
    print(f'{actor}_NOISE_MAX_DELTA_M={noise_max:.6f}')
    print(f'{actor}_POST_MAX_DELTA_M={post_max:.6f}')
    print(f'{actor}_DAMAGE_THRESHOLD_M={threshold:.6f}')
    print(f'{actor}_PERSISTENT_DEFORMATION_PASS={str(damaged).upper()}')
print('STAGED_BLOCKER_GATE=PASS')
print('MULTI_ACTOR_MOTION_GATE=PASS')
print('DIRECT_BEAM_BREAK_GATE=PASS')
print('QUALIFIED_CONTACT_DAMAGE_GATE=PASS')
print('NO_RESET_TELEPORT_GATE=PASS')
print('PERSISTENT_DEFORMATION_GATE=PASS')
print('CONTINUOUS_WORLD_GATE=PASS')
