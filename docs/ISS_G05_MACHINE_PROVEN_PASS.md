# ISS-G05 Native Contact Truth / No-Cheating — MACHINE_PROVEN PASS

Date: 2026-09-15

Status: `MACHINE_PROVEN_PASS` — preserved project evidence, not a user LOCK and not production readiness.

## Acceptance authority

- Runtime: `ISS_GENERIC_BATTLE_RUNTIME_V1_CANDIDATE_4_2_G05`
- GitHub run: `34996856866`
- GitHub job: `104475157827`
- Acceptance head: `b4e4b3ee58e023585e395c57d4bab966b8c2db86`
- Artifact: `10407867929`
- Artifact SHA256: `8dae22ba67321f4adcb80e829111229cfb4ba283cf4558284763fe32aa4be192`
- Blender: `4.5.13 LTS`
- Contact authority: `RECIPROCAL_NATIVE_SOLVER_RESPONSE_V1`
- Outer authority: `PAIRWISE_CONTACT_OUTER_AUTHORITY_V1`

## Preserved prerequisites

- ISS-G04 Candidate 4.0 autonomy source unchanged.
- Candidate 3.9 supported envelope and semantic-surface source unchanged.
- Candidate 3.7.1 surface-aware consequence hardening preserved.
- Existing ImpactModel gate preserved.
- Damage threshold unchanged (`MIN_DAMAGE_SEVERITY=0.055`).
- No contact-threshold weakening.
- No actor pose/velocity mutation.
- No asset-specific battle code.
- No exact collision-frame, trajectory, impact-speed or target-energy forcing.
- OBB is not final contact authority.
- Blender sweep API is not final contact authority.

## Exact Bugatti acceptance

Asset SHA256: `8cc074c40fe9ced7271cbeddf223cd9a520dee868977ffcbd439cec1c2b62cb4`

- Candidate 3.9 asset/semantic regression: PASS.
- G04 `TRACK -> CONTACT_HANDOFF`: preserved.
- Pairwise solver contact verified at frame 31.
- Pair locality gap: `-0.041466 m`.
- Semantic front-zone distance: `0.210853 m` for the direct physical transaction.
- Impulse balance ratio: `0.995505`.
- Impulse opposition cosine: `0.999561`.
- Existing ImpactModel qualification: PASS.
- Direct pairwise physical transaction count: 1.
- Reciprocal intent inherited from that same physical transaction: 1.
- Runtime result: PASS.
- Max target refresh count: 14.

## Generic hypercar acceptance

Asset SHA256: `0b2710a840d128aee53161277edb8cb77e1930d339f53585c6faece3f1dc2b1c`

- Same Candidate 4.2 source; no asset-specific branch.
- G04 `TRACK -> CONTACT_HANDOFF`: preserved.
- Pairwise solver contact verified at frame 33.
- Pair locality gap: `-0.046669 m`.
- Semantic front-zone distance: `0.240595 m` for the direct physical transaction.
- Impulse balance ratio: `0.997814`.
- Impulse opposition cosine: `0.999857`.
- Existing ImpactModel qualification: PASS.
- Direct pairwise physical transaction count: 1.
- Reciprocal intent inherited from that same physical transaction: 1.
- Runtime result: PASS.
- Max target refresh count: 16.

## Negative-control acceptance

The zero-cost property suite proved the contact authority rejects:

- wrong target identity;
- controller authority not released;
- non-adjacent pair response;
- semantic-zone mismatch;
- rolling/friction-only deceleration;
- unilateral wall response;
- vertical/ground response;
- same-direction/external impulse that is not reciprocal.

It accepts physically consistent reciprocal responses for equal and asymmetric masses.

## Gate conclusion

`ISS-G05 = MACHINE_PROVEN_PASS`.

This result proves the G05 native-contact/no-cheating contract only. It does **not** claim:

- ISS-G06 damage/persistent-state acceptance;
- dramatic multi-event battle progression;
- cinematic/human visual acceptance;
- scale acceptance;
- full 9-service E2E;
- production readiness.

Next gate: `ISS-G06_DAMAGE_PERSISTENT_STATE`.
