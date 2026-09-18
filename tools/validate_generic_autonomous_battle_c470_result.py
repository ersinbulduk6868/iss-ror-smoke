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

REQUIRED_DIRECT_EVENTS = {"evt-escalation", "evt-counterattack"}


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


def _surface_transaction_runtime_proof(path: str) -> dict[str, object]:
    rows = _rows(path)
    refinements = [
        (idx, row)
        for idx, row in enumerate(rows)
        if row.get("marker") == "GENERIC_HANDOFF_LIVE_PAIR_SURFACE_REFINED"
    ]
    contacts = [
        (idx, row)
        for idx, row in enumerate(rows)
        if row.get("marker") == "PAIRWISE_NATIVE_SOLVER_CONTACT_VERIFIED"
    ]
    assert refinements, "C470_LIVE_PAIR_SURFACE_REFINEMENT_NOT_OBSERVED"
    assert contacts, "C470_NATIVE_CONTACT_NOT_VERIFIED"

    refined_events = {str(row.get("eventId") or "") for _, row in refinements}
    contact_events = {str(row.get("eventId") or "") for _, row in contacts}
    assert REQUIRED_DIRECT_EVENTS <= contact_events, (
        "C470_REQUIRED_DIRECT_CONTACT_EVENTS_MISSING", sorted(contact_events)
    )

    matched: list[dict[str, object]] = []
    for contact_idx, contact in contacts:
        event_id = str(contact.get("eventId") or "")
        actor_id = str(contact.get("attackerId") or "")
        if event_id not in REQUIRED_DIRECT_EVENTS:
            continue
        prior = [
            row
            for idx, row in refinements
            if idx < contact_idx
            and str(row.get("eventId") or "") == event_id
            and str(row.get("actorId") or "") == actor_id
        ]
        assert prior, ("C470_CONTACT_WITHOUT_FRESH_SURFACE_TRANSACTION", event_id, actor_id)
        refinement = prior[-1]
        assert refinement.get("storyTargetZonePrescribed") is False, refinement
        assert refinement.get("assetIdentityBranch") is False, refinement
        assert refinement.get("fixedWorldCoordinate") is False, refinement
        assert refinement.get("semanticToleranceChanged") is False, refinement
        assert refinement.get("localityToleranceChanged") is False, refinement
        assert refinement.get("contactThresholdChanged") is False, refinement
        assert str(contact.get("targetZone") or "") == str(refinement.get("selectedSemanticZone") or ""), (
            "C470_VERIFIED_CONTACT_DID_NOT_USE_TRANSACTION_SURFACE",
            refinement,
            contact,
        )
        matched.append({
            "eventId": event_id,
            "actorId": actor_id,
            "selectedSemanticZone": str(refinement.get("selectedSemanticZone") or ""),
            "surfaceToSemanticZoneDistanceM": float(refinement.get("surfaceToSemanticZoneDistanceM") or 0.0),
            "verifiedSemanticDistanceM": float(contact.get("semanticDistance") or 0.0),
        })

    matched_events = {str(row["eventId"]) for row in matched}
    assert REQUIRED_DIRECT_EVENTS <= matched_events, (
        "C470_REQUIRED_TRANSACTION_CONTACT_BINDINGS_MISSING", sorted(matched_events)
    )

    return {
        "surfaceRefinementCount": len(refinements),
        "refinedEventIds": sorted(refined_events),
        "verifiedNativeContactCount": len(contacts),
        "verifiedContactEventIds": sorted(contact_events),
        "requiredTransactionBindings": matched,
        "livePairSurfaceBoundToVerifiedContact": True,
        "storyTargetZonePrescribed": False,
        "semanticToleranceChanged": False,
        "localityToleranceChanged": False,
        "contactThresholdChanged": False,
    }


def main() -> None:
    p = argparse.ArgumentParser()
    for prefix in ("bugatti", "generic"):
        for key in ("battle", "g06", "g07", "g08", "log"):
            p.add_argument(f"--{prefix}-{key}", required=True)
    a = p.parse_args()

    fixtures = []
    cutoff = {}
    surface = {}
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
        surface[prefix] = _surface_transaction_runtime_proof(getattr(a, f"{prefix}_log"))

    print(json.dumps({
        "marker": "GENERIC_AUTONOMOUS_BATTLE_C470_MACHINE_ACCEPTANCE",
        "status": "PASS",
        "affectedLayerAudit": "PASS",
        "failureFamily": "HANDOFF_ZONE_LABEL_DRIFTS_FROM_LIVE_PAIR_CONTACT_SURFACE",
        "sameRuntimeAcrossAssets": True,
        "livePairSurfaceSemanticSelection": "PASS",
        "freshHandoffTransactionBinding": "PASS",
        "c469CutoffCleanupPropertyPreserved": "PASS",
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
        "storyTargetZonePrescribed": False,
        "perAssetBattleCode": False,
        "perVideoTrajectoryEngineering": False,
        "humanCinematicAcceptance": "PENDING",
        "gateClosed": False,
        "productionReadyClaimed": False,
        "cutoffRuntimeProof": cutoff,
        "surfaceTransactionRuntimeProof": surface,
        "fixtures": fixtures,
    }, sort_keys=True))


if __name__ == "__main__":
    main()
