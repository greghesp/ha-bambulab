from .models import BambuLabEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.core import HomeAssistant, callback
from .const import DOMAIN, LOGGER

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
    LOGGER.debug(f"Entry {entry.data['serial']}")
    LOGGER.debug(f"Async Setup Light {coordinator.data}")

    entities_to_add: list = []

    #   TODO:  Somehow need to handle this for the P1P. State is always unknown for all at initialisation,
    #    so we need to be able to do this after the MQTT data is populated
    # if not coordinator.data.lights.chamber_light == "Unknown":
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
        if not self.coordinator.data.lights.chamber_light == "Unknown":
            return True
        return False

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
