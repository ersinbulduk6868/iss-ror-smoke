from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable

ENGAGEMENT_APPROACH_TRANSACTION_MODEL = "GENERIC_ENGAGEMENT_APPROACH_TRANSACTION_V1"


@dataclass(frozen=True, slots=True)
class EngagementApproachDecision:
    hold: bool
    frozen_zone: str | None
    started: bool
    released: bool
    refined_by_handoff: bool
    source_sample_frame: int | None


def latest_contact_commit_sample(
    samples: Iterable[dict[str, Any]],
    event_id: str,
) -> dict[str, Any] | None:
    event_key = str(event_id)
    latest: dict[str, Any] | None = None
    latest_frame = -1
    for row in samples:
        if str(row.get("eventId") or "") != event_key:
            continue
        frame = int(row.get("frame") or -1)
        if frame >= latest_frame:
            latest = row
            latest_frame = frame
    return latest


def decide_engagement_approach_transaction(
    *,
    frozen_zone: str | None,
    current_zone: str | None,
    contact_commit: bool,
    event_terminal: bool,
    active_handoff: bool,
    source_sample_frame: int | None,
) -> EngagementApproachDecision:
    """Pure semantic-label lifecycle for one generic contact attempt.

    The transaction freezes only the semantic zone identity.  It never freezes a
    world coordinate, pose, velocity, trajectory, collision frame, impact energy,
    asset identity or asset-specific control value.

    An active solver handoff may refine the semantic zone from live pair geometry;
    that refined label becomes the transaction's new frozen zone.  Once tactical
    contact commitment ends, or the event is terminal, live semantic adaptation is
    allowed again.
    """
    if event_terminal:
        return EngagementApproachDecision(
            hold=False,
            frozen_zone=None,
            started=False,
            released=frozen_zone is not None,
            refined_by_handoff=False,
            source_sample_frame=source_sample_frame,
        )

    if active_handoff:
        zone = str(current_zone) if current_zone else frozen_zone
        return EngagementApproachDecision(
            hold=bool(zone),
            frozen_zone=zone,
            started=frozen_zone is None and bool(zone),
            released=False,
            refined_by_handoff=(
                bool(zone)
                and frozen_zone is not None
                and str(zone) != str(frozen_zone)
            ),
            source_sample_frame=source_sample_frame,
        )

    if contact_commit:
        zone = frozen_zone or (str(current_zone) if current_zone else None)
        return EngagementApproachDecision(
            hold=bool(zone),
            frozen_zone=zone,
            started=frozen_zone is None and bool(zone),
            released=False,
            refined_by_handoff=False,
            source_sample_frame=source_sample_frame,
        )

    return EngagementApproachDecision(
        hold=False,
        frozen_zone=None,
        started=False,
        released=frozen_zone is not None,
        refined_by_handoff=False,
        source_sample_frame=source_sample_frame,
    )
