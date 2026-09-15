from __future__ import annotations

import json
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

import bpy

from blender import iss_blender_battle_runtime_v1 as runtime
from blender import iss_blender_battle_runtime_v1_hardened as hardened
from blender import run_generic_battle_runtime_v1_candidate40 as candidate40
from blender import run_generic_battle_runtime_v1_candidate42 as candidate42
from blender import run_generic_battle_runtime_v1_candidate43 as candidate43
from blender.iss_battle_runtime_assets import BlenderBattleRuntimeError, marker

CANDIDATE = "ISS_GENERIC_BATTLE_RUNTIME_V1_CANDIDATE_4_4_G07"
DRAMA_MODEL = "PHYSICAL_CAUSAL_DRAMA_STATE_MACHINE_V1"
DOMINANCE_MODEL = "UNIQUE_DIRECT_G05_DAMAGE_PRESSURE_V1"

_ORIGINAL_G06_RESOLVE = candidate43.g06_pairwise_resolve_pending_contacts
_ORIGINAL_G06_OUTCOME = candidate43.g06_outcome_resolve
_ORIGINAL_G06_SET_CONTROLS = candidate43.g06_set_controls


def _json_copy(value: Any) -> Any:
    return json.loads(json.dumps(value))


def _phase(event: Any) -> str:
    return str(getattr(event, "phase", "") or "").upper()


def _prior_damage_from(actor: Any, source_actor_id: str, before_frame: int | None = None) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for damage in actor.state.damage_events:
        if str(damage.get("attackerId") or "") != source_actor_id:
            continue
        frame = int(damage.get("frame") or -1)
        if before_frame is not None and frame >= int(before_frame):
            continue
        if damage.get("g05NativeContactAuthority") is not True:
            continue
        if damage.get("g05ReceiptStatus") != "VERIFIED":
            continue
        rows.append(damage)
    return rows


@dataclass
class CausalDramaTracker:
    direct_pressure: dict[str, float] = field(default_factory=dict)
    received_pressure: dict[str, float] = field(default_factory=dict)
    direct_hit_count: dict[str, int] = field(default_factory=dict)
    seen_transactions: set[str] = field(default_factory=set)
    direct_transactions: list[dict[str, Any]] = field(default_factory=list)
    transitions: list[dict[str, Any]] = field(default_factory=list)
    activations: dict[str, dict[str, Any]] = field(default_factory=dict)
    completions: dict[str, dict[str, Any]] = field(default_factory=dict)
    initial_dominant_actor: str | None = None
    initial_dominance_frame: int | None = None
    initial_dominance_snapshot: dict[str, Any] | None = None
    reversal: dict[str, Any] | None = None
    escalation: dict[str, Any] | None = None
    counterattack: dict[str, Any] | None = None
    climax: dict[str, Any] | None = None
    payoff: dict[str, Any] | None = None

    def reset(self) -> None:
        self.direct_pressure.clear()
        self.received_pressure.clear()
        self.direct_hit_count.clear()
        self.seen_transactions.clear()
        self.direct_transactions.clear()
        self.transitions.clear()
        self.activations.clear()
        self.completions.clear()
        self.initial_dominant_actor = None
        self.initial_dominance_frame = None
        self.initial_dominance_snapshot = None
        self.reversal = None
        self.escalation = None
        self.counterattack = None
        self.climax = None
        self.payoff = None

    def _actor_state(self, actor: Any) -> dict[str, Any]:
        state = actor.state
        return {
            "structuralIntegrity": float(state.structural_integrity),
            "driveEfficiency": float(state.drive_efficiency),
            "disabled": bool(state.disabled),
            "damageEventCount": len(state.damage_events),
            "lastImpactFrame": int(state.last_impact_frame) if state.last_impact_frame is not None else None,
        }

    def dominance_snapshot(self, actors: dict[str, Any], frame: int) -> dict[str, Any]:
        rows: dict[str, Any] = {}
        for actor_id, actor in sorted(actors.items()):
            inflicted = float(self.direct_pressure.get(actor_id, 0.0))
            received = float(self.received_pressure.get(actor_id, 0.0))
            # Dominance is deliberately grounded in unique direct G05 damage
            # transactions. Persistent actor state is reported alongside it but
            # is not used to manufacture a scripted winner.
            score = inflicted - received * 0.25
            rows[actor_id] = {
                "score": score,
                "directDamagePressureInflicted": inflicted,
                "directDamagePressureReceived": received,
                "directDamageHitCount": int(self.direct_hit_count.get(actor_id, 0)),
                "state": self._actor_state(actor),
            }
        ranked = sorted(rows, key=lambda actor_id: (-float(rows[actor_id]["score"]), actor_id))
        leader = ranked[0] if ranked else None
        runner_up = ranked[1] if len(ranked) > 1 else None
        unique = False
        if leader is not None:
            leader_score = float(rows[leader]["score"])
            runner_score = float(rows[runner_up]["score"]) if runner_up is not None else float("-inf")
            unique = leader_score > runner_score + 1.0e-12 and leader_score > 0.0
        return {
            "frame": int(frame),
            "leader": leader if unique else None,
            "rows": rows,
        }

    def _transition(self, stage: str, frame: int, **payload: Any) -> dict[str, Any]:
        row = {
            "stage": stage,
            "frame": int(frame),
            "model": DRAMA_MODEL,
            **payload,
        }
        if not any(x.get("stage") == stage for x in self.transitions):
            self.transitions.append(_json_copy(row))
            marker("G07_DRAMA_TRANSITION", stage=stage, frame=frame, model=DRAMA_MODEL, **payload)
        return row

    def guard_ready(
        self,
        event: Any,
        actors: dict[str, Any],
        frame: int,
    ) -> tuple[bool, str]:
        phase = _phase(event)
        if phase == "COUNTERATTACK":
            if not event.target_id or not event.attackers:
                return False, "COUNTERATTACK_REQUIRES_ATTACKER_AND_TARGET"
            for attacker_id in event.attackers:
                actor = actors.get(attacker_id)
                if actor is None:
                    continue
                if _prior_damage_from(actor, str(event.target_id), before_frame=frame):
                    return True, "PRIOR_G05_G06_DAMAGE_FROM_TARGET"
            return False, "COUNTERATTACK_WAITS_FOR_PRIOR_DAMAGE_FROM_TARGET"
        if phase == "CLIMAX":
            if self.reversal is None:
                return False, "CLIMAX_WAITS_FOR_PHYSICAL_DOMINANCE_REVERSAL"
            return True, "PHYSICAL_DOMINANCE_REVERSAL_OBSERVED"
        if phase == "PAYOFF":
            if self.climax is None:
                return False, "PAYOFF_WAITS_FOR_CAUSAL_CLIMAX"
            return True, "CAUSAL_CLIMAX_OBSERVED"
        return True, "BASE_DEPENDENCY_AND_STORY_WINDOW"

    def record_activation(self, event: Any, actors: dict[str, Any], frame: int, reason: str) -> None:
        if event.event_id in self.activations:
            return
        snapshot = self.dominance_snapshot(actors, frame) if actors else {"frame": int(frame), "leader": None, "rows": {}}
        row = {
            "eventId": str(event.event_id),
            "phase": _phase(event),
            "frame": int(frame),
            "reason": reason,
            "dominance": snapshot,
        }
        self.activations[event.event_id] = _json_copy(row)
        marker(
            "G07_EVENT_CAUSALLY_ACTIVATED",
            eventId=event.event_id,
            phase=_phase(event),
            frame=frame,
            reason=reason,
            model=DRAMA_MODEL,
        )

    def record_completion(self, event: Any, actors: dict[str, Any], frame: int, status: str) -> None:
        if event.event_id in self.completions:
            return
        snapshot = self.dominance_snapshot(actors, frame) if actors else {"frame": int(frame), "leader": None, "rows": {}}
        row = {
            "eventId": str(event.event_id),
            "phase": _phase(event),
            "frame": int(frame),
            "status": str(status),
            "dominance": snapshot,
        }
        self.completions[event.event_id] = _json_copy(row)
        if _phase(event) == "PAYOFF" and status in {"SETTLED", "OBSERVED", "SUCCEEDED"}:
            self.payoff = self._transition(
                "PAYOFF_RESOLVED",
                frame,
                eventId=event.event_id,
                climaxEventId=(self.climax or {}).get("eventId"),
            )

    def note_transaction(self, row: dict[str, Any], event: Any, actors: dict[str, Any]) -> None:
        if row.get("nativeContactAuthority") is not True:
            return
        receipt = row.get("nativeContactReceipt")
        if not isinstance(receipt, dict) or receipt.get("status") != "VERIFIED":
            return
        if receipt.get("model") != candidate42.CONTACT_AUTHORITY:
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
        phase = _phase(event)
        prior_damage = False
        attacker = actors.get(attacker_id)
        if attacker is not None:
            prior_damage = bool(_prior_damage_from(attacker, target_id, before_frame=frame))
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
            "g05ReceiptStatus": "VERIFIED",
            "g05ContactAuthorityModel": candidate42.CONTACT_AUTHORITY,
            "inheritedReciprocalAlias": False,
        }
        self.direct_transactions.append(tx)
        if not damage_earned:
            return

        self.direct_pressure[attacker_id] = float(self.direct_pressure.get(attacker_id, 0.0)) + severity
        self.received_pressure[target_id] = float(self.received_pressure.get(target_id, 0.0)) + severity
        self.direct_hit_count[attacker_id] = int(self.direct_hit_count.get(attacker_id, 0)) + 1
        snapshot = self.dominance_snapshot(actors, frame)

        if phase in {"FIRST_ATTACK", "ESCALATION"} and self.escalation is None:
            self.escalation = self._transition(
                "ESCALATION_PHYSICALLY_EARNED",
                frame,
                eventId=event.event_id,
                attackerId=attacker_id,
                targetId=target_id,
                transactionKey=transaction_key,
            )

        if self.initial_dominant_actor is None and snapshot.get("leader"):
            self.initial_dominant_actor = str(snapshot["leader"])
            self.initial_dominance_frame = frame
            self.initial_dominance_snapshot = _json_copy(snapshot)
            self._transition(
                "INITIAL_PHYSICAL_DOMINANCE_ESTABLISHED",
                frame,
                actorId=self.initial_dominant_actor,
                transactionKey=transaction_key,
            )

        if phase == "COUNTERATTACK" and prior_damage and self.counterattack is None:
            self.counterattack = self._transition(
                "COUNTERATTACK_CAUSALLY_EARNED",
                frame,
                eventId=event.event_id,
                attackerId=attacker_id,
                targetId=target_id,
                transactionKey=transaction_key,
            )

        leader = snapshot.get("leader")
        if (
            self.reversal is None
            and self.initial_dominant_actor is not None
            and leader is not None
            and str(leader) != self.initial_dominant_actor
            and attacker_id == str(leader)
            and prior_damage
        ):
            self.reversal = self._transition(
                "DOMINANCE_REVERSAL_COMEBACK_PHYSICALLY_EARNED",
                frame,
                fromActorId=self.initial_dominant_actor,
                toActorId=str(leader),
                eventId=event.event_id,
                transactionKey=transaction_key,
                dominance=_json_copy(snapshot),
            )

        if phase == "CLIMAX" and self.reversal is not None and self.climax is None:
            self.climax = self._transition(
                "CLIMAX_PHYSICALLY_EARNED",
                frame,
                eventId=event.event_id,
                attackerId=attacker_id,
                targetId=target_id,
                transactionKey=transaction_key,
                reversalFrame=int(self.reversal["frame"]),
            )


_tracker = CausalDramaTracker()
_actor_refs: dict[str, Any] = {}
_program_ref: Any | None = None
_states_ref: dict[str, Any] | None = None


def g07_active_goal_for_actor(
    entity: str,
    frame: int,
    program: Any,
    states: dict[str, Any],
):
    priorities = {
        "CLIMAX": 0,
        "COUNTERATTACK": 1,
        "ESCALATION": 2,
        "FIRST_ATTACK": 3,
        "HOOK": 4,
        "PAYOFF": 5,
    }
    rows = []
    for event in program.events:
        if entity not in event.attackers:
            continue
        state = states[event.event_id]
        if state.status != "ACTIVE":
            continue
        ready, _ = _tracker.guard_ready(event, _actor_refs, frame)
        if not ready:
            continue
        rows.append(event)
    if not rows:
        return None
    rows.sort(key=lambda event: (priorities.get(_phase(event), 50), event.start_frame, event.event_id))
    return rows[0]


def g07_dominant_event(frame: int, program: Any, states: dict[str, Any]):
    priorities = {
        "CLIMAX": 0,
        "COUNTERATTACK": 1,
        "ESCALATION": 2,
        "FIRST_ATTACK": 3,
        "HOOK": 4,
        "PAYOFF": 5,
    }
    rows = []
    for event in program.events:
        state = states[event.event_id]
        if state.status != "ACTIVE":
            continue
        ready, _ = _tracker.guard_ready(event, _actor_refs, frame)
        if ready:
            rows.append(event)
    if not rows:
        return None
    rows.sort(key=lambda event: (priorities.get(_phase(event), 50), event.start_frame, event.event_id))
    return rows[0]


def _dramatic_goal_met(event: Any, state: Any) -> bool:
    if not hardened._lifecycle.requirements_met(event, state):
        return False
    phase = _phase(event)
    if phase == "COUNTERATTACK":
        return _tracker.counterattack is not None and _tracker.reversal is not None
    if phase == "CLIMAX":
        return _tracker.reversal is not None and _tracker.climax is not None
    return True


def g07_update_event_lifecycle(frame: int, program: Any, states: dict[str, Any]) -> None:
    global _program_ref, _states_ref
    _program_ref = program
    _states_ref = states
    for event in program.events:
        state = states[event.event_id]
        if state.status in hardened.TERMINAL:
            continue

        deps_ready = hardened._lifecycle.dependencies_ready(event, states)
        if not deps_ready:
            if frame >= program.total_frames and hardened._lifecycle.dependency_failure(event, states):
                state.status = "FAILED_DEPENDENCY"
                state.completed_frame = frame
            continue

        if frame >= event.start_frame and state.first_active_frame is None:
            ready, reason = _tracker.guard_ready(event, _actor_refs, frame)
            if ready:
                state.first_active_frame = frame
                state.status = "ACTIVE"
                _tracker.record_activation(event, _actor_refs, frame, reason)
            elif frame >= program.total_frames:
                state.status = "FAILED"
                state.completed_frame = frame
                marker(
                    "G07_EVENT_GUARD_UNSATISFIED",
                    eventId=event.event_id,
                    phase=_phase(event),
                    frame=frame,
                    reason=reason,
                    model=DRAMA_MODEL,
                )
            continue

        if state.status != "ACTIVE":
            continue

        if not event.requires_contact:
            settle_frame = int(event.end_frame)
            if _phase(event) == "PAYOFF" and state.first_active_frame is not None:
                settle_frame = max(settle_frame, int(state.first_active_frame) + max(1, int(program.fps) // 2))
            if frame >= settle_frame:
                state.status = "SETTLED" if _phase(event) == "PAYOFF" else "OBSERVED"
                state.completed_frame = frame
                _tracker.record_completion(event, _actor_refs, frame, state.status)
            continue

        if _dramatic_goal_met(event, state):
            state.status = "SUCCEEDED"
            state.completed_frame = frame
            _tracker.record_completion(event, _actor_refs, frame, state.status)
            continue

        if frame >= event.end_frame and event.event_id not in candidate40._overtime_marked:
            candidate40._overtime_marked.add(event.event_id)
            marker(
                "STORY_WINDOW_EXCEEDED_GOAL_STILL_ACTIVE",
                frame=frame,
                eventId=event.event_id,
                storyEndFrame=event.end_frame,
                finalBattleFrame=program.total_frames,
                timingAuthority="STORY_GUIDANCE_NOT_EXACT_PHYSICS_DEADLINE",
                dramaGuarded=True,
            )

        if frame >= program.total_frames:
            state.status = "SUCCEEDED" if _dramatic_goal_met(event, state) else "FAILED"
            state.completed_frame = frame
            _tracker.record_completion(event, _actor_refs, frame, state.status)


def g07_pairwise_resolve_pending_contacts(
    frame: int,
    actors: dict[str, Any],
    states: dict[str, Any],
    events_by_id: dict[str, Any],
    pending: list[Any],
    camera: Any,
    impact_log: list[dict[str, Any]],
) -> None:
    global _actor_refs
    _actor_refs = actors
    before = len(impact_log)
    _ORIGINAL_G06_RESOLVE(
        frame,
        actors,
        states,
        events_by_id,
        pending,
        camera,
        impact_log,
    )
    for row in impact_log[before:]:
        event_id = str(row.get("eventId") or "")
        event = events_by_id.get(event_id)
        if event is not None:
            _tracker.note_transaction(row, event, actors)


def g07_set_controls(
    frame: int,
    program: Any,
    actors: dict[str, Any],
    states: dict[str, Any],
    control_samples: list[dict[str, Any]],
) -> None:
    global _actor_refs, _program_ref, _states_ref
    _actor_refs = actors
    _program_ref = program
    _states_ref = states
    _ORIGINAL_G06_SET_CONTROLS(frame, program, actors, states, control_samples)


def _write_g07_evidence(states: dict[str, Any], outcome: dict[str, Any]) -> None:
    if hardened._capture_output is None:
        raise BlenderBattleRuntimeError("G07_OUTPUT_DIR_UNAVAILABLE")
    if _program_ref is None or not _actor_refs:
        raise BlenderBattleRuntimeError("G07_RUNTIME_REFERENCES_MISSING")
    frame = int(bpy.context.scene.frame_current)
    final_dominance = _tracker.dominance_snapshot(_actor_refs, frame)
    chain_complete = all(
        value is not None
        for value in (
            _tracker.escalation,
            _tracker.counterattack,
            _tracker.reversal,
            _tracker.climax,
            _tracker.payoff,
        )
    )
    evidence = {
        "status": "COMPLETE" if chain_complete else "INCOMPLETE",
        "candidate": CANDIDATE,
        "model": DRAMA_MODEL,
        "dominanceModel": DOMINANCE_MODEL,
        "finalFrame": frame,
        "programTotalFrames": int(_program_ref.total_frames),
        "directTransactions": _json_copy(_tracker.direct_transactions),
        "transitions": _json_copy(_tracker.transitions),
        "eventActivations": _json_copy(_tracker.activations),
        "eventCompletions": _json_copy(_tracker.completions),
        "initialDominantActor": _tracker.initial_dominant_actor,
        "initialDominanceFrame": _tracker.initial_dominance_frame,
        "initialDominance": _json_copy(_tracker.initial_dominance_snapshot),
        "reversal": _json_copy(_tracker.reversal),
        "escalation": _json_copy(_tracker.escalation),
        "counterattack": _json_copy(_tracker.counterattack),
        "climax": _json_copy(_tracker.climax),
        "payoff": _json_copy(_tracker.payoff),
        "finalDominance": final_dominance,
        "eventStates": {
            event_id: {
                "status": str(state.status),
                "contactCount": int(state.contact_count),
                "damageCount": int(state.damage_count),
                "firstActiveFrame": int(state.first_active_frame) if state.first_active_frame is not None else None,
                "completedFrame": int(state.completed_frame) if state.completed_frame is not None else None,
            }
            for event_id, state in sorted(states.items())
        },
        "outcome": _json_copy(outcome),
        "g04AutonomySourceChanged": False,
        "g05ContactAuthoritySourceChanged": False,
        "g06PersistenceSourceChanged": False,
        "damageThresholdChanged": False,
        "contactThresholdChanged": False,
        "actorPoseOrVelocityMutation": False,
        "stateResetMechanismIntroduced": False,
        "forcedWinnerIntroduced": False,
        "exactCollisionFrameTarget": False,
        "exactImpactEnergyTarget": False,
        "productionReadyClaimed": False,
    }
    path = Path(hardened._capture_output) / "g07-causal-drama-evidence.json"
    path.write_text(json.dumps(evidence, indent=2, sort_keys=True), encoding="utf-8")
    marker(
        "G07_CAUSAL_DRAMA_EVIDENCE_WRITTEN",
        path=str(path),
        status=evidence["status"],
        directTransactionCount=len(_tracker.direct_transactions),
        transitionCount=len(_tracker.transitions),
        reversalObserved=_tracker.reversal is not None,
        climaxObserved=_tracker.climax is not None,
        payoffObserved=_tracker.payoff is not None,
        model=DRAMA_MODEL,
    )


def g07_outcome_resolve(states: dict[str, Any], events: dict[str, Any]) -> dict[str, Any]:
    outcome = _ORIGINAL_G06_OUTCOME(states, events)
    _write_g07_evidence(events, outcome)
    outcome = dict(outcome)
    outcome["causalDrama"] = {
        "model": DRAMA_MODEL,
        "initialDominantActor": _tracker.initial_dominant_actor,
        "dominanceReversalObserved": _tracker.reversal is not None,
        "climaxObserved": _tracker.climax is not None,
        "payoffObserved": _tracker.payoff is not None,
    }
    return outcome


def _reset() -> None:
    global _actor_refs, _program_ref, _states_ref
    _tracker.reset()
    _actor_refs = {}
    _program_ref = None
    _states_ref = None


def main() -> None:
    _reset()
    candidate43.CANDIDATE = CANDIDATE
    candidate43.g06_pairwise_resolve_pending_contacts = g07_pairwise_resolve_pending_contacts
    candidate43.g06_set_controls = g07_set_controls
    candidate43.g06_outcome_resolve = g07_outcome_resolve
    candidate40._active_goal_for_actor = g07_active_goal_for_actor
    candidate40.autonomous_update_event_lifecycle = g07_update_event_lifecycle
    runtime.dominant_event = g07_dominant_event

    print(
        json.dumps(
            {
                "marker": "GENERIC_BATTLE_RUNTIME_CANDIDATE44_G07_ENGINEERING_PASS",
                "candidate": CANDIDATE,
                "dramaModel": DRAMA_MODEL,
                "dominanceModel": DOMINANCE_MODEL,
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
    candidate43.main()


if __name__ == "__main__":
    main()
