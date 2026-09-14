from __future__ import annotations

import sys
from pathlib import Path

import bpy
from mathutils import Vector

HERE = Path(__file__).resolve()
# RC2 modules use package imports from repo root; the readability shim also
# retains one legacy top-level import. Bind both deterministic module roots.
sys.path.insert(0, str(HERE.parents[1]))
sys.path.insert(0, str(HERE.parent))
from blender import visual_vnext_rc2_bugatti_duel as wrapper

duel = wrapper.duel


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
                    f"|centerX={float(((pa+pb)*0.5).x):.6f}"
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


duel.simulate = solver_contact_simulate

# Readability binds only presentation functions on top of the same RC2 duel.
from blender import visual_vnext_rc2_bugatti_duel_readability as readability


def main() -> None:
    duel.main()
    readability.postprocess_result()


if __name__ == "__main__":
    main()
