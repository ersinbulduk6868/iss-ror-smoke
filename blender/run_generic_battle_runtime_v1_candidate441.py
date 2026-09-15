from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from blender import run_generic_battle_runtime_v1_candidate44 as candidate44
from blender.iss_battle_runtime_assets import BlenderBattleRuntimeError, marker

CANDIDATE = "ISS_GENERIC_BATTLE_RUNTIME_V1_CANDIDATE_4_4_1_G07"
DRAMA_MODEL = "PHYSICAL_CAUSAL_DRAMA_STATE_MACHINE_V1"
DOMINANCE_MODEL = "LATEST_UNIQUE_DIRECT_G05_PHYSICAL_INITIATIVE_V2"

_ORIGINAL_RESET = candidate44.CausalDramaTracker.reset


def _initiative_frames(tracker: Any) -> dict[str, int]:
    value = getattr(tracker, "_g07_v2_latest_initiative_frame", None)
    if not isinstance(value, dict):
        value = {}
        setattr(tracker, "_g07_v2_latest_initiative_frame", value)
    return value


def g07_v2_reset(self: Any) -> None:
    _ORIGINAL_RESET(self)
    setattr(self, "_g07_v2_latest_initiative_frame", {})


def g07_v2_dominance_snapshot(self: Any, actors: dict[str, Any], frame: int) -> dict[str, Any]:
    initiative = _initiative_frames(self)
    rows: dict[str, Any] = {}
    for actor_id, actor in sorted(actors.items()):
        rows[actor_id] = {
            "directDamagePressureInflicted": float(self.direct_pressure.get(actor_id, 0.0)),
            "directDamagePressureReceived": float(self.received_pressure.get(actor_id, 0.0)),
            "directDamageHitCount": int(self.direct_hit_count.get(actor_id, 0)),
            "latestDirectDamageFrame": self.latest_direct_damage_frame.get(actor_id),
            "latestDirectInitiativeFrame": initiative.get(actor_id),
            "state": self._actor_state(actor),
        }
    latest = {
        actor_id: int(row["latestDirectInitiativeFrame"])
        for actor_id, row in rows.items()
        if row["latestDirectInitiativeFrame"] is not None
    }
    leader: str | None = None
    if latest:
        newest = max(latest.values())
        leaders = sorted(actor_id for actor_id, tx_frame in latest.items() if tx_frame == newest)
        if len(leaders) == 1:
            leader = leaders[0]
    return {
        "frame": int(frame),
        "leader": leader,
        "authority": DOMINANCE_MODEL,
        "rows": rows,
    }


def g07_v2_note_transaction(
    self: Any,
    row: dict[str, Any],
    event: Any,
    actors: dict[str, Any],
) -> None:
    if row.get("nativeContactAuthority") is not True:
        return
    receipt = row.get("nativeContactReceipt")
    if not isinstance(receipt, dict) or receipt.get("status") != "VERIFIED":
        return
    if receipt.get("model") != candidate44.candidate42.CONTACT_AUTHORITY:
        raise BlenderBattleRuntimeError(
            f"G07_CONTACT_AUTHORITY_MODEL_INVALID:{row.get('eventId')}:{receipt.get('model')}"
        )
    if row.get("nativeContactInheritedFromPhysicalTransaction") is True:
        return
    evidence = row.get("evidence")
    if not isinstance(evidence, dict):
        return

    frame = int(receipt.get("contactFrame") or evidence.get("frame") or -1)
    attacker_id = str(evidence.get("attacker_id") or "")
    target_id = str(evidence.get("target_id") or "")
    if not attacker_id or not target_id or frame < 0:
        return
    transaction_key = "|".join(
        [
            str(row.get("physicalTransactionEventId") or row.get("eventId") or ""),
            str(frame),
            attacker_id,
            target_id,
        ]
    )
    if transaction_key in self.seen_transactions:
        return
    self.seen_transactions.add(transaction_key)

    severity = float(evidence.get("severity") or 0.0)
    damage_earned = bool(row.get("damageEarned"))
    phase = candidate44._phase(event)
    attacker = actors.get(attacker_id)
    prior_damage = bool(
        attacker is not None
        and candidate44._prior_damage_from(attacker, target_id, before_frame=frame)
    )

    initiative_qualified = False
    initiative_reason = "NOT_DRAMATIC_INITIATIVE"
    if phase in {"FIRST_ATTACK", "ESCALATION"} and damage_earned:
        initiative_qualified = True
        initiative_reason = "OPENING_G05_G06_PERSISTENT_DAMAGE"
    elif phase == "COUNTERATTACK" and prior_damage:
        initiative_qualified = True
        initiative_reason = "DIRECT_G05_COUNTER_AFTER_PRIOR_G06_DAMAGE"
    elif phase == "CLIMAX" and self.reversal is not None:
        initiative_qualified = True
        initiative_reason = "DIRECT_G05_CLIMAX_AFTER_REVERSAL"

    tx = {
        "transactionKey": transaction_key,
        "eventId": str(event.event_id),
        "phase": phase,
        "frame": frame,
        "attackerId": attacker_id,
        "targetId": target_id,
        "severity": severity,
        "damageEarned": damage_earned,
        "attackerPreviouslyDamagedByTarget": prior_damage,
        "physicalInitiativeQualified": initiative_qualified,
        "physicalInitiativeReason": initiative_reason,
        "g05ReceiptStatus": "VERIFIED",
        "g05ContactAuthorityModel": candidate44.candidate42.CONTACT_AUTHORITY,
        "inheritedReciprocalAlias": False,
    }
    self.direct_transactions.append(tx)

    if damage_earned:
        self.direct_pressure[attacker_id] = float(self.direct_pressure.get(attacker_id, 0.0)) + severity
        self.received_pressure[target_id] = float(self.received_pressure.get(target_id, 0.0)) + severity
        self.direct_hit_count[attacker_id] = int(self.direct_hit_count.get(attacker_id, 0)) + 1
        self.latest_direct_damage_frame[attacker_id] = frame

    if not initiative_qualified:
        return

    _initiative_frames(self)[attacker_id] = frame
    snapshot = self.dominance_snapshot(actors, frame)

    if phase in {"FIRST_ATTACK", "ESCALATION"}:
        if not damage_earned:
            raise BlenderBattleRuntimeError("G07_OPENING_INITIATIVE_WITHOUT_G06_DAMAGE")
        if self.escalation is None:
            self.escalation = self._transition(
                "ESCALATION_PHYSICALLY_EARNED",
                frame,
                eventId=event.event_id,
                attackerId=attacker_id,
                targetId=target_id,
                transactionKey=transaction_key,
                authority="G05_VERIFIED_PLUS_G06_DAMAGE",
            )
        if self.initial_dominant_actor is None and snapshot.get("leader"):
            self.initial_dominant_actor = str(snapshot["leader"])
            self.initial_dominance_frame = frame
            self.initial_dominance_snapshot = candidate44._json_copy(snapshot)
            self._transition(
                "INITIAL_PHYSICAL_DOMINANCE_ESTABLISHED",
                frame,
                actorId=self.initial_dominant_actor,
                transactionKey=transaction_key,
                authority=DOMINANCE_MODEL,
            )
        return

    if phase == "COUNTERATTACK" and prior_damage:
        if self.counterattack is None:
            self.counterattack = self._transition(
                "COUNTERATTACK_CAUSALLY_EARNED",
                frame,
                eventId=event.event_id,
                attackerId=attacker_id,
                targetId=target_id,
                transactionKey=transaction_key,
                damageEarned=damage_earned,
                authority="DIRECT_G05_VERIFIED_AFTER_PRIOR_G06_DAMAGE",
            )
        leader = snapshot.get("leader")
        if (
            self.reversal is None
            and self.initial_dominant_actor is not None
            and leader is not None
            and str(leader) != self.initial_dominant_actor
            and attacker_id == str(leader)
            and frame > int(self.initial_dominance_frame or -1)
        ):
            self.reversal = self._transition(
                "DOMINANCE_REVERSAL_COMEBACK_PHYSICALLY_EARNED",
                frame,
                fromActorId=self.initial_dominant_actor,
                toActorId=str(leader),
                eventId=event.event_id,
                transactionKey=transaction_key,
                damageEarned=damage_earned,
                dominance=candidate44._json_copy(snapshot),
                authority=DOMINANCE_MODEL,
            )
        return

    if phase == "CLIMAX" and self.reversal is not None and self.climax is None:
        self.climax = self._transition(
            "CLIMAX_PHYSICALLY_EARNED",
            frame,
            eventId=event.event_id,
            attackerId=attacker_id,
            targetId=target_id,
            transactionKey=transaction_key,
            damageEarned=damage_earned,
            reversalFrame=int(self.reversal["frame"]),
            authority="DIRECT_G05_VERIFIED_AFTER_REVERSAL",
        )


def main() -> None:
    candidate44.CANDIDATE = CANDIDATE
    candidate44.DRAMA_MODEL = DRAMA_MODEL
    candidate44.DOMINANCE_MODEL = DOMINANCE_MODEL
    candidate44.CausalDramaTracker.reset = g07_v2_reset
    candidate44.CausalDramaTracker.dominance_snapshot = g07_v2_dominance_snapshot
    candidate44.CausalDramaTracker.note_transaction = g07_v2_note_transaction

    print(
        json.dumps(
            {
                "marker": "GENERIC_BATTLE_RUNTIME_CANDIDATE441_G07_ENGINEERING_PASS",
                "candidate": CANDIDATE,
                "dramaModel": DRAMA_MODEL,
                "dominanceModel": DOMINANCE_MODEL,
                "openingPersistentDamageRequired": True,
                "laterInitiativeRequiresDirectG05VerifiedPhysicalTransaction": True,
                "repeatedDamageThresholdCrossingRequired": False,
                "g04AutonomySourceChanged": False,
                "g05ContactAuthoritySourceChanged": False,
                "g06PersistenceSourceChanged": False,
                "damageThresholdChanged": False,
                "contactThresholdChanged": False,
                "actorPoseOrVelocityMutation": False,
                "stateResetMechanismIntroduced": False,
                "forcedWinnerIntroduced": False,
                "assetSpecificBattleCode": False,
                "exactCollisionFrameTarget": False,
                "exactImpactEnergyTarget": False,
                "productionReadyClaimed": False,
            },
            sort_keys=True,
        ),
        flush=True,
    )
    candidate44.main()


if __name__ == "__main__":
    main()
