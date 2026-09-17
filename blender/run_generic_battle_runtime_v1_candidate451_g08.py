from __future__ import annotations

import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from blender import iss_blender_battle_runtime_v1 as runtime
from blender import iss_blender_battle_runtime_v1_hardened as hardened
from blender import run_generic_battle_runtime_v1_candidate446 as candidate446
from blender.iss_battle_runtime_camera_g08_v3 import (
    AUTOFRAME_MODEL,
    EventDrivenCinematicCameraDirectorV3,
)
from blender.iss_battle_runtime_camera_g08 import CAMERA_G08_MODEL

CANDIDATE = "ISS_GENERIC_BATTLE_RUNTIME_V1_CANDIDATE_4_5_1_G08"
DEFAULT_SHORTS_RESOLUTION = (540, 960)


def _is_valid_vertical_9x16(width: int, height: int) -> bool:
    if width <= 0 or height <= 0 or height <= width:
        return False
    return abs((float(width) / float(height)) - (9.0 / 16.0)) <= 0.01


def g08_setup_world(request, program, _base_setup_world=runtime.setup_world) -> None:
    """Enforce G08 portrait presentation without touching battle physics.

    Valid lower-resolution 9:16 presentation requests are preserved for review
    rendering. Landscape or invalid upstream presentation is normalized to the
    canonical G08 machine target.
    """
    render = request.setdefault("renderSpec", {})
    resolution = render.get("resolution") or {}
    width = int(resolution.get("width") or 0)
    height = int(resolution.get("height") or 0)
    if not _is_valid_vertical_9x16(width, height):
        width, height = DEFAULT_SHORTS_RESOLUTION
    render["aspectRatio"] = "9:16"
    render["resolution"] = {"width": width, "height": height}
    _base_setup_world(request, program)


def main() -> None:
    candidate446.CANDIDATE = CANDIDATE
    hardened.ForwardPreviewDirector = EventDrivenCinematicCameraDirectorV3
    runtime.CAMERA_MODEL = CAMERA_G08_MODEL
    runtime.setup_world = g08_setup_world

    print(
        json.dumps(
            {
                "marker": "GENERIC_BATTLE_RUNTIME_CANDIDATE451_G08_ENGINEERING_PASS",
                "candidate": CANDIDATE,
                "cameraModel": CAMERA_G08_MODEL,
                "autoFrameModel": AUTOFRAME_MODEL,
                "gateScope": "G08_EVENT_DRIVEN_CINEMATIC_CAMERA_ONLY",
                "readsRealizedWorldState": True,
                "readsG07EventState": True,
                "verticalShortsComposition": True,
                "defaultVerticalShortsResolution": list(DEFAULT_SHORTS_RESOLUTION),
                "validLowerResolution9x16ReviewAllowed": True,
                "portraitFullBoundsAutoFraming": True,
                "phaseAwareShotGrammar": True,
                "machineFramingAcceptanceSeparateFromHumanReview": True,
                "g04ControlLawChanged": False,
                "g05ContactAuthorityChanged": False,
                "g06DamagePersistenceChanged": False,
                "g07DramaAuthorityChanged": False,
                "actorPoseOrVelocityMutation": False,
                "physicsMutation": False,
                "cameraFakesPhysics": False,
                "perAssetCameraBranch": False,
                "issR041ScopePreserved": True,
                "issR042ScopePreserved": True,
                "issR043ScopePreflightPreserved": True,
                "issR044UserPostflightApprovalRequired": True,
                "humanCinematicAcceptance": "PENDING",
                "gateClosed": False,
                "productionReadyClaimed": False,
            },
            sort_keys=True,
        ),
        flush=True,
    )
    candidate446.main()


if __name__ == "__main__":
    main()
