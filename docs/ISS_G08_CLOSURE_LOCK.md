# ISS G08 Closure / Lock Record

Status: **CLOSED / LOCKED**
Gate: **G08 — Event-Driven Cinematic Camera / Portrait Full-Bounds Framing**
Closed: **2026-09-17 (Europe/Berlin)**
Governance: ISS-R043 Scope Pre/Post Flight + ISS-R044 explicit user approval

## Authoritative accepted candidate

- Candidate: **Generic Battle Runtime v1 Candidate 4.5.1 G08**
- Accepted head SHA: `aa7ad7c3adfb4ff043ee849aac824cb8b0bb8441`
- Accepted workflow run: `35244674429`
- Accepted job: `105281683428`
- Job conclusion: **success**
- Artifact ID: `10507137080`
- Artifact name: `iss-generic-battle-runtime-v1-candidate451-g08-35244674429`
- Artifact digest: `sha256:41db5fe95d30f08d91275971231cec03c40d1a4af0fa65dddd47502bc82f1cb3`

## Machine-proven acceptance

The authoritative run completed every required step successfully:

1. Checkout audited G08 candidate — PASS
2. Static scope and predecessor integrity — PASS
3. Resolve and acquire exact Bugatti — PASS
4. Build accepted G07 fixtures and isolate G08 output — PASS
5. Install exact Blender 4.5.13 runtime — PASS
6. Exact Bugatti G08 machine runtime — PASS
7. Generic hypercar G08 machine runtime — PASS
8. Strict G08 machine framing acceptance — PASS
9. Isolated low-cost human review fixtures — PASS
10. Exact Bugatti human-review previews — PASS
11. Generic hypercar human-review previews — PASS
12. Strict low-cost review evidence acceptance — PASS
13. Human cinematic review contact sheet — PASS
14. Evidence upload — PASS
15. Job completion — PASS

## Scope Post-Flight

**PASS**

Verified closure conditions:

- G04/G05/G06/G07 predecessor integrity checks passed in the accepted workflow.
- Exact Bugatti and generic hypercar both passed the same G08 camera source and acceptance path.
- G08 machine framing acceptance passed after 9:16 portrait full-bounds auto-framing.
- G08 camera remained presentation-only; no authorized scope expansion into physics, control, collision, damage, or battle-drama authority.
- Human-review previews and contact sheet passed separately from machine acceptance.
- The final Step-14 compatibility repair commit modified only `tools/build_g08_review_contact_sheet.py` (11 additions, 1 deletion) and did not modify G04-G07 runtime sources, physics, camera authority, or machine thresholds.
- Final artifact is preserved by ID and SHA-256 digest above.
- No production-ready claim beyond the G08 gate is implied.

## Final Step-14 repair provenance

Commit: `aa7ad7c3adfb4ff043ee849aac824cb8b0bb8441`
Message: `Fix G08 contact sheet Pillow compatibility`

The repair made the human-review contact-sheet builder compatible with both newer `Image.Resampling.LANCZOS` and older `Image.LANCZOS` Pillow APIs. It did not weaken or bypass any G08 acceptance gate.

## R044 explicit approval

The user explicitly approved G08 closure on **2026-09-17** with the instruction:

> “Tamam gate8 kapanışını onaylıyorum yeni Gate geçme ama”

Therefore R044 is satisfied.

## LOCK declaration

G08 is now **CLOSED / LOCKED**.

Until the user explicitly unlocks or changes G08, do not:

- modify the accepted G08 camera authority or behavior,
- weaken its 9:16/full-bounds framing acceptance,
- move G08 presentation logic into physics/control layers,
- alter accepted predecessor contracts to accommodate later gates,
- overwrite this accepted provenance.

## Continuation hold

**Do not advance to G09.**

Per the user’s explicit instruction, the project is held immediately after G08 closure. G09 remains unopened by this closure action.