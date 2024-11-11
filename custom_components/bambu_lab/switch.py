from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import EntityCategory

from .const import DOMAIN, LOGGER
from .models import BambuLabEntity
from .pybambu.const import Features

from homeassistant.components.switch import (
    SwitchEntity,
    SwitchEntityDescription,
)

from .coordinator import BambuDataUpdateCoordinator


MANUAL_REFRESH_MODE_SWITCH_DESCRIPTION = SwitchEntityDescription(
    key="manual",
    icon="mdi:refresh-auto",
    translation_key="manual",
    entity_category=EntityCategory.CONFIG,
)

CAMERA_SWITCH_DESCRIPION = SwitchEntityDescription(
    key="camera",
    icon="mdi:refresh-auto",
    translation_key="camera",
    entity_category=EntityCategory.CONFIG,
)

CAMERA_IMAGE_SENSOR_DESCRIPION = SwitchEntityDescription(
    key="imagecamera",
    icon="mdi:refresh-auto",
    translation_key="imagecamera",
    entity_category=EntityCategory.CONFIG,
)

async def async_setup_entry(
        hass: HomeAssistant,
        entry: ConfigEntry,
        async_add_entities: AddEntitiesCallback
) -> None:
    coordinator: BambuDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]
    LOGGER.debug(f"SWITCH::async_setup_entry")

    if coordinator.get_model().supports_feature(Features.MANUAL_MODE):
        async_add_entities([BambuLabManualModeSwitch(coordinator, entry)])

    # A camera is always present so the switch to turn it on and off should be always present.
    async_add_entities([BambuLabCameraSwitch(coordinator, entry)])

    if coordinator.get_model().supports_feature(Features.CAMERA_IMAGE):
        async_add_entities([BambuLabCameraImageSwitch(coordinator, entry)])


class BambuLabSwitch(BambuLabEntity, SwitchEntity):
    """Base BambuLab Switch"""

    def __init__(
            self,
            coordinator: BambuDataUpdateCoordinator,
            config_entry: ConfigEntry
    ) -> None:
        """Initialise a Switch."""
        super().__init__(coordinator)
        self._attr_unique_id = (
            f"{config_entry.data['serial']}_{self.entity_description.key}"
        )
        self._attr_is_on = False


class BambuLabManualModeSwitch(BambuLabSwitch):
    """BambuLab Refresh data Switch"""

    entity_description = MANUAL_REFRESH_MODE_SWITCH_DESCRIPTION

    def __init__(
            self,
            coordinator: BambuDataUpdateCoordinator,
            config_entry: ConfigEntry
    ) -> None:
        super().__init__(coordinator, config_entry)
        self._attr_is_on = self.coordinator.client.manual_refresh_mode

    @property
    def available(self) -> bool:
        return self.coordinator.get_model().info.mqtt_mode == "local"

    @property
    def icon(self) -> str:
        """Return the icon for the switch."""
        return "mdi:pause-octagon-outline" if self.is_on else "mdi:refresh-auto"

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Enable manual refresh mode."""
        self._attr_is_on = not self.coordinator.client.manual_refresh_mode
        await self.coordinator.set_manual_refresh_mode(True)

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Disable manual refresh mode."""
        self._attr_is_on = not self.coordinator.client.manual_refresh_mode
        await self.coordinator.set_manual_refresh_mode(False)

class BambuLabCameraSwitch(BambuLabSwitch):
    """BambuLab Refresh data Switch"""

    entity_description = CAMERA_SWITCH_DESCRIPION

    def __init__(
            self,
            coordinator: BambuDataUpdateCoordinator,
            config_entry: ConfigEntry
    ) -> None:
        super().__init__(coordinator, config_entry)
        self._attr_is_on = self.coordinator.camera_enabled

    @property
    def available(self) -> bool:
        return True

    @property
    def icon(self) -> str:
        """Return the icon for the switch."""
        return "mdi:video" if self.is_on else "mdi:video-off"

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Enable the camera."""
        self._attr_is_on = True
        await self.coordinator.set_camera_enabled(self._attr_is_on)

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Disable the camera."""
        self._attr_is_on = False
        await self.coordinator.set_camera_enabled(self._attr_is_on)


class BambuLabCameraImageSwitch(BambuLabSwitch):
    """BambuLab Refresh data Switch"""

    entity_description = CAMERA_IMAGE_SENSOR_DESCRIPION

    def __init__(
            self,
            coordinator: BambuDataUpdateCoordinator,
            config_entry: ConfigEntry
    ) -> None:
        super().__init__(coordinator, config_entry)
        self._attr_is_on = self.coordinator.camera_as_image_sensor

    @property
    def available(self) -> bool:
        return self.coordinator.camera_enabled

    @property
    def icon(self) -> str:
        """Return the icon for the switch."""
        return "mdi:image" if self.is_on else "mdi:video"

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Enable the camera."""
        self._attr_is_on = True
        await self.coordinator.set_camera_as_image_sensor(self._attr_is_on)

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Disable the camera."""
        self._attr_is_on = False
        await self.coordinator.set_camera_as_image_sensor(self._attr_is_on)
