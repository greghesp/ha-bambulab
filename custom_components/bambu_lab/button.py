from .models import BambuLabEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity import EntityCategory

from .const import DOMAIN, LOGGER
from .pybambu.commands import PAUSE, RESUME, STOP

from homeassistant.components.button import (
    ButtonDeviceClass,
    ButtonEntity,
    ButtonEntityDescription,
)

from .coordinator import BambuDataUpdateCoordinator

PAUSE_BUTTON_DESCRIPTION = ButtonEntityDescription(
    key="pause",
    name="Pause Printing",
    entity_category=EntityCategory.CONFIG,
)
RESUME_BUTTON_DESCRIPTION = ButtonEntityDescription(
    key="resume",
    name="Resume Printing",
    entity_category=EntityCategory.CONFIG,
)
STOP_BUTTON_DESCRIPTION = ButtonEntityDescription(
    key="stop",
    name="Stop Printing",
    entity_category=EntityCategory.CONFIG,
)


async def async_setup_entry(
        hass: HomeAssistant,
        entry: ConfigEntry,
        async_add_entities: AddEntitiesCallback
) -> None:
    coordinator: BambuDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]
    LOGGER.debug(f"Async Setup Button")

    async_add_entities([BambuLabPauseButton(coordinator, entry), BambuLabResumeButton(coordinator, entry),
                        BambuLabStopButton(coordinator, entry)])


class BambuLabButton(BambuLabEntity, ButtonEntity):
    """Base BambuLab Button"""

    __attr_has_entity_name: bool = True

    def __init__(
            self,
            coordinator: BambuDataUpdateCoordinator,
            config_entry: ConfigEntry
    ) -> None:
        """Initialise a LIFX button."""
        super().__init__(coordinator)
        self._attr_unique_id = (
            f"{config_entry.data['serial']}_{self.entity_description.key}"
        )


class BambuLabPauseButton(BambuLabButton):
    """BambuLab Print Pause Button"""

    __attr_icon = "mdi:pause"
    entity_description = PAUSE_BUTTON_DESCRIPTION

    @property
    def available(self) -> bool:
        """Return if the button is available"""
        if self.coordinator.data.info.gcode_state == "RUNNING":
            return True
        return False

    async def async_press(self) -> None:
        """ Pause the Print on button press"""
        self.coordinator.client.publish(PAUSE)


class BambuLabResumeButton(BambuLabButton):
    """BambuLab Print Resume Button"""

    __attr_icon = "mdi:play"
    entity_description = RESUME_BUTTON_DESCRIPTION

    @property
    def available(self) -> bool:
        """Return if the button is available"""
        if self.coordinator.data.info.gcode_state == "PAUSE":
            return True
        return False

    async def async_press(self) -> None:
        """ Pause the Print on button press"""
        self.coordinator.client.publish(RESUME)


class BambuLabStopButton(BambuLabButton):
    """BambuLab Print Stop Button"""

    __attr_icon = "mdi:stop"
    entity_description = STOP_BUTTON_DESCRIPTION

    @property
    def available(self) -> bool:
        """Return if the button is available"""
        if self.coordinator.data.info.gcode_state == "RUNNING" or self.coordinator.data.info.gcode_state == "PAUSE":
            return True
        return False

    async def async_press(self) -> None:
        """ Stop the Print on button press"""
        self.coordinator.client.publish(STOP)
