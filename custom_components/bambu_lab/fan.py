from dataclasses import dataclass
from collections.abc import Callable

from homeassistant.components.fan import (
    FanEntity,
    FanEntityFeature,
    FanEntityDescription
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN, LOGGER
from .coordinator import BambuDataUpdateCoordinator
from .models import BambuLabEntity
from .pybambu.const import Features
#from .pybambu.commands import part_cooling_fan_speed


@dataclass
class BambuLabFanEntityDescriptionMixin:
    """Mixin for required keys."""
    value_fn: Callable[..., any]


@dataclass
class BambuLabFanEntityDescription(FanEntityDescription, BambuLabFanEntityDescriptionMixin):
    """Fan entity description for Bambu Lab."""
    exists_fn: Callable[..., bool] = lambda _: True
    extra_attributes: Callable[..., dict] = lambda _: {}


FANS: tuple[FanEntityDescription, ...] = (
    BambuLabFanEntityDescription(
        key="cooling_fan_speed",
        name="Cooling Fan Speed",
        value_fn=lambda device: device.fans.cooling_fan_speed
    ),
    BambuLabFanEntityDescription(
        key="aux_fan_speed",
        name="Aux Fan Speed",
        value_fn=lambda device: device.fans.aux_fan_speed
    ),
    BambuLabFanEntityDescription(
        key="chamber_fan_speed",
        name="Chamber Fan Speed",
        value_fn=lambda device: device.fans.chamber_fan_speed,
        exists_fn=lambda coordinator: coordinator.get_model().supports_feature(Features.CHAMBER_FAN)
    ),
    BambuLabFanEntityDescription(
        key="heatbreak_fan_speed",
        name="Heatbreak Fan Speed",
        value_fn=lambda device: device.fans.heatbreak_fan_speed
    )
)


async def async_setup_entry(
        hass: HomeAssistant,
        entry: ConfigEntry,
        async_add_entities: AddEntitiesCallback
) -> None:
    LOGGER.debug("FAN::async_setup_entry")
    coordinator: BambuDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]

    for description in FANS:
        if description.exists_fn(coordinator):
            async_add_entities([BambuLabFan(coordinator, description, entry)])

    LOGGER.debug("FAN::async_setup_entry DONE")

class BambuLabFan(BambuLabEntity, FanEntity):
    """ Defined the Fan"""

    def __init__(
            self,
            coordinator: BambuDataUpdateCoordinator,
            description: BambuLabFanEntityDescription,
            config_entry: ConfigEntry
    ) -> None:
        """Initialize the fan."""
        self.entity_description = description
        self._attr_unique_id = f"{config_entry.data['serial']}_{description.key}"
        self._attr_name = description.name
        self._attr_supported_features = FanEntityFeature.SET_SPEED

        super().__init__(coordinator=coordinator)

    @property
    def available(self) -> bool:
        """Is the fan available"""
        return True

    @property
    def is_on(self) -> bool:
        """Return the state of the fan"""
        if self.entity_description.value_fn(self.coordinator.data) > 0:
            return True
        return False

    @property
    def percentage(self) -> int:
        """Return the current speed percentage."""
        return self.entity_description.value_fn(self.coordinator.get_model())

    def set_percentage(self, percentage: int) -> None:
        """Set the speed percentage of the fan."""
        match self.entity_description.key:
            case "cooling_fan_speed":
                self.coordinator.get_model().fans.set_part_cooling_fan_speed(percentage)
            case "aux_fan_speed":
                self.coordinator.get_model().fans.set_aux_fan_speed(percentage)
            case "chamber_fan_speed":
                self.coordinator.get_model().fans.set_chamber_fan_speed(percentage)

    def turn_on(self, speed: str = None, percentage: int = None, preset_mode: str = None, **kwargs: any) -> None:
        """Turn the fan on."""
        match self.entity_description.key:
            case "cooling_fan_speed":
                self.coordinator.get_model().fans.set_part_cooling_fan_speed(100)
            case "aux_fan_speed":
                self.coordinator.get_model().fans.set_aux_fan_speed(100)
            case "chamber_fan_speed":
                self.coordinator.get_model().fans.set_chamber_fan_speed(100)


    def turn_off(self, **kwargs) -> None:
        """Turn the fan off."""
        match self.entity_description.key:
            case "cooling_fan_speed":
                self.coordinator.get_model().fans.set_part_cooling_fan_speed(0)
            case "aux_fan_speed":
                self.coordinator.get_model().fans.set_aux_fan_speed(0)
            case "chamber_fan_speed":
                self.coordinator.get_model().fans.set_chamber_fan_speed(0)
