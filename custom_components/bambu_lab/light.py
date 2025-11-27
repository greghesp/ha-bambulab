from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.core import HomeAssistant

from .const import DOMAIN, LOGGER
from .models import BambuLabEntity
from .pybambu.const import Features

from homeassistant.components.light import (
    LightEntity,
    ColorMode,
)
from .coordinator import BambuDataUpdateCoordinator


async def async_setup_entry(
        hass: HomeAssistant,
        entry: ConfigEntry,
        async_add_entities: AddEntitiesCallback
) -> None:
    coordinator: BambuDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]
    if not coordinator.get_model().has_full_printer_data:
        return

    entities_to_add: list = []
    entities_to_add.append(BambuLabChamberLight(coordinator, entry))
    if coordinator.data.supports_feature(Features.HEATBED_LIGHT):
        entities_to_add.append(BambuLabHeatbedLight(coordinator, entry))
    async_add_entities(entities_to_add)


class BambuLabChamberLight(BambuLabEntity, LightEntity):
    """ Defined the Chamber Light """

    _attr_icon = "mdi:led-strip-variant"
    _attr_color_mode = ColorMode.ONOFF
    _attr_supported_color_modes = {ColorMode.ONOFF}

    def __init__(
            self,
            coordinator: BambuDataUpdateCoordinator,
            config_entry: ConfigEntry
    ) -> None:
        """Initialize the sensor."""

        if config_entry.data['device_type'] == "A1 Mini":
            self._attr_unique_id = f"{config_entry.data['serial']}_camera_light"
            self._attr_translation_key = "camera_light"
        else:
            self._attr_unique_id = f"{config_entry.data['serial']}_chamber_light"
            self._attr_translation_key = "chamber_light"

        super().__init__(coordinator=coordinator)

    @property
    def available(self) -> bool:
        """Is the light available"""
        return True

    @property
    def is_on(self) -> bool:
        """Return the state of the switch"""
        if self.coordinator.get_model().lights.is_chamber_light_on:
            return True
        return False

    def turn_off(self) -> None:
        """ Turn off the power"""
        self.coordinator.get_model().lights.TurnChamberLightOff()

    def turn_on(self) -> None:
        """ Turn on the power"""
        self.coordinator.get_model().lights.TurnChamberLightOn()

class BambuLabHeatbedLight(BambuLabEntity, LightEntity):
    """ Defined the Heatbed Light """

    _attr_icon = "mdi:led-strip-variant"
    _attr_color_mode = ColorMode.ONOFF
    _attr_supported_color_modes = {ColorMode.ONOFF}

    def __init__(
            self,
            coordinator: BambuDataUpdateCoordinator,
            config_entry: ConfigEntry
    ) -> None:
        """Initialize the sensor."""

        self._attr_unique_id = f"{config_entry.data['serial']}_heatbed_light"
        self._attr_translation_key = "heatbed_light"

        super().__init__(coordinator=coordinator)

    @property
    def available(self) -> bool:
        """Is the light available"""
        return True

    @property
    def is_on(self) -> bool | None:
        """Return the state of the switch"""
        return self.coordinator.get_model().lights.is_heatbed_light_on

    def turn_off(self) -> None:
        """ Turn off the power"""
        self.coordinator.get_model().lights.TurnHeatbedLightOff()

    def turn_on(self) -> None:
        """ Turn on the power"""
        self.coordinator.get_model().lights.TurnHeatbedLightOn()
