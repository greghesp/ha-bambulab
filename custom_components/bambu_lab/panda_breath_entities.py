"""Entities for a BIQU Panda Breath chamber heater linked to a printer.

Each platform module calls the matching *_entities() helper from its
async_setup_entry. The entities read PandaBreathClient.state and are
unavailable while the WebSocket is disconnected.
"""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from homeassistant.components.number import NumberDeviceClass, NumberEntity, NumberEntityDescription, NumberMode
from homeassistant.components.select import SelectEntity, SelectEntityDescription
from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.components.switch import SwitchEntity, SwitchEntityDescription
from homeassistant.const import EntityCategory, UnitOfTemperature, UnitOfTime
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers.entity import DeviceInfo, Entity

from .panda_breath import (
    AUTO_TRIGGER_RANGE,
    DEFAULT_DRYING_HOURS,
    DEFAULT_DRYING_TEMPERATURE,
    DRYING_HOURS_RANGE,
    DRYING_TEMPERATURE_RANGE,
    MODE_ALWAYS_ON,
    MODE_AUTO,
    MODE_FILAMENT_DRYING,
    SENSOR_STATUS,
    TARGET_TEMPERATURE_RANGE,
    PandaBreathState,
    build_auto_trigger,
    build_drying_temperature,
    build_drying_time,
    build_mode,
    build_power,
    build_start_drying,
    build_stop_drying,
    build_target_temperature,
)


class PandaBreathEntity(Entity):
    """Base entity pushed by the Panda Breath client."""

    _attr_has_entity_name = True
    _attr_should_poll = False

    def __init__(self, coordinator, key: str) -> None:
        self.coordinator = coordinator
        self.client = coordinator.panda_breath
        self._attr_unique_id = f"{coordinator.config_entry.data['serial']}_panda_breath_{key}"

    @property
    def device_info(self) -> DeviceInfo:
        return self.coordinator.get_panda_breath_device()

    @property
    def available(self) -> bool:
        return self.client.connected

    @property
    def panda_state(self) -> PandaBreathState:
        return self.client.state

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        self.async_on_remove(self.client.async_add_listener(self.async_write_ha_state))

    async def _send(self, messages: list[dict[str, Any]]) -> None:
        try:
            await self.client.async_send(messages)
        except ValueError as err:
            raise ServiceValidationError(str(err)) from err


def _drying_temperature(state: PandaBreathState) -> int:
    return state.drying_temperature or DEFAULT_DRYING_TEMPERATURE


def _drying_hours(state: PandaBreathState) -> int:
    return state.drying_hours or DEFAULT_DRYING_HOURS


# --- Sensors -----------------------------------------------------------------

@dataclass(frozen=True, kw_only=True)
class PandaBreathSensorDescription(SensorEntityDescription):
    value_fn: Callable[[PandaBreathState], Any]


PANDA_BREATH_SENSORS: tuple[PandaBreathSensorDescription, ...] = (
    PandaBreathSensorDescription(
        key="chamber_temperature",
        translation_key="panda_breath_chamber_temperature",
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
        value_fn=lambda state: state.chamber_temperature,
    ),
    PandaBreathSensorDescription(
        key="heater_temperature",
        translation_key="panda_breath_heater_temperature",
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda state: state.heater_temperature,
    ),
    PandaBreathSensorDescription(
        key="drying_remaining_time",
        translation_key="panda_breath_drying_remaining_time",
        native_unit_of_measurement=UnitOfTime.MINUTES,
        device_class=SensorDeviceClass.DURATION,
        icon="mdi:timer-sand",
        value_fn=lambda state: state.drying_remaining_minutes,
    ),
    PandaBreathSensorDescription(
        key="heater_sensor_status",
        translation_key="panda_breath_heater_sensor_status",
        device_class=SensorDeviceClass.ENUM,
        options=list(SENSOR_STATUS.values()),
        entity_category=EntityCategory.DIAGNOSTIC,
        icon="mdi:thermometer-alert",
        value_fn=lambda state: state.heater_sensor_status,
    ),
)


class PandaBreathSensor(PandaBreathEntity, SensorEntity):
    entity_description: PandaBreathSensorDescription

    def __init__(self, coordinator, description: PandaBreathSensorDescription) -> None:
        super().__init__(coordinator, description.key)
        self.entity_description = description

    @property
    def native_value(self):
        return self.entity_description.value_fn(self.panda_state)


# --- Switches ----------------------------------------------------------------

class PandaBreathPowerSwitch(PandaBreathEntity, SwitchEntity):
    entity_description = SwitchEntityDescription(
        key="power", translation_key="panda_breath_power", icon="mdi:heat-wave",
    )

    def __init__(self, coordinator) -> None:
        super().__init__(coordinator, "power")

    @property
    def is_on(self) -> bool | None:
        return self.panda_state.power

    async def async_turn_on(self, **kwargs: Any) -> None:
        await self._send(build_power(True))

    async def async_turn_off(self, **kwargs: Any) -> None:
        await self._send(build_power(False))


class PandaBreathDryingSwitch(PandaBreathEntity, SwitchEntity):
    """Starts drying with the drying temperature and time numbers, or stops it."""

    entity_description = SwitchEntityDescription(
        key="drying", translation_key="panda_breath_drying", icon="mdi:hair-dryer",
    )

    def __init__(self, coordinator) -> None:
        super().__init__(coordinator, "drying")

    @property
    def is_on(self) -> bool | None:
        return self.panda_state.drying

    async def async_turn_on(self, **kwargs: Any) -> None:
        state = self.panda_state
        await self._send(build_start_drying(_drying_temperature(state), _drying_hours(state)))

    async def async_turn_off(self, **kwargs: Any) -> None:
        await self._send(build_stop_drying())


# --- Select ------------------------------------------------------------------

class PandaBreathModeSelect(PandaBreathEntity, SelectEntity):
    entity_description = SelectEntityDescription(
        key="mode",
        translation_key="panda_breath_mode",
        icon="mdi:fan-auto",
        options=[MODE_AUTO, MODE_ALWAYS_ON, MODE_FILAMENT_DRYING],
    )

    def __init__(self, coordinator) -> None:
        super().__init__(coordinator, "mode")

    @property
    def current_option(self) -> str | None:
        return self.panda_state.mode

    async def async_select_option(self, option: str) -> None:
        messages = build_mode(option)
        if option != MODE_FILAMENT_DRYING and self.panda_state.drying:
            # Leaving drying mode: stop the drying run explicitly rather than rely on the firmware.
            messages = build_stop_drying() + messages
        await self._send(messages)


# --- Numbers -----------------------------------------------------------------

@dataclass(frozen=True, kw_only=True)
class PandaBreathNumberDescription(NumberEntityDescription):
    value_fn: Callable[[PandaBreathState], float | None]
    command_fn: Callable[[PandaBreathState, float], list[dict[str, Any]]]


def _bounds(bounds: tuple[int, int]) -> dict[str, float]:
    return {"native_min_value": bounds[0], "native_max_value": bounds[1], "native_step": 1}


PANDA_BREATH_NUMBERS: tuple[PandaBreathNumberDescription, ...] = (
    PandaBreathNumberDescription(
        key="target_temperature",
        translation_key="panda_breath_target_temperature",
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        device_class=NumberDeviceClass.TEMPERATURE,
        mode=NumberMode.BOX,
        icon="mdi:thermometer",
        **_bounds(TARGET_TEMPERATURE_RANGE),
        value_fn=lambda state: state.target_temperature,
        command_fn=lambda state, value: build_target_temperature(state.mode, value),
    ),
    PandaBreathNumberDescription(
        key="auto_trigger_bed_temperature",
        translation_key="panda_breath_auto_trigger_bed_temperature",
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        device_class=NumberDeviceClass.TEMPERATURE,
        mode=NumberMode.BOX,
        icon="mdi:radiator",
        entity_category=EntityCategory.CONFIG,
        **_bounds(AUTO_TRIGGER_RANGE),
        value_fn=lambda state: state.auto_trigger_bed_temperature,
        command_fn=lambda state, value: build_auto_trigger(value),
    ),
    PandaBreathNumberDescription(
        key="drying_temperature",
        translation_key="panda_breath_drying_temperature",
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        device_class=NumberDeviceClass.TEMPERATURE,
        mode=NumberMode.BOX,
        icon="mdi:thermometer-water",
        **_bounds(DRYING_TEMPERATURE_RANGE),
        value_fn=_drying_temperature,
        command_fn=lambda state, value: build_drying_temperature(value),
    ),
    PandaBreathNumberDescription(
        key="drying_time",
        translation_key="panda_breath_drying_time",
        native_unit_of_measurement=UnitOfTime.HOURS,
        device_class=NumberDeviceClass.DURATION,
        mode=NumberMode.BOX,
        icon="mdi:timer-outline",
        **_bounds(DRYING_HOURS_RANGE),
        value_fn=_drying_hours,
        command_fn=lambda state, value: build_drying_time(value),
    ),
)


class PandaBreathNumber(PandaBreathEntity, NumberEntity):
    entity_description: PandaBreathNumberDescription

    def __init__(self, coordinator, description: PandaBreathNumberDescription) -> None:
        super().__init__(coordinator, description.key)
        self.entity_description = description

    @property
    def native_value(self) -> float | None:
        return self.entity_description.value_fn(self.panda_state)

    async def async_set_native_value(self, value: float) -> None:
        try:
            messages = self.entity_description.command_fn(self.panda_state, value)
        except ValueError as err:
            raise ServiceValidationError(str(err)) from err
        await self._send(messages)


# --- Platform helpers --------------------------------------------------------

def _linked(coordinator) -> bool:
    return getattr(coordinator, "panda_breath", None) is not None


def sensor_entities(coordinator) -> list[Entity]:
    return [PandaBreathSensor(coordinator, d) for d in PANDA_BREATH_SENSORS] if _linked(coordinator) else []


def switch_entities(coordinator) -> list[Entity]:
    if not _linked(coordinator):
        return []
    return [PandaBreathPowerSwitch(coordinator), PandaBreathDryingSwitch(coordinator)]


def select_entities(coordinator) -> list[Entity]:
    return [PandaBreathModeSelect(coordinator)] if _linked(coordinator) else []


def number_entities(coordinator) -> list[Entity]:
    return [PandaBreathNumber(coordinator, d) for d in PANDA_BREATH_NUMBERS] if _linked(coordinator) else []
