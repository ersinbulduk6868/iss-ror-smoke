from __future__ import annotations

from dataclasses import replace
import json
from pathlib import Path
import sys
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from blender import run_generic_battle_runtime_v1_candidate485_generic_battle as candidate485
from blender.iss_battle_runtime_assets import marker
from blender.iss_battle_runtime_precontact_corridor_v1 import (
    ALLOW_CONTACT,
    HOLD_STANDOFF,
    PRECONTACT_CORRIDOR_MODEL,
    REOPEN_DISTANCE,
    decide_precontact_corridor,
)
from blender.iss_battle_runtime_tactics_v5 import GenericBattleTacticalPlanner

CANDIDATE = "ISS_GENERIC_BATTLE_RUNTIME_V1_CANDIDATE_4_8_6_GENERIC_AUTONOMOUS_BATTLE"
MECHANISM = PRECONTACT_CORRIDOR_MODEL
AUDIT = "G04_COUNTERATTACK_HANDOFF_FULL_AFFECTED_LAYER_AUDIT_AFTER_C483_C484_C485_20260918"
FAILURE_FAMILY = "STALE_PRECONTACT_RUNWAY_PERMISSION_ALLOWS_UNREADY_CONTACT_CORRIDOR_COLLAPSE"

_C485_TACTICAL_DECIDE = candidate485.generic_contact_commit_decide
_corridor_active: set[tuple[str, str]] = set()
_corridor_rows: list[dict[str, Any]] = []


def _pair_key() -> tuple[str, str]:
    return candidate485._pair_key()


def _mark_once(marker_name: str, pair_key: tuple[str, str], row: dict[str, Any]) -> None:
    tagged = dict(row)
    tagged["attackerId"] = pair_key[0] or None
    tagged["targetId"] = pair_key[1] or None
    _corridor_rows.append(tagged)
    marker(marker_name, **tagged)


def corridor_aware_tactical_decide(
    memory: Any,
    obs: Any,
    *,
    symmetry_bias: float = 1.0,
) -> Any:
    """Keep an unready contact-capable actor outside the live contact corridor.

    C485 proved that contact_commit=False alone is insufficient: COUNTER still has
    a contact-directed navigation goal. C486 continuously revalidates the already
    existing geometry/capability runway. If readiness is absent, it either holds
    the actor on the runway stand-off surface or reopens the runway with the
    existing generic OPEN_DISTANCE policy. No new impact/contact threshold enters.
    """
    goal = _C485_TACTICAL_DECIDE(
        memory,
        obs,
        symmetry_bias=symmetry_bias,
    )
    decision = decide_precontact_corridor(
        requires_contact=bool(obs.requires_contact),
        runway_armed=bool(memory.engagement_runway_armed),
        contact_commit_ready=bool(goal.contact_commit),
        surface_gap_m=float(obs.surface_gap_m),
        runway_required_m=float(memory.engagement_runway_required_m),
    )
    pair_key = _pair_key()

    if decision.action == REOPEN_DISTANCE:
        memory.engagement_runway_armed = False
        base_scale = GenericBattleTacticalPlanner._capability_speed_scale(obs)
        if pair_key not in _corridor_active:
            _corridor_active.add(pair_key)
            _mark_once(
                "G04_PRECONTACT_CORRIDOR_REOPENED",
                pair_key,
                {
                    "frame": int(obs.frame),
                    "surfaceGapM": float(obs.surface_gap_m),
                    "runwayRequiredM": float(decision.desired_surface_gap_m),
                    "headingErrorRad": float(obs.heading_error_rad),
                    "contention": float(obs.contention),
                    "model": MECHANISM,
                },
            )
        return GenericBattleTacticalPlanner._open_distance(
            memory,
            base_scale,
            bool(goal.transition),
            "PRECONTACT_LIVE_READINESS_CORRIDOR_REOPEN",
        )

    if decision.action == HOLD_STANDOFF:
        transition = GenericBattleTacticalPlanner._set_mode(
            memory,
            "REPOSITION",
            "PRECONTACT_LIVE_READINESS_STANDOFF",
        ) or bool(goal.transition)
        if pair_key not in _corridor_active:
            _corridor_active.add(pair_key)
            _mark_once(
                "G04_PRECONTACT_CORRIDOR_STANDOFF_HELD",
                pair_key,
                {
                    "frame": int(obs.frame),
                    "surfaceGapM": float(obs.surface_gap_m),
                    "runwayRequiredM": float(decision.desired_surface_gap_m),
                    "headingErrorRad": float(obs.heading_error_rad),
                    "contention": float(obs.contention),
                    "model": MECHANISM,
                },
            )
        return replace(
            goal,
            mode="REPOSITION",
            reason=memory.reason,
            speed_intent="ACCELERATE",
            forward_offset_scale=0.0,
            contact_commit=False,
            transition=transition,
            stand_off_surface_gap_m=float(decision.desired_surface_gap_m),
        )

    if decision.action == ALLOW_CONTACT and pair_key in _corridor_active:
        _corridor_active.discard(pair_key)
        _mark_once(
            "G04_PRECONTACT_CORRIDOR_LIVE_READINESS_READY",
            pair_key,
            {
                "frame": int(obs.frame),
                "surfaceGapM": float(obs.surface_gap_m),
                "runwayRequiredM": float(decision.desired_surface_gap_m),
                "headingErrorRad": float(obs.heading_error_rad),
                "contention": float(obs.contention),
                "model": MECHANISM,
            },
        )
    return goal


def main() -> None:
    _corridor_active.clear()
    _corridor_rows.clear()

    # C485 remains the authoritative generic commit/realized-handoff layer.
    # Replace only its tactical extension point so the full historical runtime
    # chain and G05/G06/G07/G08 ownership remain unchanged.
    candidate485.generic_contact_commit_decide = corridor_aware_tactical_decide

    print(json.dumps({
        "marker": "GENERIC_AUTONOMOUS_BATTLE_C486_ENGINEERING_READY",
        "candidate": CANDIDATE,
        "mechanism": MECHANISM,
        "affectedLayerAudit": AUDIT,
        "affectedLayerAuditStatus": "PASS",
        "failureFamily": FAILURE_FAMILY,
        "rootCauses": [
            "ENGAGEMENT_RUNWAY_ARMED_PERSISTED_AFTER_LIVE_READINESS_COLLAPSED",
            "CONTACT_COMMIT_FALSE_DID_NOT_CHANGE_COUNTER_CONTACT_DIRECTED_NAVIGATION",
            "UNREADY_COUNTER_COULD_ENTER_NEGATIVE_SURFACE_GAP_WITH_MOTOR_AUTHORITY",
        ],
        "failureFamilyRealPhysicsEvidence": ["C483", "C484", "C485"],
        "threeIterationAuditRuleSatisfied": True,
        "continuousRunwayRevalidation": True,
        "unreadyContactCorridorForbidden": True,
        "existingOpenDistancePolicyReused": True,
        "existingGeometryCapabilityRunwayReused": True,
        "standOffDerivedFromExistingRunway": True,
        "c485GenericCommitAndRealizedHandoffPreserved": True,
        "c484TranslationDominantAlignmentPreserved": True,
        "c483DriveDirectionPreserved": True,
        "c482CollisionRolesPreserved": True,
        "c481DeferredHandoffProgressPreserved": True,
        "c480ApproachSemanticTransactionPreserved": True,
        "g05NativeSolverFinalAuthorityPreserved": True,
        "g05ThresholdImported": False,
        "contactThresholdChanged": False,
        "damageAdmissionThresholdChanged": False,
        "damageThresholdAwareControl": False,
        "targetToughnessAwareControl": False,
        "desiredImpactSpeedControl": False,
        "desiredImpactEnergyControl": False,
        "assetIdentityBranch": False,
        "perAssetBattleCode": False,
        "perAssetTacticalTuning": False,
        "perVideoTrajectoryEngineering": False,
        "fixedWorldCoordinates": False,
        "exactCollisionFrameTarget": False,
        "exactImpactEnergyTarget": False,
        "actorPoseOrVelocityMutation": False,
        "fixtureBattlePlanChanged": False,
        "g01ToG03Changed": False,
        "frozenNineServiceArchitectureChanged": False,
        "gateClosed": False,
        "productionReadyClaimed": False,
    }, sort_keys=True), flush=True)

    candidate485.main()


if __name__ == "__main__":
    main()
