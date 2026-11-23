"""Collect the entities of every linked BIQU Panda device for one platform."""
from __future__ import annotations

from homeassistant.helpers.entity import Entity

from .panda_breath_entities import breath_entities
from .panda_devices import PANDA_BREATH, PANDA_PWR, PANDA_STATUS
from .panda_pwr_entities import pwr_entities
from .panda_status_entities import status_entities

_BUILDERS = {
    PANDA_BREATH: breath_entities,
    PANDA_PWR: pwr_entities,
    PANDA_STATUS: status_entities,
}


def platform_entities(platform: str, coordinator) -> list[Entity]:
    entities: list[Entity] = []
    for kind in getattr(coordinator, "panda_devices", {}):
        entities.extend(_BUILDERS[kind](platform, coordinator))
    return entities
