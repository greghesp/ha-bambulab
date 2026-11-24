import os

from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.core import HomeAssistant, callback
from io import BytesIO
from PIL import Image, ImageDraw

from .const import DOMAIN, LOGGER, Options
from .models import BambuLabEntity
from .pybambu.const import Features
from .pybambu.utils import async_resolve_ipv4, get_authenticated_rtsp_url
from .definitions import BambuLabSensorEntityDescription

from homeassistant.components.camera import Camera, CameraEntityFeature
from homeassistant.components.stream import Stream
from homeassistant.components.stream.const import CONF_USE_WALLCLOCK_AS_TIMESTAMPS

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

        super().__init__(coordinator=coordinator)
        Camera.__init__(self)
        # P2S and X1 RTSPS feeds start at dts 0 and then jump by hours.
        # The stream worker aborts when that gap exceeds 30 seconds.
        # Arrival-time timestamps keep the live view open.
        self.stream_options[CONF_USE_WALLCLOCK_AS_TIMESTAMPS] = True
        self._had_stream_source = False

    @callback
    def _handle_coordinator_update(self) -> None:
        # Home Assistant only picks a WebRTC provider (go2rtc) when a camera is added.
        # LAN Only Liveview may be off at that point, so look again when the stream URL
        # appears or goes away. Otherwise the camera stays on HLS until a reload.
        has_stream_source = self._stream_source() is not None
        if has_stream_source != self._had_stream_source:
            self._had_stream_source = has_stream_source
            self.hass.async_create_task(self.async_refresh_providers())
        super()._handle_coordinator_update()

    @property
    def is_streaming(self) -> bool:
        return self.available

    @property
    def available(self) -> bool:
        """Return whether the printer is online and has supplied a usable RTSP endpoint."""
        return (super().available
                and self.coordinator.get_model().info.online
                and self._stream_source() is not None)

    @property
    def is_recording(self) -> bool:
        return False

    @property
    def use_stream_for_stills(self) -> bool:
        return True

    async def stream_source(self) -> str | None:
        # go2rtc checks the certificate when the URL contains a hostname, but not when
        # it contains an IP address. The printer's certificate never carries the user's
        # hostname, so the connection fails unless the name is resolved here.
        if self._stream_source() is None:
            return None
        host = self.coordinator.get_model().info.ip_address
        return self._stream_source(await async_resolve_ipv4(host))

    async def async_create_stream(self) -> Stream | None:
        # Home Assistant keeps this stream's URL for the life of the entity, so a resolved
        # address would go stale if DHCP moved the printer. ffmpeg doesn't check the
        # certificate, so it can keep using the hostname.
        stream = await super().async_create_stream()
        if stream and (source := self._stream_source()):
            stream.source = source
        return stream

    def _stream_source(self, host: str | None = None) -> str | None:
        model = self.coordinator.get_model()
        return get_authenticated_rtsp_url(
            model.camera.rtsp_url,
            host or model.info.ip_address,
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
    # The chamber image is pushed by the printer over its own socket rather
    # than pulled on demand, so it keeps running even when nobody is looking.
    # ON_OFF exposes camera.turn_on / camera.turn_off to start and stop it.
    _attr_supported_features = CameraEntityFeature.ON_OFF

    def __init__(
        self,
        coordinator: BambuDataUpdateCoordinator,
        config_entry: ConfigEntry,
    ) -> None:
        """Initialize the camera entity."""

        self._attr_unique_id = f"{config_entry.data['serial']}_camera"

        super().__init__(coordinator=coordinator)
        Camera.__init__(self)

    @property
    def _camera_enabled(self) -> bool:
        """Return whether the chamber image thread is running."""
        return self.coordinator.client.camera_enabled

    def camera_image(self, width: int | None = None, height: int | None = None) -> bytes | None:
        # Do not serve the last frame captured before the camera was turned off:
        # a stale image would look like a live view of a printer we stopped
        # watching. Returning None fails the request instead.
        if not self._camera_enabled:
            return None
        return self.coordinator.get_model().chamber_image.get_image()

    @property
    def available(self) -> bool:
        """Go unavailable while the printer is offline rather than serving the last stale frame."""
        return super().available and self.coordinator.get_model().info.online

    @property
    def is_streaming(self) -> bool:
        return self.available and self._camera_enabled

    @property
    def is_recording(self) -> bool:
        return False

    async def async_turn_on(self) -> None:
        """Start the chamber image stream."""
        # set_camera_enabled() starts or stops the chamber image thread and
        # joins it, so keep it off the event loop.
        await self.hass.async_add_executor_job(
            self.coordinator.client.set_camera_enabled, True
        )
        self.async_write_ha_state()

    async def async_turn_off(self) -> None:
        """Stop the chamber image stream."""
        await self.hass.async_add_executor_job(
            self.coordinator.client.set_camera_enabled, False
        )
        self.async_write_ha_state()
