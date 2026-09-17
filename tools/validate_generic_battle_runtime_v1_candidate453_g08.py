#!/usr/bin/env python3
from __future__ import annotations

import ast
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CAMERA = ROOT / "blender" / "iss_battle_runtime_camera_g08_v4.py"
WRAPPER = ROOT / "blender" / "run_generic_battle_runtime_v1_candidate453_g08.py"
PREFLIGHT = ROOT / "docs" / "ISS_G08_G09_SCOPE_PREFLIGHT.md"

ACTOR_MUTATION = (
    ".chassis.location", ".chassis.rotation_euler", ".chassis.rotation_quaternion",
    ".linear_velocity", ".angular_velocity", ".rigid_body.kinematic", ".rigid_body.mass",
    ".state.structural_integrity", ".state.drive_efficiency", ".state.disabled",
)
FORBIDDEN_CALLS = ("rig.command", "rig.brake", "rig.coast", "DamageAccumulator.apply", "ConsequenceEngine.apply", "ImpactModel.estimate")


def dotted(node: ast.AST) -> str:
    if isinstance(node, ast.Name): return node.id
    if isinstance(node, ast.Attribute):
        left=dotted(node.value)
        return f"{left}.{node.attr}" if left else node.attr
    return ""


def require(text: str, token: str, code: str) -> None:
    if token not in text: raise SystemExit(f"{code}:{token}")


def audit_camera(tree: ast.AST) -> None:
    bad_assign=[]; bad_call=[]
    for node in ast.walk(tree):
        if isinstance(node,(ast.Assign,ast.AnnAssign,ast.AugAssign)):
            targets=list(node.targets) if isinstance(node,ast.Assign) else [node.target]
            for target in targets:
                name=dotted(target)
                if any(x in name for x in ACTOR_MUTATION): bad_assign.append(name)
        if isinstance(node,ast.Call):
            name=dotted(node.func)
            if any(name.endswith(x) for x in FORBIDDEN_CALLS): bad_call.append(name)
    if bad_assign: raise SystemExit("G08_C453_ACTOR_OR_PHYSICS_ASSIGNMENT_FORBIDDEN:"+",".join(sorted(set(bad_assign))))
    if bad_call: raise SystemExit("G08_C453_FORBIDDEN_RUNTIME_CALL:"+",".join(sorted(set(bad_call))))


def audit_wrapper(tree: ast.AST) -> None:
    roots={"candidate446","hardened","runtime"}; observed=[]
    for node in ast.walk(tree):
        if isinstance(node,(ast.Assign,ast.AnnAssign,ast.AugAssign)):
            targets=list(node.targets) if isinstance(node,ast.Assign) else [node.target]
            for target in targets:
                name=dotted(target)
                if name and name.split('.',1)[0] in roots: observed.append(name)
    allowed={"candidate446.CANDIDATE","hardened.ForwardPreviewDirector","runtime.CAMERA_MODEL","runtime.setup_world"}
    if set(observed)-allowed: raise SystemExit("G08_C453_WRAPPER_SCOPE_DRIFT:"+",".join(sorted(set(observed)-allowed)))
    if allowed-set(observed): raise SystemExit("G08_C453_WRAPPER_REQUIRED_PATCH_MISSING:"+",".join(sorted(allowed-set(observed))))


def main() -> None:
    camera=CAMERA.read_text(encoding='utf-8'); wrapper=WRAPPER.read_text(encoding='utf-8'); preflight=PREFLIGHT.read_text(encoding='utf-8')
    audit_camera(ast.parse(camera,filename=str(CAMERA))); audit_wrapper(ast.parse(wrapper,filename=str(WRAPPER)))
    for token in (
        'CINEMATIC_SALIENCE_MODEL = "CUE_AWARE_VERTICAL_CINEMATIC_SALIENCE_V2"',
        'PAYOFF_FOCUS_MODEL = "REALIZED_G07_DOMINANCE_LEADER_FOCUS_V1"',
        'SALIENCE_ANCHOR_MODEL = "REALIZED_CUE_ANCHOR_ONLY_V1"',
        '"CLIMAX": {"minActorHeight": 0.10, "minCombinedArea": 0.026}',
        '"PAYOFF": {"minActorHeight": 0.085, "minCombinedArea": 0.020}',
        'DOMINANCE_REVERSAL_COMEBACK_PHYSICALLY_EARNED', 'INITIAL_PHYSICAL_DOMINANCE_ESTABLISHED',
        'FIRST_REALIZED_CUE_ENTRY', 'REALIZED_G07_STAGE_TRANSITION',
        '"perAssetFocusBranch": False', '"humanCinematicAcceptance": "PENDING"', '"gateClosed": False',
    ): require(camera,token,"G08_C453_CAMERA_CONTRACT_MISSING")
    for token in (
        'CANDIDATE = "ISS_GENERIC_BATTLE_RUNTIME_V1_CANDIDATE_4_5_3_G08"',
        'hardened.ForwardPreviewDirector = EventDrivenCinematicCameraDirectorV4',
        '"payoffFocusFromRealizedDominance": True', '"climaxRelationshipAnchor": True',
        '"perAssetTuning": False', '"issR045MasterPlanAligned": True', '"gateClosed": False',
    ): require(wrapper,token,"G08_C453_WRAPPER_CONTRACT_MISSING")
    for token in ("ISS-G08 SCOPE PRE-FLIGHT = PASS","G04 closed-loop autonomy is read-only upstream authority.","G07 dramatic causal progression is read-only upstream authority."):
        require(preflight,token,"G08_C453_PREFLIGHT_CONTRACT_MISSING")
    raw=(camera+'\n'+wrapper).lower()
    for forbidden in ("forcedwinner=true","forced_winner = true","teleport(","impactenergyjtarget","exactcollisionframe","bugattispecific"):
        if forbidden in raw: raise SystemExit("G08_C453_FORBIDDEN_SCOPE_LITERAL:"+forbidden)
    print(json.dumps({
        "marker":"GENERIC_BATTLE_RUNTIME_CANDIDATE453_G08_PROPERTY_ACCEPTANCE","status":"PASS",
        "candidate":"ISS_GENERIC_BATTLE_RUNTIME_V1_CANDIDATE_4_5_3_G08","gateScope":"G08_EVENT_DRIVEN_CINEMATIC_CAMERA_ONLY",
        "cinematicSalienceModel":"CUE_AWARE_VERTICAL_CINEMATIC_SALIENCE_V2","salienceAnchorModel":"REALIZED_CUE_ANCHOR_ONLY_V1",
        "payoffFocusModel":"REALIZED_G07_DOMINANCE_LEADER_FOCUS_V1","thresholdsWeakened":False,"perAssetTuning":False,
        "g04SourceMutationRequired":False,"g05SourceMutationRequired":False,"g06SourceMutationRequired":False,"g07SourceMutationRequired":False,
        "actorPoseOrVelocityMutation":False,"physicsMutation":False,"cameraFakesPhysics":False,"humanCinematicAcceptance":"PENDING",
        "issR045MasterPlanAligned":True,"gateClosed":False,"productionReadyClaimed":False,
    },sort_keys=True))

if __name__=='__main__': main()
