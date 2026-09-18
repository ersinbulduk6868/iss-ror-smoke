from __future__ import annotations

from collections.abc import Mapping, MutableMapping
from typing import Any

from blender.iss_battle_runtime_handoff_v1 import SolverHandoffLatch

CUTOFF_FRAME_AUTHORITY_MODEL = "EVENT_LOCAL_HANDOFF_START_FRAME_IMMUTABILITY_V1"


def stabilize_active_handoff_cutoff_frames(
    cutoff_frames: MutableMapping[tuple[str, str], int],
    active_latches: Mapping[tuple[str, str], SolverHandoffLatch],
) -> tuple[dict[str, Any], ...]:
    """Keep G05 controller-cutoff evidence bound to the authority-release transition.

    G05 treats ``_cutoff_frames`` as the frame at which motor authority was released.
    A latched COAST state may last for many frames, but those later frames are not new
    authority-release transitions. Rewriting the cutoff every COAST frame can move the
    recorded cutoff *after* a solver contact frame and make a real native contact fail
    the preserved G05 ordering check.

    This helper changes no contact, locality, semantic, damage, or timing threshold.
    It only restores the event-local handoff start frame while that latch is active.
    A later, genuinely new handoff for the same event/actor gets a new latch start and
    therefore a new authoritative cutoff frame.
    """
    changes: list[dict[str, Any]] = []
    for key, latch in active_latches.items():
        authoritative = int(latch.start_frame)
        previous = cutoff_frames.get(key)
        if previous is None or int(previous) != authoritative:
            cutoff_frames[key] = authoritative
            changes.append(
                {
                    "eventId": str(key[0]),
                    "actorId": str(key[1]),
                    "previousCutoffFrame": None if previous is None else int(previous),
                    "authoritativeCutoffFrame": authoritative,
                    "model": CUTOFF_FRAME_AUTHORITY_MODEL,
                }
            )
    return tuple(changes)
