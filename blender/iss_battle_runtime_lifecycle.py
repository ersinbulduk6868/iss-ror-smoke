from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from blender.iss_battle_runtime_core import EventState, RuntimeEvent

TERMINAL_SUCCESS = {"SUCCEEDED", "OBSERVED", "SETTLED"}
TERMINAL_FAILURE = {"FAILED", "FAILED_DEPENDENCY"}
TERMINAL = TERMINAL_SUCCESS | TERMINAL_FAILURE


@dataclass
class BattleLifecycle:
    physically_resolved: set[str] = field(default_factory=set)
    causally_resolved: set[str] = field(default_factory=set)
    qualified_attackers: dict[str, set[str]] = field(default_factory=dict)
    qualified_contact_counts: dict[str, int] = field(default_factory=dict)
    damage_earned: set[str] = field(default_factory=set)

    def dependencies_ready(
        self,
        event: RuntimeEvent,
        states: dict[str, EventState],
    ) -> bool:
        for dependency in event.dependencies:
            state = states[dependency]
            if dependency in self.causally_resolved:
                continue
            if state.status in TERMINAL_SUCCESS:
                continue
            return False
        return True

    def note_impact(
        self,
        event: RuntimeEvent,
        attacker_id: str,
        *,
        damage_earned: bool,
    ) -> None:
        event_id = event.event_id
        self.physically_resolved.add(event_id)
        self.qualified_attackers.setdefault(event_id, set()).add(attacker_id)
        self.qualified_contact_counts[event_id] = (
            self.qualified_contact_counts.get(event_id, 0) + 1
        )
        if damage_earned:
            self.damage_earned.add(event_id)

        min_contacts, min_distinct = self.requirements(event)
        distinct = len(self.qualified_attackers.get(event_id, set()))
        contacts = self.qualified_contact_counts.get(event_id, 0)
        damage_ok = (not event.damage_required) or event_id in self.damage_earned
        if contacts >= min_contacts and distinct >= min_distinct and damage_ok:
            self.causally_resolved.add(event_id)

    @staticmethod
    def _execution_requirements(event: RuntimeEvent) -> dict[str, Any]:
        raw = event.original or {}
        for key in (
            "runtimeAcceptance",
            "executionRequirements",
            "battleExecutionContract",
        ):
            value = raw.get(key)
            if isinstance(value, dict):
                return value
        req = raw.get("physicsRequirements")
        return req if isinstance(req, dict) else {}

    def requirements(
        self,
        event: RuntimeEvent,
    ) -> tuple[int, int]:
        req = self._execution_requirements(event)
        default_contacts = 1 if event.requires_contact else 0
        default_distinct = 1 if event.requires_contact else 0
        try:
            min_contacts = int(req.get("minQualifiedContacts", default_contacts))
        except (TypeError, ValueError):
            min_contacts = default_contacts
        try:
            min_distinct = int(req.get("minDistinctAttackers", default_distinct))
        except (TypeError, ValueError):
            min_distinct = default_distinct
        min_contacts = max(default_contacts, min_contacts)
        min_distinct = max(default_distinct, min_distinct)
        if event.attackers:
            min_distinct = min(min_distinct, len(event.attackers))
        return min_contacts, min_distinct

    def requirements_met(
        self,
        event: RuntimeEvent,
        state: EventState,
    ) -> bool:
        if not event.requires_contact:
            return True
        min_contacts, min_distinct = self.requirements(event)
        distinct = len(self.qualified_attackers.get(event.event_id, set()))
        internal_contacts = self.qualified_contact_counts.get(event.event_id, 0)
        effective_contacts = min(state.contact_count, internal_contacts)
        if effective_contacts < min_contacts:
            return False
        if distinct < min_distinct:
            return False
        if event.damage_required and (
            state.damage_count <= 0 or event.event_id not in self.damage_earned
        ):
            return False
        return True

    def dependency_failure(
        self,
        event: RuntimeEvent,
        states: dict[str, EventState],
    ) -> bool:
        return any(states[d].status in TERMINAL_FAILURE for d in event.dependencies)

    def snapshot(self) -> dict[str, Any]:
        return {
            "physicallyResolvedEvents": sorted(self.physically_resolved),
            "causallyResolvedEvents": sorted(self.causally_resolved),
            "damageEarnedEvents": sorted(self.damage_earned),
            "qualifiedContactCounts": dict(sorted(self.qualified_contact_counts.items())),
            "qualifiedAttackers": {
                event_id: sorted(values)
                for event_id, values in sorted(self.qualified_attackers.items())
            },
        }
