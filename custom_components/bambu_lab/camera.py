from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.core import HomeAssistant
from yarl import URL
from urllib.parse import urlparse, urlunparse, quote

from homeassistant.components import ffmpeg

from .const import DOMAIN, LOGGER
from .models import BambuLabEntity
from .pybambu.const import Features

from homeassistant.components.camera import Camera, CameraEntityFeature

from .coordinator import BambuDataUpdateCoordinator


async def async_setup_entry(
        hass: HomeAssistant,
        entry: ConfigEntry,
        async_add_entities: AddEntitiesCallback
) -> None:
    LOGGER.debug(f"CAMERA::async_setup_entry")

    coordinator: BambuDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]
    if coordinator.get_model().supports_feature(Features.CAMERA_RTSP):
        entities_to_add: list = [BambuLabCamera(coordinator, entry)]
        async_add_entities(entities_to_add)


class BambuLabCamera(BambuLabEntity, Camera):
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
        self._access_code = config_entry.data['access_code']
        self._host = config_entry.data['host']

        super().__init__(coordinator=coordinator)
        Camera.__init__(self)

    @property
    def is_streaming(self) -> bool:
        if self.coordinator.get_model().camera.rtsp_url == "disable" or None:
            return False
        return True

    @property
    def is_recording(self) -> bool:
        if self.coordinator.get_model().camera.recording == "enable":
            return True
        return False

    async def stream_source(self) -> str | None:
        if self.coordinator.get_model().camera.rtsp_url is not None:
            # rtsps://192.168.1.1/streaming/live/1

            parsed_url = urlparse(self.coordinator.get_model().camera.rtsp_url)
            url = fr"{parsed_url.scheme}://bblp:{self._access_code}@{parsed_url.netloc}{parsed_url.path}"

            LOGGER.debug(f"Camera RTSP Feed is {url}")
            return str(url)
        LOGGER.debug("No RTSP Feed available")
        return None

    # TODO: async camera image doesn't work for some reason
    async def async_camera_image(
            self, width: int | None = None, height: int | None = None
    ) -> bytes | None:
        """Return a still image response from the camera."""
        stream_source = await self.stream_source()
        if not stream_source:
            return None
        return await ffmpeg.async_get_image(
            self.hass,
            stream_source,
            width=width,
            height=height,
        )
