# ISS-G06 — Causal Damage / Breakage / Debris / Persistent State

## Status

**MACHINE_PROVEN PASS** on the Generic Battle Runtime engineering branch.

This is **not** a user LOCK, **not** a G07 claim, and **not** a production-readiness claim. It is a known-good project asset that successors must preserve.

## Acceptance provenance

- Branch: `iss-engineering/generic-battle-runtime-v1`
- Runtime candidate: `ISS_GENERIC_BATTLE_RUNTIME_V1_CANDIDATE_4_3_G06`
- Acceptance source commit: `409eaa1c2714600468f5fe9e3beae7c77f363317`
- GitHub Actions run: `35008259169`
- Job: `104513409528`
- Terminal conclusion: `success`
- Blender: `4.5.13`
- Evidence artifact: `10411389678`
- Artifact name: `iss-generic-battle-runtime-v1-candidate43-g06-35008259169`
- Artifact SHA256: `bcda75668face31f8e21cb4cb5818cf0c0c8156436de5af39453dd21c68a6641`
- Persistence model: `CAUSAL_DAMAGE_PERSISTENT_STATE_V1`

## Preserved upstream truth

- G04 closed-loop autonomy: preserved.
- G05 native pairwise contact truth: preserved.
- G05 contact authority model remains `RECIPROCAL_NATIVE_SOLVER_RESPONSE_V1`.
- G05 outer authority model remains `PAIRWISE_CONTACT_OUTER_AUTHORITY_V1`.
- `MIN_DAMAGE_SEVERITY` remained `0.055`.
- No damage/contact threshold was lowered.
- No actor pose or velocity mutation was introduced.
- No reset/teleport/forced-winner mechanism was introduced.
- No asset-specific battle source code was introduced.
- No exact collision-frame, exact impact-energy, or fixture-specific success target was introduced.

## Exact Bugatti acceptance

Machine validator result: `PASS`.

- G05-proven damage events: `2`
- Direct G05 physical transactions: `2`
- Inherited reciprocal transactions: `1`
- G05 actor-state provenance bindings: `2`
- Final frame: `360`
- Later-event damaged-state observations: `1`
- Follow-up drive efficiency: `0.9618099808479218`
- Follow-up effective max speed: `19.236199616958437 m/s`
- Profile max speed: `20.0 m/s`
- Persistent damage shape keys: `7`
- Persistent debris objects: `6`

The later event consumed the reduced `drive_efficiency`; damage therefore changed subsequent effective capability rather than existing only as visual metadata.

A later native follow-up contact produced severity `0.054643`, below the unchanged `0.055` threshold, and correctly did **not** earn new damage. This is evidence that the gate was preserved rather than weakened to force G06 success.

## Generic hypercar identical-source acceptance

Machine validator result: `PASS`.

- G05-proven damage events: `4`
- Direct G05 physical transactions: `2`
- Inherited reciprocal transactions: `1`
- G05 actor-state provenance bindings: `4`
- Final frame: `360`
- Later-event damaged-state observations: `1`
- Follow-up drive efficiency: `0.9531504501001701`
- Follow-up effective max speed: `17.156708101803062 m/s`
- Profile max speed: `18.0 m/s`
- Persistent damage shape keys: `4`
- Persistent debris objects: `8`

The generic fixture used the same Candidate 4.3 runtime source and acceptance model as the exact Bugatti fixture.

## Failure-family engineering completed before PASS

### 1. G06 private-asset OIDC scope handoff

The first G06 attempt never reached the Blender runtime because `iss-final-video-transfer-once` rejected the new G06 workflow identity. The helper's GitHub OIDC security model was preserved; only the exact Candidate 4.3 G06 `workflow_ref` was added to the existing branch/workflow allowlist.

- Edge Function deployed as v13.
- Function SHA256: `802d8dfb47c8d0fd02a33b6e03eaf689eccc7834735b782b635042670270daa5`
- Repository/ref/workflow/audience/time/signature checks remained fail-closed.
- Same failed workflow was rerun; private asset resolve and exact Bugatti acquisition then PASSed.

### 2. Mirrored damage provenance binding

The second attempt reached both Blender runtimes and both runtime executions PASSed, but the strict machine validator correctly rejected a mirrored actor-state damage record whose historical `detector` field still contained `SOLVER_CORRELATED_OBB_CONTACT`.

Candidate 4.2/G05 canonicalized direct damage-event detector metadata, but a mirrored damage record could retain the underlying ImpactModel detector when there was no reciprocal alias row to rewrite it.

The validator was **not** weakened and G05 source was **not** modified. Candidate 4.3's verified-receipt provenance binder was hardened so that, only after a `VERIFIED` G05 native-contact receipt matches exact frame + attacker + target, both direct and mirrored actor-state damage records receive the canonical G05 contact-authority metadata. The binder also fail-closes if the receipt model is not the expected G05 authority model.

This is provenance hardening only; it does not change contact, damage magnitude, motion, control, or thresholds.

## Machine acceptance marker

`GENERIC_BATTLE_RUNTIME_CANDIDATE43_G06_MACHINE_ACCEPTANCE` returned:

- `status = PASS`
- `g04Preserved = true`
- `g05Preserved = true`
- `g06CausalDamagePersistentState = true`
- `g07DramaClaimed = false`
- `productionReadyClaimed = false`

The workflow emitted `ISS_G06_MACHINE_ACCEPTANCE=PASS` and terminated successfully.

## Continuation

The next Master Plan gate is **ISS-G07 — Battle State Machine + Dramatic Causal Progression**.

G07 must preserve this G06 state and prove multiple causally dependent battle events in one continuous world: escalation, counterattack, dominance reversal/comeback, climax/payoff and outcome must emerge from realized physical state. G07 may not force outcomes, reset actors, weaken physics/damage gates, or replace the G04/G05/G06 truth chain with choreography.
