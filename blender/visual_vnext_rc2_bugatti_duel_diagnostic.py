from __future__ import annotations

import json
import sys
from pathlib import Path

import bpy
from mathutils import Vector

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from blender import visual_vnext_rc2_bugatti_duel as wrapper

# Keep the exact audited import/orientation implementation from the wrapper.
duel = wrapper.duel


def diagnostic_simulate(scene: bpy.types.Scene, a: dict, b: dict) -> dict:
    if scene.rigidbody_world is None:
        duel.fail("RIGID_BODY_WORLD_MISSING")
    scene.rigidbody_world.point_cache.frame_start = duel.START
    scene.rigidbody_world.point_cache.frame_end = duel.END
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
    min_abs_x_sep = float("inf")
    min_3d_sep = float("inf")
    min_sep_frame = None
    first_crossing_frame = None
    prior_order = None
    samples = {}
    sample_frames = {1, 2, 3, 4, 5, 6, 7, 8, 12, 18, 24, 36, 48, 72, 96, 120, duel.END}

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

        order = 1 if pb.x > pa.x else (-1 if pb.x < pa.x else 0)
        if prior_order is not None and order != 0 and prior_order != 0 and order != prior_order and first_crossing_frame is None:
            first_crossing_frame = frame
        if order != 0:
            prior_order = order
        abs_x_sep = abs(float(pb.x - pa.x))
        sep3 = float((pb - pa).length)
        if abs_x_sep < min_abs_x_sep:
            min_abs_x_sep = abs_x_sep
            min_sep_frame = frame
        min_3d_sep = min(min_3d_sep, sep3)

        if frame in sample_frames:
            samples[str(frame)] = {
                "aPos": [float(x) for x in pa],
                "bPos": [float(x) for x in pb],
                "aVel": [float(x) for x in va],
                "bVel": [float(x) for x in vb],
                "absXSeparation": abs_x_sep,
                "distance3d": sep3,
                "overlap": bool(duel.overlap(a, b)),
                "aKinematic": bool(a["proxy"].rigid_body.kinematic),
                "bKinematic": bool(b["proxy"].rigid_body.kinematic),
            }

        if frame >= duel.HANDOFF and impact is None:
            a_pre_max = max(a_pre_max, va.length)
            b_pre_max = max(b_pre_max, vb.length)
            a_approach = a_approach or va.x > 8.0
            b_approach = b_approach or vb.x < -8.0
            if frame >= duel.HANDOFF + 2 and duel.overlap(a, b) and (va - vb).length > 15.0:
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

    diag = {
        "handoffFrame": duel.HANDOFF,
        "endFrame": duel.END,
        "proxyDimensionsA": [float(x) for x in a["proxy"].dimensions],
        "proxyDimensionsB": [float(x) for x in b["proxy"].dimensions],
        "massA": float(a["proxy"].rigid_body.mass),
        "massB": float(b["proxy"].rigid_body.mass),
        "frictionA": float(a["proxy"].rigid_body.friction),
        "frictionB": float(b["proxy"].rigid_body.friction),
        "linearDampingA": float(a["proxy"].rigid_body.linear_damping),
        "linearDampingB": float(b["proxy"].rigid_body.linear_damping),
        "minAbsXSeparation": min_abs_x_sep,
        "min3dSeparation": min_3d_sep,
        "minSeparationFrame": min_sep_frame,
        "firstOrderingCrossFrame": first_crossing_frame,
        "aPreImpactMaxSpeed": float(a_pre_max),
        "bPreImpactMaxSpeed": float(b_pre_max),
        "aApproachObserved": bool(a_approach),
        "bApproachObserved": bool(b_approach),
        "impactObserved": impact is not None,
        "impactFrame": impact,
        "samples": samples,
    }
    print("BUGATTI_DUEL_TRAJECTORY_DIAGNOSTIC=" + json.dumps(diag, separators=(",", ":"), sort_keys=True))

    if impact is None or impact_data is None:
        duel.fail("HEAD_ON_IMPACT_NOT_OBSERVED_WITH_TRAJECTORY_DIAGNOSTIC")
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


duel.simulate = diagnostic_simulate

if __name__ == "__main__":
    duel.main()
