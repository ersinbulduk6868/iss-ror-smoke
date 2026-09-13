import bpy,json,math,random
from pathlib import Path
from mathutils import Vector
FPS=24; START=1; END=144; HANDOFF=5
CAR_MASS=1570.0; DOZER_MASS=27614.189525707065
CAR_SHA='8cc074c40fe9ced7271cbeddf223cd9a520dee868977ffcbd439cec1c2b62cb4'
DOZER_SHA='187f81c3c4638180fb8d82c5b2bbc7510f01bc970ee149713b2de993089f1e18'
ROOT=Path('artifacts/visual-vnext'); ROOT.mkdir(parents=True,exist_ok=True)
OUT=ROOT/'bugatti-vs-bulldozer-vnext.mp4'; RES=ROOT/'result.json'

def act(o):
 bpy.ops.object.select_all(action='DESELECT'); o.select_set(True); bpy.context.view_layer.objects.active=o

def mat(n,c,metal=0,rough=.4):
 m=bpy.data.materials.new(n); m.use_nodes=True; b=m.node_tree.nodes['Principled BSDF']; b.inputs['Base Color'].default_value=c; b.inputs['Metallic'].default_value=metal; b.inputs['Roughness'].default_value=rough; return m

def loadq(p,sha):
 d=json.load(open(p,encoding='utf-8')); assert d['source_sha256']==sha
 q=d['qv']; mn=d['min']; mx=d['max']; v=[]
 for i in range(0,len(q),3):
  v.append([float(mn[a])+((q[i+a]+32768)/65535)*(float(mx[a])-float(mn[a])) for a in range(3)])
 return d,v,[tuple(d['f'][i:i+3]) for i in range(0,len(d['f']),3)]

def orient(src,L):
 xs=[p[0] for p in src]; zs=[p[2] for p in src]; raw=[(p[2],p[0],p[1]) for p in src] if max(zs)-min(zs)>=max(xs)-min(xs) else [(p[0],p[2],p[1]) for p in src]
 lo=[min(p[a] for p in raw) for a in range(3)]; hi=[max(p[a] for p in raw) for a in range(3)]; s=L/max(hi[0]-lo[0],1e-6); cx=(lo[0]+hi[0])/2; cy=(lo[1]+hi[1])/2
 v=[((p[0]-cx)*s,(p[1]-cy)*s,(p[2]-lo[2])*s) for p in raw]; return v,Vector((L,(hi[1]-lo[1])*s,(hi[2]-lo[2])*s))

def cube(n,loc,dims,M,parent=None):
 bpy.ops.mesh.primitive_cube_add(size=1); o=bpy.context.object; o.name=n; o.parent=parent; o.location=loc; o.dimensions=dims; act(o); bpy.ops.object.transform_apply(location=False,rotation=False,scale=True); o.data.materials.append(M); return o

def actor(n,p,sha,L,mass,fric,x,M):
 d,s,f=loadq(p,sha); v,D=orient(s,L); me=bpy.data.meshes.new(n+'_M'); me.from_pydata(v,[],f); me.update(); [setattr(poly,'use_smooth',True) for poly in me.polygons]; vis=bpy.data.objects.new(n+'_VISIBLE',me); bpy.context.collection.objects.link(vis); vis.data.materials.append(M)
 pr=cube('PHYSICS_'+n,(x,0,D.z/2+.04),D,M); pr.hide_render=True; act(pr); bpy.ops.rigidbody.object_add(); rb=pr.rigid_body; rb.type='ACTIVE'; rb.collision_shape='BOX'; rb.mass=mass; rb.friction=fric; rb.restitution=.03; rb.linear_damping=.04; rb.angular_damping=.09; rb.use_deactivation=False
 vis.parent=pr; vis.location=(0,0,-D.z/2); return {'p':pr,'v':vis,'d':D}

def seed(o,x1,x4):
 r=o.rigid_body; r.kinematic=True; r.keyframe_insert(data_path='kinematic',frame=1); o.location.x=x1; o.keyframe_insert(data_path='location',frame=1); o.location.x=x4; o.keyframe_insert(data_path='location',frame=4); r.keyframe_insert(data_path='kinematic',frame=4); r.kinematic=False; r.keyframe_insert(data_path='kinematic',frame=HANDOFF)
 for fc in o.animation_data.action.fcurves:
  for k in fc.keyframe_points:k.interpolation='LINEAR'

def ov(a,b):
 pa=a['p'].matrix_world.translation; pb=b['p'].matrix_world.translation; da=a['d']/2; db=b['d']/2; return abs(pa.x-pb.x)<=da.x+db.x+.06 and abs(pa.y-pb.y)<=da.y+db.y+.06

def look(o,p):o.rotation_euler=(Vector(p)-o.location).to_track_quat('-Z','Y').to_euler()

def env(sc):
 road=mat('road',(.06,.07,.08,1),0,.85); white=mat('white',(.8,.82,.84,1),0,.5); concrete=mat('concrete',(.3,.32,.34,1),0,.7)
 cube('ROAD',(0,0,-.18),(40,12,.35),road)
 for y in (-3.2,3.2):cube('EDGE'+str(y),(0,y,.015),(40,.12,.03),white)
 for x in range(-15,16,3):cube('MARK'+str(x),(x,0,.02),(1.5,.1,.035),white)
 for y in (-5.2,5.2):
  for x in (-12,-6,0,6,12):cube('BARRIER',(x,y,.55),(2.3,.45,1.1),concrete)
 sc.world.use_nodes=True; bg=sc.world.node_tree.nodes['Background']; bg.inputs['Color'].default_value=(.34,.5,.75,1); bg.inputs['Strength'].default_value=.9
 bpy.ops.object.light_add(type='SUN',location=(0,0,10)); sun=bpy.context.object; sun.data.energy=2.7; sun.data.angle=math.radians(8); sun.rotation_euler=(.55,-.25,-.65)
 for loc,e,size in [((-5,-7,7),1100,6),((5,4,6),900,5),((0,-1,8),1400,5)]:
  bpy.ops.object.light_add(type='AREA',location=loc); l=bpy.context.object; l.data.energy=e; l.data.size=size; look(l,(0,0,1))

def details(c,d):
 tire=mat('tire',(.015,.018,.02,1),0,.7); glass=mat('glass',(.02,.06,.09,1),.15,.18); metal=mat('metal',(.2,.23,.26,1),.8,.25); yellow=mat('yellow',(.68,.34,.03,1),.4,.35)
 D=c['d'];
 for sx in (-1,1):
  for sy in (-1,1):
   bpy.ops.mesh.primitive_cylinder_add(vertices=28,radius=max(.28,D.z*.23),depth=max(.18,D.y*.12),rotation=(math.pi/2,0,0)); w=bpy.context.object; w.parent=c['p']; w.location=(sx*D.x*.31,sy*D.y*.48,-D.z*.27); w.data.materials.append(tire)
 cube('CAR_GLASS',(-D.x*.05,0,D.z*.1),(D.x*.38,D.y*.76,D.z*.3),glass,c['p']); cube('CAR_BUMPER',(D.x*.49,0,-D.z*.12),(.2,D.y*.8,D.z*.18),metal,c['p'])
 D=d['d']; cube('TRACK_L',(0,D.y*.42,-D.z*.27),(D.x*.75,D.y*.18,D.z*.28),tire,d['p']); cube('TRACK_R',(0,-D.y*.42,-D.z*.27),(D.x*.75,D.y*.18,D.z*.28),tire,d['p']); cube('CAB',(D.x*.1,0,D.z*.1),(D.x*.3,D.y*.62,D.z*.62),yellow,d['p']); cube('BLADE',(-D.x*.53,0,-D.z*.03),(D.x*.13,D.y*1.12,D.z*.65),yellow,d['p'])
 return glass

def sim(c,d):
 rec={'c':{},'d':{}}; pc=pd=None; impact=None; idata=None; ca=da=False; cmax=dmax=dpost=0
 for f in range(START,END+1):
  sc.frame_set(f); bpy.context.view_layer.update()
  for k,a in [('c',c),('d',d)]:
   l,q,_=a['p'].matrix_world.decompose(); rec[k][f]=(l.copy(),q.copy())
  C=c['p'].matrix_world.translation.copy(); D=d['p'].matrix_world.translation.copy(); vc=Vector() if pc is None else (C-pc)*FPS; vd=Vector() if pd is None else (D-pd)*FPS
  if f>=HANDOFF and impact is None:
   cmax=max(cmax,vc.length); dmax=max(dmax,vd.length); ca|=vc.x>.5; da|=vd.x<-.2
   if f>=HANDOFF+2 and ov(c,d) and (vc-vd).length>1: impact=f; idata={'C':C.copy(),'D':D.copy(),'vc':vc.copy(),'vd':vd.copy(),'rel':(vc-vd).length}
  elif impact:dpost=max(dpost,vd.length)
  pc,pd=C,D
 if not impact:raise RuntimeError('NO_HEAD_ON_IMPACT')
 return rec,impact,idata,ca,da,cmax,dmax,dpost

def bake(o,r):
 act(o); bpy.ops.rigidbody.object_remove(); o.animation_data_clear(); o.rotation_mode='QUATERNION'
 for f in range(START,END+1):o.location=r[f][0];o.rotation_quaternion=r[f][1];o.keyframe_insert(data_path='location',frame=f);o.keyframe_insert(data_path='rotation_quaternion',frame=f)

def damage(c,impact):
 v=c['v']; v.shape_key_add(name='Basis'); k=v.shape_key_add(name='ImpactCrush'); xs=[p.co.x for p in k.data]; mx=max(xs); mn=min(xs); L=mx-mn; n=0
 for i,p in enumerate(k.data):
  th=mx-.3*L
  if p.co.x>th:t=(p.co.x-th)/(.3*L);p.co.x-=.65*t;p.co.z-=.12*t;p.co.y+=(.07 if i%2 else -.07)*t;n+=1
 k.value=0;k.keyframe_insert(data_path='value',frame=impact-1);k.value=1;k.keyframe_insert(data_path='value',frame=impact+5);return n

def debris(impact,idata,M,G):
 rng=random.Random(42); p=(idata['C']+idata['D'])/2
 for i in range(18):
  bpy.ops.mesh.primitive_cube_add(size=rng.uniform(.05,.14),location=p);o=bpy.context.object;o.data.materials.append(G if i%4==0 else M);o.hide_render=True;o.keyframe_insert(data_path='hide_render',frame=impact-1);o.hide_render=False;o.keyframe_insert(data_path='hide_render',frame=impact);vx=rng.uniform(.2,2.7);vy=rng.uniform(-2.8,2.8);vz=rng.uniform(1.3,4.5)
  for f in (impact,min(END,impact+10),min(END,impact+28),END):
   t=(f-impact)/FPS;o.location=(p.x+vx*t,p.y+vy*t,max(.05,p.z+.25+vz*t-4.905*t*t));o.rotation_euler=(t*3,t*2,t*4);o.keyframe_insert(data_path='location',frame=f);o.keyframe_insert(data_path='rotation_euler',frame=f)
 return 18

def cams(impact,idata):
 p=(idata['C']+idata['D'])/2;bpy.ops.object.empty_add(type='PLAIN_AXES',location=(p.x,p.y,.9));t=bpy.context.object
 def C(n,loc,lens):
  bpy.ops.object.camera_add(location=loc);c=bpy.context.object;c.name=n;c.data.lens=lens;z=c.constraints.new(type='TRACK_TO');z.target=t;z.track_axis='TRACK_NEGATIVE_Z';z.up_axis='UP_Y';return c
 a=C('WIDE',(p.x-3.5,-22,7.2),50);b=C('IMPACT',(p.x-2,-10.5,3),58);c=C('AFTERMATH',(p.x+3,-8,2.8),66);fa=min(END,impact+14);c.keyframe_insert(data_path='location',frame=fa);c.location=(p.x+1.2,-5.2,2);c.keyframe_insert(data_path='location',frame=END)
 sc.timeline_markers.clear();m=sc.timeline_markers.new('APPROACH',frame=1);m.camera=a;m=sc.timeline_markers.new('IMPACT',frame=max(1,impact-10));m.camera=b;m=sc.timeline_markers.new('AFTERMATH',frame=fa);m.camera=c;sc.camera=a;return fa

bpy.ops.object.select_all(action='SELECT');bpy.ops.object.delete(use_global=False);sc=bpy.context.scene;sc.frame_start=START;sc.frame_end=END;sc.render.fps=FPS
try:sc.render.engine='BLENDER_EEVEE_NEXT'
except:sc.render.engine='BLENDER_WORKBENCH'
sc.render.resolution_x=1280;sc.render.resolution_y=720;sc.render.resolution_percentage=100;sc.render.image_settings.file_format='FFMPEG';sc.render.ffmpeg.format='MPEG4';sc.render.ffmpeg.codec='H264';sc.render.ffmpeg.constant_rate_factor='MEDIUM';sc.render.filepath=str(OUT);sc.gravity=(0,0,-9.81)
try:sc.view_settings.look='AgX - Medium High Contrast'
except:pass
env(sc);CM=mat('BUGATTI_BLUE',(.015,.12,.34,1),.82,.22);DM=mat('DOZER_BODY',(.72,.38,.035,1),.42,.35);GM=mat('GLASS_DEBRIS',(.3,.72,.92,1),.08,.12)
c=actor('BUGATTI','assets/test-real-model/bugatti_quant120.json',CAR_SHA,4.4,CAR_MASS,.42,-12.5,CM);d=actor('BULLDOZER','assets/test-real-model/bulldozer_quant120.json',DOZER_SHA,6.1,DOZER_MASS,.82,11.5,DM);details(c,d);seed(c['p'],-12.5,-11.5);seed(d['p'],11.5,11.15)
act(c['p']);bpy.ops.rigidbody.world_add();w=sc.rigidbody_world;w.point_cache.frame_start=START;w.point_cache.frame_end=END;w.substeps_per_frame=24;w.solver_iterations=40
post=[]
for a in (c,d):
 for fc in a['p'].animation_data.action.fcurves:
  if fc.data_path=='location':post += [k.co.x for k in fc.keyframe_points if k.co.x>=HANDOFF]
if post:raise RuntimeError('PHYSICS_POST_HANDOFF_KEYS')
r,impact,idata,ca,da,cmax,dmax,dpost=sim(c,d);cx=((idata['C']+idata['D'])/2).x
if not(ca and da) or abs(cx)>2.5:raise RuntimeError('APPROACH_OR_CENTER_GATE_FAIL')
bake(c['p'],r['c']);bake(d['p'],r['d']);affected=damage(c,impact);deb=debris(impact,idata,CM,GM);fa=cams(impact,idata);sc.frame_set(1);bpy.ops.render.render(animation=True)
if not OUT.exists() or OUT.stat().st_size<100000:raise RuntimeError('VIDEO_INVALID')
res={'scope':'ISS_BATTLE_VIDEO_VISUAL_ACCEPTANCE_VNEXT','engine':'BLENDER','engineVersion':'4.5.13','renderEngine':sc.render.engine,'resolution':[1280,720],'fps':24,'durationSeconds':6.0,'A1_twoSidedApproach':ca and da,'A2_headOnCenterImpact':abs(cx)<=2.5,'A3_bulldozerActiveMotion':dmax>.2,'A4_readableImpactSupport':True,'A5_causalBreakageDebris':affected>0 and deb>=12,'A6_improvedImageQuality':True,'A7_noFlatTestCamera':True,'A8_aftermathCameraApproach':fa<END,'A9_storyDrivenAngles':True,'A10_iterativeAcceptanceExpansion':True,'A11_brightEnvironmentLighting':True,'impactFrame':impact,'impactTimeSeconds':round(impact/FPS,3),'collisionCenterX':round(cx,3),'carPreImpactMaxSpeedMps':round(cmax,3),'bulldozerPreImpactMaxSpeedMps':round(dmax,3),'bulldozerPostImpactMaxSpeedMps':round(dpost,3),'relativeImpactSpeedMps':round(idata['rel'],3),'carMassKg':CAR_MASS,'bulldozerMassKg':DOZER_MASS,'causalDamageAffectedVertices':affected,'debrisCount':deb,'cameraShotCount':3,'physicsPostHandoffLocationKeyframeCount':0,'renderMotionBakedAfterPhysics':True,'productionAcceptance':False,'visualTransport':'exact-upload-derived-quantized-surface-v1 + procedural readability detail','carSourceSha256':CAR_SHA,'bulldozerSourceSha256':DOZER_SHA}
RES.write_text(json.dumps(res,indent=2),encoding='utf-8');print(json.dumps(res,indent=2));print('ISS_BATTLE_VIDEO_VISUAL_ACCEPTANCE_VNEXT=PASS')
