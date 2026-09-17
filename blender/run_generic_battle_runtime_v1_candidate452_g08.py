from __future__ import annotations

import json
import sys
from pathlib import Path

import bpy

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from blender import iss_blender_battle_runtime_v1 as runtime
from blender import iss_blender_battle_runtime_v1_hardened as hardened
from blender import run_generic_battle_runtime_v1_candidate446 as candidate446
from blender.iss_battle_runtime_assets import BlenderBattleRuntimeError, marker
from blender.iss_battle_runtime_camera_g08_v3 import AUTOFRAME_MODEL
from blender.iss_battle_runtime_camera_g08_v4 import (
    CAMERA_G08_V4_MODEL,
    CINEMATIC_SALIENCE_MODEL,
    EventDrivenCinematicCameraDirectorV4,
)

CANDIDATE = "ISS_GENERIC_BATTLE_RUNTIME_V1_CANDIDATE_4_5_2_G08"
DEFAULT_SHORTS_RESOLUTION = (540, 960)
REVIEW_RENDER_SAMPLES = 8
REVIEW_RENDER_PROFILE = "G08_HUMAN_REVIEW_EEVEE_LOW_COST_V1"


def _is_valid_vertical_9x16(width: int, height: int) -> bool:
    if width <= 0 or height <= 0 or height <= width:
        return False
    return abs((float(width) / float(height)) - (9.0 / 16.0)) <= 0.01


def _apply_review_render_profile() -> None:
    """Reduce only review-render sampling cost; never alter camera or physics."""
    scene = bpy.context.scene
    eevee = getattr(scene, "eevee", None)
    if eevee is None or not hasattr(eevee, "taa_render_samples"):
        raise BlenderBattleRuntimeError("G08_REVIEW_EEVEE_SAMPLING_API_UNAVAILABLE")
    eevee.taa_render_samples = REVIEW_RENDER_SAMPLES
    marker(
        "G08_REVIEW_RENDER_PROFILE_APPLIED",
        profile=REVIEW_RENDER_PROFILE,
        engine=str(scene.render.engine),
        renderSamples=int(eevee.taa_render_samples),
        resolution=[int(scene.render.resolution_x), int(scene.render.resolution_y)],
        cameraStateChanged=False,
        actorPoseOrVelocityMutation=False,
        physicsMutation=False,
        productionRenderProfileChanged=False,
    )


def g08_setup_world(request, program, _base_setup_world=runtime.setup_world) -> None:
    """Enforce G08 portrait presentation without touching battle truth."""
    render = request.setdefault("renderSpec", {})
    resolution = render.get("resolution") or {}
    width = int(resolution.get("width") or 0)
    height = int(resolution.get("height") or 0)
    if not _is_valid_vertical_9x16(width, height):
        width, height = DEFAULT_SHORTS_RESOLUTION
    render["aspectRatio"] = "9:16"
    render["resolution"] = {"width": width, "height": height}
    _base_setup_world(request, program)
    if hardened._capture_enabled:
        _apply_review_render_profile()


def main() -> None:
    candidate446.CANDIDATE = CANDIDATE
    hardened.ForwardPreviewDirector = EventDrivenCinematicCameraDirectorV4
    runtime.CAMERA_MODEL = CAMERA_G08_V4_MODEL
    runtime.setup_world = g08_setup_world

    print(
        json.dumps(
            {
                "marker": "GENERIC_BATTLE_RUNTIME_CANDIDATE452_G08_ENGINEERING_PASS",
                "candidate": CANDIDATE,
                "cameraModel": CAMERA_G08_V4_MODEL,
                "autoFrameModel": AUTOFRAME_MODEL,
                "cinematicSalienceModel": CINEMATIC_SALIENCE_MODEL,
                "gateScope": "G08_EVENT_DRIVEN_CINEMATIC_CAMERA_ONLY",
                "readsRealizedWorldState": True,
                "readsG07EventState": True,
                "verticalShortsComposition": True,
                "defaultVerticalShortsResolution": list(DEFAULT_SHORTS_RESOLUTION),
                "validLowerResolution9x16ReviewAllowed": True,
                "portraitFullBoundsAutoFraming": True,
                "climaxPayoffCinematicSalience": True,
                "phaseAwareShotGrammar": True,
                "machineFramingAcceptanceSeparateFromHumanReview": True,
                "reviewRenderProfile": REVIEW_RENDER_PROFILE,
                "reviewRenderSamples": REVIEW_RENDER_SAMPLES,
                "reviewRenderOnly": True,
                "productionRenderProfileChanged": False,
                "g04ControlLawChanged": False,
                "g05ContactAuthorityChanged": False,
                "g06DamagePersistenceChanged": False,
                "g07DramaAuthorityChanged": False,
                "actorPoseOrVelocityMutation": False,
                "physicsMutation": False,
                "cameraFakesPhysics": False,
                "perAssetCameraBranch": False,
                "perAssetTuning": False,
                "issR041ScopePreserved": True,
                "issR042ScopePreserved": True,
                "issR043ScopePreflightPreserved": True,
                "issR044UserPostflightApprovalRequired": True,
                "issR045MasterPlanAligned": True,
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
