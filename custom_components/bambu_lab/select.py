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

        # Printers with a BirdsEye camera report more than one live view camera
        if coordinator.get_model().camera.supports_liveview_switch:
            async_add_entities([BambuLabLiveviewCameraSelect(coordinator)])


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


class BambuLabLiveviewCameraSelect(BambuLabEntity, SelectEntity):
    """Which camera feeds the live view: the main camera or the BirdsEye camera.

    The printer streams one camera at a time, so the camera entity shows whichever is chosen.
    """

    _attr_icon = "mdi:camera-switch"
    _attr_translation_key = "liveview_camera"

    def __init__(self, coordinator: BambuDataUpdateCoordinator) -> None:
        """Initialize Live View Camera Select."""
        super().__init__(coordinator=coordinator)
        printer = self.coordinator.get_model().info
        self._attr_unique_id = f"{printer.serial}_LiveviewCamera"

    @property
    def available(self) -> bool:
        """Unavailable until the printer reports a live camera, and while its live view is off."""
        camera = self.coordinator.get_model().camera
        return (
            super().available
            and camera.liveview_camera is not None
            and camera.rtsp_url != "disable"
        )

    @property
    def options(self) -> list[str]:
        """Return the cameras the printer can show."""
        return self.coordinator.get_model().camera.liveview_camera_options

    @property
    def current_option(self) -> str | None:
        """Return the camera feeding the live view."""
        return self.coordinator.get_model().camera.liveview_camera

    async def async_select_option(self, option: str) -> None:
        """Switch the live view camera."""
        self.coordinator.get_model().camera.set_liveview_camera(option)
