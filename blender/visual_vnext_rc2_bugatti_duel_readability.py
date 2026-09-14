from __future__ import annotations

import json
import math
from pathlib import Path

import bpy
from bpy_extras.object_utils import world_to_camera_view
from mathutils import Vector

import visual_vnext_rc2_bugatti_duel_contactfix as contactfix

# Keep the machine-proven RC2 solver/contact implementation and improve only
# presentation/readability on top of it.
duel = contactfix.duel
core = duel.core
READABILITY: dict = {"damage": {}}


def fail(msg: str) -> None:
    raise RuntimeError(msg)


def proxy(name: str) -> bpy.types.Object:
    obj = bpy.data.objects.get(f"PHYSICS_{name}")
    if obj is None:
        fail(f"READABILITY_PROXY_MISSING:{name}")
    return obj


def actor_meshes(name: str) -> list[bpy.types.Object]:
    root = bpy.data.objects.get(f"{name}_VISUAL_ROOT")
    if root is None:
        fail(f"READABILITY_ACTOR_ROOT_MISSING:{name}")
    out: list[bpy.types.Object] = []
    stack = list(root.children)
    while stack:
        obj = stack.pop()
        if obj.type == "MESH" and len(obj.data.vertices) > 0:
            out.append(obj)
        stack.extend(list(obj.children))
    if not out:
        fail(f"READABILITY_ACTOR_MESH_MISSING:{name}")
    return out


def debris_objects() -> list[bpy.types.Object]:
    return sorted(
        [o for o in bpy.data.objects if o.name.startswith("IMPACT_DEBRIS_") and o.type == "MESH"],
        key=lambda o: o.name,
    )


def actor_midpoint(scene: bpy.types.Scene, frame: int) -> Vector:
    scene.frame_set(frame)
    bpy.context.view_layer.update()
    return (proxy("BUGATTI_A").matrix_world.translation + proxy("BUGATTI_B").matrix_world.translation) * 0.5


def actor_separation(scene: bpy.types.Scene, frame: int) -> float:
    scene.frame_set(frame)
    bpy.context.view_layer.update()
    return (proxy("BUGATTI_A").matrix_world.translation - proxy("BUGATTI_B").matrix_world.translation).length


def damage_factor(scene: bpy.types.Scene, name: str, frame: int) -> float:
    scene.frame_set(frame)
    bpy.context.view_layer.update()
    marker = f"ImpactCrumple_{name}"
    values: list[float] = []
    for obj in actor_meshes(name):
        keys = getattr(obj.data, "shape_keys", None)
        if keys is None:
            continue
        key = keys.key_blocks.get(marker)
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


def impact_damage_readable(actor: dict, impact_frame: int, front_sign: int) -> int:
    scene = bpy.context.scene
    scene.frame_set(duel.START)
    bpy.context.view_layer.update()
    p = actor["proxy"]
    center_x = float(p.matrix_world.translation.x)
    half_len = float(actor["dims"].x) * 0.5
    threshold = center_x + front_sign * half_len * 0.42
    affected = 0
    max_deformation = 0.0
    marker = f"ImpactCrumple_{actor['name']}"

    for obj in actor["meshes"]:
        if obj.type != "MESH" or len(obj.data.vertices) == 0:
            continue
        try:
            if obj.data.shape_keys is None:
                obj.shape_key_add(name="Basis", from_mix=False)
            key = obj.shape_key_add(name=marker, from_mix=False)
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
            dx = 0.90 * t
            dz = 0.22 * t
            dy = (0.11 if (i % 2) else -0.11) * t
            target.x -= front_sign * dx
            target.z -= dz
            target.y += dy
            point.co = inv @ target
            max_deformation = max(max_deformation, math.sqrt(dx * dx + dy * dy + dz * dz))
            local_hits += 1

        if local_hits:
            key.value = 0.0
            key.keyframe_insert(data_path="value", frame=max(duel.START, impact_frame - 1))
            key.value = 1.0
            key.keyframe_insert(data_path="value", frame=min(duel.END, impact_frame + 3))
            keys = obj.data.shape_keys
            if keys.animation_data and keys.animation_data.action:
                for fc in keys.animation_data.action.fcurves:
                    for kp in fc.keyframe_points:
                        kp.interpolation = "LINEAR"
            affected += local_hits
        else:
            obj.shape_key_remove(key)

    if affected < 500:
        fail(f"{actor['name']}_DAMAGE_VERTEX_GATE_TOO_LOW:{affected}")
    if max_deformation < 0.65:
        fail(f"{actor['name']}_DAMAGE_READABILITY_DEFORMATION_TOO_LOW:{max_deformation}")
    READABILITY["damage"][actor["name"]] = {
        "affectedVertices": int(affected),
        "maxDeformationM": float(max_deformation),
    }
    return affected


def choose_event_frames(scene: bpy.types.Scene, impact_frame: int, center: Vector) -> dict[str, int]:
    if impact_frame <= duel.HANDOFF + 1:
        fail("READABILITY_IMPACT_TOO_EARLY")

    target_sep = duel.CAR_TARGET_LENGTH * 2.1
    approach = min(
        range(duel.HANDOFF, impact_frame),
        key=lambda frame: (abs(actor_separation(scene, frame) - target_sep), -frame),
    )

    impact_rows = []
    for frame in range(impact_frame, min(duel.END, impact_frame + 10) + 1):
        da = damage_factor(scene, "BUGATTI_A", frame)
        db = damage_factor(scene, "BUGATTI_B", frame)
        dn = debris_near(scene, frame, center, 6.0)
        score = min(da, db) * 4.0 + min(dn, 12) * 0.18 - abs(frame - (impact_frame + 4)) * 0.03
        impact_rows.append((score, da, db, dn, frame))
    viable_impact = [row for row in impact_rows if min(row[1], row[2]) >= 0.90 and row[3] >= 4]
    impact_visual = max(viable_impact or impact_rows)[4]

    aftermath_rows = []
    for frame in range(min(duel.END, impact_frame + 12), min(duel.END, impact_frame + 44) + 1):
        da = damage_factor(scene, "BUGATTI_A", frame)
        db = damage_factor(scene, "BUGATTI_B", frame)
        dn = debris_near(scene, frame, center, 8.0)
        sep = actor_separation(scene, frame)
        continuity = 1.0 if 2.0 <= sep <= 16.0 else max(0.0, 1.0 - abs(sep - 9.0) / 18.0)
        score = min(da, db) * 2.6 + min(dn, 12) * 0.16 + continuity - abs(frame - (impact_frame + 24)) * 0.02
        aftermath_rows.append((score, da, db, dn, sep, frame))
    viable_after = [row for row in aftermath_rows if min(row[1], row[2]) >= 0.95 and row[3] >= 2 and 1.5 <= row[4] <= 18.0]
    aftermath = max(viable_after or aftermath_rows)[5]

    if not (approach < impact_visual < aftermath):
        fail(f"EVENT_FRAME_ORDER_INVALID:{approach}:{impact_visual}:{aftermath}")
    return {"approach": int(approach), "impact": int(impact_visual), "aftermath": int(aftermath)}


def rect_for(scene: bpy.types.Scene, cam: bpy.types.Object, objects: list[bpy.types.Object]) -> dict:
    points = []
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
    area = max(0.0, maxx - minx) * max(0.0, maxy - miny)
    visible = not behind and minx >= 0.015 and maxx <= 0.985 and miny >= 0.025 and maxy <= 0.975
    return {"visible": bool(visible), "area": float(area), "rect": [minx, miny, maxx, maxy]}


def union_area(a: dict, b: dict) -> float:
    ar, br = a["rect"], b["rect"]
    minx, miny = min(ar[0], br[0]), min(ar[1], br[1])
    maxx, maxy = max(ar[2], br[2]), max(ar[3], br[3])
    return max(0.0, maxx - minx) * max(0.0, maxy - miny)


def create_target(name: str, point: Vector) -> bpy.types.Object:
    bpy.ops.object.empty_add(type="PLAIN_AXES", location=(point.x, point.y, point.z))
    target = bpy.context.object
    target.name = name
    return target


def fit_camera(scene: bpy.types.Scene, name: str, frame: int, point: Vector, lens: float, x_offset: float, z_offset: float) -> tuple[bpy.types.Object, dict]:
    target = create_target(f"{name}_TARGET", point)
    cam = core.camera(name, (point.x + x_offset, point.y - 16.0, point.z + z_offset), lens, target)
    meshes_a = actor_meshes("BUGATTI_A")
    meshes_b = actor_meshes("BUGATTI_B")
    best = None
    for distance in (7.0, 8.0, 9.0, 10.0, 11.0, 12.0, 13.0, 14.0, 15.0, 16.0, 18.0, 20.0, 22.0, 24.0, 27.0, 30.0):
        cam.location = (point.x + x_offset, point.y - distance, point.z + z_offset)
        scene.frame_set(frame)
        bpy.context.view_layer.update()
        ra = rect_for(scene, cam, meshes_a)
        rb = rect_for(scene, cam, meshes_b)
        ua = union_area(ra, rb)
        if ra["visible"] and rb["visible"]:
            score = ua + min(ra["area"], rb["area"]) * 0.45
            candidate = (score, distance, ra, rb, ua)
            if best is None or candidate[0] > best[0]:
                best = candidate
    if best is None:
        fail(f"CAMERA_AUTOFIT_FAILED:{name}:frame={frame}")
    _, distance, ra, rb, ua = best
    cam.location = (point.x + x_offset, point.y - distance, point.z + z_offset)
    scene.frame_set(frame)
    bpy.context.view_layer.update()
    return cam, {
        "frame": int(frame),
        "distance": float(distance),
        "bugattiAArea": float(ra["area"]),
        "bugattiBArea": float(rb["area"]),
        "unionArea": float(ua),
        "bothActorsFullyVisible": bool(ra["visible"] and rb["visible"]),
    }


def setup_cameras_readable(scene: bpy.types.Scene, impact_frame: int, center: Vector) -> dict:
    frames = choose_event_frames(scene, impact_frame, center)
    points: dict[str, Vector] = {}
    for label, frame in frames.items():
        point = actor_midpoint(scene, frame)
        point.z = 1.20 if label == "approach" else (1.05 if label == "impact" else 1.20)
        points[label] = point

    approach, m_approach = fit_camera(scene, "CAM_APPROACH_EVENT", frames["approach"], points["approach"], 46.0, -0.4, 3.4)
    impact, m_impact = fit_camera(scene, "CAM_IMPACT_CONTACT", frames["impact"], points["impact"], 52.0, 0.0, 2.7)
    aftermath, m_aftermath = fit_camera(scene, "CAM_AFTERMATH_EVENT", frames["aftermath"], points["aftermath"], 54.0, 0.6, 3.0)

    aft_start_loc = aftermath.location.copy()
    aftermath.keyframe_insert(data_path="location", frame=frames["aftermath"])
    aft_end_loc = aft_start_loc.copy()
    aft_end_loc.y += 2.8
    aftermath.location = aft_end_loc
    aftermath.keyframe_insert(data_path="location", frame=duel.END)

    scene.timeline_markers.clear()
    marker = scene.timeline_markers.new("APPROACH", frame=frames["approach"])
    marker.camera = approach
    marker = scene.timeline_markers.new("IMPACT", frame=frames["impact"])
    marker.camera = impact
    marker = scene.timeline_markers.new("AFTERMATH", frame=frames["aftermath"])
    marker.camera = aftermath
    scene.camera = approach

    metrics = {"approach": m_approach, "impact": m_impact, "aftermath": m_aftermath}
    for label, row in metrics.items():
        if not row["bothActorsFullyVisible"]:
            fail(f"CAMERA_ACTOR_VISIBILITY_FAIL:{label}")
        if min(row["bugattiAArea"], row["bugattiBArea"]) < 0.02:
            fail(f"CAMERA_SUBJECT_SCALE_TOO_SMALL:{label}:{row}")
    if m_impact["unionArea"] < 0.12:
        fail(f"IMPACT_FRAME_SCALE_TOO_SMALL:{m_impact['unionArea']}")

    READABILITY["eventFrames"] = frames
    READABILITY["cameraMetrics"] = metrics
    return {
        "cameras": [approach, impact, aftermath],
        "approachFrame": frames["approach"],
        "impactCutFrame": frames["impact"],
        "aftermathFrame": frames["aftermath"],
        "aftermathDollyDistance": float((aft_end_loc - aft_start_loc).length),
        "eventFrames": frames,
        "cameraMetrics": metrics,
    }


def debris_visible_on_camera(scene: bpy.types.Scene, cam: bpy.types.Object, frame: int) -> int:
    scene.frame_set(frame)
    bpy.context.view_layer.update()
    visible = 0
    for obj in debris_objects():
        if obj.hide_render:
            continue
        co = world_to_camera_view(scene, cam, obj.matrix_world.translation)
        if co.z > 0 and 0.02 <= co.x <= 0.98 and 0.03 <= co.y <= 0.97:
            visible += 1
    return visible


def render_preflight_readable(scene: bpy.types.Scene, camdata: dict, impact_frame: int, outdir: Path) -> list[dict]:
    frames = camdata["eventFrames"]
    labels = ("approach", "impact", "aftermath")
    camera_map = {"approach": camdata["cameras"][0], "impact": camdata["cameras"][1], "aftermath": camdata["cameras"][2]}
    rows = []
    for label in labels:
        frame = int(frames[label])
        cam = camera_map[label]
        scene.frame_set(frame)
        scene.camera = cam
        bpy.context.view_layer.update()
        ra = rect_for(scene, cam, actor_meshes("BUGATTI_A"))
        rb = rect_for(scene, cam, actor_meshes("BUGATTI_B"))
        ua = union_area(ra, rb)
        damage_a = damage_factor(scene, "BUGATTI_A", frame)
        damage_b = damage_factor(scene, "BUGATTI_B", frame)
        debris_visible = debris_visible_on_camera(scene, cam, frame)
        separation = actor_separation(scene, frame)

        if not (ra["visible"] and rb["visible"]):
            fail(f"PREVIEW_ACTORS_NOT_FULLY_VISIBLE:{label}")
        if min(ra["area"], rb["area"]) < 0.02:
            fail(f"PREVIEW_SUBJECT_SCALE_TOO_SMALL:{label}:{ra['area']}:{rb['area']}")
        if label == "impact":
            if min(damage_a, damage_b) < 0.90:
                fail(f"IMPACT_DAMAGE_NOT_READABLE:{damage_a}:{damage_b}")
            if debris_visible < 4:
                fail(f"IMPACT_DEBRIS_NOT_READABLE:{debris_visible}")
            if ua < 0.12:
                fail(f"IMPACT_UNION_AREA_TOO_SMALL:{ua}")
        if label == "aftermath":
            if min(damage_a, damage_b) < 0.95:
                fail(f"AFTERMATH_DAMAGE_CONTINUITY_FAIL:{damage_a}:{damage_b}")
            if debris_visible < 2:
                fail(f"AFTERMATH_DEBRIS_CONTINUITY_FAIL:{debris_visible}")
            if not (1.5 <= separation <= 18.0):
                fail(f"AFTERMATH_SPATIAL_CONTINUITY_FAIL:{separation}")

        path = outdir / f"preview-{label}-f{frame:04d}.png"
        scene.render.filepath = str(path)
        bpy.ops.render.render(write_still=True)
        if not path.is_file() or path.stat().st_size < 20000:
            fail(f"PREVIEW_RENDER_INVALID:{path}")
        row = {
            "label": label,
            "frame": frame,
            "path": str(path),
            "bytes": path.stat().st_size,
            "readability": {
                "bothActorsFullyVisible": bool(ra["visible"] and rb["visible"]),
                "bugattiAArea": float(ra["area"]),
                "bugattiBArea": float(rb["area"]),
                "unionArea": float(ua),
                "bugattiADamageFactor": float(damage_a),
                "bugattiBDamageFactor": float(damage_b),
                "visibleDebrisCount": int(debris_visible),
                "actorSeparationM": float(separation),
            },
        }
        print(f"PREVIEW_FRAME=PASS|label={label}|frame={frame}|bytes={path.stat().st_size}", flush=True)
        rows.append(row)

    READABILITY["previewRows"] = rows
    return rows


def postprocess_result() -> None:
    parsed = duel.args()
    path = Path(parsed.out) / "preflight-result.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    rows = READABILITY.get("previewRows") or []
    cameras = READABILITY.get("cameraMetrics") or {}
    frames = READABILITY.get("eventFrames") or {}
    damage = READABILITY.get("damage") or {}

    impact_row = next((row for row in rows if row.get("label") == "impact"), {})
    aftermath_row = next((row for row in rows if row.get("label") == "aftermath"), {})
    ir = impact_row.get("readability") or {}
    ar = aftermath_row.get("readability") or {}

    gates = data.setdefault("machineGates", {})
    gates["A10_subjectScaleReadable"] = bool(
        len(cameras) == 3
        and all(row.get("bothActorsFullyVisible") and min(float(row.get("bugattiAArea", 0)), float(row.get("bugattiBArea", 0))) >= 0.02 for row in cameras.values())
    )
    gates["A12_impactReadability"] = bool(
        float(ir.get("unionArea", 0)) >= 0.12
        and min(float(ir.get("bugattiADamageFactor", 0)), float(ir.get("bugattiBDamageFactor", 0))) >= 0.90
        and int(ir.get("visibleDebrisCount", 0)) >= 4
    )
    gates["A13_aftermathContinuity"] = bool(
        min(float(ar.get("bugattiADamageFactor", 0)), float(ar.get("bugattiBDamageFactor", 0))) >= 0.95
        and int(ar.get("visibleDebrisCount", 0)) >= 2
        and 1.5 <= float(ar.get("actorSeparationM", 999.0)) <= 18.0
    )
    gates["A14_eventDrivenPreviewSelection"] = bool(
        isinstance(frames.get("approach"), int)
        and isinstance(frames.get("impact"), int)
        and isinstance(frames.get("aftermath"), int)
        and frames["approach"] < frames["impact"] < frames["aftermath"]
        and frames["impact"] >= int(data.get("impactFrame", 0))
    )
    required = ("A10_subjectScaleReadable", "A12_impactReadability", "A13_aftermathContinuity", "A14_eventDrivenPreviewSelection")
    if not all(gates.get(key) is True for key in required):
        fail("READABILITY_MACHINE_GATE_FAIL:" + ",".join(key for key in required if gates.get(key) is not True))

    damage_visible = bool(
        float((damage.get("BUGATTI_A") or {}).get("maxDeformationM", 0)) >= 0.65
        and float((damage.get("BUGATTI_B") or {}).get("maxDeformationM", 0)) >= 0.65
    )
    debris_visible = bool(int(ir.get("visibleDebrisCount", 0)) >= 4 and int(ar.get("visibleDebrisCount", 0)) >= 2)
    if not damage_visible or not debris_visible:
        fail("READABILITY_VISIBILITY_CONTRACT_FAIL")

    data["readabilityContract"] = {
        "version": "VISUAL_VNEXT_RC2_BUGATTI_READABILITY_V1",
        "previewSelection": "EVENT_DRIVEN",
        "cameraFraming": "CONTACT_CENTRIC_AUTOFIT",
        "damageVisibilityFailClosed": damage_visible,
        "debrisVisibilityFailClosed": debris_visible,
        "eventFrames": frames,
        "cameraMetrics": cameras,
        "damageMetrics": damage,
    }
    data["previews"] = rows
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")
    print("BUGATTI_DUEL_READABILITY_CONTRACT=PASS", flush=True)


duel.impact_damage = impact_damage_readable
core.setup_cameras = setup_cameras_readable
core.render_preflight = render_preflight_readable


if __name__ == "__main__":
    duel.main()
    postprocess_result()
