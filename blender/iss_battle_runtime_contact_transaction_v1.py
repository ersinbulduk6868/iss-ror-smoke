from __future__ import annotations

from typing import Iterable

TRANSACTION_LOCALITY_MODEL = "G05_TRANSACTION_BOUNDED_LOCALITY_WINDOW_V1"


def transaction_window_start(
    frame: int,
    cutoff_frame: int | None,
    window_frames: int,
) -> int:
    """Return the oldest locality sample frame eligible for this transaction.

    G05 may inspect a short recent geometry window, but a fresh controller-handoff
    transaction must never authorize a geometry sample that predates its immutable
    cutoff. This helper changes neither locality nor semantic tolerances; it only
    constrains evidence ownership to the active transaction.
    """
    frame_i = int(frame)
    window_i = max(1, int(window_frames))
    start = max(2, frame_i - window_i + 1)
    if cutoff_frame is not None:
        start = max(start, int(cutoff_frame))
    return start


def transaction_candidate_frames(
    frame: int,
    cutoff_frame: int | None,
    window_frames: int,
) -> tuple[int, ...]:
    start = transaction_window_start(frame, cutoff_frame, window_frames)
    if start > int(frame):
        return ()
    return tuple(range(start, int(frame) + 1))


def all_samples_belong_to_transaction(
    sample_frames: Iterable[int],
    cutoff_frame: int | None,
) -> bool:
    if cutoff_frame is None:
        return True
    cutoff_i = int(cutoff_frame)
    return all(int(frame) >= cutoff_i for frame in sample_frames)
