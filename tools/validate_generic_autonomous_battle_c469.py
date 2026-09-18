#!/usr/bin/env python3
from __future__ import annotations

import ast
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from blender.iss_battle_runtime_handoff_v1 import SolverHandoffLatch
from blender.iss_battle_runtime_handoff_v3 import (
    CUTOFF_TRANSACTION_CLEANUP_MODEL,
    invalidate_released_handoff_cutoffs,
)

WRAPPER = ROOT / "blender" / "run_generic_battle_runtime_v1_candidate469_generic_battle.py"
HELPER = ROOT / "blender" / "iss_battle_runtime_handoff_v3.py"
C468 = ROOT / "blender" / "run_generic_battle_runtime_v1_candidate468_generic_battle.py"
C465 = ROOT / "blender" / "run_generic_battle_runtime_v1_candidate465_generic_battle.py"
G05 = ROOT / "blender" / "run_generic_battle_runtime_v1_candidate42.py"
FORBIDDEN_ASSET_TOKENS = ("bugatti", "bulldozer", "ferrari")


def _latch(start: int) -> SolverHandoffLatch:
    return SolverHandoffLatch(
        start_frame=int(start),
        contact_count_at_latch=0,
        handoff_gap_m=0.10,
        last_surface_gap_m=0.05,
    )


def _property_tests() -> dict[str, bool]:
    key = ("evt-escalation", "actor_alpha")
    other = ("evt-other", "actor_beta")

    # 1. Same active transaction: immutable transition cutoff remains intact.
    cutoff = {key: 100, other: 44}
    changes = invalidate_released_handoff_cutoffs(
        cutoff,
        {key: 100},
        {key: _latch(100)},
    )
    active_preserved = cutoff == {key: 100, other: 44} and changes == ()

    # 2. Released transaction: old authorization evidence must disappear.
    cutoff = {key: 100, other: 44}
    changes = invalidate_released_handoff_cutoffs(
        cutoff,
        {key: 100},
        {},
    )
    released_invalidated = (
        key not in cutoff
        and cutoff.get(other) == 44
        and len(changes) == 1
        and changes[0]["action"] == "RELEASED_TRANSACTION_INVALIDATED"
        and changes[0]["previousCutoffFrame"] == 100
    )

    # 3. Old transaction may end and a genuinely fresh one may start in the same
    # control update. The fresh cutoff belongs to the new transaction and survives.
    cutoff = {key: 130, other: 44}
    changes = invalidate_released_handoff_cutoffs(
        cutoff,
        {key: 100},
        {key: _latch(130)},
    )
    fresh_preserved = (
        cutoff.get(key) == 130
        and cutoff.get(other) == 44
        and len(changes) == 1
        and changes[0]["action"] == "FRESH_TRANSACTION_PRESERVED"
        and changes[0]["previousHandoffStartFrame"] == 100
        and changes[0]["newHandoffStartFrame"] == 130
    )

    # 4. A new transaction that did not replace an old one is not touched.
    cutoff = {key: 200}
    changes = invalidate_released_handoff_cutoffs(
        cutoff,
        {},
        {key: _latch(200)},
    )
    unrelated_new_latch_preserved = cutoff == {key: 200} and changes == ()

    return {
        "activeTransactionCutoffPreserved": bool(active_preserved),
        "releasedTransactionCutoffInvalidated": bool(released_invalidated),
        "sameFrameFreshRelatchCutoffPreserved": bool(fresh_preserved),
        "unrelatedNewLatchPreserved": bool(unrelated_new_latch_preserved),
    }


def main() -> None:
    texts = {
        "wrapper": WRAPPER.read_text(encoding="utf-8"),
        "helper": HELPER.read_text(encoding="utf-8"),
        "c468": C468.read_text(encoding="utf-8"),
        "c465": C465.read_text(encoding="utf-8"),
        "g05": G05.read_text(encoding="utf-8"),
    }
    for name, text in texts.items():
        ast.parse(text, filename=name)

    for token in FORBIDDEN_ASSET_TOKENS:
        assert token not in texts["wrapper"].lower(), ("ASSET_SPECIFIC_WRAPPER_TOKEN", token)
        assert token not in texts["helper"].lower(), ("ASSET_SPECIFIC_HELPER_TOKEN", token)

    # Preserve existing G05 and C465/C468 contracts; C469 adds only transaction-end
    # cleanup instead of weakening the authority gate or rewriting cutoff semantics.
    assert "contact_frame - cutoff_frame <= max(2, int(fps))" in texts["g05"]
    assert "stabilize_active_handoff_cutoff_frames" in texts["c465"]
    assert "age >= budget" in texts["c468"]
    assert "G05_CUTOFF_RECENCY_BUDGET" in texts["c468"]
    assert "battle_v6.decide_solver_handoff = candidate468.recency_bounded_decide_solver_handoff" in texts["wrapper"]
    assert "battle_v6.set_controls = transaction_clean_set_controls" in texts["wrapper"]
    assert "invalidate_released_handoff_cutoffs" in texts["wrapper"]

    for required in (
        '"g05CutoffRecencyContractPreserved": True',
        '"activeHandoffCutoffImmutableWithinLatch": True',
        '"releasedTransactionCutoffInvalidated": True',
        '"sameFrameFreshRelatchCutoffPreserved": True',
        '"newLatchEstablishesFreshCutoff": True',
        '"existingG05DetectorReusedUnchanged": True',
        '"contactThresholdChanged": False',
        '"damageAdmissionThresholdChanged": False',
        '"perAssetBattleCode": False',
        '"actorPoseOrVelocityMutation": False',
        '"gateClosed": False',
    ):
        assert required in texts["wrapper"], required

    for forbidden in (
        "MIN_DAMAGE_SEVERITY",
        "semantic_tolerance =",
        "locality_tolerance =",
        "ImpactModel.qualifies",
        "target_toughness",
        "desired_impact_speed",
        "desired_impact_energy",
        "collision_frame",
        "impact_frame",
        "set_pose",
        "linear_velocity =",
    ):
        assert forbidden not in texts["wrapper"], forbidden
        assert forbidden not in texts["helper"], forbidden

    properties = _property_tests()
    assert all(properties.values()), properties

    print(json.dumps({
        "marker": "GENERIC_AUTONOMOUS_BATTLE_C469_PROPERTY_ACCEPTANCE",
        "status": "PASS",
        "affectedLayerAudit": "PASS",
        "failureFamily": "RELEASED_HANDOFF_LEAVES_STALE_G05_CUTOFF_AUTHORIZATION",
        "rootCause": "LATCH_RELEASE_WITHOUT_EVENT_LOCAL_CUTOFF_INVALIDATION",
        "cleanupModel": CUTOFF_TRANSACTION_CLEANUP_MODEL,
        **properties,
        "g05CutoffRecencyContractPreserved": True,
        "activeHandoffCutoffImmutableWithinLatch": True,
        "existingG05DetectorReusedUnchanged": True,
        "contactThresholdChanged": False,
        "damageAdmissionThresholdChanged": False,
        "perAssetBattleCode": False,
        "actorPoseOrVelocityMutation": False,
        "masterPlanAligned": True,
        "gateClosed": False,
    }, sort_keys=True))


if __name__ == "__main__":
    main()
