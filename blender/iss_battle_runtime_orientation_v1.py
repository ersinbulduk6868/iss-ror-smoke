from __future__ import annotations

from typing import Any, Callable, Iterable

ORIENTATION_MODEL = "G04_PHYSICS_SEMANTIC_ORIENTATION_FALLBACK_V1"
PHYSICS_CONTAINER_NAME = "physics"
CHASSIS_TERMS = ("chassis", "frame", "hull")


def _ancestor_names(obj: Any) -> tuple[str, ...]:
    names: list[str] = []
    parent = getattr(obj, "parent", None)
    while parent is not None:
        names.append(str(getattr(parent, "name", "")))
        parent = getattr(parent, "parent", None)
    return tuple(names)


def _under_named_container(obj: Any, name: str) -> bool:
    wanted = str(name).strip().lower()
    if not wanted:
        return False
    if str(getattr(obj, "name", "")).strip().lower() == wanted:
        return True
    return any(str(value).strip().lower() == wanted for value in _ancestor_names(obj))


def _point_for_object(
    obj: Any,
    *,
    world_bounds: Callable[[Iterable[Any]], tuple[Any, Any]],
) -> tuple[float, float, float]:
    if str(getattr(obj, "type", "")) == "MESH" and len(getattr(getattr(obj, "data", None), "vertices", ())) > 0:
        lo, hi = world_bounds([obj])
        center = (lo + hi) * 0.5
        return (float(center.x), float(center.y), float(center.z))
    point = getattr(getattr(obj, "matrix_world", None), "translation", None)
    if point is None:
        raise ValueError("ORIENTATION_OBJECT_WORLD_TRANSLATION_MISSING")
    return (float(point.x), float(point.y), float(point.z))


def _average(points: list[tuple[float, float, float]]) -> tuple[float, float, float]:
    if not points:
        raise ValueError("ORIENTATION_POINT_SET_EMPTY")
    n = float(len(points))
    return (
        sum(p[0] for p in points) / n,
        sum(p[1] for p in points) / n,
        sum(p[2] for p in points) / n,
    )


def _delta(a: tuple[float, float, float], b: tuple[float, float, float]) -> tuple[float, float, float]:
    return (a[0] - b[0], a[1] - b[1], a[2] - b[2])


def _axis_from_delta(delta: tuple[float, float, float]) -> str | None:
    dx, dy, _ = delta
    if max(abs(dx), abs(dy)) < 1.0e-5:
        return None
    if abs(dx) >= abs(dy):
        return "X" if dx >= 0.0 else "-X"
    return "Y" if dy >= 0.0 else "-Y"


def resolve_physics_semantic_forward_axis(
    objects: Iterable[Any],
    *,
    front_terms: tuple[str, ...],
    rear_terms: tuple[str, ...],
    object_tokens: Callable[[Any], set[str]],
    token_match: Callable[[set[str], tuple[str, ...]], bool],
    world_bounds: Callable[[Iterable[Any]], tuple[Any, Any]],
    physics_container_name: str = PHYSICS_CONTAINER_NAME,
) -> dict[str, Any] | None:
    """Resolve orientation from generic ready-asset structural semantics.

    This is a fallback only. The caller must preserve explicit canonical-frame and
    existing visible mesh/material orientation resolution as higher authority.

    Only objects inside the generic Physics hierarchy are eligible. This avoids
    duplicate semantic labels in DamageZones, DamageBindings, and Joints from
    contaminating orientation. No asset identity, source SHA, provider UID, or
    per-video information enters the decision.
    """

    rows = list(objects)

    def eligible(terms: tuple[str, ...]) -> list[tuple[Any, tuple[float, float, float]]]:
        out: list[tuple[Any, tuple[float, float, float]]] = []
        for obj in rows:
            if not _under_named_container(obj, physics_container_name):
                continue
            if not token_match(object_tokens(obj), terms):
                continue
            out.append((obj, _point_for_object(obj, world_bounds=world_bounds)))
        return out

    fronts = eligible(front_terms)
    if not fronts:
        return None

    rears = eligible(rear_terms)
    chassis = eligible(CHASSIS_TERMS)

    front_point = _average([point for _, point in fronts])
    if rears:
        reference_point = _average([point for _, point in rears])
        reference_source = "PHYSICS_REAR_SEMANTIC"
    elif chassis:
        reference_point = _average([point for _, point in chassis])
        reference_source = "PHYSICS_CHASSIS_SEMANTIC"
    else:
        return None

    delta = _delta(front_point, reference_point)
    axis = _axis_from_delta(delta)
    if axis is None:
        return None

    return {
        "model": ORIENTATION_MODEL,
        "axis": axis,
        "referenceSource": reference_source,
        "delta": list(delta),
        "frontAnchors": [str(getattr(obj, "name", "")) for obj, _ in fronts],
        "rearAnchors": [str(getattr(obj, "name", "")) for obj, _ in rears],
        "chassisAnchors": [str(getattr(obj, "name", "")) for obj, _ in chassis],
        "assetIdentityBranch": False,
        "sourceShaBranch": False,
        "perAssetOrientationOverride": False,
    }
