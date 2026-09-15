# ISS-G05 — Native Contact Truth / No-Cheating Full Affected-Layer Audit

Date: 2026-09-15
Baseline branch: `iss-engineering/generic-battle-runtime-v1`
Baseline commit entering G05: `9de0055d6e060b96a981a4838236f056d6b7ea09`
Preserved predecessor: `ISS-G04 MACHINE_PROVEN PASS`, Candidate 4.0, run `34972872527`
Gate: `ISS-G05 — Native Contact Truth / No-Cheating`
Status at audit start: `OPEN_ACTIVE_ENGINEERING`

## LOCK pre-flight

Preserve without modification:

- frozen 9-service architecture and independent Merge Service boundary;
- RC3.4 Production Asset Runtime Binding lock;
- RC1.9 Real Production Battle Integration lock;
- G04 Candidate 4.0 autonomous controller/replanner PASS evidence;
- Candidate 3.9 supported physical envelope and semantic-surface binding;
- Candidate 3.7.1 surface-aware consequence realization;
- ISS-R007/008/009 no pose/velocity/teleport cheating;
- ISS-R039/R040 product-truth acceptance;
- existing damage/contact thresholds unless a separate evidence-backed correctness defect is proven.

No downstream gate, production readiness, or generic-runtime lock is implied by this audit.

## Current contact path audited

The current runtime contact path is not acceptable as final G05 product truth:

1. `iss_blender_battle_runtime_v1.detect_contacts()` first requires `obb_overlap_2d(attacker, target)`.
2. It derives an approximate normal from actor center-to-center direction.
3. It derives a contact point from a support-point helper against the hidden physics chassis.
4. It checks semantic-zone distance.
5. The hardened layer additionally requires controller motor authority to have been relinquished recently.
6. Two frames later it requires a solver-correlated velocity-response delta before qualifying an impact.

This is materially stronger than a scripted collision, but OBB overlap is still the initiating contact detector. A proxy/OBB predicate therefore remains capable of creating the pending physical transaction. Under ISS-R039/R040, that is insufficient for final native-contact authority.

## Blender 4.5 API capability finding

The Blender Python `RigidBodyWorld` API exposes `convex_sweep_test(object, start, end)` against the current rigid-body world and returns object location, hit point, hit normal and a native `has_hit` result. The public Python API does not expose a rigid-body contact-manifold collection/callback through `RigidBodyWorld` or `PointCache`.

Therefore the justified machine-probe path is:

- first prove on exact Blender 4.5.13 that `RigidBodyWorld.convex_sweep_test` produces a positive hit and correct negative control without self-hit contamination;
- only if that exact probe passes, integrate it as native rigid-body-world collision evidence;
- combine native rigid-body-world hit evidence with actual post-solver velocity/angular-response evidence and controller-authority handoff;
- OBB may remain only as a broad-phase optimization/diagnostic and may never be sufficient to increment contact count or earn damage.

If the exact 4.5.13 native sweep probe fails or proves unsuitable for moving-world contact truth, do not rename proxy evidence as native. G05 must remain open and another native evidence source must be engineered.

## Required G05 evidence contract

A contact can become product-authoritative only if all of the following are true:

1. Correct event attacker and target are active and semantically resolved.
2. Controller motor authority is relinquished before solver response when the G04 handoff mode is used.
3. A Blender rigid-body-world native collision query reports a hit associated with the actual swept motion interval, or an equivalent stronger Blender-native evidence source is proven.
4. The native hit point is consistent with the intended target semantic region.
5. Actual solver response is observed after the native hit: nontrivial actor response delta and/or angular response, not a scripted value.
6. Contact evidence is bound to the real frame interval and persisted in the evidence receipt.
7. Damage is impossible without this G05 contact receipt.

## Negative controls required

G05 cannot PASS from a positive collision alone. The acceptance suite must also prove:

- near miss: OBB/proximity may be close but native query reports no hit, therefore no contact count and no damage;
- proxy false positive: broad-phase overlap alone cannot create a contact receipt;
- motor-authority violation: a would-be hit while controller is still driving through contact is rejected by the existing solver-ownership guard;
- wrong semantic zone: native hit at the wrong target area does not satisfy the event;
- no response: a native-query candidate without actual solver response cannot earn impact/damage;
- no-contact damage: direct consequence invocation is not an accepted runtime path without a G05 receipt.

## Exact runtime acceptance required

The same G05 sensor implementation must run without asset-specific source branches on:

- exact Bugatti pair;
- generic hypercar regression.

Both must preserve G04 autonomy markers and no-cheating evidence. G05 may close only if the final evidence receipt states the native detector model explicitly and the old OBB-only path cannot independently increment `contact_count` or trigger consequence.

## Forbidden fixes

- calling OBB overlap `native contact`;
- using pre-scripted contact frames or positions;
- hidden pose/velocity injection;
- threshold weakening to make a response qualify;
- using asset name/source UID to choose the contact algorithm;
- changing G04 control behavior merely to manufacture G05 contact evidence;
- claiming G06 damage acceptance or production readiness from a G05 PASS.

## Audit conclusion

`G05_FULL_AFFECTED_LAYER_AUDIT = PASS_FOR_NATIVE_API_PROBE`

Next justified action: exact Blender 4.5.13 machine probe of `RigidBodyWorld.convex_sweep_test` with positive and negative controls. Runtime integration is forbidden until that probe establishes the API behavior needed by G05.