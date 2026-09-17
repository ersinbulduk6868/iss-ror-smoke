from __future__ import annotations

from typing import Any

EFFECTIVENESS_MODEL = "ISS_RUNTIME_OWNED_EFFECTIVE_ATTACK_V1"
EFFECTIVE_ATTACK_PHASES = frozenset({"ESCALATION", "FIRST_ATTACK", "COUNTERATTACK"})


def event_phase(event: Any) -> str:
    return str(getattr(event, "phase", "") or "").strip().upper()


def requires_productive_damage(event: Any) -> bool:
    """Runtime battle-quality policy; Story does not prescribe impact geometry.

    Contact-bearing aggressive battle phases must produce at least one physically
    earned damage consequence before the attack is considered effective. This
    adds no target zone, speed, energy, collision frame, or trajectory input.
    """
    return bool(getattr(event, "requires_contact", False)) and event_phase(event) in EFFECTIVE_ATTACK_PHASES


def productive_effect_met(event: Any, state: Any, lifecycle: Any) -> bool:
    if not requires_productive_damage(event):
        return True
    event_id = str(getattr(event, "event_id", "") or "")
    return int(getattr(state, "damage_count", 0) or 0) > 0 and event_id in lifecycle.damage_earned
