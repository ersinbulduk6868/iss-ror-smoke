import json
import pathlib
import sys

if len(sys.argv) != 2:
    raise SystemExit("usage: validate_smoke.py <result.json>")

path = pathlib.Path(sys.argv[1])
if not path.is_file():
    raise SystemExit(f"missing evidence file: {path}")

data = json.loads(path.read_text(encoding="utf-8"))

expected = {
    "scope": "BLENDER_RIGID_BODY_COLLISION_TRUTH_TEST",
    "productionAcceptance": False,
    "engine": "BLENDER",
    "engineVersion": "4.5.13",
    "renderEngine": "BLENDER_EEVEE_NEXT",
    "physicsBackend": "BLENDER_RIGID_BODY",
    "continuousWorld": True,
    "simulationCompleted": True,
    "collisionObserved": True,
    "momentumTransferObserved": True,
    "persistentWorldState": True,
    "renderCompleted": True,
    "scriptedDamageUsed": False,
    "kinematicBodyCount": 0,
    "locationKeyframeCurveCount": 0,
    "simulationFrames": 96,
    "renderedFrames": 96,
    "fps": 24,
}
failures = [
    f"{k}: expected {v!r}, got {data.get(k)!r}"
    for k, v in expected.items()
    if data.get(k) != v
]


def num(name, default=0.0):
    try:
        return float(data.get(name, default))
    except (TypeError, ValueError):
        return default


target_disp = num("maxTargetDisplacementMeters")
target_final_disp = num("finalTargetDisplacementMeters")
target_vmax = num("targetMaxSpeedMps")
attacker_vmax = num("attackerMaxSpeedMps")
impact_frame = data.get("impactFrame")
impact_distance = num("impactCenterDistanceMeters", 999.0)

if target_disp <= 0.15:
    failures.append(f"maxTargetDisplacementMeters must be > 0.15, got {target_disp}")
if target_final_disp <= 0.10:
    failures.append(f"finalTargetDisplacementMeters must be > 0.10, got {target_final_disp}")
if target_vmax <= 0.35:
    failures.append(f"targetMaxSpeedMps must be > 0.35, got {target_vmax}")
if attacker_vmax <= 0.80:
    failures.append(f"attackerMaxSpeedMps must be > 0.80, got {attacker_vmax}")
if not isinstance(impact_frame, int) or not (9 <= impact_frame <= 96):
    failures.append(f"impactFrame must be an integer in [9,96], got {impact_frame!r}")
if impact_distance > 2.55:
    failures.append(f"impactCenterDistanceMeters must be <= 2.55, got {impact_distance}")

samples = data.get("samples")
if not isinstance(samples, list) or len(samples) < 5:
    failures.append("expected >=5 continuous-world telemetry samples")

if failures:
    print("ISS_BLENDER_EVIDENCE=FAIL")
    for failure in failures:
        print(f"FAIL: {failure}")
    raise SystemExit(1)

print("ISS_BLENDER_EVIDENCE=PASS")
print(f"impactFrame={impact_frame}")
print(f"targetMaxSpeedMps={target_vmax:.6f}")
print(f"maxTargetDisplacementMeters={target_disp:.6f}")
print(f"impactCenterDistanceMeters={impact_distance:.6f}")
