from pathlib import Path

p=Path('blender/visual_acceptance_vnext.py')
s=p.read_text(encoding='utf-8')
# Keep the two-sided launch centered near x=0 at impact.
s=s.replace("c=actor('BUGATTI','assets/test-real-model/bugatti_quant120.json',CAR_SHA,4.4,CAR_MASS,.42,-12.5,CM);d=actor('BULLDOZER','assets/test-real-model/bulldozer_quant120.json',DOZER_SHA,6.1,DOZER_MASS,.82,11.5,DM);details(c,d);seed(c['p'],-12.5,-11.5);seed(d['p'],11.5,11.15)","c=actor('BUGATTI','assets/test-real-model/bugatti_quant120.json',CAR_SHA,4.4,CAR_MASS,.42,-18.0,CM);d=actor('BULLDOZER','assets/test-real-model/bulldozer_quant120.json',DOZER_SHA,6.1,DOZER_MASS,.82,8.05,DM);details(c,d);seed(c['p'],-18.0,-17.0);seed(d['p'],8.05,7.70)")
# The visual road must also be a real passive collision floor. Low friction models rolling resistance
# for the box proxies so both actors retain their seeded approach speeds.
s=s.replace("env(sc);CM=mat('BUGATTI_BLUE'", "env(sc)\nroad=bpy.data.objects.get('ROAD')\nif road is None: raise RuntimeError('ROAD_MISSING')\nact(road); bpy.ops.rigidbody.object_add(); road.rigid_body.type='PASSIVE'; road.rigid_body.collision_shape='BOX'; road.rigid_body.friction=.08; road.rigid_body.restitution=.01\nCM=mat('BUGATTI_BLUE'")
# Avoid attempting to create a second rigid-body world if object_add already created it.
s=s.replace("act(c['p']);bpy.ops.rigidbody.world_add();w=sc.rigidbody_world;w.point_cache.frame_start=START;w.point_cache.frame_end=END;w.substeps_per_frame=24;w.solver_iterations=40","\nif sc.rigidbody_world is None:\n act(c['p']); bpy.ops.rigidbody.world_add()\nw=sc.rigidbody_world\nif w is None: raise RuntimeError('RIGID_BODY_WORLD_MISSING')\nw.point_cache.frame_start=START;w.point_cache.frame_end=END;w.substeps_per_frame=24;w.solver_iterations=40")
exec(compile(s,str(p),'exec'))
