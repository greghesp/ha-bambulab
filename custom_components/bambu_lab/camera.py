from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.core import HomeAssistant
import yarl
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

        self._attr_unique_id = f"{config_entry.data['serial']}camera"
        super().__init__(coordinator=coordinator)
        Camera.__init__(self)

    @property
    def is_streaming(self) -> bool:
        if self.coordinator.get_model().camera.rtsp_url == "disable":
            return False
        return True

    @property
    def is_recording(self) -> bool:
        if self.coordinator.get_model().camera.recording == "enable":
            return True
        return False

    async def stream_source(self) -> str | None:
        url = yarl.URL(self.coordinator.get_model().camera.rtsp_url)
        # TODO: Replace password with access code from config flow
        url = url.with_user('bblp').with_password('xxxxxx')
        return str(url)

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
