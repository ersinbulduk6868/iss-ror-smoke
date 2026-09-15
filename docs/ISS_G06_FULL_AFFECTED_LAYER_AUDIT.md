# ISS-G06 Damage + Persistent State — full affected-layer audit

Date: 2026-09-15

Status: OPEN engineering gate. This audit does not lock G06 and does not claim production readiness.

## Lock / known-good pre-flight

The following are immutable inputs to G06 unless the user explicitly unlocks them:

- Frozen 9-service ISS architecture; Merge remains a separate service.
- RC3.4 production asset/runtime binding.
- REAL_PRODUCTION_BATTLE_INTEGRATION_V1 RC1.9 known-good state.
- Candidate 3.9 supported physical envelope and semantic-surface projection.
- Candidate 3.7.1 surface-aware causal visual consequence hardening.
- ISS-G04 Candidate 4.0 closed-loop autonomy MACHINE_PROVEN PASS.
- ISS-G05 Candidate 4.2 pairwise native-contact/no-cheating MACHINE_PROVEN PASS.
- `MIN_DAMAGE_SEVERITY = 0.055`.
- Existing ImpactModel qualification and semantic tolerance.
- ISS-R039/R040 product-truth / no-cheating requirements.

G06 may not solve persistence by changing contact authority, lowering thresholds, injecting pose/velocity, resetting actors, manufacturing damage, targeting impact Joules, or adding asset-specific battle code.

## Gate purpose

G05 proves that the intended actor pair produced a qualifying native solver response and that final contact authority is not OBB/sweep/proxy truth. G06 must prove what happens *after* that verified physical transaction:

`G05 verified contact -> earned damage -> physical/visual consequence -> persistent actor/world state -> later autonomous behavior consumes changed state`

A single impact frame is insufficient. G06 requires later-world evidence.

## Affected-layer audit

### 1. Damage state model — present but not yet later-event proven

`ActorState` already persists in memory across the continuous runtime and contains:

- `structural_integrity`
- `drive_efficiency`
- `zone_integrity`
- `disabled`
- `damage_events`
- `last_impact_frame`

`DamageAccumulator.apply` mutates this same actor state object; it does not replace it between events. It records before/after integrity, drive efficiency, contact identity and detector provenance.

Finding: **implementation capability exists; later-event persistence is not yet machine-proven by G04/G05 acceptance.**

### 2. Damage qualification — correct causal location, must remain unchanged

The hardened resolver applies DamageAccumulator / ConsequenceEngine only after an existing ImpactModel-qualified physical transaction. Candidate 4.2 now ensures the pending physical transaction itself carries G05 pairwise native contact authority.

`MIN_DAMAGE_SEVERITY=0.055` remains the damage-earned gate. If an event requires damage and severity does not earn damage, lifecycle must not falsely resolve it.

Finding: **causal ordering is present and must be preserved. G06 must prove fail-closed behavior and provenance binding.**

### 3. Visual deformation — persistence mechanism exists, not yet acceptance-proven

Candidate 3.7/3.7.1 replaces sparse-vertex-only deformation with surface-aware deformation on a copy-on-damage realization. A shape key is created at the realization frame and set from 0 to 1. No later key returns it to 0. The original visual instance is hidden and the damaged realization is parented to the authoritative actor chassis.

Finding: **persistence mechanism exists; G06 must inspect a later frame and prove the damaged realization remains active and the damage shape key remains applied.**

### 4. Debris — causal birth exists, later physical persistence not yet acceptance-proven

Debris shards are created from the impact contact, become rigid bodies, and store:

- source actor
- impact frame
- impact severity
- `iss_debris_trajectory_injection = False`

Their pre-birth `kinematic=True` / hidden state and impact-frame activation are object-birth lifecycle control, not battle trajectory injection. G06 must nevertheless prove that after birth the shards remain solver-controlled world objects and are not later removed/reset/repositioned by ISS code.

Finding: **causal debris creation exists; later-world persistence must be machine-proven.**

### 5. Autonomous controller consumption of damage state — implementation exists, runtime proof missing

ISS-G04 `ClosedLoopGoalController` consumes `drive_efficiency` and `actor_disabled` every update. Candidate 4.0 constructs each `AutonomyObservation` from the current actor state. Lower drive efficiency scales maximum forward, reverse and yaw authority; disabled actors are forced to `DISABLED` + `COAST`.

Finding: **the data path exists, but G04/G05 fixtures end in payoff after the first collision. They do not prove that a later active battle event actually sees and uses the damaged state.**

### 6. Event lifecycle / dependencies — sufficient for a persistence fixture

BattleLifecycle carries event dependencies and damage-earned status in the same continuous runtime. A later event can depend on a prior damage-required event. This permits a non-choreographed G06 acceptance fixture where the damaged target becomes an attacker in a later event.

Finding: **no lifecycle redesign required for G06.**

### 7. Current evidence gap

Existing G05 acceptance proves:

- verified pairwise native solver contact;
- qualified impact;
- incidental causal damage in both exact Bugatti and generic hypercar fixtures;
- G04 target refresh / contact handoff;
- no pose/velocity mutation.

It does **not** prove:

- state survives into a later active event;
- later controller observation sees degraded drive efficiency;
- disabled state, if reached, prevents later motor authority;
- deformation remains active at a later frame;
- debris remains present/physical later;
- no hidden state reset occurred between events.

This is the exact G06 failure family: `DAMAGE_PERSISTENT_STATE_ACCEPTANCE_GAP`.

## G06 acceptance contract

A Candidate 4.3 G06 acceptance is valid only if all of the following pass with no locked-source regression:

1. Every accepted damage event is bound to a G05 `nativeContactReceipt` with `nativeContactAuthority=true`.
2. No damage is applied without such verified physical transaction provenance.
3. Existing `MIN_DAMAGE_SEVERITY=0.055` is unchanged and damage-required lifecycle remains fail-closed below it.
4. The first damage-required event naturally earns damage. No target Joule, impact speed, collision frame or trajectory point is prescribed.
5. At least one actor damaged by the first event becomes an attacker in a later dependent active event in the **same continuous world**.
6. At that later event, the controller receives the same actor state's degraded `drive_efficiency < 1.0` and unchanged accumulated structural/zone state.
7. Property acceptance proves that, for otherwise equal observations, lower drive efficiency reduces available controller capability; runtime evidence proves the later event actually consumes the degraded state.
8. Damage event history remains append-only/non-reset across the later event.
9. Damaged visual realization exists at a later verification frame; at least one damage shape key created by the causal impact remains applied.
10. Causally spawned debris remains present in the scene at the later verification frame, remains rigid-body controlled after birth, and carries `iss_debris_trajectory_injection=false`.
11. No actor transform, pose, velocity, teleport, reset or hidden post-impact winner forcing is introduced by Candidate 4.3.
12. Exact Bugatti and generic hypercar run the identical Candidate 4.3 runtime source. Only asset/profile data may differ.
13. G04 target/replan behavior and G05 pairwise native-contact authority remain accepted in the G06 run.
14. G06 claims only damage/persistent-state acceptance. Dramatic strategy, cinematic visual quality, scale and E2E remain downstream.

## G06 acceptance fixture contract

The G06 fixture must be intent-only and generic:

- setup / hold;
- first one-sided damage-required attack, e.g. `actor_alpha -> actor_beta:front`;
- a later dependent attack where the previously damaged `actor_beta` must autonomously act against `actor_alpha`;
- payoff/aftermath.

The same event structure is used for exact Bugatti and generic hypercar.

Forbidden fixture fields / behavior:

- exact collision frame/time;
- exact impact speed;
- target impact energy/Joules;
- waypoint/path/trajectory points executable by the runtime;
- per-asset event timing or speed constants;
- scripted state decrement;
- manual reposition/reset between events.

Story time windows are guidance/dependency windows only, not collision choreography.

## Negative-control family

Before the real Blender fixture, zero-cost acceptance must prove:

- damage provenance without G05 receipt is rejected by the G06 evidence validator;
- state reset/decreased damage history is rejected;
- restored drive efficiency after damage is rejected;
- a later active event that does not observe degraded state is rejected;
- missing/inactive deformation receipt is rejected;
- missing/deleted or trajectory-injected debris is rejected when debris was causally spawned;
- disabled actor motor authority is rejected if it becomes nonzero;
- Candidate 4.0, Candidate 4.2, Candidate 3.9 and Candidate 3.7.1 preserved source blobs remain unchanged.

## Engineering decision

G06 does **not** require redesigning the damage model, G04 controller, G05 detector, Story Service, or service architecture. The missing item is primarily a full persistence/continuity acceptance layer over capabilities already present.

Therefore Candidate 4.3 should be an isolated observer + evidence hardening layer over Candidate 4.2, plus a sequential generic G06 fixture. Production behavior is changed only if real machine evidence demonstrates an actual persistence defect.

Next action: build Candidate 4.3 G06 observer/evidence contract and generic sequential fixture; run cheap property/static acceptance first, then exact Bugatti + generic hypercar on Blender 4.5.13 to terminal result.
