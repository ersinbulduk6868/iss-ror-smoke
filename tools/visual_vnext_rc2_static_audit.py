import ast
from pathlib import Path

scene = Path("blender/visual_v4_scene.py").read_text(encoding="utf-8")
wrapper = Path("tools/visual_vnext_rc2_asset_preflight.py").read_text(encoding="utf-8")
failures = []

for token in ("assets/test-real-model", "_quant120.json", "BLENDER_WORKBENCH", "generic_hypercar.glb"):
    if token in scene or token in wrapper:
        failures.append("FORBIDDEN:" + token)

for token in ("BLENDER_EEVEE_NEXT", "FULL_SOURCE_GLTF", "damagePhysicalSolver"):
    if token not in scene:
        failures.append("MISSING:" + token)

for token in ("BUGATTI_SOURCE_URL", "BULLDOZER_SOURCE_URL", "2c0be359bbc6c99118751e7caa4b71a205961914e78d2e58c5dd7afc0f498468"):
    if token not in wrapper:
        failures.append("MISSING:" + token)

tree = ast.parse(scene)
for node in ast.walk(tree):
    if isinstance(node, ast.Dict):
        for key, value in zip(node.keys, node.values):
            if isinstance(key, ast.Constant) and isinstance(key.value, str) and key.value.startswith("A"):
                if isinstance(value, ast.Constant) and value.value is True:
                    failures.append("HARDCODED:" + key.value)

if failures:
    raise SystemExit("STATIC_AUDIT_FAIL|" + "|".join(failures))

print("VISIBLE_QUANT120_REFERENCE=NO")
print("WORKBENCH_FALLBACK=NO")
print("HARDCODED_ACCEPTANCE_PASS=NO")
print("FULL_SOURCE_SCENE_CONTRACT=PASS")
print("STATIC_CANDIDATE_AUDIT=PASS")
