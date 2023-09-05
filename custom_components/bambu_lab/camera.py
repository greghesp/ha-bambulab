from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.core import HomeAssistant
from yarl import URL
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
    coordinator: BambuDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]
    if coordinator.get_model().supports_feature(Features.CHAMBER_FAN):
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
            url = URL(self.coordinator.get_model().camera.rtsp_url).with_user('bblp').with_password(
                self._access_code)
            return str(url)
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
