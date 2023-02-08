"""Definitions for Bambu Lab sensors added to MQTT."""
from __future__ import annotations
from .const import LOGGER
from collections.abc import Callable
from dataclasses import dataclass
from homeassistant.helpers.entity import EntityCategory
from homeassistant.const import (
    POWER_WATT,
    PERCENTAGE,
    TEMPERATURE,
    SIGNAL_STRENGTH_DECIBELS_MILLIWATT,
    SPEED,
    UnitOfTemperature
)

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)


def trim_wifi(string):
    return string.replace("dBm", "")


def fan_to_percent(speed):
    percentage = (int(speed) / 15) * 100
    return math.ceil(percentage / 10) * 10


# Temperature(bed_temp=14, target_bed_temp=0, chamber_temp=20, nozzle_temp=25, target_nozzle_temp=0)

def temp_as_string(value):
    return round(int(value))


def log_test(data, key):
    LOGGER.debug(f"Log Test: {data.temperature[key]}")
    return data.temperature[key]


@dataclass
class BambuLabSensorEntityDescriptionMixin:
    """Mixin for required keys."""
    value_fn: Callable[..., datetime | StateType]


@dataclass
class BambuLabSensorEntityDescription(SensorEntityDescription, BambuLabSensorEntityDescriptionMixin):
    """Sensor entity description for Bambu Lab."""
    exists_fn: Callable[..., bool] = lambda _: True
    extra_attributes: Callable[..., dict] = lambda _: {}


SENSORS: tuple[BambuLabSensorEntityDescription, ...] = (
    BambuLabSensorEntityDescription(
        key="wifi_signal",
        name="Wi-Fi Signal",
        native_unit_of_measurement=SIGNAL_STRENGTH_DECIBELS_MILLIWATT,
        device_class=SensorDeviceClass.SIGNAL_STRENGTH,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda device: device.info.wifi_signal
    ),
    BambuLabSensorEntityDescription(
        key="bed_temp",
        name="Bed Temperature",
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda device: device.temperature.bed_temp
    ),
    BambuLabSensorEntityDescription(
        key="target_bed_temp",
        name="Target Bed Temperature",
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda device: device.temperature.target_bed_temp
#        available_fn=lambda device: (device.temperature.target_bed_temp != 0)
    ),
    BambuLabSensorEntityDescription(
        key="chamber_temp",
        name="Chamber Temperature",
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda device: device.temperature.chamber_temp
    ),
    BambuLabSensorEntityDescription(
        key="target_nozzle_temp",
        name="Nozzle Target Temperature",
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        icon="mdi:printer-3d-nozzle",
        value_fn=lambda device: device.temperature.target_nozzle_temp
    ),
    BambuLabSensorEntityDescription(
        key="nozzle_temp",
        name="Nozzle Temperature",
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        icon="mdi:printer-3d-nozzle",
        value_fn=lambda device: device.temperature.nozzle_temp
    ),
    BambuLabSensorEntityDescription(
        key="aux_fan_speed",
        name="Aux Fan Speed",
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        icon="mdi:fan",
        value_fn=lambda device: device.fans.aux_fan_speed
    ),
    BambuLabSensorEntityDescription(
        key="chamber_fan_speed",
        name="Chamber Fan Speed",
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        icon="mdi:fan",
        value_fn=lambda device: device.fans.chamber_fan_speed
    ),
    BambuLabSensorEntityDescription(
        key="cooling_fan_speed",
        name="Cooling Fan Speed",
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        icon="mdi:fan",
        value_fn=lambda device: device.fans.cooling_fan_speed
    ),
    BambuLabSensorEntityDescription(
        key="heatbreak_fan_speed",
        name="Heatbreak Fan Speed",
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        icon="mdi:fan",
        value_fn=lambda device: device.fans.heatbreak_fan_speed
    ),
    BambuLabSensorEntityDescription(
        key="speed_profile",
        name="Speed Profile",
        icon="mdi:speedometer",
        value_fn=lambda device: device.speed.name,
        extra_attributes=lambda device: {"modifier": device.speed.modifier}
    ),
    BambuLabSensorEntityDescription(
        key="stage",
        name="Current Stage",
        icon="mdi:file-tree",
        value_fn=lambda device: device.stage.description
    )
)
