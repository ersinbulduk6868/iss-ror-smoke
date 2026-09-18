from __future__ import annotations

COLLISION_ROLE_MODEL = "GENERIC_BATTLE_RIGID_BODY_COLLISION_ROLE_V1"
COLLISION_COLLECTION_COUNT = 20
BATTLE_BODY_GROUP = 0
DRIVE_HELPER_GROUP = 1


def collision_mask(*groups: int) -> tuple[bool, ...]:
    selected = {int(g) for g in groups}
    if any(g < 0 or g >= COLLISION_COLLECTION_COUNT for g in selected):
        raise ValueError("COLLISION_GROUP_OUT_OF_RANGE")
    return tuple(i in selected for i in range(COLLISION_COLLECTION_COUNT))


BATTLE_BODY_MASK = collision_mask(BATTLE_BODY_GROUP)
DRIVE_HELPER_MASK = collision_mask(DRIVE_HELPER_GROUP)
GROUND_MASK = collision_mask(BATTLE_BODY_GROUP, DRIVE_HELPER_GROUP)


def runtime_collision_role(object_name: str) -> str:
    name = str(object_name or "")
    if name.startswith("ISS_DRIVE_WHEEL_"):
        return "DRIVE_HELPER"
    if name.startswith("ISS_PHYSICS_"):
        return "BATTLE_BODY"
    if name == "ISS_RUNTIME_GROUND":
        return "GROUND"
    return "UNCHANGED"


def mask_for_role(role: str) -> tuple[bool, ...] | None:
    value = str(role or "").upper()
    if value == "BATTLE_BODY":
        return BATTLE_BODY_MASK
    if value == "DRIVE_HELPER":
        return DRIVE_HELPER_MASK
    if value == "GROUND":
        return GROUND_MASK
    return None
