# G04–G08: intent/readiness correction

Status: candidate change, behavioral checks passed; runtime and human acceptance pending.

Product scope: the same reusable runtime consumes story intent, live world state,
and supported ActorProfiles. No asset identity branch or per-video choreography.
R040–R046 and prior bounded PASS evidence remain authoritative.

## Provenance

- Baseline actually executed: `ec53ea47f3d0a763987d5bd9da1949662d15e037`.
- Job: `0770f579-5e2f-47e9-a3c5-4d003359f8c6`.
- Actual run: `e8d3f484-31b2-41b1-bf1a-6db30dab3731`.
- Snapshot's external run reference does not resolve in iss_test_runs.
- DB audit rows report defer then TACTIC_NOT_CONTACT_DIRECTED at frame 617.
- Raw stdout object has not been independently downloaded/hash-verified here.
  Stored audit rows and stdout tail are corroborating evidence, not a raw-log proof.

## Root cause reproduced in actual function bodies

C488 computed contact-directed intent from `contactCommit`, an instantaneous
readiness flag. C491 deliberately sets this flag false during alignment hold.
Consequently C488 passed `contact_directed_mode=False` to the C491 certificate
wrapper, skipping its hold branch and invalidating an earned certificate.

C488 then delegated to the base controller with the original observation's
`requires_contact=True`. Thus an upper-layer readiness refusal did not prohibit
a lower-layer proximity handoff. The test verifies the delegated observation;
it does not claim a real physics handoff was reproduced locally.

## Correction

Carry `event.requires_contact` independently in the context. Use that intent to
classify contact-directed tactics. When current readiness is false, pass a copied
observation with contact handoff disabled to the base controller. Preserve original
event/observation, existing heading/contention/contact thresholds, native solver,
damage rules, real separation invalidation, and recovery ownership.

Only the C488 wrapper changes. Historical commit bytes remain unchanged; this
branch is an unaccepted candidate. Old launcher blob hashes must not be reused.

## Validation

`python -m unittest discover -s tests -p test_contact_intent_readiness.py`

Four tests cover context propagation, alignment hold for ENGAGE/COUNTER at 1/4/12 m
characteristic dimensions, unready delegation, and invalidation for noncontact,
recovery, and real separation. Before correction, seven assertions failed across
the original three tests. After correction, all four tests pass. Actual C488/C491
function bodies are loaded via AST with scene lookup/base-controller doubles;
certificate/authority helpers are real. This is not Blender or cross-asset proof.

Existing C483–C491 static validators all exit 0, unchanged.

## Remaining acceptance work

1. Obtain complete runtime evidence JSON and raw logs through authorized access.
2. Review the complete composed runtime, not just these wrapper functions.
3. Keep product invariants and recovery coverage explicit. Existing C489/C491
   validators require a confirmed NACK/recovery and a specific counterattack
   alignment sequence. Missing coverage cannot be waived or fabricated. A
   successful battle alone does not prove those conditional mechanisms.
4. Prepare an exact-source launcher and acceptance suite only after that review.
5. Same-source dissimilar-profile physics regression and full G04–G07 acceptance.
6. G08 event-bound camera machine checks plus independent human video review.

No gate is closed, no production code is deployed, no paid run is started, and
no existing failed result is promoted by this change.
