# ISS-G08 / ISS-G09 Mandatory Scope Pre-Flight

Date: 2026-09-17
Governance: ISS-R043 / ISS-R044
Backend authority: Blender 4.5.13
Predecessor gate: ISS-G07 CLOSED / MACHINE_PROVEN / SCOPE-PRESERVED / USER-APPROVED

## Authoritative scope sources reread
1. Supabase Engineering Memory (ISS_MASTER and current G07 closure evidence)
2. ISS Master Project Documentation — 2026-09-15 v1.1
3. Current generic-runtime branch source and G07 accepted candidate lineage
4. Current Environment Library / Native Audio Engineering Memory provenance

## Shared invariants
- Frozen 9-service architecture remains unchanged.
- Merge Service remains separate.
- Current battle backend remains Blender 4.5.13.
- G04 closed-loop autonomy is read-only upstream authority.
- G05 native contact truth is read-only upstream authority.
- G06 causal damage/persistent state is read-only upstream authority.
- G07 dramatic causal progression is read-only upstream authority.
- ISS-R041 generic multi-vehicle runtime invariant remains mandatory.
- ISS-R042 asset-independent collision realization remains mandatory.
- No actor pose/velocity mutation, teleport/reset, forced winner, threshold weakening, or Story-authored trajectory/collision choreography.
- No production-ready claim before downstream gates complete.

## ISS-G08 — Event-Driven Cinematic Camera

### Gate scope
ISS-MR-V04..V09; ISS-MR-CAM01..CAM08.

### Entry condition
PASS. G07 now provides reliable physically-derived event/state telemetry including escalation, counterattack, dominance reversal, causal climax and payoff.

### Allowed engineering
- Camera Director only.
- Read-only consumption of actor transforms, dimensions, velocity/state and G07/G05/G06 event telemetry.
- Event-driven shot selection/framing.
- Vertical Shorts 9:16 composition and pacing.
- Readability gates for actor scale/direction/relationship and physical consequences.
- Machine framing acceptance separated from human cinematic review.

### Forbidden scope drift
- No physics/control/contact/damage/drama mutation to make a shot work.
- No actor repositioning or velocity injection for camera convenience.
- No hidden/faked impact/damage.
- No per-asset camera source branches.
- No camera acceptance that substitutes for physics/product truth.

### Current gap
Current `iss_battle_runtime_camera.py` is event-aware but still basic: deterministic azimuth, fixed distance/elevation heuristics, periodic location keyframes, one impact-emphasis mode and three-frame preview logic. It does not yet provide a complete phase-aware cinematic shot grammar, vertical composition/readability oracle, consequence coverage guarantees, or a separate human cinematic acceptance artifact.

## ISS-G09 — Environment + Native Diegetic Audio Runtime

### Gate scope
ISS-MR-E01..E08; ISS-MR-AU01..AU13.

### Entry condition
PASS. G05/G06/G07 contact/consequence/event authority is stable enough to drive environment/audio integration.

### Preserved prior foundation
- Environment Library V1 data/control-plane foundation: 6 presets and required coverage preparation exist, but old final runtime acceptance did not pass and must not be promoted.
- Native Audio preparation records 21-slot coverage / asset+binding preparation, but prior joint L4/Isaac readiness claims were provenance-repaired and are not current runtime PASS.
- Vehicle Battle V1 diegetic-audio-only policy remains locked.

### Required backend reconciliation
Old Environment/Audio runtime assumptions tied to Isaac/PhysX/Omniverse are historical. They must not be revived as current backend authority. G09 runtime integration must target Blender 4.5.13 while preserving reusable data, licensing, coverage, synchronization and Merge/Quality contracts.

### Allowed engineering
- Environment preset/data adapter into Blender runtime.
- Persistent collision-capable terrain/environment composition.
- Event/state-driven diegetic audio event manifest/timeline from real G05/G06/G07 telemetry.
- Blender/local audio rendering or deterministic event-audio timeline generation compatible with existing Merge/Quality contracts.
- Runtime evidence for environment persistence, collision integrity, event/audio sync and 21-slot coverage.

### Forbidden scope drift
- No narrator/voice-over for Vehicle Battle V1.
- No environment-driven hidden physics manipulation.
- No audio cues for impacts/damage that did not physically occur.
- No silent public/proxy asset substitution.
- No promotion of old Isaac acceptance or stale static readiness to Blender runtime PASS.
- No Merge/Quality contract weakening.

## Pre-flight result
**ISS-G08 SCOPE PRE-FLIGHT = PASS**
**ISS-G09 SCOPE PRE-FLIGHT = PASS**

Engineering may start under these exact boundaries. Each gate still requires its own machine acceptance, mandatory scope post-flight, and explicit user OK before closure.
