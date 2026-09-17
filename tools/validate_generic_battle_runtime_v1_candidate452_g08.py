#!/usr/bin/env python3
from __future__ import annotations

import ast
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CAMERA_V2 = ROOT / "blender" / "iss_battle_runtime_camera_g08.py"
CAMERA_V3 = ROOT / "blender" / "iss_battle_runtime_camera_g08_v3.py"
CAMERA_V4 = ROOT / "blender" / "iss_battle_runtime_camera_g08_v4.py"
WRAPPER = ROOT / "blender" / "run_generic_battle_runtime_v1_candidate452_g08.py"
PREFLIGHT = ROOT / "docs" / "ISS_G08_G09_SCOPE_PREFLIGHT.md"

FORBIDDEN_CALL_SUFFIXES = {
    "rig.command", "rig.brake", "rig.coast", "DamageAccumulator.apply",
    "ConsequenceEngine.apply", "ImpactModel.estimate",
}
ACTOR_MUTATION_TOKENS = (
    ".chassis.location", ".chassis.rotation_euler", ".chassis.rotation_quaternion",
    ".linear_velocity", ".angular_velocity", ".rigid_body.kinematic",
    ".rigid_body.mass", ".state.structural_integrity", ".state.drive_efficiency",
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


def audit_camera(tree: ast.AST) -> dict[str, int]:
    actor_assignments: list[str] = []
    forbidden_calls: list[str] = []
    camera_mutations = 0
    for node in ast.walk(tree):
        if isinstance(node, (ast.Assign, ast.AnnAssign, ast.AugAssign)):
            targets = list(node.targets) if isinstance(node, ast.Assign) else [node.target]
            for target in targets:
                name = dotted(target)
                if any(token in name for token in ACTOR_MUTATION_TOKENS):
                    actor_assignments.append(name)
                if name.startswith("camera.") or name.startswith("target."):
                    camera_mutations += 1
        if isinstance(node, ast.Call):
            name = dotted(node.func)
            if any(name.endswith(suffix) for suffix in FORBIDDEN_CALL_SUFFIXES):
                forbidden_calls.append(name)
    if actor_assignments:
        raise SystemExit("G08_C452_ACTOR_OR_PHYSICS_ASSIGNMENT_FORBIDDEN:" + ",".join(sorted(set(actor_assignments))))
    if forbidden_calls:
        raise SystemExit("G08_C452_FORBIDDEN_RUNTIME_CALL:" + ",".join(sorted(set(forbidden_calls))))
    if camera_mutations < 1:
        raise SystemExit("G08_C452_CAMERA_MUTATION_MISSING")
    return {"cameraMutationCount": camera_mutations}


def audit_wrapper(tree: ast.AST) -> None:
    external: list[str] = []
    roots = {"candidate446", "hardened", "runtime"}
    for node in ast.walk(tree):
        if not isinstance(node, (ast.Assign, ast.AnnAssign, ast.AugAssign)):
            continue
        targets = list(node.targets) if isinstance(node, ast.Assign) else [node.target]
        for target in targets:
            name = dotted(target)
            if name and name.split(".", 1)[0] in roots:
                external.append(name)
    allowed = {
        "candidate446.CANDIDATE", "hardened.ForwardPreviewDirector",
        "runtime.CAMERA_MODEL", "runtime.setup_world",
    }
    drift = sorted(set(external) - allowed)
    missing = sorted(allowed - set(external))
    if drift:
        raise SystemExit("G08_C452_WRAPPER_PATCH_SCOPE_DRIFT:" + ",".join(drift))
    if missing:
        raise SystemExit("G08_C452_REQUIRED_PATCH_MISSING:" + ",".join(missing))


def main() -> None:
    v2 = CAMERA_V2.read_text(encoding="utf-8")
    v3 = CAMERA_V3.read_text(encoding="utf-8")
    v4 = CAMERA_V4.read_text(encoding="utf-8")
    wrapper = WRAPPER.read_text(encoding="utf-8")
    preflight = PREFLIGHT.read_text(encoding="utf-8")

    ast_info = audit_camera(ast.parse(v4, filename=str(CAMERA_V4)))
    audit_wrapper(ast.parse(wrapper, filename=str(WRAPPER)))

    for token in (
        'CINEMATIC_SALIENCE_MODEL = "CUE_AWARE_VERTICAL_CINEMATIC_SALIENCE_V1"',
        'CAMERA_G08_V4_MODEL = "ISS_EVENT_DRIVEN_CINEMATIC_CAMERA_DIRECTOR_V4"',
        'class EventDrivenCinematicCameraDirectorV4(EventDrivenCinematicCameraDirectorV3):',
        '"CLIMAX": {"minActorHeight": 0.10, "minCombinedArea": 0.026}',
        '"PAYOFF": {"minActorHeight": 0.085, "minCombinedArea": 0.020}',
        'camera.location = candidate_location',
        '"assetIdentityBranch": False',
        '"actorPoseOrVelocityMutation": False',
        '"physicsMutation": False',
        '"cinematicSaliencePass"',
        '"humanCinematicAcceptance": "PENDING"',
        '"gateClosed": False',
    ):
        require(v4, token, "G08_C452_V4_CONTRACT_MISSING")

    for token in (
        'AUTOFRAME_MODEL = "PORTRAIT_FULL_BOUNDS_AUTOFRAME_V1"',
        'FULL_BOUNDS_READABILITY_MODEL = "VERTICAL_FULL_BOUNDS_READABILITY_ORACLE_V2"',
        '"fullBoundsReadabilityPass"', '"cameraInterpolationOvershootGuard": True',
    ):
        require(v3, token, "G08_C452_V3_BASE_CONTRACT_MISSING")

    for token in (
        '"g04ControlLawChanged": False', '"g05ContactAuthorityChanged": False',
        '"g06DamagePersistenceChanged": False', '"g07DramaAuthorityChanged": False',
        '"perAssetCameraBranch": False', '"cameraFakesPhysics": False',
    ):
        require(v2, token, "G08_C452_V2_BASE_CONTRACT_MISSING")

    for token in (
        'CANDIDATE = "ISS_GENERIC_BATTLE_RUNTIME_V1_CANDIDATE_4_5_2_G08"',
        'hardened.ForwardPreviewDirector = EventDrivenCinematicCameraDirectorV4',
        'runtime.CAMERA_MODEL = CAMERA_G08_V4_MODEL', 'runtime.setup_world = g08_setup_world',
        '"climaxPayoffCinematicSalience": True', '"perAssetTuning": False',
        '"issR045MasterPlanAligned": True', '"gateClosed": False',
        '"productionReadyClaimed": False',
    ):
        require(wrapper, token, "G08_C452_WRAPPER_CONTRACT_MISSING")

    for token in (
        "ISS-G08 SCOPE PRE-FLIGHT = PASS",
        "G04 closed-loop autonomy is read-only upstream authority.",
        "G07 dramatic causal progression is read-only upstream authority.",
    ):
        require(preflight, token, "G08_C452_PREFLIGHT_CONTRACT_MISSING")

    raw = (v4 + "\n" + wrapper).lower()
    forbidden_literals = (
        "forcedwinner=true", "forced_winner = true", "teleport(",
        "min_damage_severity =", "contact_threshold =", "impactenergyjtarget",
        "exactcollisionframe", "bugatti" + "specific",
    )
    present = [token for token in forbidden_literals if token in raw]
    if present:
        raise SystemExit("G08_C452_FORBIDDEN_SCOPE_LITERAL:" + ",".join(present))

    print(json.dumps({
        "marker": "GENERIC_BATTLE_RUNTIME_CANDIDATE452_G08_PROPERTY_ACCEPTANCE",
        "status": "PASS",
        "candidate": "ISS_GENERIC_BATTLE_RUNTIME_V1_CANDIDATE_4_5_2_G08",
        "gateScope": "G08_EVENT_DRIVEN_CINEMATIC_CAMERA_ONLY",
        "cameraModel": "ISS_EVENT_DRIVEN_CINEMATIC_CAMERA_DIRECTOR_V4",
        "autoFrameModel": "PORTRAIT_FULL_BOUNDS_AUTOFRAME_V1",
        "cinematicSalienceModel": "CUE_AWARE_VERTICAL_CINEMATIC_SALIENCE_V1",
        "genericProjectionDrivenSalience": True,
        "climaxPayoffSalienceRequired": True,
        "perAssetTuning": False,
        "cameraMutationCount": ast_info["cameraMutationCount"],
        "g04SourceMutationRequired": False, "g05SourceMutationRequired": False,
        "g06SourceMutationRequired": False, "g07SourceMutationRequired": False,
        "actorPoseOrVelocityMutation": False, "physicsMutation": False,
        "cameraFakesPhysics": False, "humanCinematicAcceptance": "PENDING",
        "issR045MasterPlanAligned": True, "gateClosed": False,
        "productionReadyClaimed": False,
    }, sort_keys=True))


if __name__ == "__main__":
    main()
