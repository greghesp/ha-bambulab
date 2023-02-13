from enum import Enum
from .models import BambuLabEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.core import HomeAssistant, callback
from .const import DOMAIN, LOGGER
from .pybambu.commands import CHAMBER_LIGHT_ON, CHAMBER_LIGHT_OFF
from .pybambu.const import Features

from homeassistant.components.light import (
    ATTR_BRIGHTNESS,
    ATTR_EFFECT,
    ColorMode,
    LightEntity,
    LightEntityFeature
)
from .coordinator import BambuDataUpdateCoordinator


async def async_setup_entry(
        hass: HomeAssistant,
        entry: ConfigEntry,
        async_add_entities: AddEntitiesCallback
) -> None:
    coordinator: BambuDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]
    await coordinator.wait_for_data_ready()
    # LOGGER.debug(f"Printer type: {coordinator.data.info.device_type}")

    entities_to_add: list = []

    if coordinator.supports_feature(Features.AUX_FAN):
        entities_to_add.append(BambuLabChamberLight(coordinator, entry))
    async_add_entities(entities_to_add)


class BambuLabChamberLight(BambuLabEntity, LightEntity):
    """ Defined the Chamber Light """

    def __init__(
            self,
            coordinator: BambuDataUpdateCoordinator,
            config_entry: ConfigEntry
    ) -> None:
        """Initialize the sensor."""
        self._attr_unique_id = f"{config_entry.data['serial']}_chamber_light"
        self._attr_name = "Chamber Light"
        super().__init__(coordinator=coordinator)

    @property
    def available(self) -> bool:
        """Is the light available"""
        return True

    @property
    def is_on(self) -> bool:
        """Return the state of the switch"""
        if self.coordinator.data.lights.chamber_light == "on":
            return True
        return False

    @property
    def icon(self) -> str:
        """Return the icon to use in the frontend, if any."""
        return "mdi:led-strip-variant"

    def turn_off(self) -> None:
        """ Turn off the power"""
        self.coordinator.client.publish(CHAMBER_LIGHT_OFF)

    def turn_on(self) -> None:
        """ Turn on the power"""
        self.coordinator.client.publish(CHAMBER_LIGHT_ON)
