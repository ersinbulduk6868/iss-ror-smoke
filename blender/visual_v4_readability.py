from __future__ import annotations

import json
import math
from pathlib import Path

import bpy
from bpy_extras.object_utils import world_to_camera_view
from mathutils import Vector

import visual_v4_scene as base

READABILITY_STATE: dict = {}


def fail(msg: str) -> None:
    raise RuntimeError(msg)


def descendant_meshes(root: bpy.types.Object) -> list[bpy.types.Object]:
    out: list[bpy.types.Object] = []
    stack = list(root.children)
    while stack:
        obj = stack.pop()
        if obj.type == "MESH" and len(obj.data.vertices) > 0:
            out.append(obj)
        stack.extend(list(obj.children))
    return out


def actor_meshes(name: str) -> list[bpy.types.Object]:
    root = bpy.data.objects.get(f"{name}_VISUAL_ROOT")
    if root is None:
        fail(f"READABILITY_ACTOR_ROOT_MISSING:{name}")
    meshes = descendant_meshes(root)
    if not meshes:
        fail(f"READABILITY_ACTOR_MESH_MISSING:{name}")
    return meshes


def proxy(name: str) -> bpy.types.Object:
    obj = bpy.data.objects.get(f"PHYSICS_{name}")
    if obj is None:
        fail(f"READABILITY_PROXY_MISSING:{name}")
    return obj


def debris_objects() -> list[bpy.types.Object]:
    return sorted(
        [o for o in bpy.data.objects if o.name.startswith("IMPACT_DEBRIS_") and o.type == "MESH"],
        key=lambda o: o.name,
    )


def actor_midpoint(scene: bpy.types.Scene, frame: int) -> Vector:
    scene.frame_set(frame)
    bpy.context.view_layer.update()
    return (proxy("BUGATTI").matrix_world.translation + proxy("BULLDOZER").matrix_world.translation) * 0.5


def actor_separation(scene: bpy.types.Scene, frame: int) -> float:
    scene.frame_set(frame)
    bpy.context.view_layer.update()
    return (proxy("BUGATTI").matrix_world.translation - proxy("BULLDOZER").matrix_world.translation).length


def damage_factor(scene: bpy.types.Scene, frame: int) -> float:
    scene.frame_set(frame)
    bpy.context.view_layer.update()
    values: list[float] = []
    for obj in actor_meshes("BUGATTI"):
        keys = getattr(obj.data, "shape_keys", None)
        if not keys:
            continue
        key = keys.key_blocks.get("ImpactCrumple")
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


def choose_event_frames(scene: bpy.types.Scene, impact_frame: int, center: Vector) -> dict:
    if impact_frame <= base.HANDOFF + 1:
        fail("READABILITY_IMPACT_TOO_EARLY")

    target_sep = (base.CAR_TARGET_LENGTH + base.DOZER_TARGET_LENGTH) * 0.5 + 3.0
    approach_candidates = range(base.HANDOFF, impact_frame)
    approach = min(
        approach_candidates,
        key=lambda f: (abs(actor_separation(scene, f) - target_sep), -f),
    )

    impact_candidates = range(impact_frame, min(base.END, impact_frame + 10) + 1)
    impact_rows = []
    for f in impact_candidates:
        df = damage_factor(scene, f)
        dn = debris_near(scene, f, center, 5.5)
        score = df * 4.0 + min(dn, 12) * 0.18 - abs(f - (impact_frame + 4)) * 0.035
        impact_rows.append((score, df, dn, f))
    viable_impact = [r for r in impact_rows if r[1] >= 0.65 and r[2] >= 4]
    impact_visual = max(viable_impact or impact_rows)[3]

    aftermath_start = min(base.END, impact_frame + 10)
    aftermath_end = min(base.END, impact_frame + 44)
    aftermath_rows = []
    for f in range(aftermath_start, aftermath_end + 1):
        df = damage_factor(scene, f)
        dn = debris_near(scene, f, center, 7.0)
        sep = actor_separation(scene, f)
        continuity = 1.0 if 2.0 <= sep <= 15.0 else max(0.0, 1.0 - abs(sep - 8.0) / 16.0)
        score = df * 2.5 + min(dn, 12) * 0.16 + continuity - abs(f - (impact_frame + 24)) * 0.025
        aftermath_rows.append((score, df, dn, sep, f))
    viable_after = [r for r in aftermath_rows if r[1] >= 0.95 and r[2] >= 3 and 1.5 <= r[3] <= 16.0]
    aftermath = max(viable_after or aftermath_rows)[4]

    if not (approach < impact_visual < aftermath):
        fail(f"EVENT_FRAME_ORDER_INVALID:{approach}:{impact_visual}:{aftermath}")
    return {
        "approach": int(approach),
        "impact": int(impact_visual),
        "aftermath": int(aftermath),
    }


def rect_for(scene: bpy.types.Scene, cam: bpy.types.Object, objects: list[bpy.types.Object]) -> dict:
    pts = []
    behind = False
    for obj in objects:
        for corner in obj.bound_box:
            co = world_to_camera_view(scene, cam, obj.matrix_world @ Vector(corner))
            if co.z <= 0:
                behind = True
            pts.append((float(co.x), float(co.y), float(co.z)))
    if not pts:
        return {"visible": False, "area": 0.0, "rect": [0.0, 0.0, 0.0, 0.0]}
    minx = min(p[0] for p in pts)
    maxx = max(p[0] for p in pts)
    miny = min(p[1] for p in pts)
    maxy = max(p[1] for p in pts)
    width = max(0.0, maxx - minx)
    height = max(0.0, maxy - miny)
    visible = (
        not behind
        and minx >= 0.015
        and maxx <= 0.985
        and miny >= 0.025
        and maxy <= 0.975
    )
    return {
        "visible": bool(visible),
        "area": float(width * height),
        "rect": [minx, miny, maxx, maxy],
    }


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
    cam = base.camera(name, (target_point.x + x_offset, target_point.y - 16.0, target_point.z + z_offset), lens, target)
    car_meshes = actor_meshes("BUGATTI")
    dozer_meshes = actor_meshes("BULLDOZER")
    best = None
    for distance in (8.0, 9.0, 10.0, 11.0, 12.0, 13.0, 14.0, 15.0, 16.0, 18.0, 20.0, 22.0, 24.0, 27.0, 30.0):
        cam.location = (
            target_point.x + x_offset,
            target_point.y - distance,
            target_point.z + z_offset,
        )
        scene.frame_set(frame)
        bpy.context.view_layer.update()
        cr = rect_for(scene, cam, car_meshes)
        dr = rect_for(scene, cam, dozer_meshes)
        ua = union_area(cr, dr)
        if cr["visible"] and dr["visible"]:
            score = ua + min(cr["area"], dr["area"]) * 0.35
            candidate = (score, distance, cr, dr, ua)
            if best is None or candidate[0] > best[0]:
                best = candidate
    if best is None:
        fail(f"CAMERA_AUTOFIT_FAILED:{name}:frame={frame}")
    _, distance, cr, dr, ua = best
    cam.location = (
        target_point.x + x_offset,
        target_point.y - distance,
        target_point.z + z_offset,
    )
    scene.frame_set(frame)
    bpy.context.view_layer.update()
    return cam, {
        "frame": int(frame),
        "distance": float(distance),
        "bugattiArea": float(cr["area"]),
        "bulldozerArea": float(dr["area"]),
        "unionArea": float(ua),
        "bothActorsFullyVisible": bool(cr["visible"] and dr["visible"]),
    }


def impact_damage_readable(car: dict, impact_frame: int) -> int:
    scene = bpy.context.scene
    scene.frame_set(base.START)
    bpy.context.view_layer.update()
    p = car["proxy"]
    car_center_x = p.matrix_world.translation.x
    half_len = float(car["dims"].x) * 0.5
    threshold = car_center_x + half_len * 0.42
    affected = 0
    max_deformation = 0.0

    for obj in car["meshes"]:
        if obj.type != "MESH" or len(obj.data.vertices) == 0:
            continue
        try:
            if obj.data.shape_keys is None:
                obj.shape_key_add(name="Basis", from_mix=False)
            key = obj.shape_key_add(name="ImpactCrumple", from_mix=False)
        except Exception:
            continue

        inv = obj.matrix_world.inverted()
        local_hits = 0
        for i, point in enumerate(key.data):
            world = obj.matrix_world @ point.co
            if world.x <= threshold:
                continue
            t = min(1.0, max(0.0, (world.x - threshold) / max(0.20, half_len * 0.58)))
            target = world.copy()
            dx = 0.90 * t
            dz = 0.22 * t
            dy = (0.11 if (i % 2) else -0.11) * t
            target.x -= dx
            target.z -= dz
            target.y += dy
            point.co = inv @ target
            max_deformation = max(max_deformation, math.sqrt(dx * dx + dy * dy + dz * dz))
            local_hits += 1

        if local_hits:
            key.value = 0.0
            key.keyframe_insert(data_path="value", frame=max(base.START, impact_frame - 1))
            key.value = 1.0
            key.keyframe_insert(data_path="value", frame=min(base.END, impact_frame + 3))
            keys = obj.data.shape_keys
            if keys.animation_data and keys.animation_data.action:
                for fc in keys.animation_data.action.fcurves:
                    if fc.data_path.endswith('key_blocks["ImpactCrumple"].value'):
                        for kp in fc.keyframe_points:
                            kp.interpolation = "LINEAR"
            affected += local_hits
        else:
            obj.shape_key_remove(key)

    if affected < 500:
        fail(f"DAMAGE_VERTEX_GATE_TOO_LOW:{affected}")
    if max_deformation < 0.65:
        fail(f"DAMAGE_READABILITY_DEFORMATION_TOO_LOW:{max_deformation}")
    READABILITY_STATE["damageMaxDeformationM"] = float(max_deformation)
    return affected


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


def setup_cameras_readable(scene: bpy.types.Scene, impact_frame: int, center: Vector) -> dict:
    frames = choose_event_frames(scene, impact_frame, center)

    points = {}
    for label, frame in frames.items():
        p = actor_midpoint(scene, frame)
        p.z = 1.25 if label == "approach" else (1.15 if label == "impact" else 1.30)
        points[label] = p

    wide, wide_metrics = fit_camera(scene, "CAM_APPROACH_EVENT", frames["approach"], points["approach"], 46.0, -0.8, 3.8)
    impact, impact_metrics = fit_camera(scene, "CAM_IMPACT_CONTACT", frames["impact"], points["impact"], 52.0, -0.3, 2.8)
    aftermath, aftermath_metrics = fit_camera(scene, "CAM_AFTERMATH_EVENT", frames["aftermath"], points["aftermath"], 56.0, 0.9, 3.0)

    scene.timeline_markers.clear()
    m = scene.timeline_markers.new("APPROACH", frame=frames["approach"])
    m.camera = wide
    impact_cut = max(base.START + 1, frames["impact"] - 2)
    m = scene.timeline_markers.new("IMPACT", frame=impact_cut)
    m.camera = impact
    m = scene.timeline_markers.new("AFTERMATH", frame=frames["aftermath"])
    m.camera = aftermath
    scene.camera = wide

    READABILITY_STATE["previewFrames"] = frames
    READABILITY_STATE["cameraMetrics"] = {
        "approach": wide_metrics,
        "impact": impact_metrics,
        "aftermath": aftermath_metrics,
    }

    start_loc = Vector(aftermath.location)
    end_loc = start_loc + Vector((1.8, 3.0, -0.35))
    aftermath.keyframe_insert(data_path="location", frame=frames["aftermath"])
    aftermath.location = end_loc
    aftermath.keyframe_insert(data_path="location", frame=base.END)

    return {
        "cameras": [wide, impact, aftermath],
        "approachFrame": frames["approach"],
        "impactCutFrame": impact_cut,
        "aftermathFrame": frames["aftermath"],
        "previewFrames": frames,
        "shotMetrics": READABILITY_STATE["cameraMetrics"],
        "aftermathDollyDistance": (end_loc - start_loc).length,
    }


def shot_metrics(scene: bpy.types.Scene, cam: bpy.types.Object, frame: int) -> dict:
    scene.frame_set(frame)
    bpy.context.view_layer.update()
    cr = rect_for(scene, cam, actor_meshes("BUGATTI"))
    dr = rect_for(scene, cam, actor_meshes("BULLDOZER"))
    return {
        "bugattiArea": float(cr["area"]),
        "bulldozerArea": float(dr["area"]),
        "unionArea": float(union_area(cr, dr)),
        "bothActorsFullyVisible": bool(cr["visible"] and dr["visible"]),
        "damageFactor": float(damage_factor(scene, frame)),
        "debrisVisibleCount": int(debris_visible_on_camera(scene, cam, frame)),
        "actorSeparationM": float(actor_separation(scene, frame)),
    }


def render_preflight_readable(scene: bpy.types.Scene, camdata: dict, impact_frame: int, outdir: Path) -> list[dict]:
    frames = camdata["previewFrames"]
    labels = ("approach", "impact", "aftermath")
    cameras = camdata["cameras"]
    rows = []

    for label, cam in zip(labels, cameras):
        frame = int(frames[label])
        scene.frame_set(frame)
        scene.camera = cam
        metrics = shot_metrics(scene, cam, frame)

        if not metrics["bothActorsFullyVisible"]:
            fail(f"VISUAL_GATE_ACTORS_CROPPED:{label}:{frame}")
        minimum_union = 0.13 if label == "approach" else 0.17 if label == "impact" else 0.14
        if metrics["unionArea"] < minimum_union:
            fail(f"VISUAL_GATE_SUBJECT_SCALE_TOO_SMALL:{label}:{metrics['unionArea']}")
        if min(metrics["bugattiArea"], metrics["bulldozerArea"]) < 0.025:
            fail(f"VISUAL_GATE_ACTOR_TOO_SMALL:{label}")

        if label == "impact":
            if metrics["damageFactor"] < 0.65:
                fail(f"VISUAL_GATE_DAMAGE_NOT_READABLE:{metrics['damageFactor']}")
            if metrics["debrisVisibleCount"] < 4:
                fail(f"VISUAL_GATE_DEBRIS_NOT_VISIBLE:{metrics['debrisVisibleCount']}")
        elif label == "aftermath":
            if metrics["damageFactor"] < 0.95:
                fail(f"VISUAL_GATE_DAMAGE_NOT_PERSISTENT:{metrics['damageFactor']}")
            if metrics["debrisVisibleCount"] < 3:
                fail(f"VISUAL_GATE_DEBRIS_CONTINUITY_FAIL:{metrics['debrisVisibleCount']}")

        path = outdir / f"preview-{label}-f{frame:04d}.png"
        scene.render.filepath = str(path)
        bpy.ops.render.render(write_still=True)
        if not path.is_file() or path.stat().st_size < 20000:
            fail(f"PREVIEW_RENDER_INVALID:{path}")
        print(
            f"PREVIEW_FRAME=PASS|label={label}|frame={frame}|bytes={path.stat().st_size}"
            f"|unionArea={metrics['unionArea']:.4f}|damage={metrics['damageFactor']:.3f}"
            f"|debrisVisible={metrics['debrisVisibleCount']}",
            flush=True,
        )
        rows.append({
            "label": label,
            "frame": frame,
            "path": str(path),
            "bytes": path.stat().st_size,
            "readability": metrics,
        })

    READABILITY_STATE["previews"] = rows
    return rows


def postprocess_result(outdir: Path, mode: str) -> None:
    result_path = outdir / ("preflight-result.json" if mode == "preflight" else "final-result.json")
    if not result_path.is_file():
        fail(f"READABILITY_RESULT_MISSING:{result_path}")
    d = json.loads(result_path.read_text(encoding="utf-8"))

    if mode == "preflight":
        previews = d.get("previews") or []
        by_label = {row.get("label"): row for row in previews}
        for label in ("approach", "impact", "aftermath"):
            if label not in by_label:
                fail(f"READABILITY_PREVIEW_ROW_MISSING:{label}")

        approach = by_label["approach"]["readability"]
        impact = by_label["impact"]["readability"]
        aftermath = by_label["aftermath"]["readability"]

        added_gates = {
            "A10_subjectScaleReadable": (
                approach["bothActorsFullyVisible"]
                and impact["bothActorsFullyVisible"]
                and aftermath["bothActorsFullyVisible"]
                and approach["unionArea"] >= 0.13
                and impact["unionArea"] >= 0.17
                and aftermath["unionArea"] >= 0.14
            ),
            "A12_impactReadability": (
                impact["damageFactor"] >= 0.65
                and impact["debrisVisibleCount"] >= 4
                and min(impact["bugattiArea"], impact["bulldozerArea"]) >= 0.025
            ),
            "A13_aftermathContinuity": (
                aftermath["damageFactor"] >= 0.95
                and aftermath["debrisVisibleCount"] >= 3
                and aftermath["actorSeparationM"] <= 16.0
            ),
            "A14_eventDrivenPreviewSelection": (
                previews[0]["frame"] < previews[1]["frame"] < previews[2]["frame"]
                and previews[1]["frame"] >= int(d["impactFrame"])
            ),
        }
        if not all(added_gates.values()):
            fail("READABILITY_MACHINE_GATE_FAIL:" + ",".join(k for k, v in added_gates.items() if not v))

        d.setdefault("machineGates", {}).update(added_gates)
        d["readabilityContract"] = {
            "version": "VISUAL_V4_READABILITY_V1",
            "previewSelection": "EVENT_DRIVEN",
            "cameraFraming": "CONTACT_CENTRIC_AUTOFIT",
            "damageVisibilityFailClosed": True,
            "debrisVisibilityFailClosed": True,
            "damageMaxDeformationM": READABILITY_STATE.get("damageMaxDeformationM"),
            "previewFrames": READABILITY_STATE.get("previewFrames"),
            "cameraMetrics": READABILITY_STATE.get("cameraMetrics"),
        }
        d["visualReviewRequired"] = [
            "A4_damage_readability",
            "A6_image_quality",
            "A11_scene_brightness",
            "overall_cinematic_readability",
        ]
        result_path.write_text(json.dumps(d, indent=2), encoding="utf-8")
        print("VISUAL_V4_READABILITY_CONTRACT=PASS", flush=True)


def main() -> None:
    parsed = base.args()
    outdir = Path(parsed.out)

    base.impact_damage = impact_damage_readable
    base.setup_cameras = setup_cameras_readable
    base.render_preflight = render_preflight_readable

    base.main()
    postprocess_result(outdir, parsed.mode)


if __name__ == "__main__":
    main()
