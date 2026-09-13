from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path

import bpy
from mathutils import Vector

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from blender import visual_v4_scene as core

FPS = core.FPS
START = core.START
END = core.END
HANDOFF = core.HANDOFF
CAR_MASS = core.CAR_MASS
CAR_TARGET_LENGTH = core.CAR_TARGET_LENGTH


def args() -> argparse.Namespace:
    argv = sys.argv
    argv = argv[argv.index("--") + 1:] if "--" in argv else []
    p = argparse.ArgumentParser()
    p.add_argument("--bugatti-a", required=True)
    p.add_argument("--bugatti-b", required=True)
    p.add_argument("--asset-manifest", required=True)
    p.add_argument("--out", default="artifacts/visual-vnext-rc2-preflight")
    p.add_argument("--mode", choices=("preflight",), default="preflight")
    return p.parse_args(argv)


def fail(msg: str) -> None:
    raise RuntimeError(msg)


def import_bugatti(name: str, path: Path, want_front_sign: int) -> dict:
    if not path.is_file():
        fail(f"{name}_PRIMARY_SCENE_MISSING:{path}")
    before = set(bpy.data.objects)
    bpy.ops.import_scene.gltf(filepath=str(path))
    new = [o for o in bpy.data.objects if o not in before]
    meshes = core.mesh_objects(new)
    if not meshes:
        fail(f"{name}_IMPORT_NO_MESH")

    root = bpy.data.objects.new(f"{name}_VISUAL_ROOT", None)
    bpy.context.collection.objects.link(root)
    new_set = set(new)
    for o in new:
        if o.parent is None or o.parent not in new_set:
            mw = o.matrix_world.copy()
            o.parent = root
            o.matrix_world = mw

    bpy.context.view_layer.update()
    lo, hi = core.world_bbox(meshes)
    dims = hi - lo
    if dims.y > dims.x:
        root.rotation_euler.z -= math.pi / 2.0
        bpy.context.view_layer.update()
    lo, hi = core.recenter_floor(root, meshes)
    dims = hi - lo
    if dims.x <= 1e-5:
        fail(f"{name}_ZERO_LENGTH")
    scale = CAR_TARGET_LENGTH / dims.x
    root.scale = tuple(float(x) * scale for x in root.scale)
    bpy.context.view_layer.update()
    lo, hi = core.recenter_floor(root, meshes)

    front_x = core.semantic_centroid_x(meshes, ("front", "hood", "bonnet", "bumper", "headlight", "grill", "grille"))
    if front_x is None:
        fail(f"{name}_FRONT_SEMANTIC_UNRESOLVED")
    current_sign = 1 if front_x >= 0.0 else -1
    if current_sign != want_front_sign:
        root.rotation_euler.z += math.pi
        bpy.context.view_layer.update()
        lo, hi = core.recenter_floor(root, meshes)

    lo, hi = core.world_bbox(meshes)
    dims = hi - lo
    if abs(dims.x - CAR_TARGET_LENGTH) > CAR_TARGET_LENGTH * 0.08:
        fail(f"{name}_NORMALIZED_LENGTH_GATE:{dims.x}")
    return {"name": name, "root": root, "objects": new, "meshes": meshes, "dims": dims}


def overlap(a: dict, b: dict) -> bool:
    pa = a["proxy"].matrix_world.translation
    pb = b["proxy"].matrix_world.translation
    da = Vector(a["proxy"].dimensions) * 0.5
    db = Vector(b["proxy"].dimensions) * 0.5
    return abs(pa.x - pb.x) <= da.x + db.x + 0.08 and abs(pa.y - pb.y) <= da.y + db.y + 0.08


def simulate(scene: bpy.types.Scene, a: dict, b: dict) -> dict:
    if scene.rigidbody_world is None:
        fail("RIGID_BODY_WORLD_MISSING")
    scene.rigidbody_world.point_cache.frame_start = START
    scene.rigidbody_world.point_cache.frame_end = END
    scene.rigidbody_world.substeps_per_frame = 30
    scene.rigidbody_world.solver_iterations = 50

    records = {"a": {}, "b": {}}
    prev_a = prev_b = None
    impact = None
    impact_data = None
    a_pre_max = b_pre_max = 0.0
    a_approach = b_approach = False
    a_pre_vx = b_pre_vx = None
    a_post_vx = b_post_vx = None

    scene.frame_set(START)
    for frame in range(START, END + 1):
        scene.frame_set(frame)
        bpy.context.view_layer.update()
        pa = a["proxy"].matrix_world.translation.copy()
        pb = b["proxy"].matrix_world.translation.copy()
        qa = a["proxy"].matrix_world.to_quaternion().copy()
        qb = b["proxy"].matrix_world.to_quaternion().copy()
        records["a"][frame] = (pa.copy(), qa)
        records["b"][frame] = (pb.copy(), qb)
        va = Vector((0, 0, 0)) if prev_a is None else (pa - prev_a) * FPS
        vb = Vector((0, 0, 0)) if prev_b is None else (pb - prev_b) * FPS

        if frame >= HANDOFF and impact is None:
            a_pre_max = max(a_pre_max, va.length)
            b_pre_max = max(b_pre_max, vb.length)
            a_approach = a_approach or va.x > 8.0
            b_approach = b_approach or vb.x < -8.0
            if frame >= HANDOFF + 2 and overlap(a, b) and (va - vb).length > 15.0:
                impact = frame
                a_pre_vx = float(va.x)
                b_pre_vx = float(vb.x)
                impact_data = {
                    "bugattiAPosition": list(pa),
                    "bugattiBPosition": list(pb),
                    "bugattiAVelocity": list(va),
                    "bugattiBVelocity": list(vb),
                    "relativeSpeed": (va - vb).length,
                    "center": list((pa + pb) * 0.5),
                }
        elif impact is not None and frame >= impact + 6 and a_post_vx is None:
            a_post_vx = float(va.x)
            b_post_vx = float(vb.x)

        prev_a, prev_b = pa, pb

    if impact is None or impact_data is None:
        fail("HEAD_ON_IMPACT_NOT_OBSERVED")
    center_x = float(impact_data["center"][0])
    if abs(center_x) > 1.5:
        fail(f"IMPACT_NOT_CENTERED:{center_x}")
    if not (a_approach and b_approach):
        fail("TWO_SIDED_APPROACH_GATE_FAIL")
    if a_pre_max < 10.0 or b_pre_max < 10.0:
        fail(f"APPROACH_SPEED_GATE_FAIL:{a_pre_max}:{b_pre_max}")
    if a_post_vx is None or b_post_vx is None or a_pre_vx is None or b_pre_vx is None:
        fail("POST_IMPACT_SAMPLE_MISSING")
    a_delta = abs(a_post_vx - a_pre_vx)
    b_delta = abs(b_post_vx - b_pre_vx)
    if a_delta < 0.5 or b_delta < 0.5:
        fail(f"POST_IMPACT_RESPONSE_TOO_SMALL:{a_delta}:{b_delta}")

    return {
        "records": records,
        "impactFrame": impact,
        "impactData": impact_data,
        "aApproach": a_approach,
        "bApproach": b_approach,
        "aPreImpactMaxSpeed": a_pre_max,
        "bPreImpactMaxSpeed": b_pre_max,
        "aResponseDeltaVx": a_delta,
        "bResponseDeltaVx": b_delta,
    }


def impact_damage(actor: dict, impact_frame: int, front_sign: int) -> int:
    scene = bpy.context.scene
    scene.frame_set(START)
    bpy.context.view_layer.update()
    proxy = actor["proxy"]
    center_x = proxy.matrix_world.translation.x
    half_len = float(actor["dims"].x) * 0.5
    threshold = center_x + front_sign * half_len * 0.42
    affected = 0
    for obj in actor["meshes"]:
        if obj.type != "MESH" or len(obj.data.vertices) == 0:
            continue
        try:
            if obj.data.shape_keys is None:
                obj.shape_key_add(name="Basis", from_mix=False)
            key = obj.shape_key_add(name=f"ImpactCrumple_{actor['name']}", from_mix=False)
        except Exception:
            continue
        inv = obj.matrix_world.inverted()
        local_hits = 0
        for i, point in enumerate(key.data):
            world = obj.matrix_world @ point.co
            penetration_axis = (world.x - threshold) * front_sign
            if penetration_axis <= 0:
                continue
            t = min(1.0, max(0.0, penetration_axis / max(0.20, half_len * 0.58)))
            target = world.copy()
            target.x -= front_sign * 0.72 * t
            target.z -= 0.16 * t
            target.y += (0.08 if (i % 2) else -0.08) * t
            point.co = inv @ target
            local_hits += 1
        if local_hits:
            key.value = 0.0
            key.keyframe_insert(data_path="value", frame=max(START, impact_frame - 1))
            key.value = 1.0
            key.keyframe_insert(data_path="value", frame=min(END, impact_frame + 5))
            affected += local_hits
        else:
            obj.shape_key_remove(key)
    if affected < 500:
        fail(f"{actor['name']}_DAMAGE_VERTEX_GATE_TOO_LOW:{affected}")
    return affected


def main() -> None:
    a = args()
    outdir = Path(a.out)
    manifest_path = Path(a.asset_manifest)
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if manifest.get("status") != "PASS" or manifest.get("quant120Forbidden") is not True:
        fail("ASSET_MANIFEST_NOT_PASS")
    assets = manifest.get("assets") or {}
    aa = assets.get("bugattiA") or {}
    bb = assets.get("bugattiB") or {}
    if aa.get("identity", {}).get("binaryExact") is not True or bb.get("identity", {}).get("binaryExact") is not True:
        fail("BUGATTI_DUEL_BINARY_IDENTITY_GATE_FAIL")
    if aa.get("identity", {}).get("primarySceneSha256") != bb.get("identity", {}).get("primarySceneSha256"):
        fail("BUGATTI_DUEL_SOURCE_IDENTITY_MISMATCH")

    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.object.delete(use_global=False)
    scene = bpy.context.scene
    scene.frame_start = START
    scene.frame_end = END
    scene.gravity = (0, 0, -9.81)
    core.configure_render(scene, a.mode, outdir)
    lighting = core.setup_environment(scene)

    car_a = import_bugatti("BUGATTI_A", Path(a.bugatti_a), +1)
    car_b = import_bugatti("BUGATTI_B", Path(a.bugatti_b), -1)
    core.add_proxy(car_a, CAR_MASS, 0.20)
    core.add_proxy(car_b, CAR_MASS, 0.20)
    core.seed_velocity(car_a["proxy"], -24.0, +15.0)
    core.seed_velocity(car_b["proxy"], +24.0, -15.0)

    if not core.no_post_handoff_vehicle_location_keys(car_a) or not core.no_post_handoff_vehicle_location_keys(car_b):
        fail("POST_HANDOFF_VEHICLE_LOCATION_KEY_DETECTED")

    sim = simulate(scene, car_a, car_b)
    core.bake_actor(car_a, sim["records"]["a"])
    core.bake_actor(car_b, sim["records"]["b"])

    impact_frame = int(sim["impactFrame"])
    center = Vector(sim["impactData"]["center"])
    damage_a = impact_damage(car_a, impact_frame, +1)
    damage_b = impact_damage(car_b, impact_frame, -1)
    debris = core.make_debris(scene, impact_frame, center)
    camdata = core.setup_cameras(scene, impact_frame, center)

    if lighting["lightCount"] < 4 or lighting["worldStrength"] < 0.7:
        fail("LIGHTING_STRUCTURE_GATE_FAIL")
    if len(camdata["cameras"]) < 3 or camdata["aftermathDollyDistance"] < 2.0:
        fail("CAMERA_STORY_STRUCTURE_GATE_FAIL")

    previews = core.render_preflight(scene, camdata, impact_frame, outdir)

    machine_gates = {
        "A1_twoSidedApproach": bool(sim["aApproach"] and sim["bApproach"]),
        "A2_headOnCenterImpact": abs(float(center.x)) <= 1.5 and float(sim["impactData"]["relativeSpeed"]) > 15.0,
        "A3_bothVehiclesActiveMotionAndResponse": sim["aPreImpactMaxSpeed"] >= 10.0 and sim["bPreImpactMaxSpeed"] >= 10.0 and sim["aResponseDeltaVx"] >= 0.5 and sim["bResponseDeltaVx"] >= 0.5,
        "A4_damageGeometryCreatedBothVehicles": damage_a >= 500 and damage_b >= 500,
        "A5_debrisRigidBodyAndImpactTriggered": debris["count"] >= 12 and debris["rigidBodyAfterRelease"] and debris["impactTriggered"] and debris["maxDisplacement"] >= 0.35,
        "A6_renderStructureImproved": scene.render.engine == "BLENDER_EEVEE_NEXT" and scene.render.resolution_x >= 960,
        "A7_threeCameraStructure": len(camdata["cameras"]) >= 3,
        "A8_aftermathDollyStructure": camdata["aftermathDollyDistance"] >= 2.0,
        "A9_storyShotStructure": camdata["impactCutFrame"] < camdata["aftermathFrame"] < END,
        "A11_lightingStructure": lighting["lightCount"] >= 4 and lighting["worldStrength"] >= 0.7,
    }
    if not all(machine_gates.values()):
        fail("MACHINE_GATE_FAIL:" + ",".join(k for k, v in machine_gates.items() if not v))

    result = {
        "scope": "ISS_VISUAL_VNEXT_RC2_BUGATTI_DUEL",
        "mode": "preflight",
        "status": "MACHINE_PREFLIGHT_PASS_VISUAL_REVIEW_REQUIRED",
        "engine": "BLENDER",
        "engineVersion": bpy.app.version_string,
        "renderEngine": scene.render.engine,
        "resolution": [scene.render.resolution_x, scene.render.resolution_y],
        "fps": FPS,
        "frameCount": END,
        "visualGeometry": "FULL_SOURCE_GLTF",
        "visualProxyUsed": False,
        "collisionProxyUsed": True,
        "vehicleMotionSolverDriven": True,
        "postHandoffVehicleLocationKeys": False,
        "damagePhysicalSolver": False,
        "damageImpactTriggered": True,
        "bugattiADamageAffectedVertices": damage_a,
        "bugattiBDamageAffectedVertices": damage_b,
        "debrisRigidBody": True,
        "debrisReleaseImpactTriggered": True,
        "debrisCount": debris["count"],
        "debrisMaxDisplacement": debris["maxDisplacement"],
        "impactFrame": impact_frame,
        "impactTimeSeconds": impact_frame / FPS,
        "impactCenter": list(center),
        "impactRelativeSpeedMps": float(sim["impactData"]["relativeSpeed"]),
        "bugattiAPreImpactMaxSpeedMps": sim["aPreImpactMaxSpeed"],
        "bugattiBPreImpactMaxSpeedMps": sim["bPreImpactMaxSpeed"],
        "bugattiAResponseDeltaVx": sim["aResponseDeltaVx"],
        "bugattiBResponseDeltaVx": sim["bResponseDeltaVx"],
        "cameraShotCount": len(camdata["cameras"]),
        "aftermathDollyDistance": camdata["aftermathDollyDistance"],
        "lighting": lighting,
        "machineGates": machine_gates,
        "visualReviewRequired": ["A4_damage_readability_both", "A6_image_quality", "A11_scene_brightness", "head_on_collision_readability", "overall_cinematic_readability"],
        "previews": previews,
        "finalFrames": [],
        "assetManifest": str(manifest_path),
    }
    result_path = outdir / "preflight-result.json"
    result_path.write_text(json.dumps(result, indent=2), encoding="utf-8")
    print("ISS_VISUAL_VNEXT_RC2_BUGATTI_DUEL_MACHINE_PREFLIGHT=PASS")
    print("FINAL_RENDER_AUTHORIZATION=NOT_YET_VISUAL_REVIEW_REQUIRED")


if __name__ == "__main__":
    main()
