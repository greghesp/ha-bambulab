from dataclasses import dataclass
from collections.abc import Awaitable, Callable

from homeassistant.components.number import (
    NumberEntity,
    NumberEntityDescription, NumberDeviceClass, NumberMode,
    RestoreNumber,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import PERCENTAGE, EntityCategory, UnitOfTemperature, UnitOfTime
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import (
    DOMAIN,
    LOGGER,
    Options,
)

from .coordinator import BambuDataUpdateCoordinator
from .ams_heater import (
    DEFAULT_HUMIDITY_OFF,
    DEFAULT_HUMIDITY_ON,
    DEFAULT_MAX_RUNTIME_HOURS,
    DEFAULT_MAX_TEMPERATURE,
    MAX_HUMIDITY,
    MAX_RUNTIME_HOURS,
    MAX_TEMPERATURE,
    MIN_HUMIDITY,
    MIN_TEMPERATURE,
)
from .models import AMSEntity, BambuLabEntity
from .pybambu.const import Features, Printers, TempEnum


@dataclass
class BambuLabNumberEntityDescriptionMixin:
    """Mixin for required keys."""
    value_fn: Callable[..., any]
    set_value_fn: Callable[..., Awaitable[None]]

@dataclass
class BambuLabNumberEntityDescription(NumberEntityDescription, BambuLabNumberEntityDescriptionMixin):
    """Sensor entity description for Bambu Lab."""
    exists_fn: Callable[..., bool] = lambda _: True
    max_value_fn: Callable[..., float | None] = lambda _: None


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
    ),
    BambuLabNumberEntityDescription(
        key="target_chamber_temperature",
        translation_key="target_chamber_temperature",
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        device_class=NumberDeviceClass.TEMPERATURE,
        icon="mdi:radiator",
        mode=NumberMode.BOX,
        native_min_value=0,
        native_max_value=60,  # Default to X1E limit; overridden per-model at init
        native_step=1,
        value_fn=lambda self: self.coordinator.get_model().temperature.target_chamber_temp,
        set_value_fn=lambda self, value: self.coordinator.get_model().temperature.set_target_temp(TempEnum.CHAMBER, value),
        exists_fn=lambda coordinator: coordinator.get_model().supports_feature(Features.ACTIVE_CHAMBER_HEATER),
        max_value_fn=lambda coordinator: 60 if coordinator.get_model().info.device_type == Printers.X1E else 65,
    ),
)


async def async_setup_entry(
        hass: HomeAssistant,
        entry: ConfigEntry,
        async_add_entities: AddEntitiesCallback
) -> None:

    coordinator: BambuDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]
    if not coordinator.get_model().has_full_printer_data:
        return
        
    LOGGER.debug("NUMBER::async_setup_entry")

    if not coordinator.get_model().info.is_hybrid_mode_blocking and not coordinator.get_model().print_fun.mqtt_signature_required:
        for description in NUMBERS:
            if description.exists_fn(coordinator):
                async_add_entities([BambuLabNumber(coordinator, description, entry)])

    heaters = getattr(coordinator, "ams_heaters", {})
    for index, ams in coordinator.get_model().ams.data.items():
        if ams is not None and ams.serial in heaters:
            has_temperature = coordinator.get_model().supports_feature(Features.AMS_TEMPERATURE)
            async_add_entities([
                AmsHeaterNumber(coordinator, heaters[ams.serial], index, description)
                for description in AMS_HEATER_NUMBERS
                # The cutoff would do nothing without an AMS temperature reading.
                if has_temperature or description.setting != "max_temperature"
            ])

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

        max_value = description.max_value_fn(coordinator)
        if max_value is not None:
            self._attr_native_max_value = max_value

        super().__init__(coordinator=coordinator)

    @property
    def native_value(self) -> float | None:
        """Return the value reported by the number."""
        return self.entity_description.value_fn(self)

    async def async_set_native_value(self, value: float) -> None:
        self.entity_description.set_value_fn(self, round(value))


@dataclass
class AmsHeaterNumberEntityDescription(NumberEntityDescription):
    """Describes a setting of an external AMS heater controller."""
    setting: str = ""
    default: float = 0.0


AMS_HEATER_NUMBERS: tuple[AmsHeaterNumberEntityDescription, ...] = (
    AmsHeaterNumberEntityDescription(
        key="ams_heater_humidity_on",
        translation_key="ams_heater_humidity_on",
        setting="humidity_on",
        default=DEFAULT_HUMIDITY_ON,
        icon="mdi:water-percent-alert",
        native_unit_of_measurement=PERCENTAGE,
        device_class=NumberDeviceClass.HUMIDITY,
        entity_category=EntityCategory.CONFIG,
        mode=NumberMode.BOX,
        native_min_value=MIN_HUMIDITY,
        native_max_value=MAX_HUMIDITY,
        native_step=1,
    ),
    AmsHeaterNumberEntityDescription(
        key="ams_heater_humidity_off",
        translation_key="ams_heater_humidity_off",
        setting="humidity_off",
        default=DEFAULT_HUMIDITY_OFF,
        icon="mdi:water-percent",
        native_unit_of_measurement=PERCENTAGE,
        device_class=NumberDeviceClass.HUMIDITY,
        entity_category=EntityCategory.CONFIG,
        mode=NumberMode.BOX,
        native_min_value=MIN_HUMIDITY,
        native_max_value=MAX_HUMIDITY,
        native_step=1,
    ),
    AmsHeaterNumberEntityDescription(
        key="ams_heater_max_temperature",
        translation_key="ams_heater_max_temperature",
        setting="max_temperature",
        default=DEFAULT_MAX_TEMPERATURE,
        icon="mdi:thermometer-alert",
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        device_class=NumberDeviceClass.TEMPERATURE,
        entity_category=EntityCategory.CONFIG,
        mode=NumberMode.BOX,
        native_min_value=MIN_TEMPERATURE,
        native_max_value=MAX_TEMPERATURE,
        native_step=1,
    ),
    AmsHeaterNumberEntityDescription(
        key="ams_heater_max_runtime",
        translation_key="ams_heater_max_runtime",
        setting="max_runtime_hours",
        default=DEFAULT_MAX_RUNTIME_HOURS,
        icon="mdi:timer-cog-outline",
        native_unit_of_measurement=UnitOfTime.HOURS,
        device_class=NumberDeviceClass.DURATION,
        entity_category=EntityCategory.CONFIG,
        mode=NumberMode.BOX,
        native_min_value=0,
        native_max_value=MAX_RUNTIME_HOURS,
        native_step=0.5,
    ),
)


class AmsHeaterNumber(AMSEntity, RestoreNumber):
    """A user setting of the external AMS heater controller, kept across restarts."""

    entity_description: AmsHeaterNumberEntityDescription

    def __init__(
            self,
            coordinator: BambuDataUpdateCoordinator,
            controller,
            index: int,
            description: AmsHeaterNumberEntityDescription,
    ) -> None:
        super().__init__(coordinator)
        self.index = index
        self.controller = controller
        self.entity_description = description
        self._attr_unique_id = f"{controller.ams_serial}_{description.key}"

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        last = await self.async_get_last_number_data()
        value = self.entity_description.default
        if last is not None and last.native_value is not None:
            value = min(max(float(last.native_value), self.native_min_value), self.native_max_value)
        self.controller.async_restore_settings(**{self.entity_description.setting: value})

    @property
    def native_value(self) -> float:
        return getattr(self.controller.settings, self.entity_description.setting)

    async def async_set_native_value(self, value: float) -> None:
        settings = self.controller.settings
        setting = self.entity_description.setting
        if setting == "humidity_on" and value <= settings.humidity_off:
            raise ServiceValidationError(
                f"The turn-on humidity must be above the turn-off humidity ({settings.humidity_off:g}%)."
            )
        if setting == "humidity_off" and value >= settings.humidity_on:
            raise ServiceValidationError(
                f"The turn-off humidity must be below the turn-on humidity ({settings.humidity_on:g}%)."
            )
        await self.controller.async_update_settings(**{setting: value})
        self.async_write_ha_state()
