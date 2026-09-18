from __future__ import annotations

from collections.abc import Mapping, MutableMapping
from typing import Any

from blender.iss_battle_runtime_handoff_v1 import SolverHandoffLatch

CUTOFF_TRANSACTION_CLEANUP_MODEL = "EVENT_LOCAL_HANDOFF_TRANSACTION_CUTOFF_INVALIDATION_V1"


def invalidate_released_handoff_cutoffs(
    cutoff_frames: MutableMapping[tuple[str, str], int],
    before_start_frames: Mapping[tuple[str, str], int],
    active_latches_after: Mapping[tuple[str, str], SolverHandoffLatch],
) -> tuple[dict[str, Any], ...]:
    """Invalidate controller-cutoff evidence when its handoff transaction ends.

    ``_cutoff_frames`` is evidence that motor authority was released for one
    event-local solver handoff transaction. Once that transaction is released,
    its cutoff must not authorize a later native-contact candidate.

    If the controller establishes a genuinely new handoff for the same
    ``(eventId, actorId)`` in the same control update, the new latch owns a new
    start frame and the newly-written cutoff is preserved. No contact, locality,
    semantic, damage, timing, pose, velocity, or asset-specific rule is changed.
    """
    changes: list[dict[str, Any]] = []
    for key, old_start_value in before_start_frames.items():
        old_start = int(old_start_value)
        after = active_latches_after.get(key)
        if after is not None and int(after.start_frame) == old_start:
            # The same transaction is still active.
            continue

        if after is not None:
            # The old transaction ended and a fresh transaction replaced it in
            # the same control update. Preserve the fresh cutoff written by the
            # new latch; C465 will stabilize it to the new start frame.
            changes.append(
                {
                    "eventId": str(key[0]),
                    "actorId": str(key[1]),
                    "previousHandoffStartFrame": old_start,
                    "newHandoffStartFrame": int(after.start_frame),
                    "previousCutoffFrame": (
                        None if cutoff_frames.get(key) is None else int(cutoff_frames[key])
                    ),
                    "action": "FRESH_TRANSACTION_PRESERVED",
                    "model": CUTOFF_TRANSACTION_CLEANUP_MODEL,
                }
            )
            continue

        previous_cutoff = cutoff_frames.pop(key, None)
        changes.append(
            {
                "eventId": str(key[0]),
                "actorId": str(key[1]),
                "previousHandoffStartFrame": old_start,
                "newHandoffStartFrame": None,
                "previousCutoffFrame": (
                    None if previous_cutoff is None else int(previous_cutoff)
                ),
                "action": "RELEASED_TRANSACTION_INVALIDATED",
                "model": CUTOFF_TRANSACTION_CLEANUP_MODEL,
            }
        )
    return tuple(changes)
