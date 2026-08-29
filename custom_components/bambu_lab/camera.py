import os

from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.core import HomeAssistant
from io import BytesIO
from PIL import Image, ImageDraw

from .const import DOMAIN, LOGGER, Options
from .models import BambuLabEntity
from .pybambu.const import Features
from .pybambu.utils import get_authenticated_rtsp_url
from .definitions import BambuLabSensorEntityDescription

from homeassistant.components.camera import Camera, CameraEntityFeature

from .coordinator import BambuDataUpdateCoordinator

CHAMBER_CAMERA_SENSOR = BambuLabSensorEntityDescription(
        key="p1p_camera",
        translation_key="p1p_camera",
        value_fn=lambda self: self.coordinator.get_model().get_camera_image(),
        exists_fn=lambda coordinator: coordinator.get_model().supports_feature(Features.CAMERA_IMAGE) and
                                      coordinator.get_option_enabled(Options.CAMERA) and
                                      not coordinator.get_option_enabled(Options.IMAGECAMERA)
    )

async def async_setup_entry(
        hass: HomeAssistant,
        entry: ConfigEntry,
        async_add_entities: AddEntitiesCallback
) -> None:

    coordinator: BambuDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]

    LOGGER.debug(f"CAMERA::async_setup_entry")

    # NOTE: We intentionally do NOT gate on has_full_printer_data here.
    #
    # When HA restarts while the printer is offline, has_full_printer_data is False
    # at setup time, causing camera entities to never be registered. When the printer
    # later comes online, _reinitialize_sensors() unloads and reloads all platforms —
    # but if async_setup_entry bails out early again, the camera entity is permanently
    # lost from the registry until the integration is manually reloaded.
    #
    # The correct HA pattern is to always register entities and let them sit as
    # `unavailable` until the device is reachable. The coordinator's
    # _reinitialize_sensors() call (triggered by event_printer_ready) then causes
    # async_setup_entry to run again with full data, at which point the entity
    # transitions to a live state.
    #
    # For the RTSP camera we check the option flags (always available from config
    # entry options) and register unconditionally; stream_source() handles the
    # unavailable state gracefully by returning None.
    #
    # For the image-based camera, exists_fn still guards against printers that
    # genuinely don't support the feature — but only once full data is available.
    # Before that, we skip it rather than crashing; it will be registered on the
    # next _reinitialize_sensors() pass after event_printer_ready fires.

    if coordinator.get_option_enabled(Options.CAMERA):
        if coordinator.get_model().supports_feature(Features.CAMERA_RTSP):
            # Printer supports RTSP and camera option is enabled.
            # Register the entity now; stream_source() will return None (gracefully)
            # until the printer is online and rtsp_url is populated.
            async_add_entities([BambuLabRtspCamera(coordinator, entry)])
        elif coordinator.get_model().has_full_printer_data:
            # Full printer data is available: we can reliably evaluate CAMERA_IMAGE
            # support and the IMAGECAMERA option. Only register if the feature is
            # actually present (some printers don't have a chamber camera at all).
            if CHAMBER_CAMERA_SENSOR.exists_fn(coordinator):
                async_add_entities([BambuLabImageCamera(coordinator, entry)])
        # If neither branch matches (no full data yet, non-RTSP printer), the entity
        # will be registered on the next _reinitialize_sensors() pass.


class BambuLabRtspCamera(BambuLabEntity, Camera):
    """ Defined the Camera """

    _attr_translation_key = "camera"
    _attr_icon = "mdi:camera"
    _attr_supported_features = CameraEntityFeature.STREAM
    _attr_brand = "Bambu Lab"

    def __init__(
            self,
            coordinator: BambuDataUpdateCoordinator,
            config_entry: ConfigEntry
    ) -> None:
        """Initialize the sensor."""

        self._attr_unique_id = f"{config_entry.data['serial']}_camera"
        self._access_code = config_entry.options.get("access_code", "")
        self._host = config_entry.options.get("host", "")

        super().__init__(coordinator=coordinator)
        Camera.__init__(self)

    @property
    def is_streaming(self) -> bool:
        return self.available

    @property
    def available(self) -> bool:
        """Return whether the printer has supplied a usable RTSP endpoint."""
        return super().available and self._stream_source() is not None

    @property
    def is_recording(self) -> bool:
        return False

    @property
    def use_stream_for_stills(self) -> bool:
        return True

    async def stream_source(self) -> str | None:
        return self._stream_source()

    def _stream_source(self) -> str | None:
        return get_authenticated_rtsp_url(
            self.coordinator.get_model().camera.rtsp_url,
            self._host,
            self._access_code,
        )

    def camera_image(self, width=None, height=None):
        """Return a still image placeholder if RTSP fails."""
        img_width = width or 320
        img_height = height or 240

        # Create black background image
        img = Image.new("RGB", (img_width, img_height), color=(0, 0, 0))
        draw = ImageDraw.Draw(img)

        mark_height = img_height // 4
        mark_width = mark_height // 6
        spacing = mark_height // 4  # space between line and dot
        center_x = img_width // 2
        center_y = img_height // 2 - spacing // 2  # shift line slightly up

        # Draw the line (upper part of exclamation mark)
        draw.rectangle(
            [center_x - mark_width // 2, center_y - mark_height // 2,
            center_x + mark_width // 2, center_y + mark_height // 2],
            fill=(255, 0, 0)
        )

        # Draw the dot below the line with spacing
        dot_radius = mark_width
        dot_center_y = center_y + mark_height // 2 + spacing + dot_radius
        draw.ellipse(
            [center_x - dot_radius, dot_center_y - dot_radius,
            center_x + dot_radius, dot_center_y + dot_radius],
            fill=(255, 0, 0)
        )

        # Convert image to bytes
        buf = BytesIO()
        img.save(buf, format="JPEG")
        return buf.getvalue()

class BambuLabImageCamera(BambuLabEntity, Camera):
    """Camera from chamber image"""

    _attr_translation_key = "camera"
    _attr_icon = "mdi:camera"
    _attr_brand = "Bambu Lab"

    def __init__(
        self,
        coordinator: BambuDataUpdateCoordinator,
        config_entry: ConfigEntry,
    ) -> None:
        """Initialize the camera entity."""

        self._attr_unique_id = f"{config_entry.data['serial']}_camera"

        super().__init__(coordinator=coordinator)
        Camera.__init__(self)

    def camera_image(self, width: int | None = None, height: int | None = None) -> bytes | None:
        return self.coordinator.get_model().chamber_image.get_image()

    @property
    def is_streaming(self) -> bool:
        return self.available
    
    @property
    def is_recording(self) -> bool:
        return False
