"""Support for Bambu Lab through MQTT."""
from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.components.select import SelectEntity

from .const import DOMAIN, LOGGER
from .pybambu.const import Features, SPEED_PROFILE
from .coordinator import BambuDataUpdateCoordinator
from .models import BambuLabEntity


async def async_setup_entry(
        hass: HomeAssistant,
        entry: ConfigEntry,
        async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up BambuLab sensor based on a config entry."""
    LOGGER.debug("SELECT::async_setup_entry")
    coordinator: BambuDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]

    async_add_entities(
        [
            BambuLabSpeedSelect(coordinator)
        ]
    )


class BambuLabSpeedSelect(BambuLabEntity, SelectEntity):
    """Speed select options."""

    _attr_icon = "mdi:speedometer"
    _attr_translation_key = "printing_speed"

    def __init__(self, coordinator: BambuDataUpdateCoordinator) -> None:
        """Initialize Speed Select."""
        super().__init__(coordinator=coordinator)
        printer = self.coordinator.get_model().info
        self._attr_unique_id = f"{printer.serial}_Speed"
        self._attr_options = [
            speed for i, speed in SPEED_PROFILE.items()
        ]

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        available =  self.coordinator.get_model().print_job.gcode_state == 'RUNNING'
        available = available and not self.coordinator.get_model().print_fun.mqtt_signature_required
        return available

    @property
    def current_option(self) -> str:
        """Return the current selected live override."""
        return self.coordinator.get_model().speed.name

    async def async_select_option(self, option: str) -> None:
        """Set print speed."""
        self.coordinator.get_model().speed.SetSpeed(option)
