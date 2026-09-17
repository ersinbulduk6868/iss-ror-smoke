#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path


def _load(path: str):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def _validate(label: str, battle_path: str, g06_path: str, g07_path: str, g08_path: str) -> dict[str, object]:
    battle = _load(battle_path)
    g06 = _load(g06_path)
    g07 = _load(g07_path)
    g08 = _load(g08_path)

    assert battle.get("battleControlModel") == "ISS_GENERIC_AUTONOMOUS_BATTLE_CONTROL_V2", (label, battle)
    assert battle.get("tacticalModel") == "ISS_GENERIC_ADAPTIVE_BATTLE_TACTICS_V2", (label, battle)
    modes = set((battle.get("modeCounts") or {}).keys())
    required_modes = {"ENGAGE", "BREAK_CONTACT", "REPOSITION", "COUNTER"}
    assert required_modes <= modes, (label, "TACTICAL_MODES_MISSING", sorted(required_modes - modes), sorted(modes))
    cycles = battle.get("maxBattleCycleByActor") or {}
    assert cycles and max(int(value) for value in cycles.values()) >= 1, (label, "NO_REALIZED_BATTLE_CYCLE", cycles)
    assert battle.get("sameRuntimeAcrossAssets") is True
    assert battle.get("liveWorldStateDriven") is True
    assert battle.get("actorProfileCapabilityDriven") is True
    assert battle.get("perAssetBattleCode") is False
    assert battle.get("perVideoTrajectoryEngineering") is False
    assert battle.get("actorPoseOrVelocityMutation") is False

    impacts = g06.get("g05BoundImpacts") or []
    direct = [row for row in impacts if not row.get("inherited")]
    assert direct, (label, "NO_DIRECT_G05_IMPACTS")
    assert all((row.get("nativeContactReceipt") or {}).get("status") == "VERIFIED" for row in direct), (label, "G05_RECEIPT_NOT_VERIFIED")
    assert all((row.get("nativeContactReceipt") or {}).get("model") == "RECIPROCAL_NATIVE_SOLVER_RESPONSE_V1" for row in direct), (label, "G05_CONTACT_AUTHORITY_DRIFT")

    actors = g06.get("finalActors") or {}
    assert actors, (label, "NO_FINAL_ACTORS")
    visible: list[tuple[str, dict]] = []
    debris = 0
    max_normalized_deformation = 0.0
    damaged_actor_count = 0
    for actor_id, row in actors.items():
        state = row.get("state") or {}
        visual = row.get("visual") or {}
        if int(state.get("damageEventCount") or 0) > 0:
            damaged_actor_count += 1
        for evidence in visual.get("damageVisualEvidence") or []:
            if evidence.get("model") != "ISS_CAUSAL_VISIBLE_IMPACT_CONSEQUENCE_V2":
                continue
            visible.append((actor_id, evidence))
            debris += int(evidence.get("debrisCount") or 0)
            max_normalized_deformation = max(
                max_normalized_deformation,
                float(evidence.get("normalizedDeformation") or 0.0),
            )
    assert damaged_actor_count >= 2, (label, "TWO_SIDED_DAMAGE_NOT_PRESERVED", damaged_actor_count)
    assert visible, (label, "V2_VISIBLE_CONSEQUENCE_NOT_OBSERVED")
    assert max_normalized_deformation >= 0.02, (label, "VISIBLE_DEFORMATION_TOO_SMALL", max_normalized_deformation)
    assert debris >= 2, (label, "VISIBLE_DEBRIS_NOT_REALIZED", debris)

    assert g07.get("status") == "COMPLETE", (label, "DRAMA_INCOMPLETE", g07.get("status"))
    for key in ("escalation", "counterattack", "reversal", "climax", "payoff"):
        assert g07.get(key) is not None, (label, "DRAMA_STAGE_MISSING", key)

    assert g08.get("cinematicSaliencePass") is True, (label, "CAMERA_SALIENCE_FAIL")
    assert g08.get("humanCinematicAcceptance") == "PENDING", (label, "HUMAN_REVIEW_MUST_REMAIN_PENDING")

    return {
        "label": label,
        "modes": sorted(modes),
        "battleCycles": cycles,
        "directG05Impacts": len(direct),
        "visibleConsequenceEvents": len(visible),
        "debrisCount": debris,
        "maxNormalizedDeformation": max_normalized_deformation,
        "g07": "COMPLETE",
        "g08MachineSalience": "PASS",
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    for prefix in ("bugatti", "generic"):
        for key in ("battle", "g06", "g07", "g08"):
            parser.add_argument(f"--{prefix}-{key}", required=True)
    args = parser.parse_args()

    rows = []
    for prefix in ("bugatti", "generic"):
        rows.append(
            _validate(
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
                "marker": "GENERIC_AUTONOMOUS_BATTLE_C460_MACHINE_ACCEPTANCE",
                "status": "PASS",
                "sameRuntimeAcrossAssets": True,
                "sportsAndHeavyPropertyAcceptance": "PASS",
                "nativeContactAuthorityPreserved": True,
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
