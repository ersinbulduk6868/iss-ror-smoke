# ISS-G05 Native Contact Truth / No-Cheating — affected-layer audit

Status: OPEN engineering gate. This document does not lock G05 and does not claim production readiness.

## Preserved machine-proven state

- ISS-G04 Candidate 4.0 remains the known-good closed-loop autonomy baseline.
- Candidate 3.9 supported physical envelope and semantic surface projection remain unchanged.
- Candidate 3.7.1 surface-aware consequence hardening remains unchanged.
- Damage threshold and contact qualification thresholds are unchanged.
- No actor pose, transform, or velocity injection is permitted.
- Frozen ISS service boundaries are unaffected.

## Root problem

The inherited contact pipeline starts its physical transaction from `obb_overlap_2d(...)` and only later correlates the event with rigid-body response. Solver response is useful evidence, but the OBB overlap is not sufficient final product authority for ISS-R039/R040. A coarse overlap may be geometrically wrong, may not identify the intended target uniquely, and must not be renamed as native contact truth.

## Blender 4.5.13 capability proof

Real GitHub run `34981399858` on exact Blender 4.5.13 proved `RigidBodyWorld.convex_sweep_test` works after the rigid-body world has been stepped. The probe used the native rigid-body world only, with no OBB helper and no pose/velocity mutation.

Negative controls were required and passed:

- positive sweep: native hit = 1, hitpoint = target surface
- near miss: native hit = 0
- empty path: native hit = 0
- self-hit contamination: false

This proof establishes a usable Blender-native collision query primitive. It does **not** by itself establish final runtime contact truth.

## G05 authority contract

A contact transaction is G05-valid only when all of the following are true:

1. The attacker is executing an ISS-G04 autonomous goal; no per-video trajectory or exact collision frame is supplied.
2. Controller authority has handed off to Blender before the physical transaction is accepted.
3. The native query sweeps only the actor's **actual previous solver position to its actual current solver position**. No predictive extension is allowed.
4. `RigidBodyWorld.convex_sweep_test` returns a hit.
5. The hit normal is compatible with an actor-to-actor lateral collision rather than the ground plane.
6. The native hitpoint resolves uniquely to the intended target actor's oriented collision envelope; ambiguous multi-actor hits are rejected rather than guessed.
7. The native hitpoint satisfies the existing semantic target-zone tolerance; that tolerance is not weakened.
8. A subsequent physical response is observed from solver-produced motion and satisfies the existing `ImpactModel` qualification.
9. Damage remains a downstream consequence gate. G05 must not manufacture damage to prove contact.
10. The evidence receipt records the native API, actual-step path, hitpoint, normal, intended target identity, semantic distance, and controller handoff state.

## Failure-family handling

- Native query miss: no contact transaction; controller/replanner remains responsible for future attempts.
- Ground/vertical hit: reject as non-target native contact.
- Intended target not at hitpoint: reject.
- Multiple non-attacker actors match hitpoint: reject as ambiguous.
- Native hit but no qualified solver response: reject as non-product contact.
- No threshold weakening, no forced velocity, no teleport, no hidden keyframe, no asset-name branch.

## Candidate strategy

Candidate 4.1 / ISS-G05 is isolated from Candidate 4.0. It reuses the exact G04 controller unchanged and replaces only the OBB-triggered contact authority with the native actual-step sensor contract above. Acceptance must run unchanged runtime code against both the exact Bugatti pair and the generic-hypercar regression fixture.

G05 PASS is not Battle Runtime completion. Damage/persistent-state, dramatic progression, camera and final viewer-believability gates remain downstream.
