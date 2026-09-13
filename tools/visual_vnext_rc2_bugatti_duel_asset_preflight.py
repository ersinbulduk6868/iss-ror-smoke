import copy
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import tools.visual_v4_asset_preflight as core

BUGATTI_SHA = "8cc074c40fe9ced7271cbeddf223cd9a520dee868977ffcbd439cec1c2b62cb4"
BUGATTI_UID = "4af92c51ecdd4efa9b1c19a1163d9f46"
BUGATTI_VERTEX_COUNT = 150188

url = os.environ.get("BUGATTI_SOURCE_URL", "").strip()
if not url.startswith("https://"):
    raise RuntimeError("BUGATTI_SOURCE_URL_MISSING")

core.ROOT = Path("artifacts/visual-vnext-rc2-preflight")
core.ASSET_ROOT = Path("runtime-assets/visual-vnext-rc2-bugatti-duel")
core.ROOT.mkdir(parents=True, exist_ok=True)
core.ASSET_ROOT.mkdir(parents=True, exist_ok=True)
core.SPECS["bugatti"]["transport"] = url
core.SPECS["bugatti"]["referenceSha256"] = BUGATTI_SHA
core.SPECS["bugatti"]["vertexRange"] = (BUGATTI_VERTEX_COUNT, BUGATTI_VERTEX_COUNT)

row = core.run_one("bugatti")
if row["sourceIdentity"]["uid"] != BUGATTI_UID:
    raise RuntimeError("BUGATTI_UID_GATE_FAIL")
if row["identity"]["binaryExact"] is not True:
    raise RuntimeError("BUGATTI_EXACT_SHA_GATE_FAIL")
if row["identity"]["primarySceneSha256"].lower() != BUGATTI_SHA:
    raise RuntimeError("BUGATTI_PRIMARY_SHA_GATE_FAIL")
if row["geometry"]["meshCount"] != 61 or row["geometry"]["materialCount"] != 61 or row["geometry"]["imageCount"] != 29 or row["geometry"]["nodeCount"] != 63:
    raise RuntimeError("BUGATTI_GEOMETRY_FINGERPRINT_GATE_FAIL")
if row["geometry"]["vertexCount"] != BUGATTI_VERTEX_COUNT:
    raise RuntimeError("BUGATTI_VERTEX_FINGERPRINT_GATE_FAIL")
if not (160000 <= row["geometry"]["triangleCount"] <= 180000):
    raise RuntimeError("BUGATTI_TRIANGLE_GATE_FAIL")

asset_a = copy.deepcopy(row)
asset_b = copy.deepcopy(row)
asset_a["kind"] = "bugattiA"
asset_b["kind"] = "bugattiB"
asset_a["actorRole"] = "HEAD_ON_LEFT_TO_RIGHT"
asset_b["actorRole"] = "HEAD_ON_RIGHT_TO_LEFT"

out = {
    "status": "PASS",
    "scope": "ISS_VISUAL_VNEXT_RC2_BUGATTI_DUEL_ASSET_PREFLIGHT",
    "visualProxyForbidden": True,
    "quant120Forbidden": True,
    "sameExactSourceAllowedForDistinctActors": True,
    "assets": {"bugattiA": asset_a, "bugattiB": asset_b},
}
(core.ROOT / "assets.json").write_text(json.dumps(out, indent=2), encoding="utf-8")
print("ASSET_PREFLIGHT=PASS")
print("BUGATTI_A_FULL_GEOMETRY=PASS")
print("BUGATTI_B_FULL_GEOMETRY=PASS")
print("BUGATTI_DUEL_EXACT_SHA=PASS")
print(f"BUGATTI_VERTEX_COUNT={row['geometry']['vertexCount']}")
print(f"BUGATTI_TRIANGLE_COUNT={row['geometry']['triangleCount']}")
print(f"BUGATTI_DUEL_PRIMARY_SCENE={row['primaryScene']}")