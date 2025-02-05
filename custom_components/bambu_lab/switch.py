from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import EntityCategory

from .const import DOMAIN, LOGGER, Options
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

PROMPT_SOUND_SWITCH_DESCRIPTION = SwitchEntityDescription(
    key="prompt_sound",
    icon="mdi:audio",
    translation_key="prompt_sound",
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

FTP_SWITCH_DESCRIPTION = SwitchEntityDescription(
    key="ftp",
    icon="mdi:folder-network",
    translation_key="ftp",
    entity_category=EntityCategory.CONFIG,
)

TIMELAPSE_SWITCH_DESCRIPTION = SwitchEntityDescription(
    key="timelapse",
    icon="mdi:folder-network",
    translation_key="timelapse",
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

    if coordinator.get_model().supports_feature(Features.PROMPT_SOUND):
        async_add_entities([BambuLabPromptSoundSwitch(coordinator, entry)])

    if coordinator.get_model().supports_feature(Features.FTP):
        async_add_entities([BambuLabFtpSwitch(coordinator, entry)])

    if coordinator.get_model().supports_feature(Features.TIMELAPSE):
        async_add_entities([BambuLabTimelapseSwitch(coordinator, entry)])


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
        self._attr_is_on = self.coordinator.get_option_enabled(Options.MANUALREFRESH)

    @property
    def available(self) -> bool:
        return self.coordinator.get_model().info.mqtt_mode == "local"

    @property
    def icon(self) -> str:
        """Return the icon for the switch."""
        return "mdi:pause-octagon-outline" if self.is_on else "mdi:refresh-auto"

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Enable manual refresh mode."""
        self._attr_is_on = True
        await self.coordinator.set_option_enabled(Options.MANUALREFRESH, True)

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Disable manual refresh mode."""
        self._attr_is_on = False
        await self.coordinator.set_option_enabled(Options.MANUALREFRESH, False)


class BambuLabCameraSwitch(BambuLabSwitch):
    """BambuLab Refresh data Switch"""

    entity_description = CAMERA_SWITCH_DESCRIPION

    def __init__(
            self,
            coordinator: BambuDataUpdateCoordinator,
            config_entry: ConfigEntry
    ) -> None:
        super().__init__(coordinator, config_entry)
        self._attr_is_on = self.coordinator.get_option_enabled(Options.CAMERA)

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
        await self.coordinator.set_option_enabled(Options.CAMERA, True)

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Disable the camera."""
        self._attr_is_on = False
        await self.coordinator.set_option_enabled(Options.CAMERA, False)


class BambuLabCameraImageSwitch(BambuLabSwitch):
    """BambuLab Refresh data Switch"""

    entity_description = CAMERA_IMAGE_SENSOR_DESCRIPION

    def __init__(
            self,
            coordinator: BambuDataUpdateCoordinator,
            config_entry: ConfigEntry
    ) -> None:
        super().__init__(coordinator, config_entry)
        self._attr_is_on = self.coordinator.get_option_enabled(Options.IMAGECAMERA)

    @property
    def available(self) -> bool:
        return self.coordinator.get_option_enabled(Options.CAMERA)

    @property
    def icon(self) -> str:
        """Return the icon for the switch."""
        return "mdi:image" if self.is_on else "mdi:video"

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Enable the camera."""
        self._attr_is_on = True
        await self.coordinator.set_option_enabled(Options.IMAGECAMERA, self._attr_is_on)

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Disable the camera."""
        self._attr_is_on = False
        await self.coordinator.set_option_enabled(Options.IMAGECAMERA, self._attr_is_on)


class BambuLabFtpSwitch(BambuLabSwitch):
    """BambuLab FTP Switch"""

    entity_description = FTP_SWITCH_DESCRIPTION

    def __init__(
            self,
            coordinator: BambuDataUpdateCoordinator,
            config_entry: ConfigEntry
    ) -> None:
        super().__init__(coordinator, config_entry)
        self._attr_is_on = self.coordinator.get_option_enabled(Options.FTP)

    @property
    def available(self) -> bool:
        return True

    @property
    def icon(self) -> str:
        """Return the icon for the switch."""
        return "mdi:folder-network" if self.is_on else "mdi:folder-hidden"

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Enable FTP."""
        self._attr_is_on = True
        await self.coordinator.set_option_enabled(Options.FTP, self._attr_is_on)

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Disable FTP."""
        self._attr_is_on = False
        await self.coordinator.set_option_enabled(Options.FTP, self._attr_is_on)


class BambuLabTimelapseSwitch(BambuLabSwitch):
    """BambuLab FTP Switch"""

    entity_description = TIMELAPSE_SWITCH_DESCRIPTION

    def __init__(
            self,
            coordinator: BambuDataUpdateCoordinator,
            config_entry: ConfigEntry
    ) -> None:
        super().__init__(coordinator, config_entry)
        self._attr_is_on = self.coordinator.get_option_enabled(Options.TIMELAPSE)

    @property
    def available(self) -> bool:
        return True

    @property
    def icon(self) -> str:
        """Return the icon for the switch."""
        return "mdi:folder-network" if self.is_on else "mdi:folder-hidden"

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Enable Timelapse Download."""
        self._attr_is_on = True
        await self.coordinator.set_option_enabled(Options.TIMELAPSE, self._attr_is_on)

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Disable Timelapse Download."""
        self._attr_is_on = False
        await self.coordinator.set_option_enabled(Options.TIMELAPSE, self._attr_is_on)


class BambuLabPromptSoundSwitch(BambuLabSwitch):
    """BambuLab Refresh data Switch"""

    entity_description = PROMPT_SOUND_SWITCH_DESCRIPTION

    @property
    def icon(self) -> str:
        """Return the icon for the switch."""
        return "mdi:volume-on" if self.is_on else "mdi:volume-off"

    @property
    def is_on(self) -> bool:
        """Return True if entity is on."""
        return self.coordinator.get_model().home_flag.xcam_prompt_sound

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Enable manual refresh mode."""
        self.coordinator.get_model().info.set_prompt_sound(True)

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Disable manual refresh mode."""
        self.coordinator.get_model().info.set_prompt_sound(False)
