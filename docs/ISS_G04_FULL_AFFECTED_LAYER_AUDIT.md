# ISS-G04 — Full Affected-Layer Audit

Date: 2026-09-15
Baseline branch: `iss-engineering/generic-battle-runtime-v1`
Baseline commit: `0e14d9d770634b59aa5e184bea902abdd88b5270`
Gate: `ISS-G04 — Closed-Loop Autonomous Motion + Replanning`
Status at audit start: `OPEN_ACTIVE_ENGINEERING`

## LOCK pre-flight

This audit does not unlock or alter the frozen 9-service architecture, Merge/Generation boundary, RC3.4 Production Asset Runtime Binding, RC1.9 Real Production Battle Integration, Content/Story/Quality/Orchestrator preserved contracts, ISS-R039/R040 product-truth rules, no-cheating rules, or acceptance thresholds.

The Generic Battle Runtime candidate layer is open. Candidate 3.9 remains immutable historical evidence: exact Bugatti asset identity/envelope/semantic-surface handling and reciprocal-intent coalescing are preserved; its terminal execution result remains FAIL.

## Sources audited

- `blender/iss_battle_runtime_contract.py`
- `blender/iss_battle_runtime_models.py`
- `blender/iss_battle_runtime_physics.py`
- `blender/iss_battle_runtime_lifecycle.py`
- `blender/iss_blender_battle_runtime_v1.py`
- `blender/iss_blender_battle_runtime_v1_hardened.py`
- `blender/iss_battle_runtime_consequences.py`
- `blender/iss_battle_runtime_assets.py`
- `blender/run_generic_battle_runtime_v1_candidate35.py`
- `blender/run_generic_battle_runtime_v1_candidate37.py`
- `blender/run_generic_battle_runtime_v1_candidate371.py`
- `blender/run_generic_battle_runtime_v1_candidate39.py`
- `tools/build_generic_battle_runtime_v1_preflight.py`
- `tools/build_generic_battle_runtime_v1_bugatti_preflight.py`
- `tools/validate_generic_battle_runtime_v1_candidate3.py`
- GitHub run `34956570930`, job `104339940792`, exact Candidate 3.9 logs.

## Preserved machine-proven assets

1. Exact Bugatti source identity SHA256 `8cc074c40fe9ced7271cbeddf223cd9a520dee868977ffcbd439cec1c2b62cb4`.
2. Candidate 3.9 supported physical envelope: `4.900918 x 2.225155 x 1.191856 m`.
3. Candidate 3.9 generic removal of two detached near-ground auxiliary meshes.
4. Candidate 3.9 semantic-surface projection for front/rear/left/right zones.
5. Candidate 3.9 reciprocal two-sided intent coalescing into one physical transaction.
6. Candidate 3.7.1 surface-aware causal damage realization and truthful contact-to-visual receipt timing.
7. Candidate 3.5 mass/acceleration/radius/traction drive-authority calibration.
8. No post-initialization actor pose or velocity mutation in the preserved candidate chain.
9. No damage/contact threshold weakening.

## Root cause — G04 failure family

The active failure family is not “Bugatti needs more impact energy”. It is `AUTONOMOUS_CONTROL_REPLANNING_GAP`.

The current runtime contains useful dynamic targeting and rigid-body actuation, but the execution loop is still partly choreography/heuristic driven:

- `drive_command()` selects fixed tactic speed fractions (`FLANK 0.74`, `SURROUND 0.62`, `COUNTER 0.78`, `RAM 0.88`) instead of deriving control from current goal error, capability and world state.
- Contact approach uses a dimension-derived `contact_cutoff` and the hardened layer adds a velocity-derived predictive margin. These values are controller heuristics that can dominate whether an impact is physically useful.
- `active_event_for_actor()` and contact detection stop authority at story event end plus a one-second grace window.
- Replanning is only a lifecycle marker/opened grace window; it does not contain a real recovery state machine.
- No explicit controller memory exists for progress, stall, miss, blockage, failed/nonproductive contact, recovery phase, target movement, or multi-agent contention.
- A target point is recomputed every frame, but the control law does not explicitly measure progress toward the goal or decide when the current approach has failed.
- A contact that is real but does not achieve the event outcome does not autonomously cause a retreat/reorientation/re-attack cycle.
- Disabled actors are not given a dedicated autonomous disposition beyond lower-level drive behavior.

Candidate 3.9 therefore exposed a system-level controller gap: the runtime reached real native response contact, but its next behavior was governed by the same fixed approach/cutoff/lifecycle rules instead of an autonomous “observe → decide → act → evaluate → replan” loop.

## G02 compatibility finding — intent-only compiler

The existing `BattleCompiler` does not contain exact collision frames, target Joules or explicit trajectories as executable numerical paths, which is useful. However it still reads free-text `physicsRequirements.trajectory` and `speedIntent` during tactic inference and preserves the complete raw event in `RuntimeEvent.original`.

For the G04 successor, Story compatibility must be preserved while adding an intent firewall:

- high-level action/tactic intent may be derived from existing Story text;
- descriptive `trajectory` may be translated into a high-level tactic and then removed from the executable event contract;
- exact choreography fields such as collision/contact frame, impact speed, target Joules, cutoff distance, path points, waypoints, pose/velocity keyframes are forbidden in the executable goal contract;
- story timing remains narrative activation guidance, not an exact physics-contact deadline.

No Story Service change is required.

## G03 compatibility finding — ActorProfile / asset onboarding

Candidate 3.9 asset fixes are generic and must remain unchanged in the G04 successor. G04 must consume ActorProfile/canonical dimensions/semantic zones as data only. The controller may derive dimensionless or capability-based control quantities from ActorProfile and current geometry; it may not branch on asset name, source UID or fixture identity.

G03 remains only partially closed because a third dissimilar real asset has not yet proven the same onboarding path. G04 engineering must not pretend otherwise.

## Required G04 architecture

The successor must introduce a stateful closed-loop controller with the following cycle on every control step:

`OBSERVE WORLD → RESOLVE CURRENT GOAL → ESTIMATE PROGRESS/CONSTRAINTS → CHOOSE CONTROL MODE → ISSUE GENERIC ACTUATION → EVALUATE RESULT → REPLAN IF NEEDED`

Controller state is per `(event, actor)` and must persist across frames.

### Required observations

- current actor pose/orientation from physics state;
- target semantic point re-resolved every frame;
- current distance and surface gap;
- heading error;
- actor forward speed and target-relative closing trend;
- drive efficiency and disabled state;
- current event contact/damage counters;
- progress trend over time;
- nearby non-target actor contention/obstruction pressure.

### Required control modes

- `TRACK` — continuously steer toward current semantic goal.
- `CONTACT_HANDOFF` — relinquish motor authority only when physical proximity makes solver ownership imminent; this is a controller handoff, not contact truth.
- `RECOVER_REVERSE` — back out after stall/miss/nonproductive contact/blockage.
- `RECOVER_TURN` — reorient with deterministic generic side bias.
- `DISABLED` — zero authority for disabled actors.
- `IDLE/HOLD` — no attack authority when no executable goal exists.

### Required replanning triggers

1. Moving target: target is re-resolved continuously; steering must change without trajectory regeneration.
2. Miss: actor passed the best approach state and range opens again without successful event evidence.
3. Stall: commanded motion produces insufficient goal progress for a capability-derived timeout.
4. Blockage/contention: nearby non-target actor pressure plus loss of progress triggers recovery.
5. Nonproductive contact: contact evidence increased but required event consequence did not; actor must disengage/re-approach rather than remain pressed into the target.
6. Disabled actor: disabled actor relinquishes control; other eligible attackers remain able to continue.
7. Multi-agent contention: target lanes/avoidance are resolved generically; no actor-specific routing branch.

## Control-law policy

The new controller must not prescribe a target impact Joule value, exact collision frame, exact trajectory, exact cutoff distance, or asset-specific speed.

Allowed control quantities are generic functions of current observation and ActorProfile, for example:

- yaw-rate demand from current heading error and max yaw capability;
- wheel-speed targets from commanded forward speed + yaw rate + track width;
- approach speed bounded by max speed, acceleration, current goal distance/surface gap, heading quality and drive efficiency;
- recovery duration from locomotion/yaw capability;
- progress timeout from actor length/max speed and control period;
- contact handoff from current geometric surface gap and one-step travel, solely to remove motor authority before solver response.

These are runtime control laws, not fixture tuning.

## Lifecycle policy

Story `endTime` must not automatically mean “physics event failed exactly here”. For contact goals, the runtime may continue autonomous attempts while the global battle window remains available. Replan events may occur more than once. Final failure is allowed only when the runtime exhausts the authorized battle window or a true physical impossibility/disabled-state condition is reached.

G07 will later own dramatic scheduling and cross-event advantage progression; G04 only establishes correct autonomous goal execution/recovery behavior.

## G05 boundary

G04 does not claim Native Contact Truth is complete. The existing solver-correlated contact path may be used as provisional evidence for the G04 motion acceptance, but OBB/proxy overlap is not promoted to final product contact authority. G05 remains open until native Blender contact/response authority is independently established without OBB as final truth.

## G06 boundary

G04 does not tune damage thresholds or impact energy. A dedicated G04 motion fixture may set `damage.required=false` so autonomous movement/contact/replanning can be accepted independently from G06 causal-damage requirements. Candidate 3.9’s damage failure remains evidence for G06, not a reason to weaken G04/G06 boundaries.

## Acceptance plan for one clean G04 candidate

A candidate may close G04 only if all of the following pass with the same runtime source:

1. Pure controller property tests:
   - moving-target steering response;
   - stall detection and recovery;
   - miss detection and recovery;
   - blockage/contention recovery;
   - nonproductive-contact recovery;
   - disabled-actor zero authority;
   - deterministic replan state progression;
   - no exact-impact target inputs.
2. Static source audit:
   - no Bugatti/fixture/actor-name branches in runtime autonomy source;
   - no pose/velocity mutation;
   - no threshold weakening;
   - no exact trajectory/contact-frame/Joule controls;
   - preserved Candidate 3.9 asset/semantic models.
3. Real Blender 4.5.13 exact-Bugatti motion acceptance with `damage.required=false`:
   - exact asset identity preserved;
   - both targets are resolved from current state every frame;
   - controller telemetry proves closed-loop mode/goal updates;
   - actor pose/velocity mutation remains false;
   - physically qualified contact occurs or, if an intentional obstacle/recovery fixture is used, the required recovery behavior is machine evidenced;
   - final G04-specific acceptance passes without requiring G05/G06 to be declared closed.
4. Generic hypercar regression using the identical autonomy code.

## Forbidden fixes

- Bugatti-specific speed, mass, lane, yaw, timing, energy or contact constants.
- Per-video coordinates/waypoints.
- Lowering `MIN_DAMAGE_SEVERITY`.
- Treating OBB overlap alone as final contact PASS.
- Teleport, actor pose keyframes, post-init pose mutation, hidden velocity injection.
- Re-opening RC3.4 or RC1.9.
- Changing the frozen nine-service architecture.
- Claiming G05, G06, G07 or production readiness from a G04 PASS.

## Audit conclusion

`FULL_AFFECTED_LAYER_AUDIT = PASS_FOR_IMPLEMENTATION`

The next justified engineering action is one clean isolated G04 successor that adds an intent firewall plus a capability/world-state-driven autonomous controller/replanner, preserves Candidate 3.9 asset/semantic fixes and Candidate 3.7.1 consequence hardening, and is tested first with zero-cost property/static checks and then real Blender GitHub acceptance. No fixture-specific impact-energy tuning is justified.