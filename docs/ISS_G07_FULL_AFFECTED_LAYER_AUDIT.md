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
- viewer-visible causal product truth and continuous-world requirements;
- ISS-R041 generic multi-vehicle scope: one Battle Runtime source across supported vehicle sets; asset/profile + Story intent may vary, battle source code may not.

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

Current `BattleLifecycle` proves physical and causal resolution at the event level through qualified contacts, distinct qualified attackers, damage earned, dependency readiness and event requirements. It does not model dramatic battle state, comeback/reversal, state-driven counterattack eligibility, climax readiness or payoff readiness.

### G04 goal selection / autonomy

Candidate 4.0 chooses an active goal using event timing, dependency readiness, phase priority and terminal state. The controller itself is closed-loop and consumes realized geometry/velocity/damage capability. This is correct and must remain unchanged.

**Gap:** a `COUNTERATTACK` label or planned time is not evidence that the actor is physically responding to prior damage.

### G05 contact authority

Candidate 4.2 supplies the accepted native pairwise physical transaction authority. It is the only admissible authority for G07 combat-state transitions that depend on contact/damage.

**Constraint:** G07 may observe G05 receipts but must not replace, bypass, lower or reinterpret the G05 contact gate.

### G06 persistence

Candidate 4.3 binds verified G05 receipts to persistent actor damage state and proves a later controller invocation consumes degraded capability.

**Gap:** this state is observable but there is no battle-level state machine that turns it into causal dramatic transitions.

### OutcomeResolver

Current outcome resolution ranks final actors from disabled/structural/drive state and reports incomplete events. It does not prove that the path to the outcome contained escalation, counterattack, reversal/comeback and climax/payoff.

## Root capability gap

**G07_CAUSAL_DRAMA_STATE_MACHINE_MISSING**

The runtime has physical truth and persistent consequences, but no authoritative battle-state layer that converts verified physical events into eligibility for later dramatic goals.

This is a capability gap, not a G04/G05/G06 defect.

## Failure family / adjacent risks

The affected failure family includes:

- phase labels being mistaken for realized drama;
- counterattack starting only because planned time arrived;
- comeback/reversal being declared without a physical change in initiative;
- requiring artificial repeated hits merely to manufacture a numeric dominance score;
- climax starting before reversal is physically earned;
- payoff settling without a resolved climax;
- outcome being forced to match Story prose rather than final physical state;
- duplicate/coalesced G05 receipts inflating initiative evidence;
- mirrored damage being counted as a second independent physical transaction;
- state-machine gates accidentally modifying physics thresholds or controller commands;
- camera selecting an event that the causal state machine has not admitted;
- fixture-specific actor IDs, exact frames, exact energy or exact trajectories leaking into runtime source;
- regression of G04 autonomy, G05 contact authority or G06 persistent damage/debris;
- private-asset OIDC workflow scope omission for the G07 acceptance workflow.

## Accepted engineering design

Create **Candidate 4.4 G07** as an additive successor wrapper around Candidate 4.3.

### Causal battle-state authority

Introduce `PHYSICAL_CAUSAL_DRAMA_STATE_MACHINE_V1`, consuming only:

- G05 VERIFIED direct physical transactions;
- damage actually earned through unchanged G06 consequence logic;
- persistent actor structural/drive state;
- event causal/dependency state;
- Story/Battle phase/tactic intent as intent, never as proof.

It must never write actor pose, velocity, contact truth, damage magnitude or thresholds.

### State-driven eligibility

- `HOOK` / initial escalation may open from normal dependency readiness.
- `COUNTERATTACK` becomes eligible only when its attacker already carries G05/G06-backed damage from the intended target.
- climax becomes eligible only after a real physical initiative reversal/comeback.
- payoff becomes eligible only after the climax is causally resolved.

Planned start/end windows remain Story guidance, not physical proof or exact execution deadlines.

### Dominance / comeback authority — final reconciled contract

The authoritative G07 model is **`LATEST_UNIQUE_DIRECT_G05_DAMAGE_INITIATIVE_V1`**.

This intentionally does **not** require cumulative multi-hit score overtaking. G04 is a goal-driven controller; after a successful damage event it is not required to manufacture repeated extra hits simply to satisfy a drama score. Requiring repeated score accumulation would turn the acceptance into test-driven choreography.

The physical initiative rules are:

1. Only a **unique direct G05 VERIFIED physical transaction that actually earns damage** can establish or change initiative.
2. Mirrored damage rows and inherited reciprocal aliases never create independent initiative.
3. The first such direct damage transaction establishes the initial physical initiative actor.
4. A later actor earns a genuine reversal/comeback when:
   - that actor previously received G05/G06-backed damage from the initial initiative actor; and
   - it later earns its own unique direct G05 VERIFIED damage transaction against that actor.
5. The latest qualifying direct damage transaction is the initiative authority. No cumulative severity threshold, repeated-hit quota, asset-specific score or scripted winner is required.
6. The state machine records the before/after initiative evidence and exact physical receipt provenance. If physics does not earn the counter-hit, G07 fails.

This models the generic causal relation “you physically damaged me → I later physically counter-damaged you → initiative reversed” without vehicle-specific choreography.

### Lifecycle integration

Candidate 4.4 may gate event activation/completion and camera event eligibility, but it must reuse the existing G04 controller, G05 resolver and G06 persistence path unchanged.

For a counterattack, base contact/damage counts are insufficient unless the prior-damage guard and physical reversal evidence exist. The autonomous goal may continue/replan within the continuous run. This is state-driven control, not forced choreography.

### Outcome

The existing final physical actor-state ranking remains authoritative. G07 adds evidence that the required dramatic causal chain occurred; it does not set the winner.

## Acceptance design

One Candidate 4.4 workflow must perform:

1. zero-cost syntax/property/no-cheating checks;
2. exact private full-source Bugatti identity acquisition;
3. Candidate 3.9 asset/semantic regression;
4. preserved Candidate 4.3 G06 regression where practical, using the unchanged G06 source and acceptance validator;
5. exact Bugatti Candidate 4.4 run on Blender 4.5.13;
6. identical-source generic-hypercar Candidate 4.4 run using the same Candidate 4.4 runtime source;
7. strict machine-result validation proving:
   - continuous world;
   - G05 VERIFIED direct physical transactions;
   - G06 persistent damage/debris and degraded capability consumption;
   - state-driven counterattack eligibility from prior damage;
   - escalation evidence;
   - `LATEST_UNIQUE_DIRECT_G05_DAMAGE_INITIATIVE_V1` reversal/comeback evidence;
   - climax activation after reversal;
   - payoff after climax;
   - final causal outcome with no forced winner;
   - no pose/velocity/reset/threshold/choreography cheating;
8. artifact upload with logs and JSON evidence.

The machine validator must fail closed. Missing reversal/climax/payoff evidence is a failure, not a warning.

## Known infrastructure preflight

Before the first real G07 workflow run, extend the private-asset helper OIDC allowlist with **only** the exact Candidate 4.4 G07 workflow reference. Preserve all existing issuer, audience, repository, branch/ref, runner, time and RSA signature checks.

## ISS-R041 scope preflight

Candidate 4.4 design remains within locked project scope:

- one runtime source for both acceptance fixtures;
- no vehicle-name branch in runtime;
- fixture actor IDs exist only in request/test data, not battle-engine source;
- no exact collision frame, impact energy, trajectory or winner target;
- asset identity/profile differences remain data;
- Story remains intent/dependency input;
- physical events remain Blender/G05/G06 authority.

**Pre-acceptance scope status: SCOPE PRESERVED.** Final post-Gate scope status still requires terminal machine acceptance evidence.

## Exit decision

This audit supports exactly one clean Candidate 4.4 G07 successor. No locked production service or prior MACHINE_PROVEN runtime source requires redesign.
