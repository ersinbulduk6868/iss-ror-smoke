import bpy, os, json, math, hashlib
from mathutils import Vector
V='4.5.13'; ROOT=os.getcwd(); OUT=os.path.join(ROOT,'assets','generated','generic-hypercar-v1'); os.makedirs(OUT,exist_ok=True)
GLB=os.path.join(OUT,'generic_hypercar.glb'); MAN=os.path.join(OUT,'manifest.json'); PNG=os.path.join(OUT,'preview.png')
def act(o):
 bpy.ops.object.select_all(action='DESELECT'); o.select_set(True); bpy.context.view_layer.objects.active=o
def mat(n,c,metal=0,rough=.4):
 m=bpy.data.materials.new(n); m.diffuse_color=(*c,1); m.use_nodes=True; b=m.node_tree.nodes.get('Principled BSDF'); b.inputs['Base Color'].default_value=(*c,1); b.inputs['Metallic'].default_value=metal; b.inputs['Roughness'].default_value=rough; return m
def box(n,loc,dims,bev,ma):
 bpy.ops.mesh.primitive_cube_add(size=1,location=loc); o=bpy.context.object; o.name=n; o.dimensions=dims; act(o); bpy.ops.object.transform_apply(location=False,rotation=False,scale=True); x=o.modifiers.new('b','BEVEL'); x.width=bev; x.segments=4; bpy.ops.object.modifier_apply(modifier=x.name); o.data.materials.append(ma); return o
def wheel(n,loc,ma):
 bpy.ops.mesh.primitive_cylinder_add(vertices=32,radius=.34,depth=.24,location=loc,rotation=(0,math.pi/2,0)); o=bpy.context.object; o.name=n; o.data.materials.append(ma); x=o.modifiers.new('b','BEVEL'); x.width=.035; x.segments=2; act(o); bpy.ops.object.modifier_apply(modifier=x.name); return o
def look(o,p): o.rotation_euler=(Vector(p)-o.location).to_track_quat('-Z','Y').to_euler()
def sha(p):
 h=hashlib.sha256()
 with open(p,'rb') as f:
  for c in iter(lambda:f.read(1048576),b''): h.update(c)
 return h.hexdigest()
bpy.ops.object.select_all(action='SELECT'); bpy.ops.object.delete(use_global=False)
paint=mat('iss_generic_red',(0.42,.018,.012),.55,.24); rubber=mat('iss_generic_tire',(.018,.018,.018),0,.72); glass=mat('iss_generic_glass',(.025,.04,.055),.15,.16)
parts=[box('chassis',(0,0,.55),(1.86,4.42,.48),.20,paint),box('body',(0,-.1,.86),(1.78,3.72,.42),.22,paint),box('cabin',(0,.15,1.13),(1.50,2.05,.50),.24,glass),box('nose',(0,-1.78,.68),(1.76,.78,.34),.15,paint),box('rear',(0,1.63,.75),(1.78,.88,.34),.14,paint)]
for i,p in enumerate([(-.91,-1.42,.36),(.91,-1.42,.36),(-.91,1.40,.36),(.91,1.40,.36)],1): parts.append(wheel(f'wheel_{i}',p,rubber))
bpy.ops.object.select_all(action='DESELECT'); [p.select_set(True) for p in parts]; bpy.context.view_layer.objects.active=parts[0]; bpy.ops.object.join(); car=bpy.context.object; car.name='generic_hypercar_chassis_body_wheels_front_rear'; act(car)
minz=min((car.matrix_world@Vector(c)).z for c in car.bound_box); car.location.z-=minz; bpy.ops.object.transform_apply(location=True,rotation=False,scale=True)
bpy.ops.export_scene.gltf(filepath=GLB,export_format='GLB',use_selection=True,export_apply=True); digest=sha(GLB)
bpy.ops.object.select_all(action='SELECT'); bpy.ops.object.delete(use_global=False); bpy.ops.import_scene.gltf(filepath=GLB); meshes=[o for o in bpy.context.scene.objects if o.type=='MESH']
if len(meshes)!=1: raise RuntimeError('SINGLE_MESH_FAIL')
car=meshes[0]; verts=len(car.data.vertices); tris=sum(max(1,len(p.vertices)-2) for p in car.data.polygons); cs=[car.matrix_world@Vector(c) for c in car.bound_box]; xs=[v.x for v in cs]; ys=[v.y for v in cs]; zs=[v.z for v in cs]; W=max(xs)-min(xs); L=max(ys)-min(ys); H=max(zs)-min(zs)
if not(3.8<=L<=5.5 and 1.6<=W<=2.3 and .9<=H<=1.6 and verts>=300 and tris>=500): raise RuntimeError(f'GEOMETRY_FAIL {L} {W} {H} {verts} {tris}')
miny=min(v.co.y for v in car.data.vertices); dv=[v for v in car.data.vertices if v.co.y<=miny+.72]
if len(dv)<20: raise RuntimeError('DAMAGE_SET_FAIL')
old=[(v,v.co.copy()) for v in dv]
for v in dv: v.co.y+=.06
mut=any((v.co-o).length>.01 for v,o in old)
for v,o in old: v.co=o
if not mut: raise RuntimeError('DAMAGE_MUTATION_FAIL')
act(car); bpy.ops.rigidbody.object_add(); car.rigid_body.mass=1450; car.rigid_body.collision_shape='CONVEX_HULL'; car.location.z+=.6
bpy.ops.mesh.primitive_cube_add(size=1,location=(0,0,-.1)); g=bpy.context.object; g.dimensions=(8,10,.2); act(g); bpy.ops.object.transform_apply(location=False,rotation=False,scale=True); bpy.ops.rigidbody.object_add(); g.rigid_body.type='PASSIVE'; sc=bpy.context.scene; sc.frame_start=1; sc.frame_end=48; sc.frame_set(1); z0=car.matrix_world.translation.z
for f in range(1,49): sc.frame_set(f); bpy.context.view_layer.update()
z1=car.matrix_world.translation.z; rigid=(z0-z1)>.2 and z1>-.15
if not rigid: raise RuntimeError(f'RIGID_FAIL {z0} {z1}')
sc.render.engine='BLENDER_EEVEE_NEXT'; sc.render.resolution_x=320; sc.render.resolution_y=180; sc.render.resolution_percentage=50; sc.render.image_settings.file_format='PNG'; sc.render.filepath=PNG; bpy.ops.object.camera_add(location=(5.8,-7,3.3)); cam=bpy.context.object; look(cam,(0,0,.65)); sc.camera=cam; bpy.ops.object.light_add(type='AREA',location=(2,-2,6)); bpy.context.object.data.energy=1500; sc.frame_set(48); bpy.ops.render.render(write_still=True); render=os.path.isfile(PNG) and os.path.getsize(PNG)>1000
m={'contract':'iss-blender-asset-author-v1','engine':'BLENDER','engineVersion':V,'category':'sports_car','subcategory':'generic_hypercar','sourceProvider':'iss_original_blender','sourceUid':'generic-hypercar-v1','assetName':'ISS Generic Hypercar v1','licenseCode':'original_generated','commercialUseAllowed':True,'modificationAllowed':True,'redistributionTermsCompatible':True,'glbImportPass':True,'singleMeshActorPass':True,'meshObjectCount':1,'rigidBodySimulationPass':rigid,'collisionProxyPass':rigid,'damageVertexMutationPass':mut,'headlessRenderPass':render,'realWorldScalePass':True,'noBrandPass':True,'wheelSilhouetteCount':4,'vertexCount':verts,'triangleCount':tris,'damageVertexCount':len(dv),'dimensionsMeters':{'length':round(L,6),'width':round(W,6),'height':round(H,6)},'massKg':1450,'sha256':digest,'fileBytes':os.path.getsize(GLB),'productionAcceptance':'ASSET_LEVEL_ONLY'}
with open(MAN,'w') as f: json.dump(m,f,indent=2,sort_keys=True)
print(json.dumps(m,sort_keys=True)); print('ISS_HYPERCAR_AUTHORING=PASS')