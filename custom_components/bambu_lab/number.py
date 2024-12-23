from dataclasses import dataclass
from collections.abc import Callable

from homeassistant.components.number import (
    NumberEntity,
    NumberEntityDescription, NumberDeviceClass, NumberMode
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN, LOGGER
from .coordinator import BambuDataUpdateCoordinator
from .models import BambuLabEntity
from .pybambu.const import Features, TempEnum


@dataclass
class BambuLabTemperatureEntityDescriptionMixin:
    """Mixin for required keys."""
    value_fn: Callable[..., any]
    set_value_fn: Callable[..., None]


@dataclass
class BambuLabNumberEntityDescription(NumberEntityDescription, BambuLabTemperatureEntityDescriptionMixin):
    """Editable (number) temperature entity description for Bambu Lab."""


NUMBERS: tuple[BambuLabNumberEntityDescription, ...] = (
    BambuLabNumberEntityDescription(
        key="target_nozzle_temperature",
        translation_key="target_nozzle_temperature",
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        device_class=NumberDeviceClass.TEMPERATURE,
        icon="mdi:printer-3d-nozzle",
        mode=NumberMode.BOX,
        native_min_value=0,
        native_max_value=320, # TODO: Determine by actual printer model
        native_step=1,
        value_fn=lambda device: device.temperature.target_nozzle_temp,
        set_value_fn=lambda device, value: device.temperature.set_target_temp(TempEnum.NOZZLE, value)
    ),
    BambuLabNumberEntityDescription(
        key="target_bed_temperature",
        translation_key="target_bed_temperature",
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        device_class=NumberDeviceClass.TEMPERATURE,
        mode=NumberMode.BOX,
        native_min_value=0,
        native_max_value=120,  # TODO: Determine by actual printer model and voltage
        native_step=1,
        value_fn=lambda device: device.temperature.target_bed_temp,
        set_value_fn=lambda device, value: device.temperature.set_target_temp(TempEnum.HEATBED, value)
    ),
)


async def async_setup_entry(
        hass: HomeAssistant,
        entry: ConfigEntry,
        async_add_entities: AddEntitiesCallback
) -> None:
    LOGGER.debug("NUMBER::async_setup_entry")
    coordinator: BambuDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]

    for description in NUMBERS:
        async_add_entities([BambuLabNumber(coordinator, description, entry)])

    LOGGER.debug("NUMBER::async_setup_entry DONE")


class BambuLabNumber(BambuLabEntity, NumberEntity):
    """ Defined the Number"""
    entity_description: BambuLabNumberEntityDescription

    def __init__(
            self,
            coordinator: BambuDataUpdateCoordinator,
            description: BambuLabNumberEntityDescription,
            config_entry: ConfigEntry
    ) -> None:
        """Initialize the number."""
        self.entity_description = description
        self._attr_unique_id = f"{config_entry.data['serial']}_{description.key}"
        self._attr_native_value = description.value_fn(coordinator.get_model())

        super().__init__(coordinator=coordinator)

    @property
    def available(self) -> bool:
        """Is the number available"""
        return self.coordinator.get_model().supports_feature(Features.SET_TEMPERATURE)
    
    @property
    def native_value(self) -> float | None:
        """Return the value reported by the number."""
        return self.entity_description.value_fn(self.coordinator.get_model())

    def set_native_value(self, value: float) -> None:
        """Update the current value."""
        self.entity_description.set_value_fn(self.coordinator.get_model(), round(value))
