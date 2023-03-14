from datetime import datetime

from .models import BambuLabEntity
from homeassistant.config_entries import ConfigEntry
from collections.abc import Callable

from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.core import HomeAssistant, callback
from .const import DOMAIN, LOGGER
from dataclasses import dataclass
from .pybambu.commands import part_cooling_fan_speed

from homeassistant.components.fan import (
    DIRECTION_FORWARD,
    DIRECTION_REVERSE,
    FanEntity,
    FanEntityFeature,
    FanEntityDescription
)
from .coordinator import BambuDataUpdateCoordinator


@dataclass
class BambuLabFanEntityDescriptionMixin:
    """Mixin for required keys."""
    value_fn: Callable[..., any]


@dataclass
class BambuLabFanEntityDescription(FanEntityDescription, BambuLabFanEntityDescriptionMixin):
    """Fan entity description for Bambu Lab."""
    exists_fn: Callable[..., bool] = lambda _: True
    extra_attributes: Callable[..., dict] = lambda _: {}


FANS: tuple[FanEntityDescription, ...] = (
    BambuLabFanEntityDescription(
        key="aux_fan_speed",
        type="aux_fan",
        name="Aux Fan Speed",
        value_fn=lambda device: device.fans.aux_fan_speed
    ),
    BambuLabFanEntityDescription(
        key="chamber_fan_speed",
        type="chamber_fan",
        name="Chamber Fan Speed",
        value_fn=lambda device: device.fans.chamber_fan_speed
    ),
    BambuLabFanEntityDescription(
        key="cooling_fan_speed",
        type="part_fan",
        name="Cooling Fan Speed",
        value_fn=lambda device: device.fans.cooling_fan_speed
    ),
    BambuLabFanEntityDescription(
        key="heatbreak_fan_speed",
        name="Heatbreak Fan Speed",
        value_fn=lambda device: device.fans.heatbreak_fan_speed
    )
)


async def async_setup_entry(
        hass: HomeAssistant,
        entry: ConfigEntry,
        async_add_entities: AddEntitiesCallback
) -> None:
    coordinator: BambuDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]

    async_add_entities(
        BambuLabFan(coordinator, description, entry)
        for description in FANS
    )


class BambuLabFan(BambuLabEntity, FanEntity):
    """ Defined the Fan"""

    def __init__(
            self,
            coordinator: BambuDataUpdateCoordinator,
            description: BambuLabFanEntityDescription,
            config_entry: ConfigEntry
    ) -> None:
        """Initialize the fan."""
        self.entity_description = description
        self._attr_unique_id = f"{config_entry.data['serial']}_{description.key}"
        self._attr_name = description.name
        self._attr_supported_features = FanEntityFeature.SET_SPEED

        super().__init__(coordinator=coordinator)

    @property
    def available(self) -> bool:
        """Is the fan available"""
        return True

    @property
    def is_on(self) -> bool:
        """Return the state of the fan"""
        if self.entity_description.value_fn(self.coordinator.data) > 0:
            return True
        return False

    @property
    def percentage(self) -> int:
        """Return the current speed percentage."""
        LOGGER.debug(f"Fan Speed % {self.entity_description.value_fn(self.coordinator.data)}")
        return self.entity_description.value_fn(self.coordinator.data)

    async def async_turn_off(self, **kwargs) -> None:
        """Turn the fan off."""
        self.coordinator.client.publish(part_cooling_fan_speed(0))
