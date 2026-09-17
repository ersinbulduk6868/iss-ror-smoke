# ISS G08 Full Affected-Layer Audit

Date: 2026-09-17
Gate: ISS-G08 Event-Driven Cinematic Camera
Candidate: ISS_GENERIC_BATTLE_RUNTIME_V1_CANDIDATE_4_5_0_G08
Backend: Blender 4.5.13
Governance: mandatory three-iteration full affected-layer audit

## Trigger
The same G08 acceptance path required three executions before runtime acceptance could proceed:
1. GitHub run 35204991048 failed before runtime because the static wrapper validator incorrectly treated module bootstrap constant `REPO_ROOT` as runtime patch authority.
2. GitHub run 35221150331 attempt 1 passed static scope but failed private asset acquisition because the OIDC access broker did not yet allow the new G08 workflow ref.
3. GitHub run 35221150331 attempt 2 passed OIDC authorization and returned the exact Bugatti asset contract, but the workflow rejected the response because it was coupled to the broker implementation version string `3.3.13-generic-runtime-candidate446-g07-access` while the broker had correctly advanced to `3.3.14-generic-runtime-candidate450-g08-access`.

No execution above reached Blender G08 runtime. These failures are acceptance-infrastructure failures, not camera/physics failures.

## Root cause and failure family
Primary root cause: G08 acceptance orchestration was created as a successor to G07 but inherited brittle test infrastructure assumptions rather than a stable access contract.

Failure family:
- static validator false-positive on non-authority module constants;
- new workflow missing from exact GitHub OIDC allowlist;
- consumer coupled to mutable access-broker implementation version;
- duplicate G08 workflows carrying independent copies of the same access logic, creating future drift risk;
- push path filter initially ignored candidate/validator changes and therefore failed to rerun after a legitimate fix;
- GitHub Actions same-step environment propagation was initially mishandled: values appended to `$GITHUB_ENV` are available to later steps, not earlier commands in the same step.

## Locked upstream preservation
The accepted upstream source remains immutable and is guarded by exact git object hashes in the authoritative G08 workflow:
- G04 Candidate 4.0: `5fac710c646e4609d4b63d0ae23e8612f1c9c81d`
- G05 Candidate 4.2: `a6e8f624f1897f965b7fa1c87ea74afab3eaeeff`
- G06 Candidate 4.3: `e8b7172232186e7fc8f447b65ac146aacfd58b10`
- G07 Candidate 4.4.3 semantic resolver: `358d34c437ee27d3115117f0aaa1139704277212`
- G07 Candidate 4.4.6 accepted causal climax wrapper: `0a09826e539b51aebf720e3d39b7a1ba9aee733b`
- base camera source: `01aab5f4f6349b7223009085e87a20df4fa5f9fe`
- hardened runtime: `a9694d22697e1de077415f1198d88df5fa07d00a`

No G04/G05/G06/G07 source mutation is required by G08.

## G08 camera implementation audit
`blender/iss_battle_runtime_camera_g08.py` is presentation-only:
- reads realized actor transforms/dimensions and G07 transition state;
- keys camera location, camera target location, and lens only;
- derives phase-aware cues from realized HOOK/ESCALATION/COUNTERATTACK/REVERSAL/CLIMAX/PAYOFF and native IMPACT truth;
- contains no rig command/brake/coast calls;
- contains no ImpactModel, DamageAccumulator, or ConsequenceEngine mutation calls;
- contains no actor pose/velocity, rigid-body, damage-state, threshold, forced-winner, teleport, reset, or per-asset battle mutation;
- records a 9:16 relationship-readability oracle and separate human cinematic review evidence.

`blender/run_generic_battle_runtime_v1_candidate450_g08.py` patches only:
- candidate label;
- hardened camera-class hook;
- runtime camera-model label.

The accepted G07 runtime remains physical/drama authority.

## Runtime and acceptance compatibility
Upstream inputs:
- same accepted G07 fixtures are reused for exact Bugatti and generic hypercar;
- same Candidate 4.5.0 camera source is used for both asset sets;
- exact private Bugatti SHA remains `8cc074c40fe9ced7271cbeddf223cd9a520dee868977ffcbd439cec1c2b62cb4` and expected size remains 31,576,440 bytes.

Downstream evidence:
- base runtime evidence must report success, at least two actors, and at least one real impact;
- G07 evidence must remain COMPLETE with reversal, causal climax, payoff, and at least two verified direct G05 physical transactions;
- G08 evidence must cover HOOK, ESCALATION, COUNTERATTACK, REVERSAL, CLIMAX, PAYOFF, IMPACT; preserve 9:16 framing; pass relationship readability; contain no physics mutation; and keep human cinematic acceptance PENDING.

## Access and security audit
`iss-final-video-transfer-once` keeps exact GitHub OIDC verification:
- repository and repository id are pinned;
- audience is pinned;
- branch ref and workflow_ref are exact allowlisted pairs;
- runner environment must be GitHub-hosted;
- OIDC signature is verified against GitHub JWKS;
- private Storage access is issued only after successful OIDC verification.

The broker exposes a stable additive contract field `contractVersion = iss-bugatti-pair-access-v1`. Acceptance binds to this stable contract rather than the mutable broker implementation version. This avoids false failures when the broker version changes only to extend an allowlist or provenance metadata.

`verify_jwt=false` remains intentional because the function performs its own GitHub OIDC authorization and the historical endpoint already used this custom-auth model. No authorization gate was weakened.

## GitHub Actions environment-lifecycle audit extension
The first post-audit run `35221798437` proved the stable broker contract and OIDC path were correct, but exposed one remaining orchestration defect before asset download: `BUGATTI_SOURCE_URL` was appended to `$GITHUB_ENV` and then consumed later in the same step. GitHub Actions only makes `$GITHUB_ENV` additions available to subsequent steps.

Correct contract:
- validate broker response in-process;
- extract the signed URL into a shell variable;
- `export BUGATTI_SOURCE_URL` for immediate same-step consumption by `visual_vnext_rc2_bugatti_duel_asset_preflight.py`;
- also append it to `$GITHUB_ENV` only if a later step needs it.

Adjacent handoffs were checked:
- `BUGATTI_PRIMARY` is written to `$GITHUB_ENV` and consumed in the following fixture-build step: valid;
- `BLENDER_BIN` is written to `$GITHUB_ENV` and consumed in later runtime steps: valid;
- no other same-step `$GITHUB_ENV` consumer remains in the authoritative workflow.

This run did not reach Blender and therefore does not alter the G08 camera-layer assessment.

## Duplicate workflow audit
Three G08 workflow files existed:
- `generic-battle-runtime-v1-candidate450-g08-run.yml`
- `generic-battle-runtime-v1-candidate450-g08.yml`
- `generic-battle-runtime-v1-candidate450-g08-bootstrap.yml`

Maintaining three copies created configuration and access-contract drift. The clean audited state is one authoritative workflow: `generic-battle-runtime-v1-candidate450-g08-run.yml`, supporting both path-triggered push execution and manual `workflow_dispatch`. The two redundant workflows have been removed.

## Next-likely failures covered before retest
The authoritative workflow must fail closed on:
- OIDC access denial;
- access `contractVersion` mismatch;
- Bugatti SHA/size mismatch;
- signed-URL same-step propagation failure;
- Blender version mismatch;
- predecessor source-hash drift;
- fixture build failure;
- absence of G05 native contact or G07 causal climax;
- missing G08 camera evidence;
- missing required camera cues;
- non-9:16 output;
- relationship readability failure;
- actor/physics mutation claim;
- per-asset camera source divergence;
- missing mandatory human review sheet.

## Audit conclusion
FULL AFFECTED-LAYER AUDIT = PASS FOR ONE CLEAN RUNTIME RETEST

This audit does not claim G08 machine PASS, human cinematic PASS, gate closure, or production readiness. One clean authoritative runtime acceptance run is required next. If machine acceptance passes, mandatory G08 scope post-flight and explicit user approval are still required before G08 can close.
