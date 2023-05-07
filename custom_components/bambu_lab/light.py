from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.core import HomeAssistant

from .const import DOMAIN, LOGGER
from .models import BambuLabEntity
from .pybambu.const import Features

from homeassistant.components.light import (
    LightEntity
)
from .coordinator import BambuDataUpdateCoordinator


async def async_setup_entry(
        hass: HomeAssistant,
        entry: ConfigEntry,
        async_add_entities: AddEntitiesCallback
) -> None:
    coordinator: BambuDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]

    entities_to_add: list = []
    if coordinator.data.supports_feature(Features.CHAMBER_LIGHT):
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
        if self.coordinator.get_model().lights.chamber_light == "on":
            return True
        return False

    @property
    def icon(self) -> str:
        """Return the icon to use in the frontend, if any."""
        return "mdi:led-strip-variant"

    def turn_off(self) -> None:
        """ Turn off the power"""
        self.coordinator.get_model().lights.TurnChamberLightOff()

    def turn_on(self) -> None:
        """ Turn on the power"""
        self.coordinator.get_model().lights.TurnChamberLightOn()
