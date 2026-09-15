# ISS-G05 Native Contact Truth / No-Cheating — full affected-layer audit

Status: OPEN engineering gate. This document does not lock G05 and does not claim production readiness.

## Preserved machine-proven state

- ISS-G04 Candidate 4.0 remains the known-good closed-loop autonomy baseline; its source is preserved unchanged.
- Candidate 3.9 supported physical envelope and semantic surface projection remain unchanged.
- Candidate 3.7.1 surface-aware consequence hardening remains unchanged.
- Existing `ImpactModel`, damage threshold, semantic tolerance and no-cheating gates remain unchanged.
- No actor pose, transform, velocity injection, keyframed battle motion, target-energy forcing or exact collision-frame forcing is permitted.
- Frozen ISS nine-service boundaries are unaffected.

## Original failure family

The inherited contact pipeline starts a physical transaction from `obb_overlap_2d(...)` and only later correlates it with rigid-body response. Solver response is useful evidence, but OBB overlap is not final ISS-R039/R040 product authority. It cannot be relabeled as native contact truth.

## Investigation history and machine evidence

### Native API capability

Run `34981399858` on exact Blender 4.5.13 proved `RigidBodyWorld.convex_sweep_test` exists and works after the rigid-body world is stepped. Positive, near-miss and empty-path controls behaved correctly in a simple two-body world. This established API capability only.

### Candidate 4.1 integration failure

Candidate 4.1 used only the actor's actual previous solver position to actual current solver position and prohibited predictive extension. On the exact Bugatti runtime it produced native hits, but the first hits were contaminated by the complex DriveRig/environment and could not be uniquely attributed to the intended target. The candidate correctly rejected them and terminally failed rather than weakening target identity.

### DriveRig constrained-pair audit

The DriveRig contains four physical wheels, each connected to the chassis by hinge and motor constraints. Existing constraints leave `disable_collisions=False`. Blender documents this setting as controlling collision between constrained bodies.

A real Blender 4.5.13 comparison probe then set `disable_collisions=True` on all eight chassis-wheel constraints. The native sweep still returned an immediate own-rig/own-chassis-classified first hit. Therefore constrained-pair collision suppression is not sufficient to make `convex_sweep_test` a target-identifying sensor and is not accepted as the G05 solution.

### Blender API/source limitation

Blender's Python `RigidBodyWorld.convex_sweep_test` wrapper returns only sweep-object location, hitpoint, normal and hit flag. It does not expose the Bullet hit collision object identity. Blender's implementation creates Bullet `ClosestConvexResultCallback` and returns the closest result, so a complex multi-body rig can be blocked by a non-target first hit with no reliable Python-level object identity to disambiguate it.

**Audit conclusion:** forcing this API to become a pair-identifying production contact oracle would require filtering/proxy tricks that risk changing simulation state or manufacturing sensor geometry. That path is rejected for G05.

## Revised G05 authority contract — solver-produced pairwise physical response

A G05 contact transaction is valid only when all of the following hold:

1. The attacker is executing an ISS-G04 autonomous intent. No trajectory, impact energy, speed target for collision acceptance, or exact collision frame is executable input.
2. G04 controller authority has handed off before contact evidence is accepted; attacker motor authority is zero.
3. Evidence is sampled only from actual Blender-solved actor positions and velocities. No transform or velocity mutation is used by the sensor.
4. The attacker and intended target were physically closing before the response using the existing `ImpactModel` minimum closing-speed contract.
5. The two actors exhibit a same-window **reciprocal momentum response**: attacker impulse opposes target impulse, each impulse aligns with the pair collision normal in the physically correct direction, and both sides carry a non-trivial share of the transaction. This rejects ground friction, unilateral wall impacts and independent braking.
6. The pair's current authoritative chassis collision envelopes are locally adjacent within existing collision/locality numerical tolerance. Geometry is a locality/identity gate only; it is not the physical contact authority.
7. The inferred target-side contact point satisfies the existing semantic target-zone tolerance. No semantic threshold is weakened.
8. The same evidence still passes the existing `ImpactModel.qualifies` response gate.
9. In multi-actor scenes only the explicit story-intent attacker/target pair may satisfy that event; third-party response cannot be silently rebound to the requested target.
10. Damage remains downstream of contact. G05 does not require or manufacture damage; G06 remains responsible for damage/persistent-state acceptance.
11. Evidence records the solver window, pre/post velocities, reciprocal impulse metrics, locality, semantic distance, controller handoff, and no-cheating assertions.

## Negative-control family

The G05 pairwise oracle must reject:

- closing actors with only low rolling/friction deceleration;
- unilateral collision with a wall/environment;
- vertical/ground response presented as a horizontal actor collision;
- independent braking/motor action without controller handoff;
- pair response while the intended target is not locally adjacent;
- semantic-zone mismatch;
- third-actor response rebound to the wrong story target.

It must accept physically consistent reciprocal responses across materially different actor masses.

## Candidate strategy

Candidate 4.2 is isolated from Candidate 4.0. It reuses the exact G04 controller and Candidate 3.9 asset/semantic code unchanged. It replaces only final contact authority with the pairwise native solver-response oracle above. The same Candidate 4.2 source must pass exact Bugatti and generic-hypercar fixtures without asset-name branches or per-fixture constants.

G05 PASS is not Battle Runtime completion. G06 damage/persistent state, later dramatic progression, camera, visual believability and final production E2E remain downstream.

## Candidate 4.2 execution record — 2026-09-15

- Run `34996513316` failed before runtime because a static validator incorrectly required imported model constants to appear as literal strings in Candidate 4.2 source. Runtime was not executed; this is harness evidence, not a product failure.
- Run `34996597786` passed the corrected property, preservation, no-cheating and negative-control suite. It then failed before asset acquisition because the existing private-storage Edge Function OIDC allowlist did not yet include `.github/workflows/generic-battle-runtime-v1-candidate42-g05.yml`. Runtime was again not executed; this is transport authorization drift, not G05 physics evidence.
- The private bucket policy remains unchanged. Edge Function `iss-final-video-transfer-once` version 12 adds only the exact Candidate 4.2 workflow/ref tuple to the existing GitHub OIDC allowlist. No broad repository authorization, public bucket access, threshold change, controller change or battle-runtime workaround was introduced.
- Candidate 4.2 must now be re-run from the same machine acceptance workflow. G05 remains OPEN until exact Bugatti and generic hypercar both reach terminal machine acceptance with the same Candidate 4.2 source.
