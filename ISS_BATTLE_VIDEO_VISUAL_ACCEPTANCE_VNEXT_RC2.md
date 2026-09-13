# ISS Battle Video Visual Acceptance vNext RC2

Status: TEST CANDIDATE CONTRACT. This does not unlock or modify any locked ISS service or the frozen 9-service architecture.

## Carried-forward locked visual criteria

- A1: Bugatti and bulldozer both move under the collision setup and approach each other.
- A2: Approximately head-on collision occurs near scene center and is visually readable.
- A3: Bulldozer has active pre-impact motion and a measurable post-impact physical response consistent with its greater mass.
- A4: Bugatti front-impact damage must be clearly readable in rendered imagery.
- A5: Impact causes visible breakage / detached fragments / debris; release is triggered from the observed impact event.
- A6: Image quality materially exceeds the previous low-quality test look. Eevee Next is mandatory.
- A7: A single flat technical-test camera is forbidden.
- A8: Post-impact camera approaches the wreck and shows final positions, damage and debris.
- A9: Story-driven approach, impact and aftermath shots are required.
- A10: New shortcomings observed during visual review are additive acceptance items.
- A11: Environment lighting must keep both vehicles, impact and aftermath clearly readable.

## Candidate integrity gates

1. Visible vehicle geometry must be full source geometry. `quant120` and every other visible low-poly transport are forbidden.
2. Hidden collision proxies are allowed only for physics collision shapes and may never replace visible source geometry.
3. Bugatti identity is UID `4af92c51ecdd4efa9b1c19a1163d9f46`; candidate transport must hash to `8cc074c40fe9ced7271cbeddf223cd9a520dee868977ffcbd439cec1c2b62cb4`.
4. Bulldozer identity is the approved ISS Asset Library record for UID `b06a715d23a7450babac383b8bb7fb0a`. Canonical library source SHA is `2c0be359bbc6c99118751e7caa4b71a205961914e78d2e58c5dd7afc0f498468`; source and ready records must remain `SOURCE_APPROVED` and `PRODUCTION_READY` before access is authorized.
5. Bulldozer visible source must retain the strict library geometry fingerprint: 441 meshes, 14 materials, 44 images, 904 nodes and 111483 triangles.
6. The candidate may use a transient signed provider read for the already-approved bulldozer UID only as transport after the library record is verified. It must not ingest, upload, replace or mutate the library asset.
7. Vehicle motion after physics handoff must be solver-derived; post-handoff vehicle location keyframes are forbidden.
8. Procedural impact crumpling must be reported truthfully as `damagePhysicalSolver=false`.
9. Debris must become dynamic rigid bodies after impact-triggered release.
10. `BLENDER_EEVEE_NEXT` is fail-closed; Workbench fallback is forbidden.
11. Acceptance values may not be hardcoded to PASS. Structural machine gates and human visual-review gates remain separate.
12. Preflight renders only representative approach, impact and aftermath frames. Final animation render is forbidden before machine preflight PASS and explicit visual review.
13. Candidate workflow is branch-isolated and read-only with respect to the repository.

## Preflight decision rule

Machine PASS proves the structural/physics/render contract only. A4 damage readability, A6 image quality, A11 scene brightness and overall cinematic readability require review of the three rendered preflight frames before final render authorization.
