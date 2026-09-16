# ISS-G07 Scope Pre-Flight — ISS-R043

## Authority

This pre-flight is mandatory under **ISS-R043 — Mandatory Gate scope pre-flight and post-flight acceptance sandwich**.

Authoritative scope sources reread before Candidate 4.4.4 engineering:

1. Supabase Engineering Memory and active LOCKs, including ISS-R041, ISS-R042, and ISS-R043.
2. `ISS Master Project Documentation — 2026-09-15 v1.1`, including `ISS_MASTER_REQUIREMENTS.md` and `ISS_MASTER_PLAN.md`.
3. Current live GitHub evidence on branch `iss-engineering/generic-battle-runtime-v1`.

A machine PASS by itself is insufficient. G07 may be declared PASS only after a separate post-flight scope audit also passes.

## Project-scope invariants

The product is a reusable production tool, not a one-off vehicle video:

> idea + supported vehicle set -> same Battle Runtime source -> asset/profile data + Story intent -> autonomous physical battle -> different video

The following scope constraints are binding:

- no per-video battle source code;
- no per-asset battle source code;
- runtime must not need an asset name;
- asset/profile data may vary, Battle Runtime source may not;
- Story declares goals, targets, tactics, dependencies, escalation/climax/payoff intent only;
- Story/G07 must not prescribe exact trajectories, collision frames, impact speed, Joules, braking points, collision points, or semantic contact zones merely to make a fixture pass;
- collision realization belongs to the generic runtime using current world state, ActorProfile, live geometry, controller state, and native Blender physics;
- G05 remains final native contact authority;
- G06 remains consequence/persistent-state authority and its thresholds are unchanged;
- no actor pose injection, velocity injection, teleport/reset, forced winner, forced joint release, or proxy final-contact truth;
- exact Bugatti and generic-hypercar are regression fixtures, not product-specific runtime branches.

## G07 gate scope

Master Plan definition:

**ISS-G07 — Battle State Machine + Dramatic Causal Progression**

Requirement scope: `ISS-MR-B29..B30; ISS-MR-D01..D16`.

G07 must prove that a continuous battle can causally realize escalation, counterattack, dominance reversal/comeback, climax, payoff, and final outcome from realized physical state. Earlier physical consequences may affect later behavior. G07 is not a collision choreography layer and must not become one.

## Preserved MACHINE_PROVEN predecessors

Candidate 4.4.4 must preserve without source mutation:

- G04 closed-loop autonomy/replanning;
- G05 native contact truth;
- G06 causal damage/deformation/debris/persistent state;
- locked damage/contact thresholds and no-cheating gates.

The Candidate 4.4.4 workflow must verify the existing G04/G05/G06 source hashes before real execution.

## Candidate 4.4.3 evidence and exact capability gap

Run `35052143610` proved that Candidate 4.4.3 can use actor-only Story intent and select an engagement semantic surface from live target geometry without asset-name branches or Story-prescribed zones. Exact Bugatti completed under that model.

The identical runtime source failed on the generic-hypercar climax after escalation, counterattack, G05 transactions, G06 persistent consequence, and a real dominance reversal had already occurred.

The failure was not insufficient impact strength and was not a missing per-asset collision target. During climax the actors reached live physical overlap and the G04 controller entered `CONTACT_HANDOFF`, but authority oscillated back to `TRACK/MOTOR` before G05 could complete its native solver-response receipt window.

Root capability gap:

**G07_GENERIC_SOLVER_HANDOFF_LIFECYCLE_UNSTABLE**

## Candidate 4.4.4 allowed engineering surface

Candidate 4.4.4 may add only an additive **state-derived solver handoff lifecycle** around the already-proven generic controller/contact path.

When the existing generic G04 controller independently opens `CONTACT_HANDOFF`, the successor may keep motor authority at COAST while native solver evidence is being observed. The handoff may end only from generic realized state:

- a VERIFIED G05 native physical transaction;
- real live geometry showing separation/miss;
- actor/event terminal or disabled state;
- the existing G04 generic progress-timeout recovery signal/policy.

The lifecycle must derive its handoff gap and recovery timeout from the existing controller policy/evidence. It must not introduce asset-specific distance, speed, impact-energy, timing, or semantic-zone targets.

The lifecycle may maintain truthful cutoff/handoff evidence inside G05's existing solver observation window, but it may not change G05 contact authority, tolerances, solver tests, or final truth rules.

## Explicitly forbidden Candidate 4.4.4 shortcuts

- making vehicles hit harder;
- lowering `MIN_DAMAGE_SEVERITY` or any contact/damage acceptance threshold;
- adding a Bugatti/generic-hypercar/vehicle-name branch;
- prescribing `front`, `rear`, side, or any other Story contact zone in order to pass;
- adding a custom collision frame, speed, Joule target, trajectory, steering angle, braking point, or contact point;
- injecting actor pose or velocity;
- extending the solver/contact threshold merely to make a receipt pass;
- changing G04/G05/G06 source files;
- treating Candidate 4.4.3 exact-Bugatti success as sufficient generic proof.

## Acceptance plan

Candidate 4.4.4 must use the same runtime source and actor-only Story intent structure on:

1. exact full-source Bugatti regression;
2. generic-hypercar regression.

Acceptance must prove:

- R041 generic multi-vehicle scope preserved;
- R042 asset-independent collision realization preserved;
- R043 scope pre-flight passed;
- runtime-selected live semantic engagement remains active;
- stable handoff lifecycle is state-derived and controller-policy-derived;
- at least one handoff closes through a VERIFIED G05 transaction;
- no per-asset handoff tuning;
- G04/G05/G06 source integrity preserved;
- full G07 causal progression completes on both fixtures;
- production-ready is not claimed.

After machine acceptance, a fresh **SCOPE POST-FLIGHT** against the authoritative project scope is mandatory before G07 can be called PASS.

## Pre-flight decision

**SCOPE PRE-FLIGHT: PASS**

Candidate 4.4.4 is permitted only within the bounded additive handoff-lifecycle surface above. Any implementation or acceptance evidence that drifts into per-asset collision engineering, impact-strength tuning, Story choreography, or predecessor mutation invalidates the candidate and leaves G07 OPEN.
