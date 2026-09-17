# ISS Generic Autonomous Battle — C460 Full Affected-Layer Audit

Date: 2026-09-17
Scope: G04 → G08 Generic Autonomous Battle Mechanism
Status: AUDIT PASS FOR CLEAN SUCCESSOR PREPARATION; NO REAL ACCEPTANCE RUN AUTHORIZED BY THIS DOCUMENT

## Trigger

The C460 real-acceptance family reached the permanent three-iteration stop condition. No additional real Blender acceptance is allowed until the affected layer is audited and a clean successor passes static/property preflight.

## Preserved authorities

- Frozen nine-service ISS architecture: unchanged.
- G01–G03: unchanged.
- G05 native contact authority remains `RECIPROCAL_NATIVE_SOLVER_RESPONSE_V1`.
- Existing G05 contact thresholds: unchanged.
- Existing G06 damage-admission threshold: unchanged.
- G07 remains drama/lifecycle authority, not motion/contact authority.
- G08 remains observability/camera authority, not physics authority.
- No asset-name branch, fixed world coordinate, exact collision frame, exact impact energy, pose injection, velocity injection, forced winner, or state reset is permitted.

## Machine-observed failure family

1. C460 established a generic live-state tactical layer and proved its property/static suite.
2. Real Blender evidence showed exact Bugatti and generic hypercar could both execute the runtime, but cross-gate behavior diverged after physical contact.
3. Generic-hypercar evidence exposed reverse steering and timer-only post-contact re-engagement defects. Those were corrected by reverse-axis heading and geometry-confirmed separation.
4. Subsequent strict cross-gate evidence showed exact Bugatti completed required physical events but did not emit the required `REPOSITION` tactical mode, while the generic hypercar did.
5. The cause was not a G05 threshold failure and not a G06 visual-damage threshold failure. A native contact may be G05-qualified while `damageEarned=false`; contact truth still exists and must drive battle tactics.

## Root cause

The tactical adapter read `states[current_event.event_id].contact_count` and `damage_count` as if those counters represented continuous battle history. They are event-scoped by contract.

A verified physical contact in one semantic event can therefore disappear from the tactical observation when the next semantic event becomes active. This is especially important when an actor was the **target** of an earlier event and only later becomes an **attacker** (for example a counterattack): G07's active-goal resolver supplies motion goals only to event attackers, so that actor's tactical memory may be created only after the earlier contact has already occurred.

The current V2 tactical initializer then baselines non-zero counts on first observation and can silently forget that already-realized contact.

## G05 counting semantics verified

The hardened resolver increments `EventState.contact_count` exactly when a contact passes the existing physical impact qualification gate. This increment occurs even when severity is below `MIN_DAMAGE_SEVERITY`, so verified contact truth survives without requiring damage.

Reciprocal story intents can be coalesced into one physical transaction and each reciprocal event state can receive its own contact signal. Therefore a tactical aggregate must be treated as a **monotonic actor-involvement signal**, not as a unique-physical-transaction counter.

## Correct successor contract

### Tactical history

For actor `A`, derive cumulative realized-contact and realized-damage signals only from events where:

- `A` is in `event.attackers`, or
- `A == event.target_id`.

Unrelated events between other actors must not contaminate A's tactical memory.

### First observation

If an actor's tactical memory is first created after an earlier actor-involved verified contact, that historical contact is actionable and must be observed as a new battle signal. It must not be swallowed as an initialization baseline.

### Separation/re-engagement

- A realized contact signal starts/continues the post-contact cycle.
- Reverse steering is evaluated against the reverse motion axis.
- Timer expiry alone cannot authorize re-engagement.
- Live geometry must confirm required surface separation before `REPOSITION`.
- Only after separation/reposition may a new `COUNTER`/engagement commit occur.

### Event-local autonomy remains event-local

The low-level closed-loop autonomy observation must continue to receive **current event** `contact_count`/`damage_count`. Historical contacts must not falsely satisfy a new event's contact handoff or lifecycle requirements.

This intentionally separates:

- tactical battle memory = actor-scoped continuous battle history;
- event autonomy/lifecycle = current-event state.

## Failure-family coverage required before next real run

The clean successor property/static suite must prove all of the following:

- prior verified contact with `damageEarned=false` is still remembered tactically;
- actor-as-attacker history is included;
- actor-as-target history is included;
- unrelated third/fourth-actor contacts are excluded;
- reciprocal event signals do not cause repeated cycle triggers when the aggregate has not advanced;
- first tactical observation after prior actor-involved contact triggers post-contact behavior;
- reverse heading is motion-direction aware;
- timer-only re-engagement is forbidden;
- geometry-confirmed separation is required;
- sports-car and heavy/tracked capability profiles use the same planner;
- damage disadvantage can cause evasion;
- braking-distance adaptation remains active;
- current-event autonomy counters remain event-scoped;
- no G05/G06 threshold change;
- no asset-specific or video-specific choreography.

## Adjacent regression risks audited

- Global battle contact summation is forbidden because it would make an actor react to unrelated collisions.
- G05 receipt/contact authority must remain read-only to the tactical layer.
- G06 consequence realization must not be used as a proxy for contact truth.
- Reciprocal contact signals may advance the monotonic actor history by more than one in a frame; transition detection must react to the increase once, not assume the aggregate equals a unique physical-contact count.
- Disabled actors must remain non-driving.
- Target changes across events must not reset actor battle memory.
- Asset capability differences may change timings, speeds, turning and separation distances, but must not select different algorithms.

## Clean successor

Next candidate: **4.6.1**.

C460 historical commits/runs remain provenance and are not reclassified as PASS. Candidate 4.6.1 must use new successor source/wrapper/validator identities. Only after the C461 static/property suite passes may one clean real Blender acceptance be started.
