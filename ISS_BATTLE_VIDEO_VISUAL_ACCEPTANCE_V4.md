# ISS Battle Video Visual Acceptance v4 — TEST CANDIDATE CONTRACT

Scope: Blender battle-video visual iteration only. This file does not unlock or modify any locked ISS service or the frozen 9-service architecture.

## Locked acceptance carried forward

- A1: Bugatti and bulldozer both approach under the collision setup.
- A2: Approximately head-on collision occurs near scene center and is visually readable.
- A3: Bulldozer has active pre-impact motion and visible post-impact response consistent with its greater mass.
- A4: Bugatti front damage is clearly readable in rendered imagery.
- A5: Impact causes visible breakage/detached fragments/debris; release is triggered from observed impact, never pre-played.
- A6: Image quality materially exceeds the previous 640x360 Workbench test; Eevee Next is mandatory for this candidate and Workbench fallback is forbidden.
- A7: A single flat technical-test camera is forbidden.
- A8: Post-impact camera approaches the wreck and shows final positions, damage and debris.
- A9: Story-driven approach, impact and aftermath shots are required.
- A10: After review of each new video, newly observed shortcomings become additive acceptance items until the target result is accepted.
- A11: Environment must be sufficiently bright; vehicles, impact and aftermath must remain readable with key/fill/environment lighting and useful shadows.

## Candidate integrity gates

1. Visible vehicle geometry must be full source geometry. `quant120` or any other visible low-poly transport is forbidden.
2. Hidden collision proxies are allowed only as physics collision shapes; they must never replace visible source geometry.
3. Exact source model identities are Bugatti UID `4af92c51ecdd4efa9b1c19a1163d9f46` and bulldozer UID `b06a715d23a7450babac383b8bb7fb0a`.
4. Bugatti CC-BY-NC source is internal/noncommercial test-only for this candidate. No production/commercial readiness is implied.
5. Vehicle motion after physics handoff must be solver-derived. No post-handoff vehicle location keyframes are allowed.
6. Procedural impact crumpling must be reported truthfully as `damagePhysicalSolver=false`.
7. Debris must become dynamic rigid bodies after impact-triggered release.
8. `BLENDER_EEVEE_NEXT` is fail-closed. `BLENDER_WORKBENCH` fallback is forbidden.
9. Acceptance values may not be hardcoded to PASS. Structural/machine gates and visual-review gates must be separate.
10. Preflight must finish before final animation rendering is permitted. Preflight renders only representative approach/impact/aftermath frames.
11. Final render may start only after machine preflight PASS and explicit visual inspection of the preflight frames.
12. Main branch and all locked/proven ISS service files are outside this candidate and must remain untouched.
