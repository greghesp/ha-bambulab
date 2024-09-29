from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.core import HomeAssistant
from urllib.parse import urlparse

from .const import DOMAIN, LOGGER
from .models import BambuLabEntity
from .pybambu.const import Features
from .definitions import CHAMBER_IMAGE_SENSOR

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
        entities_to_add: list = [BambuLabRtspCamera(coordinator, entry)]
        async_add_entities(entities_to_add)

    elif CHAMBER_IMAGE_SENSOR.exists_fn(coordinator):
        entities_to_add: list = [BambuLabImageCamera(coordinator, entry)]
        async_add_entities(entities_to_add)


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
        self._access_code = config_entry.options['access_code']
        self._host = config_entry.options['host']

        super().__init__(coordinator=coordinator)
        Camera.__init__(self)

    @property
    def is_streaming(self) -> bool:
        return self.available

    @property
    def is_recording(self) -> bool:
        if self.coordinator.get_model().camera.recording == "enable":
            return True
        return False

    @property
    def use_stream_for_stills(self) -> bool:
        return True
    
    @property
    def available(self) -> bool:
        url = self.coordinator.get_model().camera.rtsp_url
        return url != None and url != "disable"

    async def stream_source(self) -> str | None:
        if self.available:
            # rtsps://192.168.1.1/streaming/live/1

            LOGGER.debug(f"Raw RTSP URL: {self.coordinator.get_model().camera.rtsp_url}")
            parsed_url = urlparse(self.coordinator.get_model().camera.rtsp_url)
            split_host = parsed_url.netloc.split(':')
            if self._host != "":
                # For unknown reasons the returned rtsp URL sometimes has a completely incorrect IP address in it for the host.
                # If we have the host IP (may not in bambu cloud mode), rewrite the URL to have that.
                port = "322" if (len(split_host) == 1) else split_host[1]
                url = fr"{parsed_url.scheme}://bblp:{self._access_code}@{self._host}:{port}{parsed_url.path}"
            else:
                url = fr"{parsed_url.scheme}://bblp:{self._access_code}@{parsed_url.netloc}{parsed_url.path}"
            LOGGER.debug(f"Adjusted RTSP URL: {url.replace(self._access_code, '**REDACTED**')}")
            return str(url)
        LOGGER.debug("No RTSP Feed available")
        return None


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
        return self.coordinator.get_model().chamber_image.get_jpeg()
