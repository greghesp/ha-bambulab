from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.core import HomeAssistant

from .const import DOMAIN, LOGGER
from .models import BambuLabEntity
from .pybambu.const import Features

from homeassistant.components.camera import (
    Camera
)
from .coordinator import BambuDataUpdateCoordinator


async def async_setup_entry(
        hass: HomeAssistant,
        entry: ConfigEntry,
        async_add_entities: AddEntitiesCallback
) -> None:
    coordinator: BambuDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]

    entities_to_add: list = []
    # if coordinator.data.supports_feature(Features.CHAMBER_LIGHT):
    #     entities_to_add.append(BambuLabChamberLight(coordinator, entry))
    entities_to_add.append(BambuLabCamera(coordinator, entry))
    async_add_entities(entities_to_add)


class BambuLabCamera(BambuLabEntity, Camera):
    """ Defined the Camera """

    _attr_translation_key = "camera"
    _attr_icon = "mdi:camera"

    def __init__(
            self,
            coordinator: BambuDataUpdateCoordinator,
            config_entry: ConfigEntry
    ) -> None:
        """Initialize the sensor."""
        self._attr_unique_id = f"{config_entry.data['serial']}camera"
        super().__init__(coordinator=coordinator)

    @property
    def is_streaming(self) -> bool:
        return False

    @property
    def is_recording(self) -> bool:
        return False

    async def stream_source(self) -> str | None:
        return self.coordinator.get_model().camera.rtsp_url
