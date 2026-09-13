import os
from pathlib import Path
import tools.visual_v4_asset_preflight as core

BUG_SHA = "8cc074c40fe9ced7271cbeddf223cd9a520dee868977ffcbd439cec1c2b62cb4"
DOZER_SHA = "2c0be359bbc6c99118751e7caa4b71a205961914e78d2e58c5dd7afc0f498468"

bug = os.environ.get("BUGATTI_SOURCE_URL", "").strip()
dozer = os.environ.get("BULLDOZER_SOURCE_URL", "").strip()
if not bug.startswith("https://"):
    raise RuntimeError("BUGATTI_SOURCE_URL_MISSING")
if not dozer.startswith("https://"):
    raise RuntimeError("BULLDOZER_SOURCE_URL_MISSING")

core.ROOT = Path("artifacts/visual-vnext-rc2-preflight")
core.ASSET_ROOT = Path("runtime-assets/visual-vnext-rc2")
core.ROOT.mkdir(parents=True, exist_ok=True)
core.ASSET_ROOT.mkdir(parents=True, exist_ok=True)
core.SPECS["bugatti"]["transport"] = bug
core.SPECS["bugatti"]["referenceSha256"] = BUG_SHA
core.SPECS["bulldozer"]["transport"] = dozer
core.SPECS["bulldozer"]["referenceSha256"] = DOZER_SHA
core.main()
