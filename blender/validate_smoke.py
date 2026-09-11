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
    "scope": "BACKEND_SMOKE_ONLY",
    "productionAcceptance": False,
    "engine": "BLENDER",
    "engineVersion": "4.5.13",
    "renderEngine": "BLENDER_EEVEE_NEXT",
    "physicsBackend": "BLENDER_RIGID_BODY",
    "continuousWorld": True,
    "simulationCompleted": True,
    "collisionObserved": True,
    "visibleDamageApplied": True,
    "persistentWorldState": True,
    "renderCompleted": True,
    "frames": 72,
    "fps": 24,
}

failures = []
for key, value in expected.items():
    if data.get(key) != value:
        failures.append(f"{key}: expected {value!r}, got {data.get(key)!r}")

try:
    displacement = float(data.get("maxTargetDisplacementMeters", 0.0))
except (TypeError, ValueError):
    displacement = 0.0
if displacement <= 0.08:
    failures.append(f"maxTargetDisplacementMeters must be > 0.08, got {displacement}")

samples = data.get("samples")
if not isinstance(samples, list) or len(samples) < 5:
    failures.append("expected >=5 persistent-world telemetry samples")

if failures:
    print("ISS_BLENDER_EVIDENCE=FAIL")
    for failure in failures:
        print(f"FAIL: {failure}")
    raise SystemExit(1)

print("ISS_BLENDER_EVIDENCE=PASS")
print(f"maxTargetDisplacementMeters={displacement:.6f}")
