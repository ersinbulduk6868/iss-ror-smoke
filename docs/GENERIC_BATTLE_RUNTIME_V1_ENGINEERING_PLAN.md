# ISS Generic Battle Runtime v1 — Engineering Contract

Status: ISOLATED CANDIDATE ONLY. This does not unlock, modify, or replace any locked ISS service or the frozen 9-service architecture.

## Objective

Implement a reusable Blender 4.5.13 battle execution layer that converts Story/Battle Schema intent into solver-driven, continuous, persistent, multi-event battle simulation without per-video trajectory scripting or post-physics pose cheating.

## Hard constraints

- Frozen 9-service architecture remains unchanged.
- Existing Content, Story, Visual, Asset, Merge, Quality, Publishing, and Orchestrator contracts are not changed by this candidate.
- Existing machine-proven RC2 full-geometry / no-visible-proxy / no-post-handoff-pose-keyframes / solver-driven response gates remain preserved.
- No per-video actor-name, coordinate, trajectory, or damage hack may be required by the runtime core.
- Visible source geometry remains authoritative. Hidden collision geometry may be used only for physics.
- Battle world is continuous; reset, teleport, instant repair, hidden pose correction, and hidden post-contact velocity injection are forbidden.
- Damage and debris must be causally gated by machine-observed physical contact and impact telemetry.
- Outcome must be consistent with measured world state, not a scripted winner override.

## Candidate modules

1. `battle_runtime_contract.py` — fail-closed request/schema normalization and generic battle command compilation.
2. `battle_runtime_core.py` — actor profiles, runtime state, dynamic semantic targeting, tactics, steering/drive controller, replanning, impact telemetry, persistent damage state, wave scheduling, and outcome resolution.
3. `iss_blender_battle_runtime_v1.py` — Blender adapter that binds production geometry and native rigid-body execution to the generic runtime core.
4. `validate_generic_battle_runtime_v1.py` — static/self-test validator proving absence of scenario-specific actor hardcoding and post-handoff transform scripting.
5. `generic-battle-runtime-v1-preflight.yml` — isolated zero-cost/static + Blender preflight workflow; final paid/production execution remains separately gated.

## Required generic command vocabulary

- HOLD
- ACCELERATE
- BRAKE
- REVERSE
- RAM
- FLANK_LEFT
- FLANK_RIGHT
- EVADE
- REGROUP
- PRESSURE
- SETTLE

Story text is not trusted as executable motion. The compiler maps battle event type + `physicsRequirements` + `attackTarget` to one of these generic commands.

## Runtime invariants

- Control inputs are applied through force/impulse/torque authority before contact; no post-handoff location keyframes.
- Dynamic target position is re-resolved from the target actor/semantic region every simulation step.
- If a target becomes unreachable, runtime replans or marks the event physically unresolved; it never teleports.
- Contact evidence includes actor pair, frame/time, relative speed, normal approximation, contact point approximation, reduced mass, and impact-energy proxy.
- Damage severity is a monotonic function of physically measured impact evidence plus persistent accumulated region damage.
- Damage state affects later actor capability (mobility/control multiplier) and therefore later events.
- Debris remains dynamic and persistent after release.
- Every event stores evidence for command intent, target semantics, contact, consequence, and continuation state.

## Scale policy

The runtime design must remain independent of actor count. Scaling to 5/10/25/100 actors is handled by scheduling, shared pristine visual geometry where safe, physics activation budgeting, and copy-on-damage state; no scenario-specific code path may be introduced for 100-vs-1.

## Acceptance ladder

A. Static contract + property self-tests.
B. Two arbitrary actors: dynamic target + solver-driven RAM with no pose keyframes.
C. Multi-event continuous world: RAM -> counter/replan -> aftermath with persistent state.
D. Multi-actor waves and tactics.
E. Scale 5 -> 10 -> 25 -> 100.
F. Checkpoint-free Story/Battle Schema -> continuous battle -> cinematic render acceptance.

No stage is production-accepted until its machine evidence and required human visual review pass.