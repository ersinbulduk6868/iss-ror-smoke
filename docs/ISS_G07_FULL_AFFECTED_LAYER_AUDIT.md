# ISS-G07 Full Affected-Layer Audit

## Gate

**ISS-G07 — Battle State Machine + Dramatic Causal Progression**

Entry truth is MACHINE_PROVEN through G06. G07 is OPEN and is not a user LOCK. This audit does not unlock or mutate any existing LOCK.

## Preserved project assets

The successor must preserve all of the following without source modification or acceptance weakening:

- frozen 9-service ISS production architecture; Merge Service remains independent;
- G04 closed-loop autonomy MACHINE_PROVEN PASS (`9de0055d6e060b96a981a4838236f056d6b7ea09`, run `34972872527`);
- G05 native pairwise contact truth MACHINE_PROVEN PASS (`b4e4b3ee58e023585e395c57d4bab966b8c2db86`, run `34996856866`);
- G05 contact authority `RECIPROCAL_NATIVE_SOLVER_RESPONSE_V1` and outer authority `PAIRWISE_CONTACT_OUTER_AUTHORITY_V1`;
- G06 causal damage / deformation / debris / persistent state MACHINE_PROVEN PASS (`409eaa1c2714600468f5fe9e3beae7c77f363317`, run `35008259169`);
- G06 persistence model `CAUSAL_DAMAGE_PERSISTENT_STATE_V1`;
- `MIN_DAMAGE_SEVERITY = 0.055`;
- no actor pose injection, velocity injection, teleport, reset, forced winner, forced joint release, trajectory choreography or exact collision/impact targets;
- exact source asset identity and the same generic-runtime asset/semantic path;
- viewer-visible causal product truth and continuous-world requirements.

## Machine-evidence baseline

G06 proved that:

1. real G05-verified physical transactions can earn damage;
2. damage changes `structural_integrity` / `drive_efficiency` and remains persistent;
3. deformation and debris persist in the same world;
4. a later event actually consumes reduced capability through the G04 controller;
5. both exact Bugatti and identical-source generic-hypercar fixtures pass the same Candidate 4.3 runtime source;
6. no G07 drama claim was made.

This is the exact boundary from which G07 must advance.

## Current implementation audit

### Battle compiler and event contract

`RuntimeEvent` already carries Story/Battle intent fields including `type`, `phase`, `attackers`, `target`, dependencies, tactic, speed intent, damage requirements and required outcome. `BattleCompiler` already enforces continuous-world and no-reset/no-teleport/no-silent-simplification/no-forced-transform/no-velocity-injection policy.

**Conclusion:** G07 does not need a new Story schema or a production-service redesign.

### BattleLifecycle

Current `BattleLifecycle` proves physical and causal resolution at the event level:

- qualified contact count;
- distinct qualified attackers;
- damage earned;
- dependency readiness;
- event requirements met.

It does **not** model dramatic battle state, actor dominance, comeback/reversal, state-driven counterattack eligibility, climax readiness or payoff readiness.

### G04 goal selection / autonomy

Candidate 4.0 chooses an active goal using:

- event `start_frame`;
- dependency readiness;
- a static phase priority;
- terminal event state.

The controller itself is closed-loop and consumes realized geometry/velocity/damage capability. This is correct and must remain unchanged.

**Gap:** goal *eligibility* is still primarily planned-time/dependency driven. A `COUNTERATTACK` label does not by itself prove that the actor is physically responding to damage received from the target.

### G05 contact authority

Candidate 4.2 supplies the accepted native pairwise physical transaction authority. It is the only admissible authority for G07 combat-state transitions that depend on contact/damage.

**Constraint:** G07 may observe G05 receipts but must not replace, bypass, lower or reinterpret the G05 contact gate.

### G06 persistence

Candidate 4.3 binds verified G05 receipts to persistent actor damage state and proves that a later controller invocation consumes degraded capability.

**Gap:** this state is observable but there is no battle-level state machine that turns it into causal dramatic transitions.

### OutcomeResolver

Current outcome resolution ranks final actors from disabled/structural/drive state and reports incomplete events. It does not prove that the path to the outcome contained escalation, counterattack, reversal/comeback and climax/payoff.

## Root capability gap

**G07_CAUSAL_DRAMA_STATE_MACHINE_MISSING**

The runtime has physical truth and persistent consequences, but no authoritative battle-state layer that converts verified physical events into eligibility for later dramatic goals.

This is a capability gap, not a G04/G05/G06 defect.

## Failure family / adjacent risks

The full affected failure family includes:

- phase labels being mistaken for realized drama;
- counterattack starting only because its planned time arrived;
- comeback/reversal being declared without a physical change in battle initiative/dominance;
- climax starting before reversal is physically earned;
- payoff settling without a resolved climax;
- outcome being forced to match Story prose rather than resolved from final physical state;
- duplicate/coalesced G05 receipts inflating dominance evidence;
- mirrored damage being counted as a second independent physical transaction;
- state-machine gates accidentally modifying physics thresholds or controller commands;
- camera dominance selecting an event that the causal state machine has not admitted;
- G07 fixture-specific actor IDs, exact frames, exact energy or exact trajectories leaking into runtime code;
- regression of G04 autonomy, G05 contact authority or G06 persistent damage/debris;
- private-asset OIDC workflow scope omission for a new G07 acceptance workflow.

## Accepted engineering design

Create **Candidate 4.4 G07** as an additive successor wrapper around Candidate 4.3.

### Causal battle-state authority

Introduce a generic `PHYSICAL_CAUSAL_DRAMA_STATE_MACHINE_V1` that only consumes existing machine-authoritative runtime state:

- G05 VERIFIED direct physical transactions;
- damage actually earned through the unchanged G06 path;
- actor persistent structural/drive state;
- event causal/dependency state;
- Story/Battle phase/tactic intent as intent, never as proof.

It must never write actor pose, velocity, damage magnitude, contact truth or thresholds.

### State-driven eligibility

- `HOOK` / initial escalation may open from normal dependency readiness.
- `COUNTERATTACK` becomes eligible only when its attacker has already received G05/G06-backed damage from the intended target.
- a climax becomes eligible only after a real dominance reversal/comeback has been observed.
- payoff becomes eligible only after the climax is causally resolved.

Planned start/end windows remain Story guidance and minimum scheduling hints; they are not substitutes for physical guards.

### Dominance / comeback evidence

Dominance is not a scripted winner flag. It is derived from **unique direct G05 physical transactions that earned damage**. Mirrored damage and inherited reciprocal aliases do not create independent dominance pressure.

The first actor to establish unique direct verified damage pressure becomes the initial physical initiative leader. A comeback/reversal is observed only when an actor that was previously damaged by that leader later earns enough unique direct verified damage pressure to overtake the initial leader. The state machine records the before/after scores and physical receipts. No actor is moved or strengthened to make the reversal happen; if physics does not earn it, G07 fails.

### Lifecycle integration

Candidate 4.4 may gate event activation/completion and camera event eligibility, but it must reuse the existing G04 controller, G05 resolver and G06 persistence path unchanged.

For a counterattack, meeting the base contact/damage count is not enough to terminate the goal if the required physical reversal has not yet emerged; the same autonomous goal may continue/replan within the continuous run. This is state-driven replanning, not forced choreography.

### Outcome

The existing final physical actor-state ranking remains authoritative. G07 adds evidence that the required dramatic causal chain occurred; it does not set the winner.

## Acceptance design

One Candidate 4.4 workflow must perform:

1. zero-cost syntax/property/no-cheating checks;
2. exact private full-source Bugatti identity acquisition;
3. Candidate 3.9 asset/semantic regression;
4. exact Bugatti Candidate 4.4 run on Blender 4.5.13;
5. identical-source generic-hypercar Candidate 4.4 run using the same runtime source;
6. strict machine-result validation that preserves G04/G05/G06 and proves:
   - continuous world;
   - G05 VERIFIED direct physical transactions;
   - G06 persistent damage/debris;
   - state-driven counterattack eligibility from prior damage;
   - escalation evidence;
   - physical dominance reversal/comeback evidence;
   - climax activation after reversal;
   - payoff after climax;
   - final causal outcome with no forced winner;
   - no pose/velocity/reset/threshold/choreography cheating;
7. artifact upload with logs and JSON evidence.

The machine validator must fail closed. It must not convert missing reversal/climax/payoff evidence into warnings.

## Known infrastructure preflight

Before the first real G07 workflow run, extend the existing private-asset helper OIDC allowlist with **only** the exact Candidate 4.4 G07 workflow reference. Preserve all existing issuer, audience, repository, branch/ref, runner, time and RSA signature checks. This prevents recurrence of the already-engineered G06 pre-runtime scope failure without weakening security.

## Exit decision

This audit supports creating exactly one clean Candidate 4.4 G07 successor. No locked production service or prior MACHINE_PROVEN runtime source requires redesign.
