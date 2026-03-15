"""Support for Bambu Lab through MQTT."""
from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.components.select import SelectEntity

from .const import DOMAIN, LOGGER
from .pybambu.const import Features, SPEED_PROFILE, AIRDUCT_MODES
from .coordinator import BambuDataUpdateCoordinator
from .models import BambuLabEntity


async def async_setup_entry(
        hass: HomeAssistant,
        entry: ConfigEntry,
        async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up BambuLab sensor based on a config entry."""

    coordinator: BambuDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]
    if not coordinator.get_model().has_full_printer_data:
        return

    LOGGER.debug("SELECT::async_setup_entry")
    # Unsure if hybrid mode also blocks speed control.
    if not coordinator.get_model().print_fun.mqtt_signature_required:
        async_add_entities( [ BambuLabSpeedSelect(coordinator) ] )

        if coordinator.get_model().supports_feature(Features.AIRDUCT_MODE):
            async_add_entities([BambuLabAirductModeSelect(coordinator)])


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
        return self.coordinator.get_model().print_job.gcode_state == 'RUNNING'

    @property
    def current_option(self) -> str:
        """Return the current selected live override."""
        return self.coordinator.get_model().speed.name

    async def async_select_option(self, option: str) -> None:
        """Set print speed."""
        self.coordinator.get_model().speed.SetSpeed(option)


class BambuLabAirductModeSelect(BambuLabEntity, SelectEntity):
    """Airduct mode select options."""

    _attr_icon = "mdi:air-filter"
    _attr_translation_key = "airduct_mode"
    _attr_entity_category = EntityCategory.CONFIG

    def __init__(self, coordinator: BambuDataUpdateCoordinator) -> None:
        """Initialize Airduct Mode Select."""
        super().__init__(coordinator=coordinator)
        printer = self.coordinator.get_model().info
        self._attr_unique_id = f"{printer.serial}_AirductMode"
        self._attr_options = [
            mode for mode in self.coordinator.get_model().info.airduct_modes_available
            if mode != "laser"
        ] or ["cooling", "heating"]

    @property
    def available(self) -> bool:
        """Return False if airduct is in a mode not controllable by user (e.g. laser)."""
        return self.coordinator.get_model().info.airduct_mode in (0, 1)

    @property
    def current_option(self) -> str:
        """Return the current selected airduct mode."""
        mode_id = self.coordinator.get_model().info.airduct_mode
        return AIRDUCT_MODES.get(mode_id, AIRDUCT_MODES[0])

    async def async_select_option(self, option: str) -> None:
        """Set airduct mode."""
        self.coordinator.get_model().info.set_airduct_mode(option)
