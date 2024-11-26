from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import EntityCategory

from .const import DOMAIN, LOGGER
from .models import BambuLabEntity
from .pybambu.commands import PAUSE, RESUME, STOP
from .pybambu.const import Features

from homeassistant.components.button import (
    ButtonEntity,
    ButtonEntityDescription,
)

from .coordinator import BambuDataUpdateCoordinator

PAUSE_BUTTON_DESCRIPTION = ButtonEntityDescription(
    key="pause",
    icon="mdi:pause",
    translation_key="pause",
    entity_category=EntityCategory.CONFIG,
)
RESUME_BUTTON_DESCRIPTION = ButtonEntityDescription(
    key="resume",
    icon="mdi:play",
    translation_key="resume",
    entity_category=EntityCategory.CONFIG,
)
STOP_BUTTON_DESCRIPTION = ButtonEntityDescription(
    key="stop",
    icon="mdi:stop",
    translation_key="stop",
    entity_category=EntityCategory.CONFIG,
)
FORCE_REFRESH_BUTTON_DESCRIPTION = ButtonEntityDescription(
    key="refresh",
    icon="mdi:refresh",
    translation_key="refresh",
    entity_category=EntityCategory.DIAGNOSTIC,
)


async def async_setup_entry(
        hass: HomeAssistant,
        entry: ConfigEntry,
        async_add_entities: AddEntitiesCallback
) -> None:
    coordinator: BambuDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]
    LOGGER.debug(f"BUTTON::async_setup_entry")

    buttons = [
        BambuLabPauseButton(coordinator, entry),
        BambuLabResumeButton(coordinator, entry),
        BambuLabStopButton(coordinator, entry),
        BambuLabRefreshButton(coordinator, entry)
    ]

    async_add_entities(buttons)


class BambuLabButton(BambuLabEntity, ButtonEntity):
    """Base BambuLab Button"""

    def __init__(
            self,
            coordinator: BambuDataUpdateCoordinator,
            config_entry: ConfigEntry
    ) -> None:
        """Initialise a button."""
        super().__init__(coordinator)
        self._attr_unique_id = (
            f"{config_entry.data['serial']}_{self.entity_description.key}"
        )


class BambuLabPauseButton(BambuLabButton):
    """BambuLab Print Pause Button"""

    entity_description = PAUSE_BUTTON_DESCRIPTION

    @property
    def available(self) -> bool:
        """Return if the button is available"""
        if self.coordinator.data.print_job.gcode_state == "RUNNING":
            return True
        return False

    async def async_press(self) -> None:
        """ Pause the Print on button press"""
        self.coordinator.client.publish(PAUSE)


class BambuLabResumeButton(BambuLabButton):
    """BambuLab Print Resume Button"""

    entity_description = RESUME_BUTTON_DESCRIPTION

    @property
    def available(self) -> bool:
        """Return if the button is available"""
        if self.coordinator.data.print_job.gcode_state == "PAUSE":
            return True
        return False

    async def async_press(self) -> None:
        """ Pause the Print on button press"""
        self.coordinator.client.publish(RESUME)


class BambuLabStopButton(BambuLabButton):
    """BambuLab Print Stop Button"""

    entity_description = STOP_BUTTON_DESCRIPTION

    @property
    def available(self) -> bool:
        """Return if the button is available"""
        if self.coordinator.data.print_job.gcode_state == "RUNNING" or self.coordinator.data.print_job.gcode_state == "PAUSE":
            return True
        return False

    async def async_press(self) -> None:
        """ Stop the Print on button press"""
        self.coordinator.client.publish(STOP)


class BambuLabRefreshButton(BambuLabButton):
    """BambuLab Refresh data Button"""

    entity_description = FORCE_REFRESH_BUTTON_DESCRIPTION

    @property
    def available(self) -> bool:
        return True

    async def async_press(self) -> None:
        """ Force refresh MQTT info"""
        await self.coordinator.client.refresh()
