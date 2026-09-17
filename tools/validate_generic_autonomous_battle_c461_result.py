#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path

from tools import validate_generic_autonomous_battle_c460_result as c460


def _load(path: str):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def _validate_c461(label: str, battle_path: str, g06_path: str, g07_path: str, g08_path: str) -> dict[str, object]:
    row = c460._validate(label, battle_path, g06_path, g07_path, g08_path)
    battle = _load(battle_path)
    g06 = _load(g06_path)

    samples = battle.get("samples") or []
    counter = [s for s in samples if str(s.get("eventId") or "") == "evt-counterattack"]
    assert counter, (label, "COUNTERATTACK_TACTICAL_EVIDENCE_MISSING")

    first_by_actor: dict[str, dict] = {}
    for sample in sorted(counter, key=lambda s: int(s.get("frame") or 0)):
        actor_id = str(sample.get("actorId") or "")
        if actor_id and actor_id not in first_by_actor:
            first_by_actor[actor_id] = sample
    assert first_by_actor, (label, "COUNTERATTACK_ACTOR_EVIDENCE_MISSING")
    assert any(
        str(sample.get("tacticalMode") or "") == "COUNTER" and sample.get("contactCommit") is True
        for sample in first_by_actor.values()
    ), (label, "COUNTERATTACK_DID_NOT_BEGIN_FROM_CURRENT_INTENT", first_by_actor)
    assert all(
        not (
            str(sample.get("tacticalMode") or "") == "BREAK_CONTACT"
            and str(sample.get("tacticalReason") or "") == "REALIZED_CONTACT_OR_DAMAGE"
        )
        for sample in first_by_actor.values()
    ), (label, "STALE_PRIOR_EVENT_DAMAGE_TRIGGERED_BREAK_CONTACT", first_by_actor)

    impacts = g06.get("g05BoundImpacts") or []
    direct = [impact for impact in impacts if not impact.get("inherited")]
    event_ids = {str(impact.get("eventId") or "") for impact in direct}
    assert len(direct) >= 2, (label, "SECOND_NATIVE_CONTACT_NOT_PROVEN", len(direct), direct)
    assert "evt-counterattack" in event_ids, (label, "COUNTERATTACK_NATIVE_CONTACT_NOT_PROVEN", sorted(event_ids))
    assert all((impact.get("nativeContactReceipt") or {}).get("status") == "VERIFIED" for impact in direct)
    assert all((impact.get("nativeContactReceipt") or {}).get("model") == "RECIPROCAL_NATIVE_SOLVER_RESPONSE_V1" for impact in direct)

    row.update(
        {
            "eventScopedTacticalMemory": "PASS",
            "priorEventDamageBaselined": "PASS",
            "counterattackStartsFromCurrentIntent": "PASS",
            "secondNativeContact": "PASS",
            "directImpactEventIds": sorted(event_ids),
        }
    )
    return row


def main() -> None:
    parser = argparse.ArgumentParser()
    for prefix in ("bugatti", "generic"):
        for key in ("battle", "g06", "g07", "g08"):
            parser.add_argument(f"--{prefix}-{key}", required=True)
    args = parser.parse_args()

    rows = []
    for prefix in ("bugatti", "generic"):
        rows.append(
            _validate_c461(
                prefix,
                getattr(args, f"{prefix}_battle"),
                getattr(args, f"{prefix}_g06"),
                getattr(args, f"{prefix}_g07"),
                getattr(args, f"{prefix}_g08"),
            )
        )

    print(
        json.dumps(
            {
                "marker": "GENERIC_AUTONOMOUS_BATTLE_C461_MACHINE_ACCEPTANCE",
                "status": "PASS",
                "sameRuntimeAcrossAssets": True,
                "eventScopedTacticalMemory": True,
                "priorEventDamageBaselined": True,
                "counterattackStartsFromCurrentIntent": True,
                "secondNativeContact": "PASS",
                "nativeContactAuthorityPreserved": True,
                "recipientVisualLocalization": "PASS",
                "g05ContactTruthRewritten": False,
                "damageAdmissionThresholdChanged": False,
                "contactThresholdChanged": False,
                "continuousBattleCycle": "PASS",
                "visibleCausalDamageDebris": "PASS",
                "g07AdaptiveCausalDrama": "PASS",
                "g08MachineObservability": "PASS",
                "humanCinematicAcceptance": "PENDING",
                "gateClosed": False,
                "productionReadyClaimed": False,
                "fixtures": rows,
            },
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
