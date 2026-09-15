# ISS-G07 Failure-Family Audit — Run 35019926790

## Authority and preservation boundary

This audit follows the first real Candidate 4.4 G07 runtime failure. It does not unlock or redesign G04, G05, G06, the frozen 9-service architecture, RC3.4, RC1.9, or ISS-R041.

Preserved MACHINE_PROVEN assets:

- G04 closed-loop autonomy;
- G05 `RECIPROCAL_NATIVE_SOLVER_RESPONSE_V1` + `PAIRWISE_CONTACT_OUTER_AUTHORITY_V1`;
- G06 `CAUSAL_DAMAGE_PERSISTENT_STATE_V1` and unchanged `MIN_DAMAGE_SEVERITY = 0.055`;
- no pose/velocity injection, teleport/reset, forced winner, exact collision frame, exact impact speed/Joule target or manual trajectory;
- same Battle Runtime source across supported vehicle fixtures.

## Machine evidence from run 35019926790

Before Candidate 4.4 G07 execution, all of these passed in the same workflow:

- zero-cost property/no-cheating validation;
- exact private Bugatti OIDC access and exact source identity;
- Blender 4.5.13 pin;
- Candidate 3.9 asset/semantic regression;
- Candidate 4.3 exact-Bugatti G06 runtime;
- Candidate 4.3 generic-hypercar G06 runtime;
- strict Candidate 4.3 G06 machine acceptance.

Candidate 4.4 exact-Bugatti G07 then produced a real G05 VERIFIED direct native physical transaction at frame 37:

- severity: `0.05449746606777284`;
- unchanged G06 damage threshold: `0.055`;
- `damageEarned=false`;
- G07 escalation remained incomplete;
- counterattack, climax and payoff remained dependency-blocked;
- terminal base failure: `persistentDebrisMaterialized,allRequiredEventsSucceeded`.

This is real runtime evidence, not a harness failure.

## Root failure family

`G07_DRAMA_OVERCOUPLED_TO_REPEATED_DAMAGE_GATE`

Candidate 4.4 conflated two different physical truths:

1. **persistent consequence truth** — whether a G05 contact crossed the unchanged G06 threshold and earned visible/persistent damage; and
2. **battle initiative truth** — whether a later attack/counter/climax produced a unique direct G05 VERIFIED physical transaction with real solver response.

G07 incorrectly required `damageEarned=true` before *every* dramatic initiative transition could advance. That makes a story-state gate depend on repeatedly crossing a deformation threshold and creates pressure toward forbidden impact-energy/speed/threshold tuning.

## Complete affected failure family

The successor must prevent all of the following:

- lowering `MIN_DAMAGE_SEVERITY` merely to pass G07;
- tuning exact impact speed/Joule/contact frame;
- treating any OBB/proxy overlap as physical initiative;
- treating mirrored/inherited reciprocal aliases as a new initiative transaction;
- declaring counterattack before the actor has prior G05/G06-backed damage from the intended target;
- declaring reversal from a label/timestamp instead of a later direct G05 VERIFIED transaction;
- declaring climax before reversal;
- forcing a winner;
- making every dramatic beat require new visible damage even when the native physical counter/contact is real;
- making the opening target passive merely to fit a one-sided test setup when the product concept is an actual conflict with opposing objectives;
- adding asset/video-specific source branches.

## Engineering correction

The clean successor is Candidate 4.4.1.

### Opening escalation

Opening escalation must still prove the G06 consequence chain: at least one direct G05 VERIFIED transaction must actually earn persistent damage/deformation/debris. The acceptance Story fixture expresses a **mutual opposing escalation**: both actors have explicit opposing attack intent in the same window. This is Story intent, not numeric physics choreography, and it is applied identically to exact Bugatti and generic-hypercar fixtures.

### Later battle initiative

After the persistent-damage opening, battle initiative uses:

`LATEST_UNIQUE_DIRECT_G05_PHYSICAL_INITIATIVE_V2`

A later initiative transaction must be:

- direct, not inherited reciprocal alias;
- G05 native-contact authority true;
- G05 receipt `VERIFIED` under `RECIPROCAL_NATIVE_SOLVER_RESPONSE_V1`;
- unique by physical transaction/event + contact frame + attacker + target;
- causally eligible for its phase.

Counterattack additionally requires the attacker to carry prior G05/G06-backed damage from the intended target. A qualifying direct counterattack transaction may reverse physical initiative even if it does not cross the separate G06 deformation threshold. Climax similarly requires the reversal to exist and then must earn its own direct G05 VERIFIED physical transaction. Payoff remains dependent on climax.

This separates **real physical attack authority** from **visible deformation threshold** without weakening either.

## Why this is not test tuning

The correction introduces no asset names into runtime source, no collision frame, no target speed, no Joule value, no trajectory, no threshold change and no winner. Exact Bugatti and generic hypercar use the same runtime source and same intent structure. Vehicle-specific differences remain asset/profile data.

## Adjacent compatibility

- G04 remains the motion/controller authority and is not modified.
- G05 remains the sole contact authority and is not modified.
- G06 remains the sole damage/persistence authority and is not modified.
- G07 only observes verified G05 receipts + G06 actor state and gates lifecycle/initiative transitions.
- Camera remains downstream; G07 does not fake visual evidence.
- Final outcome remains physical-state-derived.

## Acceptance requirements for Candidate 4.4.1

The workflow must fail closed unless both exact Bugatti and generic hypercar, with identical Candidate 4.4.1 runtime source, prove:

- full G06 regression remains PASS;
- opening persistent damage/debris exists under unchanged G06 threshold;
- prior damaged state is consumed by later control;
- unique direct G05 VERIFIED counterattack occurs after prior damage;
- initiative reverses to the counterattacker;
- climax activates only after reversal and earns a later direct G05 VERIFIED transaction;
- payoff activates only after climax;
- all required events resolve;
- no cheating/proxy authority/asset-specific battle code;
- `productionReadyClaimed=false`.

## ISS-R041 scope audit

Pre-test result: **SCOPE PRESERVED**.

The successor remains: idea + supported vehicle set → same Battle Runtime source → asset/profile + Story intent vary → physically different battle/video. Final scope status still requires terminal machine acceptance.
