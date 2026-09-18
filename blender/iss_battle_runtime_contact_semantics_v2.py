from __future__ import annotations

from dataclasses import dataclass
from collections.abc import Mapping, Sequence

from blender.iss_battle_runtime_handoff_v4 import select_semantic_zone_for_local_surface

OBSERVED_CONTACT_SEMANTIC_MODEL = "G05_SOLVER_OBSERVED_CONTACT_SEMANTIC_CLASSIFICATION_V1"


@dataclass(slots=True, frozen=True)
class ObservedContactSemanticSelection:
    use_observed_contact_semantics: bool
    engagement_intent_zone: str | None
    observed_contact_zone: str | None
    observed_zone_distance_m: float | None
    story_target_zone_prescribed: bool
    active_solver_handoff: bool


def should_classify_observed_contact_semantics(
    *,
    runtime_selected_semantics: bool,
    story_target_zone_prescribed: bool,
    active_solver_handoff: bool,
) -> bool:
    """Separate G04/G07 control intent from G05 solver-observed contact truth.

    Story-prescribed zones remain strict. Runtime-selected engagement semantics may
    be reclassified from the live pair contact surface only after motor authority
    has already been released into an active solver handoff. This function does not
    accept or alter any contact, locality, semantic, damage, speed or energy gate.
    """
    return bool(
        runtime_selected_semantics
        and not story_target_zone_prescribed
        and active_solver_handoff
    )


def classify_observed_contact_surface(
    *,
    surface_local: Sequence[float],
    zones: Mapping[str, Sequence[float]],
    visual_offset: Sequence[float],
    engagement_intent_zone: str | None,
    runtime_selected_semantics: bool,
    story_target_zone_prescribed: bool,
    active_solver_handoff: bool,
) -> ObservedContactSemanticSelection:
    use_observed = should_classify_observed_contact_semantics(
        runtime_selected_semantics=runtime_selected_semantics,
        story_target_zone_prescribed=story_target_zone_prescribed,
        active_solver_handoff=active_solver_handoff,
    )
    if not use_observed:
        return ObservedContactSemanticSelection(
            use_observed_contact_semantics=False,
            engagement_intent_zone=(str(engagement_intent_zone) if engagement_intent_zone else None),
            observed_contact_zone=None,
            observed_zone_distance_m=None,
            story_target_zone_prescribed=bool(story_target_zone_prescribed),
            active_solver_handoff=bool(active_solver_handoff),
        )

    zone, distance = select_semantic_zone_for_local_surface(
        surface_local,
        zones,
        visual_offset,
    )
    return ObservedContactSemanticSelection(
        use_observed_contact_semantics=True,
        engagement_intent_zone=(str(engagement_intent_zone) if engagement_intent_zone else None),
        observed_contact_zone=str(zone),
        observed_zone_distance_m=float(distance),
        story_target_zone_prescribed=False,
        active_solver_handoff=True,
    )
