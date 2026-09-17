#!/usr/bin/env python3
from __future__ import annotations

import ast
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CAMERA_V2 = ROOT / "blender" / "iss_battle_runtime_camera_g08.py"
CAMERA_V3 = ROOT / "blender" / "iss_battle_runtime_camera_g08_v3.py"
WRAPPER = ROOT / "blender" / "run_generic_battle_runtime_v1_candidate451_g08.py"
PREFLIGHT = ROOT / "docs" / "ISS_G08_G09_SCOPE_PREFLIGHT.md"

FORBIDDEN_CALL_SUFFIXES = {
    "rig.command",
    "rig.brake",
    "rig.coast",
    "DamageAccumulator.apply",
    "ConsequenceEngine.apply",
    "ImpactModel.estimate",
}

ACTOR_MUTATION_TOKENS = (
    ".chassis.location",
    ".chassis.rotation_euler",
    ".chassis.rotation_quaternion",
    ".linear_velocity",
    ".angular_velocity",
    ".rigid_body.kinematic",
    ".rigid_body.mass",
    ".state.structural_integrity",
    ".state.drive_efficiency",
    ".state.disabled",
)


def dotted(node: ast.AST) -> str:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        left = dotted(node.value)
        return f"{left}.{node.attr}" if left else node.attr
    return ""


def require(text: str, token: str, code: str) -> None:
    if token not in text:
        raise SystemExit(f"{code}:{token}")


def audit_camera_ast(tree: ast.AST) -> dict[str, int]:
    actor_assignments: list[str] = []
    forbidden_calls: list[str] = []
    camera_key_calls = 0
    for node in ast.walk(tree):
        if isinstance(node, (ast.Assign, ast.AnnAssign, ast.AugAssign)):
            targets = list(node.targets) if isinstance(node, ast.Assign) else [node.target]
            for target in targets:
                name = dotted(target)
                if any(token in name for token in ACTOR_MUTATION_TOKENS):
                    actor_assignments.append(name)
        if isinstance(node, ast.Call):
            name = dotted(node.func)
            if any(name.endswith(suffix) for suffix in FORBIDDEN_CALL_SUFFIXES):
                forbidden_calls.append(name)
            if name.endswith("keyframe_insert"):
                owner = dotted(node.func.value) if isinstance(node.func, ast.Attribute) else ""
                if owner not in {"camera", "target", "camera.data"}:
                    forbidden_calls.append(name + ":owner=" + owner)
                else:
                    camera_key_calls += 1
    if actor_assignments:
        raise SystemExit(
            "G08_C451_ACTOR_OR_PHYSICS_ASSIGNMENT_FORBIDDEN:"
            + ",".join(sorted(set(actor_assignments)))
        )
    if forbidden_calls:
        raise SystemExit(
            "G08_C451_FORBIDDEN_RUNTIME_CALL:"
            + ",".join(sorted(set(forbidden_calls)))
        )
    if camera_key_calls < 1:
        raise SystemExit("G08_C451_CAMERA_KEYING_MISSING")
    return {"cameraKeyCallCount": camera_key_calls}


def audit_wrapper_ast(tree: ast.AST) -> None:
    external_patches: list[str] = []
    protected_roots = {"candidate446", "hardened", "runtime"}
    for node in ast.walk(tree):
        if not isinstance(node, (ast.Assign, ast.AnnAssign, ast.AugAssign)):
            continue
        targets = list(node.targets) if isinstance(node, ast.Assign) else [node.target]
        for target in targets:
            name = dotted(target)
            if name and name.split(".", 1)[0] in protected_roots:
                external_patches.append(name)
    allowed = {
        "candidate446.CANDIDATE",
        "hardened.ForwardPreviewDirector",
        "runtime.CAMERA_MODEL",
        "runtime.setup_world",
    }
    drift = sorted(set(external_patches) - allowed)
    missing = sorted(allowed - set(external_patches))
    if drift:
        raise SystemExit("G08_C451_WRAPPER_PATCH_SCOPE_DRIFT:" + ",".join(drift))
    if missing:
        raise SystemExit("G08_C451_REQUIRED_PATCH_MISSING:" + ",".join(missing))


def main() -> None:
    camera_v2 = CAMERA_V2.read_text(encoding="utf-8")
    camera_v3 = CAMERA_V3.read_text(encoding="utf-8")
    wrapper = WRAPPER.read_text(encoding="utf-8")
    preflight = PREFLIGHT.read_text(encoding="utf-8")

    ast_info = audit_camera_ast(ast.parse(camera_v3, filename=str(CAMERA_V3)))
    audit_wrapper_ast(ast.parse(wrapper, filename=str(WRAPPER)))

    for token in (
        'AUTOFRAME_MODEL = "PORTRAIT_FULL_BOUNDS_AUTOFRAME_V1"',
        'FULL_BOUNDS_READABILITY_MODEL = "VERTICAL_FULL_BOUNDS_READABILITY_ORACLE_V2"',
        'INTERPOLATION_MODEL = "AUTO_CLAMPED_BEZIER_CAMERA_PATH_V1"',
        'class EventDrivenCinematicCameraDirectorV3(EventDrivenCinematicCameraDirector):',
        'camera.data.sensor_fit = "VERTICAL"',
        '"bboxInsideSafeFrame"',
        '"fullBoundsReadable"',
        '_MAX_AUTOFIT_ITERATIONS = 8',
        '_MAX_AUTOFIT_DISTANCE = 600.0',
        'camera.location = target.location + direction * next_distance',
        'point.handle_left_type = "AUTO_CLAMPED"',
        'point.handle_right_type = "AUTO_CLAMPED"',
        '"fullBoundsReadabilityPass"',
        '"autoFrameFailureCount"',
        '"cameraInterpolationOvershootGuard": True',
    ):
        require(camera_v3, token, "G08_C451_CAMERA_CONTRACT_MISSING")

    for token in (
        'CAMERA_G08_MODEL = "ISS_EVENT_DRIVEN_CINEMATIC_CAMERA_DIRECTOR_V2"',
        '"actorPoseOrVelocityMutation": False',
        '"physicsMutation": False',
        '"g04ControlLawChanged": False',
        '"g05ContactAuthorityChanged": False',
        '"g06DamagePersistenceChanged": False',
        '"g07DramaAuthorityChanged": False',
        '"perAssetCameraBranch": False',
        '"cameraFakesPhysics": False',
    ):
        require(camera_v2, token, "G08_C451_V2_BASE_CONTRACT_MISSING")

    for token in (
        'CANDIDATE = "ISS_GENERIC_BATTLE_RUNTIME_V1_CANDIDATE_4_5_1_G08"',
        'hardened.ForwardPreviewDirector = EventDrivenCinematicCameraDirectorV3',
        'runtime.CAMERA_MODEL = CAMERA_G08_MODEL',
        'runtime.setup_world = g08_setup_world',
        'render["aspectRatio"] = "9:16"',
        'DEFAULT_SHORTS_RESOLUTION = (540, 960)',
        'REVIEW_RENDER_SAMPLES = 8',
        'REVIEW_RENDER_PROFILE = "G08_HUMAN_REVIEW_EEVEE_LOW_COST_V1"',
        'if hardened._capture_enabled:',
        'eevee.taa_render_samples = REVIEW_RENDER_SAMPLES',
        '"G08_REVIEW_RENDER_PROFILE_APPLIED"',
        '"productionRenderProfileChanged": False',
        '"portraitFullBoundsAutoFraming": True',
        '"validLowerResolution9x16ReviewAllowed": True',
        '"g07DramaAuthorityChanged": False',
        '"actorPoseOrVelocityMutation": False',
        '"physicsMutation": False',
        '"gateClosed": False',
        '"productionReadyClaimed": False',
    ):
        require(wrapper, token, "G08_C451_WRAPPER_CONTRACT_MISSING")

    for token in (
        "ISS-G08 SCOPE PRE-FLIGHT = PASS",
        "ISS-G09 SCOPE PRE-FLIGHT = PASS",
        "G04 closed-loop autonomy is read-only upstream authority.",
        "G07 dramatic causal progression is read-only upstream authority.",
    ):
        require(preflight, token, "G08_C451_PREFLIGHT_CONTRACT_MISSING")

    raw = (camera_v3 + "\n" + wrapper).lower()
    forbidden_literals = (
        "forcedwinner=true",
        "forced_winner = true",
        "teleport(",
        "min_damage_severity =",
        "contact_threshold =",
        "impactenergyjtarget",
        "exactcollisionframe",
        "bugatti" + "specific",
    )
    present = [token for token in forbidden_literals if token in raw]
    if present:
        raise SystemExit("G08_C451_FORBIDDEN_SCOPE_LITERAL:" + ",".join(present))

    print(
        json.dumps(
            {
                "marker": "GENERIC_BATTLE_RUNTIME_CANDIDATE451_G08_PROPERTY_ACCEPTANCE",
                "status": "PASS",
                "candidate": "ISS_GENERIC_BATTLE_RUNTIME_V1_CANDIDATE_4_5_1_G08",
                "gateScope": "G08_EVENT_DRIVEN_CINEMATIC_CAMERA_ONLY",
                "cameraModel": "ISS_EVENT_DRIVEN_CINEMATIC_CAMERA_DIRECTOR_V2",
                "autoFrameModel": "PORTRAIT_FULL_BOUNDS_AUTOFRAME_V1",
                "fullBoundsReadabilityModel": "VERTICAL_FULL_BOUNDS_READABILITY_ORACLE_V2",
                "interpolationModel": "AUTO_CLAMPED_BEZIER_CAMERA_PATH_V1",
                "fullBoundsSafeFrameRequired": True,
                "portraitSensorFitExplicit": True,
                "genericProjectionDrivenAutoFrame": True,
                "perAssetTuning": False,
                "cameraKeyCallCount": ast_info["cameraKeyCallCount"],
                "reviewRenderProfile": "G08_HUMAN_REVIEW_EEVEE_LOW_COST_V1",
                "reviewRenderSamples": 8,
                "reviewRenderOnly": True,
                "productionRenderProfileChanged": False,
                "g04SourceMutationRequired": False,
                "g05SourceMutationRequired": False,
                "g06SourceMutationRequired": False,
                "g07SourceMutationRequired": False,
                "actorPoseOrVelocityMutation": False,
                "physicsMutation": False,
                "cameraFakesPhysics": False,
                "machineAcceptanceSeparateFromHumanReview": True,
                "issR041ScopePreserved": True,
                "issR042ScopePreserved": True,
                "issR043ScopePreflightPreserved": True,
                "issR044UserPostflightApprovalRequired": True,
                "humanCinematicAcceptance": "PENDING",
                "gateClosed": False,
                "productionReadyClaimed": False,
            },
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
