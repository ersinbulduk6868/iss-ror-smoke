# ISS-G07 Scope Correction — ISS-R042

## Decision

Candidate 4.4.1 produced a successful GitHub Actions run, but that run is **not accepted as G07 closure** because the acceptance contract still required an opening persistent-damage threshold crossing. That created an indirect incentive to engineer a harder collision instead of letting the generic runtime autonomously realize battle contact.

G07 therefore remains **OPEN** until an asset-independent successor passes.

## Locked product rule

**ISS-R042 — Asset-independent autonomous collision realization**

For every supported vehicle battle:

- Story/G07 expresses battle intent and causal state only: attack, counterattack, escalation, reversal, climax, payoff;
- G04 remains the generic closed-loop motion/approach/replan authority;
- G05 remains the generic native physical contact authority;
- G06 consumes naturally realized contact for damage/persistence when its unchanged criteria are met;
- G07 must not calculate or prescribe collision mechanics per vehicle.

Forbidden G07/Story inputs or implementation shortcuts include:

- collision frame;
- contact frame;
- impact speed target;
- Joule/energy target;
- trajectory/path/waypoints;
- world-space collision coordinates;
- steering angle or braking point;
- per-asset approach vector;
- hard-coded contact zone required to make a fixture pass;
- asset-name or video-specific collision branch;
- damage-threshold tuning used to manufacture drama progression.

## Correct G07 authority

G07 dramatic progression is earned from unique direct G05 VERIFIED native physical transactions and causal event history.

- Opening escalation is earned by a direct G05 VERIFIED physical aggression transaction.
- Counterattack becomes eligible only after the counterattacker was previously the target of a direct G05 VERIFIED aggression transaction by the intended opponent.
- A later direct G05 VERIFIED counter transaction reverses initiative.
- Climax becomes eligible only after physical reversal and must earn another later direct G05 VERIFIED physical transaction.
- Payoff follows the causal climax.

Damage is **not** a G07 collision-planning input or gate. If a naturally realized contact crosses the unchanged G06 threshold, G06 records and persists the consequence. If it does not, G07 still judges physical initiative from G05 native solver truth.

G06 remains independently MACHINE_PROVEN and its source/threshold must remain unchanged.

## Candidate 4.4.1 status

Run `35021169344` is retained as historical machine evidence that Candidate 4.4.1 can execute its own contract. It is **SUPERSEDED_FOR_G07_SCOPE** because its acceptance still required opening persistent damage and therefore did not satisfy ISS-R042.

No G04/G05/G06 PASS is revoked.

## Clean successor

Candidate 4.4.2 must satisfy all of the following with the same runtime source across exact Bugatti and generic-hypercar fixtures:

1. Story fixtures contain actor-level intent only; no target zone, speed intent, impact target, collision coordinates or trajectory points.
2. G04 autonomously computes approach/steer/throttle/brake/replan from live observations and ActorProfile/geometry.
3. G05 alone proves native contact.
4. G07 causal transitions use direct G05 VERIFIED physical transactions and prior-aggression history, not damage threshold crossings.
5. G06 source is byte-identical to the MACHINE_PROVEN predecessor and remains separately preserved.
6. No pose/velocity injection, reset, teleport, forced winner or proxy contact authority.
7. ISS-R041 and ISS-R042 both report SCOPE PRESERVED before G07 may close.

## Scope result

Candidate 4.4.1 post-run scope result: **SCOPE DRIFT DETECTED**.

Required correction: Candidate 4.4.2 asset-independent autonomous collision realization.
