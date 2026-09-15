#!/usr/bin/env python3
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

import validate_generic_battle_runtime_v1_candidate32_result as base

EXPECTED_RUNTIME = "ISS_GENERIC_BATTLE_RUNTIME_V1_CANDIDATE_3_7_1"
EXPECTED_CONSEQUENCE = "ISS_IMPACT_CONSEQUENCE_V1_1_SURFACE_AWARE"


class Candidate371ValidationError(RuntimeError):
    pass


def require(condition: bool, marker: str) -> None:
    if not condition:
        raise Candidate371ValidationError(marker)


def evidence_path() -> Path:
    args = base.args()
    return Path(args.evidence).expanduser().resolve()


def main() -> None:
    base.EXPECTED_RUNTIME = EXPECTED_RUNTIME
    base.main()

    path = evidence_path()
    evidence = json.loads(path.read_text(encoding="utf-8"))
    models = evidence.get("models") or {}
    require(models.get("consequence") == EXPECTED_CONSEQUENCE, "CONSEQUENCE_MODEL_MISMATCH")

    impacts = [row for row in (evidence.get("impacts") or []) if row.get("damageEarned") is True]
    require(bool(impacts), "EARNED_IMPACT_MISSING")

    verified_visuals = 0
    for row in impacts:
        physical = row.get("evidence") or {}
        contact_frame = int(physical.get("frame") or -1)
        visual = row.get("targetVisual") or {}
        if not visual:
            continue
        realization_frame = int(visual.get("frame") or -1)
        delay = realization_frame - contact_frame
        require(contact_frame >= 1, "PHYSICAL_CONTACT_FRAME_INVALID")
        require(realization_frame >= contact_frame, "VISUAL_REALIZATION_BACKDATED")
        require(delay <= 3, f"VISUAL_REALIZATION_DELAY_TOO_LARGE:{delay}")
        require(int(visual.get("affected_vertices") or 0) > 0, "VISUAL_AFFECTED_VERTICES_ZERO")
        require(float(visual.get("max_deformation_m") or 0.0) > 0.0, "VISUAL_DEFORMATION_ZERO")
        require(int(visual.get("debris_count") or 0) >= 2, "VISUAL_DEBRIS_COUNT_TOO_LOW")
        require(visual.get("realization") == EXPECTED_CONSEQUENCE, "VISUAL_REALIZATION_MODEL_MISMATCH")
        verified_visuals += 1

    require(verified_visuals >= 1, "NO_TRUTHFUL_VISUAL_CONSEQUENCE_RECEIPT")

    target = ((evidence.get("actors") or {}).get("actor_beta") or {}).get("state") or {}
    damage_events = target.get("damageEvents") or []
    physical_frames = {
        int((row.get("evidence") or {}).get("frame") or -1)
        for row in impacts
    }
    require(
        any(int(row.get("frame") or -1) in physical_frames for row in damage_events),
        "PERSISTENT_DAMAGE_FRAME_NOT_PHYSICAL_CONTACT_FRAME",
    )

    visual_evidence = ((evidence.get("actors") or {}).get("actor_beta") or {}).get("visualEvidence") or []
    require(bool(visual_evidence), "TARGET_VISUAL_EVIDENCE_MISSING")
    require(
        any(row.get("model") == EXPECTED_CONSEQUENCE for row in visual_evidence),
        "TARGET_VISUAL_MODEL_MISMATCH",
    )

    print(json.dumps({
        "marker": "GENERIC_BATTLE_RUNTIME_CANDIDATE371_MACHINE_PREFLIGHT",
        "status": "PASS",
        "runtime": EXPECTED_RUNTIME,
        "consequenceModel": EXPECTED_CONSEQUENCE,
        "verifiedVisualReceipts": verified_visuals,
        "gateInheritance": "CANDIDATE32_FULL_MACHINE_TRUTH_PLUS_TRANSFORM_SURFACE_TEMPORAL_DAMAGE_HARDENING",
        "nextGate": "HUMAN_VISUAL_REVIEW",
    }, sort_keys=True))


if __name__ == "__main__":
    main()
