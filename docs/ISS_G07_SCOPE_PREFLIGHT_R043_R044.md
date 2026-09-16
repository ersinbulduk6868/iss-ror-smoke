# ISS-G07 Scope Pre-Flight — R043 / R044

## Gate

**ISS-G07 — Battle State Machine + Dramatic Causal Progression**

## Authoritative project scope reread

This pre-flight is governed by the current ISS Engineering Memory plus the current Master Project Documentation baseline and the later live-machine reconciliation.

The project product invariant remains:

**Idea + any supported vehicle set -> the same Battle Runtime source -> asset/profile + Story intent vary -> runtime realizes the physical battle -> different battle behavior -> different video.**

G04, G05 and G06 are preserved MACHINE_PROVEN dependencies and are not G07 engineering surfaces.

## G07 allowed scope

G07 may:

- admit or block battle events according to realized causal state;
- model escalation, counterattack, reversal/comeback, climax and payoff;
- consume G04 autonomy state as read-only orchestration evidence;
- consume G05 VERIFIED native-contact receipts as physical truth;
- consume G06 persistent damage/state as causal context;
- hold an event in an orchestration state such as `AWAITING_G05_PHYSICAL_RECEIPT` while the already-existing G05 receipt window is pending;
- choose no new G07 goal during that receipt-pending state, allowing the unchanged G04 no-goal behavior to apply naturally.

## Forbidden scope

G07 must not:

- change G04 controller source or control law;
- issue direct motor, steering, brake, coast, force, impulse, pose or velocity commands;
- write G05 cutoff-frame/contact-authority state;
- change G05 solver windows, contact thresholds, semantic thresholds or native-contact authority;
- change G06 damage thresholds, damage magnitude, persistence or consequence logic;
- add per-asset collision engineering;
- add hard-coded vehicle names, semantic zones, collision points, speeds, Joules, frames, trajectories or winners;
- make a fixture pass by changing Story collision choreography.

## Candidate disposition

Candidate 4.4.4 is **SUPERSEDED BEFORE MACHINE TEST BY SCOPE PRE-FLIGHT** because its source directly calls `actor.rig.coast()` and writes G05 `_cutoff_frames`. Those operations cross the G07 boundary into preserved G04/G05 behavior.

Candidate 4.4.5 is the scope-correct successor. It may only manage G07 event admission. It reads the existing G04 `CONTACT_HANDOFF` state and existing G05 `SOLVER_WINDOW_MAX_FRAMES`; during that window it admits no new G07 goal. It does not directly control the vehicle and does not write G05/G06 authority state.

## Mandatory acceptance sandwich

Under ISS-R043 and ISS-R044:

1. this scope pre-flight must PASS before engineering/test;
2. machine acceptance alone is insufficient;
3. after machine acceptance, project scope must be reread and a SCOPE POST-FLIGHT report must be presented to the user;
4. G07 remains OPEN until the user explicitly answers **OK** to the post-flight report.

**SCOPE PRE-FLIGHT RESULT: PASS**
