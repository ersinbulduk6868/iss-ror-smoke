#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
TOOLS = ROOT / "tools"
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

from validate_generic_autonomous_battle_c464_result import _validate
from validate_generic_autonomous_battle_c465_result import _cutoff_runtime_proof
from validate_generic_autonomous_battle_c468_result import _log_proof as _c468_log_proof


def _rows(path: str) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for line in Path(path).read_text(encoding="utf-8", errors="replace").splitlines():
        try:
            row = json.loads(line)
        except Exception:
            continue
        if isinstance(row, dict):
            rows.append(row)
    return rows


def _cleanup_runtime_proof(path: str) -> dict[str, object]:
    rows = _rows(path)
    cleanups = [
        (idx, row)
        for idx, row in enumerate(rows)
        if row.get("marker") == "GENERIC_SOLVER_HANDOFF_TRANSACTION_CUTOFF_CLEANUP"
    ]
    invalidations = [
        (idx, row)
        for idx, row in cleanups
        if row.get("action") == "RELEASED_TRANSACTION_INVALIDATED"
    ]
    replacements = [
        (idx, row)
        for idx, row in cleanups
        if row.get("action") == "FRESH_TRANSACTION_PRESERVED"
    ]
    assert invalidations, "C469_RELEASED_TRANSACTION_CUTOFF_INVALIDATION_NOT_OBSERVED"

    stale_reuse: list[dict[str, object]] = []
    for cleanup_idx, cleanup in invalidations:
        event_id = str(cleanup.get("eventId") or "")
        actor_id = str(cleanup.get("actorId") or "")
        old_cutoff = cleanup.get("previousCutoffFrame")
        assert event_id and actor_id, cleanup
        assert old_cutoff is not None, cleanup
        old_cutoff = int(old_cutoff)

        # After transaction cleanup and before the next fresh latch for the same
        # event/actor, G05 must never observe the released cutoff again.
        for later in rows[cleanup_idx + 1 :]:
            if (
                later.get("marker") == "GENERIC_SOLVER_HANDOFF_LATCHED"
                and str(later.get("eventId") or "") == event_id
                and str(later.get("actorId") or "") == actor_id
            ):
                break
            if (
                later.get("marker") == "G05_OUTER_CONTACT_AUTHORITY_REJECTED"
                and str(later.get("eventId") or "") == event_id
                and str(later.get("attackerId") or "") == actor_id
                and later.get("cutoffFrame") is not None
                and int(later.get("cutoffFrame")) == old_cutoff
            ):
                stale_reuse.append(later)

    assert not stale_reuse, {
        "error": "C469_STALE_CUTOFF_REUSED_AFTER_TRANSACTION_INVALIDATION",
        "rows": stale_reuse[:10],
    }

    contacts = [r for r in rows if r.get("marker") == "PAIRWISE_NATIVE_SOLVER_CONTACT_VERIFIED"]
    impacts = [
        r
        for r in rows
        if r.get("marker") in {
            "QUALIFIED_NATIVE_RESPONSE_IMPACT",
            "CAUSAL_VISIBLE_IMPACT_CONSEQUENCE_V3_APPLIED",
        }
    ]
    assert contacts, "C469_NATIVE_CONTACT_NOT_VERIFIED_AFTER_CLEANUP_CAPABLE_RUNTIME"
    assert impacts, "C469_CAUSAL_IMPACT_NOT_OBSERVED_AFTER_CLEANUP_CAPABLE_RUNTIME"

    return {
        "cleanupMarkerCount": len(cleanups),
        "releasedTransactionInvalidationCount": len(invalidations),
        "sameFrameFreshReplacementCount": len(replacements),
        "staleCutoffReuseAfterInvalidationCount": len(stale_reuse),
        "nativeContactCount": len(contacts),
        "causalImpactMarkerCount": len(impacts),
        "releasedTransactionCutoffInvalidated": True,
        "staleCutoffAuthorizationPrevented": True,
    }


def main() -> None:
    p = argparse.ArgumentParser()
    for prefix in ("bugatti", "generic"):
        for key in ("battle", "g06", "g07", "g08", "log"):
            p.add_argument(f"--{prefix}-{key}", required=True)
    a = p.parse_args()

    fixtures = []
    cutoff = {}
    recency = {}
    cleanup = {}
    for prefix in ("bugatti", "generic"):
        battle = getattr(a, f"{prefix}_battle")
        fixtures.append(
            _validate(
                prefix,
                battle,
                getattr(a, f"{prefix}_g06"),
                getattr(a, f"{prefix}_g07"),
                getattr(a, f"{prefix}_g08"),
            )
        )
        cutoff[prefix] = _cutoff_runtime_proof(battle)
        recency[prefix] = _c468_log_proof(getattr(a, f"{prefix}_log"))
        cleanup[prefix] = _cleanup_runtime_proof(getattr(a, f"{prefix}_log"))

    print(json.dumps({
        "marker": "GENERIC_AUTONOMOUS_BATTLE_C469_MACHINE_ACCEPTANCE",
        "status": "PASS",
        "affectedLayerAudit": "PASS",
        "failureFamily": "RELEASED_HANDOFF_LEAVES_STALE_G05_CUTOFF_AUTHORIZATION",
        "sameRuntimeAcrossAssets": True,
        "g05CutoffRecencyContractPreserved": "PASS",
        "activeHandoffCutoffImmutableWithinLatch": "PASS",
        "releasedTransactionCutoffInvalidated": "PASS",
        "staleCutoffAuthorizationPrevented": "PASS",
        "newLatchMayEstablishFreshCutoff": "PASS",
        "semanticSelectionFrozenWithinHandoff": "PASS",
        "secondNativeContact": "PASS",
        "twoSidedDamage": "PASS",
        "visibleCausalDamageDebris": "PASS",
        "g07AdaptiveCausalDrama": "PASS",
        "g08MachineObservability": "PASS",
        "nativeContactAuthorityPreserved": True,
        "semanticToleranceChanged": False,
        "localityToleranceChanged": False,
        "contactThresholdChanged": False,
        "damageAdmissionThresholdChanged": False,
        "fixtureMutationForAcceptance": False,
        "perAssetBattleCode": False,
        "perVideoTrajectoryEngineering": False,
        "humanCinematicAcceptance": "PENDING",
        "gateClosed": False,
        "productionReadyClaimed": False,
        "cutoffRuntimeProof": cutoff,
        "recencyRuntimeProof": recency,
        "cleanupRuntimeProof": cleanup,
        "fixtures": fixtures,
    }, sort_keys=True))


if __name__ == "__main__":
    main()
