from __future__ import annotations

import ast
import hashlib
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from blender.iss_battle_runtime_contract import (  # noqa: E402
    ActorProfile,
    ActorState,
    BattleCompiler,
    BattleRuntimeContractError,
    EventState,
)
from blender.iss_battle_runtime_models import (  # noqa: E402
    DamageAccumulator,
    ImpactModel,
    OutcomeResolver,
    SpawnPlanner,
    WaveScheduler,
)

GENERIC_FILES = (
    "blender/iss_battle_runtime_contract.py",
    "blender/iss_battle_runtime_models.py",
    "blender/iss_battle_runtime_core.py",
    "blender/iss_battle_runtime_assets.py",
    "blender/iss_battle_runtime_physics.py",
    "blender/iss_battle_runtime_consequences.py",
    "blender/iss_battle_runtime_camera.py",
    "blender/iss_blender_battle_runtime_v1.py",
)
REQUIRED_FILES = GENERIC_FILES + (
    "docs/GENERIC_BATTLE_RUNTIME_V1_ENGINEERING_PLAN.md",
)
BANNED_SCENARIO_TOKENS = (
    "bugatti",
    "ferrari",
    "lamborghini",
    "mclaren",
    "koenigsegg",
)
FORBIDDEN_POSE_PATHS = {
    "location",
    "rotation_euler",
    "rotation_quaternion",
    "scale",
}
LOCKED_BLOB_SHA = {
    "blender/iss_blender_production_worker.py": "1b58ef30e899591ec9eb05133afa756ed0fa0b5b",
}


class ValidationError(RuntimeError):
    pass


def git_blob_sha(path: Path) -> str:
    data = path.read_bytes()
    header = f"blob {len(data)}\0".encode("utf-8")
    return hashlib.sha1(header + data).hexdigest()


def attr_chain(node: ast.AST) -> str:
    parts: list[str] = []
    current = node
    while isinstance(current, ast.Attribute):
        parts.append(current.attr)
        current = current.value
    if isinstance(current, ast.Name):
        parts.append(current.id)
    return ".".join(reversed(parts))


class SafetyVisitor(ast.NodeVisitor):
    def __init__(self, relative: str) -> None:
        self.relative = relative
        self.failures: list[str] = []

    def visit_Call(self, node: ast.Call) -> Any:
        if isinstance(node.func, ast.Attribute) and node.func.attr == "keyframe_insert":
            data_path: str | None = None
            for keyword in node.keywords:
                if keyword.arg == "data_path" and isinstance(keyword.value, ast.Constant):
                    if isinstance(keyword.value.value, str):
                        data_path = keyword.value.value
            if data_path is None and node.args and isinstance(node.args[0], ast.Constant):
                if isinstance(node.args[0].value, str):
                    data_path = node.args[0].value
            if data_path in FORBIDDEN_POSE_PATHS and not self.relative.endswith(
                "iss_battle_runtime_camera.py"
            ):
                self.failures.append(
                    f"POSE_KEYFRAME_STATIC_FORBIDDEN:{self.relative}:{data_path}:{node.lineno}"
                )
        self.generic_visit(node)

    def visit_Assign(self, node: ast.Assign) -> Any:
        for target in node.targets:
            chain = attr_chain(target)
            if chain.endswith(".linear_velocity"):
                self.failures.append(
                    f"DIRECT_LINEAR_VELOCITY_ASSIGNMENT_FORBIDDEN:{self.relative}:{node.lineno}"
                )
            if (
                any(chain.endswith("." + x) for x in FORBIDDEN_POSE_PATHS)
                and ".chassis." in chain
            ):
                self.failures.append(
                    f"ACTOR_CHASSIS_POSE_ASSIGNMENT_FORBIDDEN:{self.relative}:{chain}:{node.lineno}"
                )
        self.generic_visit(node)


def static_source_audit() -> dict[str, Any]:
    failures: list[str] = []
    parsed = 0
    for relative in REQUIRED_FILES:
        path = ROOT / relative
        if not path.is_file():
            failures.append(f"REQUIRED_FILE_MISSING:{relative}")

    duplicate = ROOT / "blender/battle_runtime_contract.py"
    if duplicate.exists():
        failures.append("SUPERSEDED_DUPLICATE_CONTRACT_PRESENT")

    for relative in GENERIC_FILES:
        path = ROOT / relative
        if not path.is_file():
            continue
        source = path.read_text(encoding="utf-8")
        lower = source.lower()
        for token in BANNED_SCENARIO_TOKENS:
            if token in lower:
                failures.append(f"SCENARIO_HARDCODE_FORBIDDEN:{relative}:{token}")
        try:
            tree = ast.parse(source, filename=relative)
        except SyntaxError as exc:
            failures.append(
                f"PYTHON_SYNTAX_INVALID:{relative}:{exc.lineno}:{exc.msg}"
            )
            continue
        parsed += 1
        visitor = SafetyVisitor(relative)
        visitor.visit(tree)
        failures.extend(visitor.failures)

    for relative, expected in LOCKED_BLOB_SHA.items():
        path = ROOT / relative
        if not path.is_file():
            failures.append(f"LOCKED_REFERENCE_FILE_MISSING:{relative}")
            continue
        actual = git_blob_sha(path)
        if actual != expected:
            failures.append(
                f"LOCKED_REFERENCE_DRIFT:{relative}:{actual}:{expected}"
            )

    if failures:
        raise ValidationError(";".join(failures))
    return {
        "status": "PASS",
        "parsedPythonFiles": parsed,
        "lockedReferenceChecks": len(LOCKED_BLOB_SHA),
    }


def make_request(actor_count: int = 100) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    actor_ids = [f"unit_{index:03d}" for index in range(actor_count)]
    target = actor_ids[-1]
    attackers = actor_ids[:-1]
    bindings = [
        {
            "entityId": actor_id,
            "totalMassKg": 1450.0 + (index % 7) * 25.0,
            "runtimeProfile": {
                "maxSpeedMps": 18.0,
                "accelerationMps2": 6.0,
                "brakingMps2": 9.0,
                "toughnessJPerKg": 90.0,
            },
        }
        for index, actor_id in enumerate(actor_ids)
    ]
    request = {
        "durationSeconds": 12,
        "physicsFps": 120,
        "renderSpec": {
            "fps": 30,
            "resolution": {"width": 720, "height": 1280},
        },
        "executionPolicy": {
            "continuousWorld": True,
            "persistentDamage": True,
            "persistentDebris": True,
            "resetAllowed": False,
            "teleportAllowed": False,
            "silentSimplificationAllowed": False,
            "replanOnPhysicalImpossibility": True,
            "forcedTransformAfterContactAllowed": False,
            "velocityInjectionAfterContactAllowed": False,
        },
        "battlePlan": {
            "objective": "generic runtime property test",
            "finalOutcome": "state-derived",
            "events": [
                {
                    "eventId": "evt_setup",
                    "type": "BATTLE_HOOK",
                    "phase": "HOOK",
                    "startTime": 0.0,
                    "endTime": 1.0,
                    "actors": actor_ids,
                    "attackTarget": "",
                    "causedByEventIds": [],
                    "physicsRequirements": {
                        "speedIntent": "hold",
                        "trajectory": "setup",
                    },
                },
                {
                    "eventId": "evt_wave",
                    "type": "COORDINATED_ATTACK",
                    "phase": "FIRST_ATTACK",
                    "startTime": 1.0,
                    "endTime": 9.0,
                    "actors": attackers,
                    "attackTarget": f"{target}:front",
                    "causedByEventIds": ["evt_setup"],
                    "damage": {
                        "required": True,
                        "persistent": True,
                        "zone": "front",
                    },
                    "physicsRequirements": {
                        "speedIntent": "accelerate",
                        "trajectory": "direct converging approach",
                        "targetArea": "front",
                    },
                },
                {
                    "eventId": "evt_payoff",
                    "type": "OUTCOME",
                    "phase": "PAYOFF",
                    "startTime": 9.0,
                    "endTime": 12.0,
                    "actors": actor_ids,
                    "attackTarget": "",
                    "causedByEventIds": ["evt_wave"],
                    "physicsRequirements": {
                        "speedIntent": "settle",
                        "trajectory": "natural post-contact motion",
                    },
                },
            ],
        },
        "scenes": [
            {
                "sceneNumber": 1,
                "startSecond": 0,
                "endSecond": 5,
                "eventIds": ["evt_setup", "evt_wave"],
                "cameraIntent": "track battle",
            },
            {
                "sceneNumber": 2,
                "startSecond": 5,
                "endSecond": 10,
                "eventIds": ["evt_wave", "evt_payoff"],
                "cameraIntent": "track battle",
            },
            {
                "sceneNumber": 3,
                "startSecond": 10,
                "endSecond": 12,
                "eventIds": ["evt_payoff"],
                "cameraIntent": "aftermath",
            },
        ],
    }
    return request, bindings


def compiler_scale_properties() -> dict[str, Any]:
    request, bindings = make_request(100)
    program = BattleCompiler.compile(request, bindings)
    if len(program.actor_ids) != 100:
        raise ValidationError("COMPILER_ACTOR_COUNT_NOT_100")
    if program.total_frames != 360:
        raise ValidationError(f"COMPILER_TOTAL_FRAMES_UNEXPECTED:{program.total_frames}")

    spawn = SpawnPlanner.plan(program)
    if len(spawn) != 100:
        raise ValidationError("SPAWN_COUNT_NOT_100")
    rounded = {
        (round(v[0], 5), round(v[1], 5), round(v[2], 5))
        for v in spawn.values()
    }
    if len(rounded) != 100:
        raise ValidationError("SPAWN_POSITIONS_NOT_UNIQUE")

    event = next(x for x in program.events if x.event_id == "evt_wave")
    union: set[str] = set()
    peak = 0
    for frame in range(event.start_frame, event.end_frame + 1):
        active = WaveScheduler.active_attackers(event, frame)
        union.update(active)
        peak = max(peak, len(active))
    if union != set(event.attackers):
        missing = sorted(set(event.attackers) - union)
        raise ValidationError(f"WAVE_SCHEDULER_DROPS_ATTACKERS:{missing[:5]}")
    if peak > 12:
        raise ValidationError(f"WAVE_CONCURRENCY_CAP_BROKEN:{peak}")
    return {
        "status": "PASS",
        "actorCount": len(program.actor_ids),
        "uniqueSpawnCount": len(rounded),
        "waveCoverage": len(union),
        "peakConcurrentAttackers": peak,
    }


def contract_fail_closed_properties() -> dict[str, Any]:
    request, bindings = make_request(4)

    bad_policy = json.loads(json.dumps(request))
    bad_policy["executionPolicy"]["teleportAllowed"] = True
    try:
        BattleCompiler.compile(bad_policy, bindings)
    except BattleRuntimeContractError:
        pass
    else:
        raise ValidationError("TELEPORT_POLICY_DID_NOT_FAIL_CLOSED")

    missing_mass = [dict(x) for x in bindings]
    missing_mass[0].pop("totalMassKg", None)
    try:
        ActorProfile.from_binding(missing_mass[0], ("front", "body"))
    except BattleRuntimeContractError:
        pass
    else:
        raise ValidationError("MISSING_MASS_DID_NOT_FAIL_CLOSED")

    bad_target = json.loads(json.dumps(request))
    bad_target["battlePlan"]["events"][1]["attackTarget"] = "unknown_actor:front"
    try:
        BattleCompiler.compile(bad_target, bindings)
    except BattleRuntimeContractError:
        pass
    else:
        raise ValidationError("UNKNOWN_TARGET_DID_NOT_FAIL_CLOSED")

    return {"status": "PASS", "failClosedCases": 3}


def impact_damage_properties() -> dict[str, Any]:
    severities: list[float] = []
    for speed in (2.0, 4.0, 8.0, 16.0, 24.0):
        evidence = ImpactModel.estimate(
            frame=10,
            attacker_id="alpha",
            target_id="beta",
            target_zone="front",
            attacker_mass_kg=1600.0,
            target_mass_kg=1800.0,
            relative_speed_mps=speed,
            normal_closing_speed_mps=speed,
            contact_point=(0.0, 0.0, 0.5),
            contact_normal=(1.0, 0.0, 0.0),
            response_delta_attacker_mps=max(0.2, speed * 0.05),
            response_delta_target_mps=max(0.2, speed * 0.04),
            target_toughness_j_per_kg=90.0,
        )
        severities.append(evidence.severity)

    if any(b < a for a, b in zip(severities, severities[1:])):
        raise ValidationError(f"IMPACT_SEVERITY_NOT_MONOTONIC:{severities}")

    state = ActorState("beta")
    low = ImpactModel.estimate(
        frame=10,
        attacker_id="alpha",
        target_id="beta",
        target_zone="front",
        attacker_mass_kg=1600.0,
        target_mass_kg=1800.0,
        relative_speed_mps=8.0,
        normal_closing_speed_mps=8.0,
        contact_point=(0.0, 0.0, 0.5),
        contact_normal=(1.0, 0.0, 0.0),
        response_delta_attacker_mps=1.0,
        response_delta_target_mps=0.8,
        target_toughness_j_per_kg=90.0,
    )
    before = state.structural_integrity
    DamageAccumulator.apply(state, low)
    first = state.structural_integrity
    DamageAccumulator.apply(state, low)
    second = state.structural_integrity
    if not (second < first < before):
        raise ValidationError(
            f"CUMULATIVE_DAMAGE_NOT_PERSISTENT:{before}:{first}:{second}"
        )

    event_states = {
        "e": EventState("e", status="SUCCEEDED"),
    }
    outcome = OutcomeResolver.resolve({"beta": state}, event_states)
    if outcome["allRequiredEventsSucceeded"] is not True:
        raise ValidationError("OUTCOME_RESOLVER_SUCCESS_REGRESSION")

    return {
        "status": "PASS",
        "severitySequence": severities,
        "integritySequence": [before, first, second],
    }


def main() -> None:
    result = {
        "static": static_source_audit(),
        "compilerScale": compiler_scale_properties(),
        "failClosed": contract_fail_closed_properties(),
        "impactDamage": impact_damage_properties(),
    }
    print(
        json.dumps(
            {
                "marker": "GENERIC_BATTLE_RUNTIME_STATIC_VALIDATION",
                "status": "PASS",
                "result": result,
            },
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
