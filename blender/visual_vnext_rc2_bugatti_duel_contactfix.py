from __future__ import annotations

import math
import sys
from pathlib import Path

import bpy
from bpy_extras.object_utils import world_to_camera_view
from mathutils import Vector

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from blender import visual_vnext_rc2_bugatti_duel as wrapper

duel = wrapper.duel
core = duel.core
READABILITY_STATE: dict = {"damage": {}}


def solver_contact_simulate(scene: bpy.types.Scene, a: dict, b: dict) -> dict:
    if scene.rigidbody_world is None:
        duel.fail("RIGID_BODY_WORLD_MISSING")
    scene.rigidbody_world.point_cache.frame_start = duel.START
    scene.rigidbody_world.point_cache.frame_end = duel.END
    scene.rigidbody_world.substeps_per_frame = 30
    scene.rigidbody_world.solver_iterations = 50

    records = {"a": {}, "b": {}}
    prev_a = prev_b = None
    prev_va = prev_vb = None
    impact = None
    impact_data = None
    a_pre_max = b_pre_max = 0.0
    a_approach = b_approach = False
    a_pre_vx = b_pre_vx = None
    a_post_vx = b_post_vx = None

    scene.frame_set(duel.START)
    for frame in range(duel.START, duel.END + 1):
        scene.frame_set(frame)
        bpy.context.view_layer.update()
        pa = a["proxy"].matrix_world.translation.copy()
        pb = b["proxy"].matrix_world.translation.copy()
        qa = a["proxy"].matrix_world.to_quaternion().copy()
        qb = b["proxy"].matrix_world.to_quaternion().copy()
        records["a"][frame] = (pa.copy(), qa)
        records["b"][frame] = (pb.copy(), qb)
        va = Vector((0, 0, 0)) if prev_a is None else (pa - prev_a) * duel.FPS
        vb = Vector((0, 0, 0)) if prev_b is None else (pb - prev_b) * duel.FPS

        if frame >= duel.HANDOFF and impact is None:
            a_pre_max = max(a_pre_max, va.length)
            b_pre_max = max(b_pre_max, vb.length)
            a_approach = a_approach or va.x > 8.0
            b_approach = b_approach or vb.x < -8.0

            # Bullet exposes the first contact frame after its contact response has
            # already been solved. Preserve the proven RC2 contract by pairing the
            # contact geometry with the immediately preceding incoming velocity.
            incoming_relative = None if prev_va is None or prev_vb is None else (prev_va - prev_vb).length
            if frame >= duel.HANDOFF + 2 and duel.overlap(a, b) and incoming_relative is not None and incoming_relative > 15.0:
                impact = frame
                a_pre_vx = float(prev_va.x)
                b_pre_vx = float(prev_vb.x)
                impact_data = {
                    "bugattiAPosition": list(pa),
                    "bugattiBPosition": list(pb),
                    "bugattiAVelocity": list(prev_va),
                    "bugattiBVelocity": list(prev_vb),
                    "relativeSpeed": float(incoming_relative),
                    "center": list((pa + pb) * 0.5),
                    "detector": "SOLVER_CONTACT_WITH_PRESTEP_INCOMING_SPEED",
                    "contactFrame": frame,
                    "incomingVelocityFrame": frame - 1,
                }
                print(
                    "BUGATTI_DUEL_SOLVER_CONTACT=PASS"
                    f"|contactFrame={frame}"
                    f"|incomingFrame={frame-1}"
                    f"|incomingRelativeSpeed={incoming_relative:.6f}"
                    f"|centerX={float(((pa+pb)*0.5).x):.6f}",
                    flush=True,
                )
        elif impact is not None and frame >= impact + 6 and a_post_vx is None:
            a_post_vx = float(va.x)
            b_post_vx = float(vb.x)

        prev_a, prev_b = pa, pb
        prev_va, prev_vb = va.copy(), vb.copy()

    if impact is None or impact_data is None:
        duel.fail("HEAD_ON_IMPACT_NOT_OBSERVED")
    center_x = float(impact_data["center"][0])
    if abs(center_x) > 1.5:
        duel.fail(f"IMPACT_NOT_CENTERED:{center_x}")
    if not (a_approach and b_approach):
        duel.fail("TWO_SIDED_APPROACH_GATE_FAIL")
    if a_pre_max < 10.0 or b_pre_max < 10.0:
        duel.fail(f"APPROACH_SPEED_GATE_FAIL:{a_pre_max}:{b_pre_max}")
    if a_post_vx is None or b_post_vx is None or a_pre_vx is None or b_pre_vx is None:
        duel.fail("POST_IMPACT_SAMPLE_MISSING")
    a_delta = abs(a_post_vx - a_pre_vx)
    b_delta = abs(b_post_vx - b_pre_vx)
    if a_delta < 0.5 or b_delta < 0.5:
        duel.fail(f"POST_IMPACT_RESPONSE_TOO_SMALL:{a_delta}:{b_delta}")

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


def descendant_meshes(root: bpy.types.Object) -> list[bpy.types.Object]:
    meshes: list[bpy.types.Object] = []
    stack = list(root.children)
    while stack:
        obj = stack.pop()
        if obj.type == "MESH" and len(obj.data.vertices) > 0:
            meshes.append(obj)
        stack.extend(list(obj.children))
    return meshes


def actor_meshes(name: str) -> list[bpy.types.Object]:
    root = bpy.data.objects.get(f"{name}_VISUAL_ROOT")
    if root is None:
        duel.fail(f"READABILITY_ACTOR_ROOT_MISSING:{name}")
    meshes = descendant_meshes(root)
    if not meshes:
        duel.fail(f"READABILITY_ACTOR_MESH_MISSING:{name}")
    return meshes


def proxy(name: str) -> bpy.types.Object:
    obj = bpy.data.objects.get(f"PHYSICS_{name}")
    if obj is None:
        duel.fail(f"READABILITY_PROXY_MISSING:{name}")
    return obj


def debris_objects() -> list[bpy.types.Object]:
    return sorted(
        [obj for obj in bpy.data.objects if obj.name.startswith("IMPACT_DEBRIS_") and obj.type == "MESH"],
        key=lambda obj: obj.name,
    )


def actor_midpoint(scene: bpy.types.Scene, frame: int) -> Vector:
    scene.frame_set(frame)
    bpy.context.view_layer.update()
    return (proxy("BUGATTI_A").matrix_world.translation + proxy("BUGATTI_B").matrix_world.translation) * 0.5


def actor_separation(scene: bpy.types.Scene, frame: int) -> float:
    scene.frame_set(frame)
    bpy.context.view_layer.update()
    return (proxy("BUGATTI_A").matrix_world.translation - proxy("BUGATTI_B").matrix_world.translation).length


def damage_factor(scene: bpy.types.Scene, frame: int, name: str) -> float:
    scene.frame_set(frame)
    bpy.context.view_layer.update()
    values: list[float] = []
    key_name = f"ImpactCrumple_{name}"
    for obj in actor_meshes(name):
        keys = getattr(obj.data, "shape_keys", None)
        if not keys:
            continue
        key = keys.key_blocks.get(key_name)
        if key is not None:
            values.append(float(key.value))
    return max(values) if values else 0.0


def debris_near(scene: bpy.types.Scene, frame: int, center: Vector, radius: float) -> int:
    scene.frame_set(frame)
    bpy.context.view_layer.update()
    count = 0
    for obj in debris_objects():
        if obj.hide_render:
            continue
        if (obj.matrix_world.translation - center).length <= radius:
            count += 1
    return count


def readable_impact_damage(actor: dict, impact_frame: int, front_sign: int) -> int:
    scene = bpy.context.scene
    scene.frame_set(duel.START)
    bpy.context.view_layer.update()
    p = actor["proxy"]
    center_x = p.matrix_world.translation.x
    half_len = float(actor["dims"].x) * 0.5
    threshold = center_x + front_sign * half_len * 0.40
    affected = 0
    max_deformation = 0.0

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
            t = min(1.0, max(0.0, penetration_axis / max(0.20, half_len * 0.60)))
            dx = 0.90 * t
            dz = 0.22 * t
            dy = (0.11 if (i % 2) else -0.11) * t
            target = world.copy()
            target.x -= front_sign * dx
            target.z -= dz
            target.y += dy
            point.co = inv @ target
            local_hits += 1
            max_deformation = max(max_deformation, math.sqrt(dx * dx + dy * dy + dz * dz))

        if local_hits:
            key.value = 0.0
            key.keyframe_insert(data_path="value", frame=max(duel.START, impact_frame - 1))
            key.value = 1.0
            key.keyframe_insert(data_path="value", frame=min(duel.END, impact_frame + 4))
            keys = obj.data.shape_keys
            if keys.animation_data and keys.animation_data.action:
                for fc in keys.animation_data.action.fcurves:
                    if fc.data_path.endswith(f'key_blocks["ImpactCrumple_{actor["name"]}"].value'):
                        for kp in fc.keyframe_points:
                            kp.interpolation = "LINEAR"
            affected += local_hits
        else:
            obj.shape_key_remove(key)

    if affected < 500:
        duel.fail(f"{actor['name']}_DAMAGE_VERTEX_GATE_TOO_LOW:{affected}")
    if max_deformation < 0.65:
        duel.fail(f"{actor['name']}_DAMAGE_READABILITY_DEFORMATION_TOO_LOW:{max_deformation}")

    READABILITY_STATE["damage"][actor["name"]] = {
        "affectedVertices": int(affected),
        "maxDeformationM": float(max_deformation),
    }
    print(
        f"{actor['name']}_VISIBLE_DAMAGE=PASS"
        f"|affectedVertices={affected}"
        f"|maxDeformationM={max_deformation:.6f}",
        flush=True,
    )
    return affected


def choose_event_frames(scene: bpy.types.Scene, impact_frame: int, center: Vector) -> dict[str, int]:
    if impact_frame <= duel.HANDOFF + 2:
        duel.fail("READABILITY_IMPACT_TOO_EARLY")

    target_sep = duel.CAR_TARGET_LENGTH + 3.0
    approach_candidates = range(duel.HANDOFF, max(duel.HANDOFF + 1, impact_frame - 2))
    approach = min(approach_candidates, key=lambda frame: (abs(actor_separation(scene, frame) - target_sep), -frame))

    impact_rows = []
    for frame in range(impact_frame, min(duel.END, impact_frame + 9) + 1):
        da = damage_factor(scene, frame, "BUGATTI_A")
        db = damage_factor(scene, frame, "BUGATTI_B")
        dn = debris_near(scene, frame, center, 5.5)
        score = min(da, db) * 5.0 + min(dn, 16) * 0.22 - abs(frame - (impact_frame + 4)) * 0.04
        impact_rows.append((score, min(da, db), dn, frame))
    viable_impact = [row for row in impact_rows if row[1] >= 0.75 and row[2] >= 4]
    if not viable_impact:
        duel.fail("EVENT_DRIVEN_IMPACT_FRAME_NOT_READABLE")
    impact_visual = max(viable_impact)[3]

    aftermath_rows = []
    start = min(duel.END, impact_frame + 10)
    stop = min(duel.END, impact_frame + 34)
    for frame in range(start, stop + 1):
        da = damage_factor(scene, frame, "BUGATTI_A")
        db = damage_factor(scene, frame, "BUGATTI_B")
        dn = debris_near(scene, frame, center, 8.0)
        sep = actor_separation(scene, frame)
        continuity = 1.0 if 2.0 <= sep <= 15.0 else max(0.0, 1.0 - abs(sep - 8.0) / 18.0)
        score = min(da, db) * 3.0 + min(dn, 16) * 0.16 + continuity - abs(frame - (impact_frame + 22)) * 0.025
        aftermath_rows.append((score, min(da, db), dn, sep, frame))
    viable_after = [row for row in aftermath_rows if row[1] >= 0.95 and row[2] >= 3 and 1.0 <= row[3] <= 18.0]
    if not viable_after:
        duel.fail("EVENT_DRIVEN_AFTERMATH_FRAME_NOT_READABLE")
    aftermath = max(viable_after)[4]

    if not (approach < impact_visual < aftermath):
        duel.fail(f"EVENT_FRAME_ORDER_INVALID:{approach}:{impact_visual}:{aftermath}")

    frames = {"approach": int(approach), "impact": int(impact_visual), "aftermath": int(aftermath)}
    READABILITY_STATE["previewFrames"] = frames
    print(
        "BUGATTI_DUEL_EVENT_FRAMES=PASS"
        f"|approach={frames['approach']}"
        f"|impact={frames['impact']}"
        f"|aftermath={frames['aftermath']}",
        flush=True,
    )
    return frames


def projected_rect(scene: bpy.types.Scene, cam: bpy.types.Object, objects: list[bpy.types.Object]) -> dict:
    points: list[tuple[float, float, float]] = []
    behind = False
    for obj in objects:
        for corner in obj.bound_box:
            co = world_to_camera_view(scene, cam, obj.matrix_world @ Vector(corner))
            if co.z <= 0:
                behind = True
            points.append((float(co.x), float(co.y), float(co.z)))
    if not points:
        return {"visible": False, "area": 0.0, "rect": [0.0, 0.0, 0.0, 0.0]}
    minx = min(p[0] for p in points)
    maxx = max(p[0] for p in points)
    miny = min(p[1] for p in points)
    maxy = max(p[1] for p in points)
    width = max(0.0, maxx - minx)
    height = max(0.0, maxy - miny)
    visible = not behind and minx >= 0.02 and maxx <= 0.98 and miny >= 0.03 and maxy <= 0.97
    return {"visible": bool(visible), "area": float(width * height), "rect": [minx, miny, maxx, maxy]}


def union_area(a: dict, b: dict) -> float:
    ar = a["rect"]
    br = b["rect"]
    minx = min(ar[0], br[0])
    miny = min(ar[1], br[1])
    maxx = max(ar[2], br[2])
    maxy = max(ar[3], br[3])
    return max(0.0, maxx - minx) * max(0.0, maxy - miny)


def create_target(name: str, point: Vector) -> bpy.types.Object:
    bpy.ops.object.empty_add(type="PLAIN_AXES", location=(point.x, point.y, point.z))
    target = bpy.context.object
    target.name = name
    return target


def fit_camera(
    scene: bpy.types.Scene,
    name: str,
    frame: int,
    target_point: Vector,
    lens: float,
    x_offset: float,
    z_offset: float,
) -> tuple[bpy.types.Object, dict]:
    target = create_target(f"{name}_TARGET", target_point)
    cam = core.camera(name, (target_point.x + x_offset, target_point.y - 18.0, target_point.z + z_offset), lens, target)
    meshes_a = actor_meshes("BUGATTI_A")
    meshes_b = actor_meshes("BUGATTI_B")
    best = None

    for distance in (9.0, 10.0, 11.0, 12.0, 13.0, 14.0, 15.0, 16.0, 18.0, 20.0, 22.0, 24.0, 27.0, 30.0, 34.0):
        cam.location = (target_point.x + x_offset, target_point.y - distance, target_point.z + z_offset)
        scene.frame_set(frame)
        bpy.context.view_layer.update()
        ra = projected_rect(scene, cam, meshes_a)
        rb = projected_rect(scene, cam, meshes_b)
        ua = union_area(ra, rb)
        if ra["visible"] and rb["visible"]:
            score = ua + min(ra["area"], rb["area"]) * 0.45
            candidate = (score, distance, ra, rb, ua)
            if best is None or candidate[0] > best[0]:
                best = candidate

    if best is None:
        duel.fail(f"CAMERA_AUTOFIT_FAILED:{name}:frame={frame}")

    _, distance, ra, rb, ua = best
    cam.location = (target_point.x + x_offset, target_point.y - distance, target_point.z + z_offset)
    scene.frame_set(frame)
    bpy.context.view_layer.update()
    metrics = {
        "frame": int(frame),
        "distance": float(distance),
        "bugattiAArea": float(ra["area"]),
        "bugattiBArea": float(rb["area"]),
        "unionArea": float(ua),
        "bothActorsFullyVisible": bool(ra["visible"] and rb["visible"]),
    }
    if metrics["unionArea"] < 0.08 or min(metrics["bugattiAArea"], metrics["bugattiBArea"]) < 0.018:
        duel.fail(f"SUBJECT_SCALE_READABILITY_FAIL:{name}:{metrics}")
    return cam, metrics


def setup_cameras_readable(scene: bpy.types.Scene, impact_frame: int, center: Vector) -> dict:
    frames = choose_event_frames(scene, impact_frame, center)
    points: dict[str, Vector] = {}
    for label, frame in frames.items():
        point = actor_midpoint(scene, frame)
        point.z = 1.20 if label == "approach" else (1.05 if label == "impact" else 1.20)
        points[label] = point

    approach_cam, approach_metrics = fit_camera(scene, "CAM_BUGATTI_APPROACH_EVENT", frames["approach"], points["approach"], 44.0, -0.5, 3.8)
    impact_cam, impact_metrics = fit_camera(scene, "CAM_BUGATTI_IMPACT_CONTACT", frames["impact"], points["impact"], 50.0, -0.2, 2.7)
    aftermath_cam, aftermath_metrics = fit_camera(scene, "CAM_BUGATTI_AFTERMATH_EVENT", frames["aftermath"], points["aftermath"], 54.0, 0.7, 3.0)

    aft_start = frames["aftermath"]
    aftermath_cam.keyframe_insert(data_path="location", frame=aft_start)
    initial_after = aftermath_cam.location.copy()
    direction = points["aftermath"] - aftermath_cam.location
    if direction.length <= 1e-6:
        duel.fail("AFTERMATH_DOLLY_DIRECTION_INVALID")
    direction.normalize()
    aftermath_cam.location = initial_after + direction * 2.4
    aftermath_cam.keyframe_insert(data_path="location", frame=duel.END)
    dolly_distance = (aftermath_cam.location - initial_after).length

    scene.timeline_markers.clear()
    marker = scene.timeline_markers.new("APPROACH", frame=frames["approach"])
    marker.camera = approach_cam
    impact_cut = max(frames["approach"] + 1, frames["impact"] - 2)
    marker = scene.timeline_markers.new("IMPACT", frame=impact_cut)
    marker.camera = impact_cam
    marker = scene.timeline_markers.new("AFTERMATH", frame=aft_start)
    marker.camera = aftermath_cam
    scene.camera = approach_cam

    camera_metrics = {
        "approach": approach_metrics,
        "impact": impact_metrics,
        "aftermath": aftermath_metrics,
    }
    READABILITY_STATE["cameraMetrics"] = camera_metrics
    print(
        "BUGATTI_DUEL_CONTACT_CENTRIC_CAMERA=PASS"
        f"|approachDistance={approach_metrics['distance']:.2f}"
        f"|impactDistance={impact_metrics['distance']:.2f}"
        f"|aftermathDistance={aftermath_metrics['distance']:.2f}",
        flush=True,
    )
    return {
        "cameras": [approach_cam, impact_cam, aftermath_cam],
        "approachFrame": frames["approach"],
        "impactCutFrame": impact_cut,
        "aftermathFrame": aft_start,
        "aftermathDollyDistance": float(dolly_distance),
        "previewFrames": frames,
        "cameraMetrics": camera_metrics,
    }


def debris_visible_on_camera(scene: bpy.types.Scene, cam: bpy.types.Object, frame: int) -> int:
    scene.frame_set(frame)
    bpy.context.view_layer.update()
    count = 0
    for obj in debris_objects():
        if obj.hide_render:
            continue
        co = world_to_camera_view(scene, cam, obj.matrix_world.translation)
        if co.z > 0 and 0.02 <= co.x <= 0.98 and 0.03 <= co.y <= 0.97:
            count += 1
    return count


def render_preflight_readable(scene: bpy.types.Scene, camdata: dict, impact_frame: int, outdir: Path) -> list[dict]:
    frames = camdata.get("previewFrames") or READABILITY_STATE.get("previewFrames")
    if not isinstance(frames, dict):
        duel.fail("READABILITY_PREVIEW_FRAMES_MISSING")

    labels = ("approach", "impact", "aftermath")
    cameras = {
        "approach": camdata["cameras"][0],
        "impact": camdata["cameras"][1],
        "aftermath": camdata["cameras"][2],
    }
    rows: list[dict] = []

    for label in labels:
        frame = int(frames[label])
        cam = cameras[label]
        scene.frame_set(frame)
        scene.camera = cam
        bpy.context.view_layer.update()

        ra = projected_rect(scene, cam, actor_meshes("BUGATTI_A"))
        rb = projected_rect(scene, cam, actor_meshes("BUGATTI_B"))
        ua = union_area(ra, rb)
        if not (ra["visible"] and rb["visible"]):
            duel.fail(f"PREVIEW_ACTOR_VISIBILITY_FAIL:{label}:{frame}")
        if ua < 0.08 or min(ra["area"], rb["area"]) < 0.018:
            duel.fail(f"PREVIEW_SUBJECT_SCALE_FAIL:{label}:{frame}:{ua}:{ra['area']}:{rb['area']}")

        da = damage_factor(scene, frame, "BUGATTI_A")
        db = damage_factor(scene, frame, "BUGATTI_B")
        debris_visible = debris_visible_on_camera(scene, cam, frame)
        separation = actor_separation(scene, frame)

        if label == "impact":
            if min(da, db) < 0.75:
                duel.fail(f"IMPACT_DAMAGE_NOT_VISUALLY_READY:{da}:{db}")
            if debris_visible < 4:
                duel.fail(f"IMPACT_DEBRIS_NOT_CAMERA_VISIBLE:{debris_visible}")
        elif label == "aftermath":
            if min(da, db) < 0.95:
                duel.fail(f"AFTERMATH_DAMAGE_CONTINUITY_FAIL:{da}:{db}")
            if debris_visible < 3:
                duel.fail(f"AFTERMATH_DEBRIS_CONTINUITY_FAIL:{debris_visible}")
            if not (1.0 <= separation <= 18.0):
                duel.fail(f"AFTERMATH_SPATIAL_CONTINUITY_FAIL:{separation}")

        path = outdir / f"preview-{label}-f{frame:04d}.png"
        scene.render.filepath = str(path)
        bpy.ops.render.render(write_still=True)
        if not path.is_file() or path.stat().st_size < 20000:
            duel.fail(f"PREVIEW_RENDER_INVALID:{path}")

        readability = {
            "bothActorsFullyVisible": True,
            "bugattiAArea": float(ra["area"]),
            "bugattiBArea": float(rb["area"]),
            "unionArea": float(ua),
            "bugattiADamageFactor": float(da),
            "bugattiBDamageFactor": float(db),
            "visibleDebris": int(debris_visible),
            "actorSeparationM": float(separation),
        }
        print(
            f"PREVIEW_FRAME=PASS|label={label}|frame={frame}|bytes={path.stat().st_size}"
            f"|unionArea={ua:.6f}|debrisVisible={debris_visible}|damageA={da:.3f}|damageB={db:.3f}",
            flush=True,
        )
        rows.append({
            "label": label,
            "frame": frame,
            "path": str(path),
            "bytes": path.stat().st_size,
            "readability": readability,
        })

    READABILITY_STATE["previews"] = rows
    print("BUGATTI_DUEL_VISUAL_READABILITY_CONTRACT=PASS", flush=True)
    return rows


duel.simulate = solver_contact_simulate
duel.impact_damage = readable_impact_damage
core.setup_cameras = setup_cameras_readable
core.render_preflight = render_preflight_readable

if __name__ == "__main__":
    duel.main()
