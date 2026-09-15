#!/usr/bin/env python3
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve()
ROOT = HERE.parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from blender.iss_battle_runtime_assets import marker
from blender import iss_blender_battle_runtime_v1_hardened as hardened

_original_set_controls = hardened.set_controls


def diagnostic_set_controls(frame, program, actors, states, control_samples):
    _original_set_controls(frame, program, actors, states, control_samples)
    if frame == 1 or frame % max(1, program.fps // 2) == 0:
        rows = []
        for entity, actor in sorted(actors.items()):
            pos = actor.chassis.matrix_world.translation
            vel = actor.velocity.get(frame)
            motors = actor.rig.motors_left + actor.rig.motors_right
            impulses = [float(m.rigid_body_constraint.motor_ang_max_impulse) for m in motors]
            targets = [float(m.rigid_body_constraint.motor_ang_target_velocity) for m in motors]
            rows.append({
                "actorId": entity,
                "position": [round(float(pos.x), 6), round(float(pos.y), 6), round(float(pos.z), 6)],
                "speedMps": round(float(vel.length if vel is not None else 0.0), 6),
                "motorMaxImpulse": round(max(impulses) if impulses else 0.0, 6),
                "motorTargetAbsMax": round(max((abs(v) for v in targets), default=0.0), 6),
            })
        distance = None
        if "actor_alpha" in actors and "actor_beta" in actors:
            a = actors["actor_alpha"].chassis.matrix_world.translation
            b = actors["actor_beta"].chassis.matrix_world.translation
            distance = round(float((a - b).length), 6)
        marker("PROPULSION_DIAGNOSTIC", frame=frame, actorDistance=distance, actors=rows)


hardened.set_controls = diagnostic_set_controls

if __name__ == "__main__":
    marker("GENERIC_BATTLE_RUNTIME_CANDIDATE31_DIAGNOSTIC_BOOTSTRAP_PASS", repoRoot=str(ROOT))
    hardened.main()
