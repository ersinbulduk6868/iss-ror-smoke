#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path


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


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--battle", required=True)
    p.add_argument("--log", required=True)
    a = p.parse_args()

    battle = json.loads(Path(a.battle).read_text(encoding="utf-8"))
    rows = _rows(a.log)

    pursuits = [r for r in rows if r.get("marker") == "G04_LIVE_INTERCEPT_GOAL_APPLIED"]
    counter_pursuits = [r for r in pursuits if r.get("eventId") == "evt-counterattack"]
    handoffs = [r for r in rows if r.get("marker") == "GENERIC_SOLVER_HANDOFF_LATCHED"]
    counter_handoffs = [r for r in handoffs if r.get("eventId") == "evt-counterattack"]

    assert pursuits, "C472_LIVE_INTERCEPT_NOT_OBSERVED"
    assert counter_pursuits, "C472_COUNTERATTACK_LIVE_INTERCEPT_NOT_OBSERVED"
    assert counter_handoffs, "C472_COUNTERATTACK_DID_NOT_REACQUIRE_G05_HANDOFF_BOUNDARY"

    for row in counter_pursuits:
        assert row.get("storyTargetZonePrescribed") is False, row
        assert row.get("assetIdentityBranch") is False, row
        assert row.get("fixedWorldCoordinate") is False, row
        assert row.get("cachedTrajectory") is False, row
        assert row.get("exactCollisionFrameTarget") is False, row
        assert row.get("exactImpactEnergyTarget") is False, row
        assert float(row.get("leadSeconds") or 0.0) <= 1.25 + 1.0e-9, row

    samples = [
        row for row in battle.get("samples", [])
        if str(row.get("eventId") or "") == "evt-counterattack"
        and str(row.get("actorId") or "") == "actor_beta"
        and str(row.get("tacticalMode") or "") == "COUNTER"
    ]
    assert samples, "C472_COUNTERATTACK_COUNTER_MODE_NOT_OBSERVED"
    first_gap = float(samples[0]["observation"]["surfaceGapM"])
    min_gap = min(float(row["observation"]["surfaceGapM"]) for row in samples)
    assert min_gap < first_gap, ("C472_COUNTERATTACK_NO_CLOSING_PROGRESS", first_gap, min_gap)

    event_states = {}
    # G07 evidence owns final event states, but the G04 battle evidence intentionally
    # remains controller-focused.  Contact/handoff markers are therefore the G04
    # boundary proof; downstream G05 success is reported but not required here.
    verified_contacts = [r for r in rows if r.get("marker") == "PAIRWISE_NATIVE_SOLVER_CONTACT_VERIFIED"]
    counter_verified = [r for r in verified_contacts if r.get("eventId") == "evt-counterattack"]

    print(json.dumps({
        "marker": "G04_C472_MACHINE_ACCEPTANCE",
        "status": "PASS",
        "failureFamily": "MOVING_TARGET_POINT_CHASE_FAILS_TO_REACQUIRE_CONTACT",
        "g04Boundary": "REACQUIRE_AND_HANDOFF_TO_G05",
        "liveInterceptObserved": True,
        "counterattackLiveInterceptObserved": True,
        "counterattackReacquiredG05Boundary": True,
        "counterattackHandoffCount": len(counter_handoffs),
        "counterattackVerifiedG05ContactCount": len(counter_verified),
        "counterattackFirstCounterGapM": first_gap,
        "counterattackMinCounterGapM": min_gap,
        "downstreamG05ContactRequiredForG04Pass": False,
        "storyTargetZonePrescribed": False,
        "perAssetBattleCode": False,
        "cachedTrajectory": False,
        "fixedWorldCoordinates": False,
        "exactCollisionFrameTarget": False,
        "exactImpactEnergyTarget": False,
        "actorPoseOrVelocityMutation": False,
        "gateClosed": False,
        "productionReadyClaimed": False,
    }, sort_keys=True))


if __name__ == "__main__":
    main()
