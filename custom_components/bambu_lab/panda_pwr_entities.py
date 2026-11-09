"""Entities for a BIQU Panda PWR smart power switch linked to a printer."""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.components.switch import SwitchDeviceClass, SwitchEntity, SwitchEntityDescription
from homeassistant.const import (
    UnitOfElectricCurrent,
    UnitOfElectricPotential,
    UnitOfEnergy,
    UnitOfPower,
)
from homeassistant.helpers.entity import Entity

from .panda_devices import PANDA_PWR
from .panda_entity import PandaEntity
from .panda_pwr import PandaPwrState, build_power, build_usb


class PandaPwrEntity(PandaEntity):
    kind = PANDA_PWR
    unique_id_prefix = "panda_pwr"

    @property
    def pwr_state(self) -> PandaPwrState:
        return self.client.state


@dataclass(frozen=True, kw_only=True)
class PandaPwrSensorDescription(SensorEntityDescription):
    value_fn: Callable[[PandaPwrState], Any]


PANDA_PWR_SENSORS: tuple[PandaPwrSensorDescription, ...] = (
    PandaPwrSensorDescription(
        key="voltage",
        translation_key="panda_pwr_voltage",
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        device_class=SensorDeviceClass.VOLTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda state: state.voltage,
    ),
    PandaPwrSensorDescription(
        key="current",
        translation_key="panda_pwr_current",
        native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
        device_class=SensorDeviceClass.CURRENT,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda state: state.current,
    ),
    PandaPwrSensorDescription(
        key="power",
        translation_key="panda_pwr_power",
        native_unit_of_measurement=UnitOfPower.WATT,
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda state: state.power,
    ),
    PandaPwrSensorDescription(
        key="energy",
        translation_key="panda_pwr_energy",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        value_fn=lambda state: state.energy,
    ),
)


class PandaPwrSensor(PandaPwrEntity, SensorEntity):
    entity_description: PandaPwrSensorDescription

    def __init__(self, coordinator, description: PandaPwrSensorDescription) -> None:
        super().__init__(coordinator, description.key)
        self.entity_description = description

    @property
    def native_value(self):
        return self.entity_description.value_fn(self.pwr_state)


class PandaPwrOutputSwitch(PandaPwrEntity, SwitchEntity):
    """Mains output (usually the printer itself) or the USB output."""

    def __init__(self, coordinator, description: SwitchEntityDescription, field: str, build) -> None:
        super().__init__(coordinator, description.key)
        self.entity_description = description
        self._field = field
        self._build = build

    @property
    def is_on(self) -> bool | None:
        return getattr(self.pwr_state, self._field)

    async def async_turn_on(self, **kwargs: Any) -> None:
        await self.client.async_send(self._build(True), {self._field: True})

    async def async_turn_off(self, **kwargs: Any) -> None:
        await self.client.async_send(self._build(False), {self._field: False})


def pwr_entities(platform: str, coordinator) -> list[Entity]:
    if platform == "sensor":
        return [PandaPwrSensor(coordinator, d) for d in PANDA_PWR_SENSORS]
    if platform == "switch":
        return [
            PandaPwrOutputSwitch(
                coordinator,
                SwitchEntityDescription(
                    key="power", translation_key="panda_pwr_power_output",
                    device_class=SwitchDeviceClass.OUTLET,
                ),
                "power_on",
                build_power,
            ),
            PandaPwrOutputSwitch(
                coordinator,
                SwitchEntityDescription(key="usb", translation_key="panda_pwr_usb_output", icon="mdi:usb-port"),
                "usb_on",
                build_usb,
            ),
        ]
    return []
