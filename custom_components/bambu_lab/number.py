from dataclasses import dataclass
from collections.abc import Awaitable, Callable

from homeassistant.components.number import (
    NumberEntity,
    NumberEntityDescription, NumberDeviceClass, NumberMode
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import (
    DOMAIN,
    LOGGER,
    Options,
)

from .coordinator import BambuDataUpdateCoordinator
from .models import BambuLabEntity
from .pybambu.const import Features, TempEnum


@dataclass
class BambuLabNumberEntityDescriptionMixin:
    """Mixin for required keys."""
    value_fn: Callable[..., any]
    set_value_fn: Callable[..., Awaitable[None]]

@dataclass
class BambuLabNumberEntityDescription(NumberEntityDescription, BambuLabNumberEntityDescriptionMixin):
    """Sensor entity description for Bambu Lab."""
    available_fn: Callable[..., bool] = lambda _: True
    exists_fn: Callable[..., bool] = lambda _: True


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
        value_fn=lambda self: self.coordinator.get_model().temperature.active_nozzle_target_temperature,
        set_value_fn=lambda self, value: self.coordinator.get_model().temperature.set_target_temp(TempEnum.NOZZLE, value),
        available_fn=lambda self: self.coordinator.get_model().supports_feature(Features.SET_TEMPERATURE) and not self.coordinator.get_model().print_fun.mqtt_signature_required,
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
        value_fn=lambda self: self.coordinator.get_model().temperature.target_bed_temp,
        set_value_fn=lambda self, value: self.coordinator.get_model().temperature.set_target_temp(TempEnum.HEATBED, value),
        available_fn=lambda self: self.coordinator.get_model().supports_feature(Features.SET_TEMPERATURE) and not self.coordinator.get_model().print_fun.mqtt_signature_required,
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
        self.coordinator = coordinator
        self.entity_description = description
        self._attr_unique_id = f"{config_entry.data['serial']}_{description.key}"
        self._attr_native_value = description.value_fn(self)

        super().__init__(coordinator=coordinator)

    @property
    def native_value(self) -> float | None:
        """Return the value reported by the number."""
        return self.entity_description.value_fn(self)

    async def async_set_native_value(self, value: float) -> None:
        await self.entity_description.set_value_fn(self, round(value))

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        return self.entity_description.available_fn(self)
