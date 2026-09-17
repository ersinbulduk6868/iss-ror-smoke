# ISS-G07 Candidate 4.4.6 Scope Post-Flight

## Gate

**ISS-G07 — Battle State Machine + Dramatic Causal Progression**

Candidate: `ISS_GENERIC_BATTLE_RUNTIME_V1_CANDIDATE_4_4_6_G07`
Machine-acceptance source commit: `72b03f104c46f5d3f3ca03a6f6926354e2564aea`
GitHub Actions run: `35185021529`
Job: `105085111067`
Artifact: `10481816343`
Artifact SHA256: `a501414ec7bb4d49901b27e36222f48981510b0b8a67db30d46cf4295d261931`
Backend: `Blender 4.5.13 LTS`

## Authoritative scope reread

Post-flight was evaluated against the current ISS Engineering Memory / locked governance and `ISS Master Project Documentation — 2026-09-15 v1.1`, with later verified GitHub machine evidence treated as the live execution authority without rewriting historical documentation state.

Relevant hard constraints preserved:

- Frozen 9-service ISS architecture remains unchanged.
- `ISS-R041`: generic multi-vehicle runtime; Bugatti remains a fixture, not a product target.
- `ISS-R042`: collision realization remains asset-independent and runtime-selected from live world/geometry state; Story expresses actor-level battle intent only.
- `ISS-R043`: machine PASS requires scope pre-flight and scope post-flight.
- `ISS-R044`: G07 must remain OPEN until explicit user approval after the post-flight report.
- G04 autonomous control authority remains unchanged.
- G05 native pairwise contact authority remains unchanged.
- G06 causal persistent damage state remains unchanged.
- No pose/velocity injection, teleport/reset, forced winner, exact collision-frame target, exact impact-energy target, threshold weakening, or per-asset collision engineering is permitted.

## Machine evidence reviewed

The accepted run executed the exact Bugatti fixture and a generic hypercar fixture with the same Candidate 4.4.6 runtime source.

Exact Bugatti evidence:

- G05 VERIFIED escalation contact at frame 37.
- G05 VERIFIED counterattack contact at frame 146.
- Physical dominance reversal at frame 146.
- G06 persistent damage state recorded on both actors and consumed by later events.
- Causal climax activated at frame 331 and realized from prior reversal/persistent state at frame 332.
- Payoff resolved at frame 870.
- Runtime result `success=true`.

Generic hypercar evidence:

- G05 VERIFIED escalation contact at frame 39.
- G05 VERIFIED counterattack contact at frame 139.
- Physical dominance reversal at frame 139.
- G06 persistent damage state recorded on both actors and consumed by later events.
- Causal climax activated at frame 331 and realized from prior reversal/persistent state at frame 332.
- Payoff resolved at frame 870.
- Runtime result `success=true`.

Strict machine validator result:

- `GENERIC_BATTLE_RUNTIME_CANDIDATE446_G07_MACHINE_ACCEPTANCE`
- `status=PASS`
- `g07BattleStateMachineDramaticCausalProgression=true`
- `g04Preserved=true`
- `g05Preserved=true`
- `g06Preserved=true`
- `g04ControlLawChanged=false`
- `g05ContactAuthorityChanged=false`
- `g06DamagePersistenceChanged=false`
- `runtimeChoosesCollisionRealization=true`
- `runtimeSelectedSemanticEngagement=true`
- `storyIntentOnly=true`
- `storyTargetZonePrescribed=false`
- `perAssetCollisionEngineering=false`
- `climaxRequiresNewContact=false`
- `gateClosed=false`
- `productionReadyClaimed=false`

The CI also hash-verified the preserved predecessor sources for Candidate 4.0/G04, Candidate 4.2/G05, Candidate 4.3/G06, and Candidate 4.4.3.

## Scope-drift audit

### G07 ownership

PASS. Candidate 4.4.6 changes the G07 drama/lifecycle realization of a contact-free CLIMAX. It does not replace or weaken G04 motion, G05 contact truth, or G06 consequence authority.

### Causal climax correctness

PASS. The climax is not fabricated as a third collision. It becomes observable only after a real counterattack and physical dominance reversal have already been realized, dependencies are ready, and persistent physical state exists. This matches the Master Plan requirement that climax arise from prior events.

### Physics authority

PASS. Physical escalation/counterattack events still require real G05 VERIFIED native contact. New visible damage remains governed by G05/G06. A contact-free climax does not manufacture additional impact or damage.

### Genericity / asset independence

PASS. Exact Bugatti and generic hypercar fixtures pass under the same runtime source. Semantic engagement surfaces for physical events are selected at runtime from live geometry. No per-asset collision code, target-zone prescription, trajectory points, impact energy targets, or exact collision frames are introduced.

### Regression preservation

PASS. G04/G05/G06 predecessor source hashes are unchanged and the accepted run reports no control-law, contact-authority, or damage-persistence mutation.

### Acceptance-scope correction

PASS. Candidate 4.4.6 removes the invalid G07 assumption that every dramatic beat must independently cross the G06 damage threshold. It does **not** lower or change that threshold. G06 persistent two-sided damage is still validated separately from G07 dramatic-state progression.

## Post-flight result

**SCOPE POST-FLIGHT RESULT: PASS**

No scope drift was found in Candidate 4.4.6 relative to the G07 gate, `ISS-R041`, `ISS-R042`, the frozen architecture, or the preserved G04/G05/G06 authorities.

Per `ISS-R044`, this result does **not** close or lock G07 by itself. Current disposition is:

`G07_MACHINE_PASS_SCOPE_POSTFLIGHT_PASS_PENDING_USER_OK`

G07 remains OPEN until the user explicitly approves this pre-flight/post-flight result with `OK` or equivalent. Production readiness is not claimed.