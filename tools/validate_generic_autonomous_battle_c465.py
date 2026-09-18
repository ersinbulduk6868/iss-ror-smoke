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
from blender.iss_battle_runtime_handoff_v2 import (
    CUTOFF_FRAME_AUTHORITY_MODEL,
    stabilize_active_handoff_cutoff_frames,
)

WRAPPER = ROOT / "blender" / "run_generic_battle_runtime_v1_candidate465_generic_battle.py"
HELPER = ROOT / "blender" / "iss_battle_runtime_handoff_v2.py"
FORBIDDEN_ASSET_TOKENS = ("bugatti", "bulldozer", "ferrari")


def _pure_cutoff_immutability() -> dict[str, object]:
    key = ("evt-escalation", "actor_alpha")
    latch = SolverHandoffLatch(
        start_frame=182,
        contact_count_at_latch=0,
        handoff_gap_m=0.172466,
        last_surface_gap_m=0.098305,
    )
    cutoffs: dict[tuple[str, str], int] = {key: 182}
    latches = {key: latch}
    observed: list[dict[str, object]] = []

    for heartbeat_frame in (183, 189, 200, 211, 216):
        # Reproduce the C464 failure mechanism: the latched COAST path rewrites
        # the cutoff as if each heartbeat were a fresh authority release.
        cutoffs[key] = heartbeat_frame
        changes = stabilize_active_handoff_cutoff_frames(cutoffs, latches)
        assert cutoffs[key] == 182, (heartbeat_frame, cutoffs[key])
        assert len(changes) == 1
        change = changes[0]
        assert change["previousCutoffFrame"] == heartbeat_frame
        assert change["authoritativeCutoffFrame"] == 182
        observed.append(dict(change))

    # A genuinely new handoff is allowed to establish a new cutoff frame.
    relatch = SolverHandoffLatch(
        start_frame=802,
        contact_count_at_latch=0,
        handoff_gap_m=0.059364,
        last_surface_gap_m=-1.054549,
    )
    cutoffs[key] = 802
    changes = stabilize_active_handoff_cutoff_frames(cutoffs, {key: relatch})
    assert cutoffs[key] == 802
    assert changes == ()

    return {
        "firstLatchAuthoritativeCutoffFrame": 182,
        "heartbeatFramesCorrected": [183, 189, 200, 211, 216],
        "newLatchAuthoritativeCutoffFrame": 802,
        "corrections": observed,
    }


def _static_scope() -> None:
    for path in (WRAPPER, HELPER):
        text = path.read_text(encoding="utf-8")
        ast.parse(text, filename=str(path))
        lowered = text.lower()
        for token in FORBIDDEN_ASSET_TOKENS:
            assert token not in lowered, (path.name, token)

    wrapper = WRAPPER.read_text(encoding="utf-8")
    helper = HELPER.read_text(encoding="utf-8")

    for required in (
        'CANDIDATE = "ISS_GENERIC_BATTLE_RUNTIME_V1_CANDIDATE_4_6_5_GENERIC_AUTONOMOUS_BATTLE"',
        '"marker": "GENERIC_AUTONOMOUS_BATTLE_C465_ENGINEERING_READY"',
        '"handoffCutoffFrameImmutableWithinLatch": True',
        '"g05ControllerAuthorityContractPreserved": True',
        '"damageAdmissionThresholdChanged": False',
        '"contactThresholdChanged": False',
        '"semanticToleranceChanged": False',
        '"localityToleranceChanged": False',
        '"fixtureMutationForAcceptance": False',
        '"gateClosed": False',
    ):
        assert required in wrapper, required

    assert "stabilize_active_handoff_cutoff_frames" in wrapper
    assert "battle_v6.set_controls(" in wrapper
    assert wrapper.index("battle_v6.set_controls(") < wrapper.index("stabilize_active_handoff_cutoff_frames(")

    assert 'CUTOFF_FRAME_AUTHORITY_MODEL = "EVENT_LOCAL_HANDOFF_START_FRAME_IMMUTABILITY_V1"' in helper
    assert "cutoff_frames[key] = authoritative" in helper
    for forbidden in (
        "MIN_DAMAGE_SEVERITY",
        "semantic_tolerance",
        "locality_tolerance",
        "impact_energy",
        "target_toughness",
        "collision_point",
        "trajectory",
    ):
        assert forbidden not in helper, forbidden


def main() -> None:
    _static_scope()
    proof = _pure_cutoff_immutability()
    print(json.dumps({
        "marker": "GENERIC_AUTONOMOUS_BATTLE_C465_PROPERTY_ACCEPTANCE",
        "status": "PASS",
        "affectedLayerAudit": "PASS",
        "failureFamily": "HANDOFF_CUTOFF_FRAME_REWRITTEN_AFTER_NATIVE_CONTACT_FRAME",
        "cutoffFrameAuthorityModel": CUTOFF_FRAME_AUTHORITY_MODEL,
        "handoffCutoffFrameImmutableWithinLatch": True,
        "newHandoffCanEstablishNewCutoff": True,
        "g05ControllerAuthorityContractPreserved": True,
        "damageAdmissionThresholdChanged": False,
        "contactThresholdChanged": False,
        "semanticToleranceChanged": False,
        "localityToleranceChanged": False,
        "fixtureMutationForAcceptance": False,
        "perAssetBattleCode": False,
        "perVideoTrajectoryEngineering": False,
        "gateClosed": False,
        "proof": proof,
    }, sort_keys=True))


if __name__ == "__main__":
    main()
