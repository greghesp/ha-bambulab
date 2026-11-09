from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.core import Event, HomeAssistant, callback
from homeassistant.helpers.event import async_track_state_change_event
from homeassistant.helpers.restore_state import RestoreEntity
from homeassistant.helpers.entity import EntityCategory

from .const import DOMAIN, LOGGER, Options
from .models import AMSEntity, BambuLabEntity
from .pybambu.const import Features

from homeassistant.components.switch import (
    SwitchEntity,
    SwitchEntityDescription,
)

from .coordinator import BambuDataUpdateCoordinator


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


async def async_setup_entry(
        hass: HomeAssistant,
        entry: ConfigEntry,
        async_add_entities: AddEntitiesCallback
) -> None:
    
    coordinator: BambuDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]
    if not coordinator.get_model().has_full_printer_data:
        return
    
    LOGGER.debug(f"SWITCH::async_setup_entry")

    # A camera is always present so the switch to turn it on and off should be always present.
    async_add_entities([BambuLabCameraSwitch(coordinator, entry)])

    if coordinator.get_model().supports_feature(Features.CAMERA_IMAGE):
        async_add_entities([BambuLabCameraImageSwitch(coordinator, entry)])

    if not coordinator.get_model().print_fun.mqtt_signature_required:
        if coordinator.get_model().supports_feature(Features.PROMPT_SOUND):
                async_add_entities([BambuLabPromptSoundSwitch(coordinator, entry)])

    heaters = getattr(coordinator, "ams_heaters", {})
    for index, ams in coordinator.get_model().ams.data.items():
        if ams is not None and ams.serial in heaters:
            controller = heaters[ams.serial]
            async_add_entities([
                AmsHeaterDryingSwitch(coordinator, controller, index),
                AmsHeaterPowerSwitch(coordinator, controller, index),
            ])
    


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


class BambuLabPromptSoundSwitch(BambuLabSwitch):
    """BambuLab Refresh data Switch"""

    entity_description = PROMPT_SOUND_SWITCH_DESCRIPTION

    @property
    def icon(self) -> str:
        """Return the icon for the switch."""
        return "mdi:volume-high" if self.is_on else "mdi:volume-off"

    @property
    def is_on(self) -> bool:
        """Return True if entity is on."""
        return self.coordinator.get_model().home_flag.xcam_prompt_sound

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Enable A1 / H2D sound."""
        self.coordinator.get_model().info.set_prompt_sound(True)

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Disable A1 / H2D sound."""
        self.coordinator.get_model().info.set_prompt_sound(False)



AMS_HEATER_DRYING_DESCRIPTION = SwitchEntityDescription(
    key="ams_heater_drying",
    icon="mdi:water-off",
    translation_key="ams_heater_drying",
)

AMS_HEATER_POWER_DESCRIPTION = SwitchEntityDescription(
    key="ams_heater_power",
    icon="mdi:heating-coil",
    translation_key="ams_heater_power",
)


class AmsHeaterSwitch(AMSEntity, SwitchEntity):
    """Base for switches controlling an external AMS heater via its smart plug."""

    def __init__(self, coordinator: BambuDataUpdateCoordinator, controller, index: int) -> None:
        super().__init__(coordinator)
        self.index = index
        self.controller = controller
        self._attr_unique_id = f"{controller.ams_serial}_{self.entity_description.key}"


class AmsHeaterDryingSwitch(AmsHeaterSwitch, RestoreEntity):
    """Automatic drying: switch the heater plug from the AMS humidity readings."""

    entity_description = AMS_HEATER_DRYING_DESCRIPTION

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        last_state = await self.async_get_last_state()
        # Ignore a saved unavailable/unknown state rather than reading it as "off".
        if last_state is not None and last_state.state in ("on", "off"):
            self.controller.async_restore_settings(drying_enabled=last_state.state == "on")
        await self.controller.async_evaluate()

    @property
    def is_on(self) -> bool:
        return self.controller.settings.drying_enabled

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        return {
            "heater_plug": self.controller.plug_entity_id,
            "last_reason": self.controller.last_reason,
            "runtime_lockout": self.controller.locked_out,
        }

    async def async_turn_on(self, **kwargs: Any) -> None:
        await self.controller.async_update_settings(drying_enabled=True)
        self.async_write_ha_state()

    async def async_turn_off(self, **kwargs: Any) -> None:
        await self.controller.async_update_settings(drying_enabled=False)
        self.async_write_ha_state()


class AmsHeaterPowerSwitch(AmsHeaterSwitch):
    """Mirrors and switches the smart plug the heater is powered from."""

    entity_description = AMS_HEATER_POWER_DESCRIPTION

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()

        @callback
        def _plug_changed(event: Event) -> None:
            self.async_write_ha_state()

        self.async_on_remove(
            async_track_state_change_event(self.hass, [self.controller.plug_entity_id], _plug_changed)
        )

    @property
    def available(self) -> bool:
        return self.controller.plug_available

    @property
    def is_on(self) -> bool:
        return self.controller.plug_is_on

    async def async_turn_on(self, **kwargs: Any) -> None:
        await self.controller.async_set_plug(True)

    async def async_turn_off(self, **kwargs: Any) -> None:
        await self.controller.async_set_plug(False)
