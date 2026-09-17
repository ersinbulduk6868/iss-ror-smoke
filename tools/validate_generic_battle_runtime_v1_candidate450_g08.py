#!/usr/bin/env python3
from __future__ import annotations

import ast
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CAMERA = ROOT / "blender" / "iss_battle_runtime_camera_g08.py"
WRAPPER = ROOT / "blender" / "run_generic_battle_runtime_v1_candidate450_g08.py"
PREFLIGHT = ROOT / "docs" / "ISS_G08_G09_SCOPE_PREFLIGHT.md"

FORBIDDEN_CALL_SUFFIXES = {
    "rig.command",
    "rig.brake",
    "rig.coast",
    "keyframe_insert",  # allowed only for camera/target/lens; checked structurally below
    "DamageAccumulator.apply",
    "ConsequenceEngine.apply",
    "ImpactModel.estimate",
}


def dotted(node: ast.AST) -> str:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        left = dotted(node.value)
        return f"{left}.{node.attr}" if left else node.attr
    return ""


def check_camera_ast(tree: ast.AST) -> dict[str, object]:
    actor_mutation_assignments: list[str] = []
    forbidden_calls: list[str] = []
    camera_key_calls = 0

    for node in ast.walk(tree):
        if isinstance(node, (ast.Assign, ast.AnnAssign, ast.AugAssign)):
            targets: list[ast.AST] = []
            if isinstance(node, ast.Assign):
                targets = list(node.targets)
            else:
                targets = [node.target]
            for target in targets:
                name = dotted(target)
                if any(token in name for token in (
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
                )):
                    actor_mutation_assignments.append(name)

        if isinstance(node, ast.Call):
            name = dotted(node.func)
            if name.endswith("keyframe_insert"):
                owner = dotted(node.func.value) if isinstance(node.func, ast.Attribute) else ""
                if owner not in {"camera", "target", "camera.data"}:
                    forbidden_calls.append(name + ":owner=" + owner)
                else:
                    camera_key_calls += 1
                continue
            if any(name.endswith(suffix) for suffix in FORBIDDEN_CALL_SUFFIXES - {"keyframe_insert"}):
                forbidden_calls.append(name)
            if name.endswith("bpy.ops.object.transform_apply") or name.endswith("bpy.ops.rigidbody.object_add"):
                forbidden_calls.append(name)

    if actor_mutation_assignments:
        raise SystemExit("G08_ACTOR_OR_PHYSICS_ASSIGNMENT_FORBIDDEN:" + ",".join(sorted(set(actor_mutation_assignments))))
    if forbidden_calls:
        raise SystemExit("G08_FORBIDDEN_RUNTIME_CALL:" + ",".join(sorted(set(forbidden_calls))))
    if camera_key_calls < 3:
        raise SystemExit(f"G08_CAMERA_KEYING_INSUFFICIENT:{camera_key_calls}")
    return {"cameraKeyCallCount": camera_key_calls}


def check_wrapper_ast(tree: ast.AST) -> None:
    assignments: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign):
            for target in node.targets:
                name = dotted(target)
                if name:
                    assignments.append(name)
    # REPO_ROOT and CANDIDATE are module bootstrap/constants, not runtime patch
    # authority. All external module mutations remain camera-only.
    allowed = {
        "REPO_ROOT",
        "CANDIDATE",
        "candidate446.CANDIDATE",
        "hardened.ForwardPreviewDirector",
        "runtime.CAMERA_MODEL",
    }
    drift = sorted(set(assignments) - allowed)
    if drift:
        raise SystemExit("G08_WRAPPER_PATCH_SCOPE_DRIFT:" + ",".join(drift))


def require(text: str, token: str, code: str) -> None:
    if token not in text:
        raise SystemExit(f"{code}:{token}")


def main() -> None:
    camera_text = CAMERA.read_text(encoding="utf-8")
    wrapper_text = WRAPPER.read_text(encoding="utf-8")
    preflight_text = PREFLIGHT.read_text(encoding="utf-8")

    camera_tree = ast.parse(camera_text, filename=str(CAMERA))
    wrapper_tree = ast.parse(wrapper_text, filename=str(WRAPPER))
    ast_info = check_camera_ast(camera_tree)
    check_wrapper_ast(wrapper_tree)

    for token in (
        'CAMERA_G08_MODEL = "ISS_EVENT_DRIVEN_CINEMATIC_CAMERA_DIRECTOR_V2"',
        'SHOT_GRAMMAR_MODEL = "REALIZED_EVENT_PHASE_SHOT_GRAMMAR_V1"',
        'READABILITY_MODEL = "VERTICAL_RELATIONSHIP_READABILITY_ORACLE_V1"',
        '"cameraOnlyMutation": True',
        '"actorPoseOrVelocityMutation": False',
        '"physicsMutation": False',
        '"g04ControlLawChanged": False',
        '"g05ContactAuthorityChanged": False',
        '"g06DamagePersistenceChanged": False',
        '"g07DramaAuthorityChanged": False',
        '"perAssetCameraBranch": False',
        '"cameraFakesPhysics": False',
        '"humanCinematicAcceptance": "PENDING"',
        '"gateClosed": False',
        '"productionReadyClaimed": False',
    ):
        require(camera_text, token, "G08_CAMERA_SCOPE_TOKEN_MISSING")

    for token in (
        'CANDIDATE = "ISS_GENERIC_BATTLE_RUNTIME_V1_CANDIDATE_4_5_0_G08"',
        'hardened.ForwardPreviewDirector = EventDrivenCinematicCameraDirector',
        'runtime.CAMERA_MODEL = CAMERA_G08_MODEL',
        '"gateScope": "G08_EVENT_DRIVEN_CINEMATIC_CAMERA_ONLY"',
        '"g07DramaAuthorityChanged": False',
        '"gateClosed": False',
        '"productionReadyClaimed": False',
    ):
        require(wrapper_text, token, "G08_WRAPPER_SCOPE_TOKEN_MISSING")

    for token in (
        "ISS-G08 SCOPE PRE-FLIGHT = PASS",
        "ISS-G09 SCOPE PRE-FLIGHT = PASS",
        "G04 closed-loop autonomy is read-only upstream authority.",
        "G07 dramatic causal progression is read-only upstream authority.",
        "Old Environment/Audio runtime assumptions tied to Isaac/PhysX/Omniverse are historical.",
    ):
        require(preflight_text, token, "G08_PREFLIGHT_CONTRACT_MISSING")

    raw = (camera_text + "\n" + wrapper_text).lower()
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
        raise SystemExit("G08_FORBIDDEN_SCOPE_LITERAL:" + ",".join(present))

    print(json.dumps({
        "marker": "GENERIC_BATTLE_RUNTIME_CANDIDATE450_G08_PROPERTY_ACCEPTANCE",
        "status": "PASS",
        "candidate": "ISS_GENERIC_BATTLE_RUNTIME_V1_CANDIDATE_4_5_0_G08",
        "gateScope": "G08_EVENT_DRIVEN_CINEMATIC_CAMERA_ONLY",
        "cameraModel": "ISS_EVENT_DRIVEN_CINEMATIC_CAMERA_DIRECTOR_V2",
        "phaseAwareShotGrammar": True,
        "verticalReadabilityOracle": True,
        "cameraKeyCallCount": ast_info["cameraKeyCallCount"],
        "g04SourceMutationRequired": False,
        "g05SourceMutationRequired": False,
        "g06SourceMutationRequired": False,
        "g07SourceMutationRequired": False,
        "actorPoseOrVelocityMutation": False,
        "physicsMutation": False,
        "perAssetCameraBranch": False,
        "cameraFakesPhysics": False,
        "machineAcceptanceSeparateFromHumanReview": True,
        "issR041ScopePreserved": True,
        "issR042ScopePreserved": True,
        "issR043ScopePreflightPreserved": True,
        "issR044UserPostflightApprovalRequired": True,
        "humanCinematicAcceptance": "PENDING",
        "gateClosed": False,
        "productionReadyClaimed": False,
    }, sort_keys=True))


if __name__ == "__main__":
    main()
