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
from blender.iss_battle_runtime_camera_g08 import (
    CAMERA_G08_MODEL,
    EventDrivenCinematicCameraDirector,
)

CANDIDATE = "ISS_GENERIC_BATTLE_RUNTIME_V1_CANDIDATE_4_5_0_G08"


def g08_setup_world(request, program, _base_setup_world=runtime.setup_world) -> None:
    """Apply the G08 Shorts presentation contract without touching battle physics.

    G07 fixtures remain immutable upstream evidence. G08 owns presentation and
    therefore normalizes only render composition to the locked vertical Shorts
    target before delegating to the unchanged base world setup.
    """
    request.setdefault("renderSpec", {})["aspectRatio"] = "9:16"
    request.setdefault("renderSpec", {})["resolution"] = {"width": 540, "height": 960}
    _base_setup_world(request, program)


def main() -> None:
    # G08 is a camera/presentation-only successor. The accepted G07 runtime
    # remains the physical/drama authority; hardened.main will instantiate this
    # director via its existing ForwardPreviewDirector hook.
    candidate446.CANDIDATE = CANDIDATE
    hardened.ForwardPreviewDirector = EventDrivenCinematicCameraDirector
    runtime.CAMERA_MODEL = CAMERA_G08_MODEL
    runtime.setup_world = g08_setup_world

    print(
        json.dumps(
            {
                "marker": "GENERIC_BATTLE_RUNTIME_CANDIDATE450_G08_ENGINEERING_PASS",
                "candidate": CANDIDATE,
                "cameraModel": CAMERA_G08_MODEL,
                "gateScope": "G08_EVENT_DRIVEN_CINEMATIC_CAMERA_ONLY",
                "readsRealizedWorldState": True,
                "readsG07EventState": True,
                "verticalShortsComposition": True,
                "verticalShortsResolution": [540, 960],
                "presentationContractEnforcedByG08": True,
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
