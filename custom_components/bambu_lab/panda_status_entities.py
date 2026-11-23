"""Entities for a BIQU Panda Status / Panda Aura status light linked to a printer."""
from __future__ import annotations

from typing import Any

from homeassistant.components.select import SelectEntity, SelectEntityDescription
from homeassistant.components.sensor import SensorEntity, SensorEntityDescription
from homeassistant.components.switch import SwitchEntity, SwitchEntityDescription
from homeassistant.const import EntityCategory
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers.entity import Entity

from .panda_devices import PANDA_STATUS
from .panda_entity import PandaEntity
from .panda_status import EFFECT_MODES, PandaStatusState, build_effect_mode, build_idle_light


class PandaStatusEntity(PandaEntity):
    kind = PANDA_STATUS
    unique_id_prefix = "panda_status"

    @property
    def status_state(self) -> PandaStatusState:
        return self.client.state


class PandaStatusIdleLightSwitch(PandaStatusEntity, SwitchEntity):
    entity_description = SwitchEntityDescription(
        key="idle_light", translation_key="panda_status_idle_light", icon="mdi:lightbulb",
    )

    def __init__(self, coordinator) -> None:
        super().__init__(coordinator, "idle_light")

    @property
    def is_on(self) -> bool | None:
        return self.status_state.idle_light_on

    async def async_turn_on(self, **kwargs: Any) -> None:
        await self.client.async_send(build_idle_light(True))

    async def async_turn_off(self, **kwargs: Any) -> None:
        await self.client.async_send(build_idle_light(False))


class PandaStatusEffectSelect(PandaStatusEntity, SelectEntity):
    entity_description = SelectEntityDescription(
        key="light_effect",
        translation_key="panda_status_light_effect",
        icon="mdi:palette",
        entity_category=EntityCategory.CONFIG,
        options=list(EFFECT_MODES.values()),
    )

    def __init__(self, coordinator) -> None:
        super().__init__(coordinator, "light_effect")

    @property
    def current_option(self) -> str | None:
        return self.status_state.effect_mode

    async def async_select_option(self, option: str) -> None:
        try:
            messages = build_effect_mode(option)
        except ValueError as err:
            raise ServiceValidationError(str(err)) from err
        await self.client.async_send(messages)


class PandaStatusPrinterStateSensor(PandaStatusEntity, SensorEntity):
    """The printer state as the Panda Status sees it (handy to check its printer link)."""

    entity_description = SensorEntityDescription(
        key="printer_state",
        translation_key="panda_status_printer_state",
        icon="mdi:printer-3d",
        entity_category=EntityCategory.DIAGNOSTIC,
    )

    def __init__(self, coordinator) -> None:
        super().__init__(coordinator, "printer_state")

    @property
    def native_value(self) -> str | None:
        return self.status_state.printer_state


def status_entities(platform: str, coordinator) -> list[Entity]:
    if platform == "sensor":
        return [PandaStatusPrinterStateSensor(coordinator)]
    if platform == "switch":
        return [PandaStatusIdleLightSwitch(coordinator)]
    if platform == "select":
        return [PandaStatusEffectSelect(coordinator)]
    return []
