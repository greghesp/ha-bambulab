"""Definitions for Bambu Lab sensors added to MQTT."""
from __future__ import annotations
from .const import LOGGER
from collections.abc import Callable
from dataclasses import dataclass
from typing import Final
import json
from homeassistant.helpers.entity import EntityCategory
from homeassistant.const import (
    POWER_WATT,
    PERCENTAGE,
    TEMPERATURE,
    SIGNAL_STRENGTH_DECIBELS_MILLIWATT,
    SPEED
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
    return round(int(speed) / 15) * 100


def to_whole(number):
    if not number:
        return 0
    return round(number)


def temp_as_string(value):
    return round(int(value))


@dataclass
class BambuLabSensorEntityDescriptionMixin:
    """Mixin for required keys."""
    value_fn: Callable[..., datetime | StateType]


@dataclass
class BambuLabSensorEntityDescription(SensorEntityDescription, BambuLabSensorEntityDescriptionMixin):
    """Sensor entity description for Bambu Lab."""
    exists_fn: Callable[..., bool] = lambda _: True


SENSORS: tuple[BambuLabSensorEntityDescription, ...] = (
    BambuLabSensorEntityDescription(
        key="wifi_signal",
        name="Wi-Fi Signal",
        native_unit_of_measurement=SIGNAL_STRENGTH_DECIBELS_MILLIWATT,
        device_class=SensorDeviceClass.SIGNAL_STRENGTH,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda device: trim_wifi(device["print"]["wifi_signal"])
    ),
    BambuLabSensorEntityDescription(
        key="bed_temper",
        name="Bed Temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda device: to_whole(device["print"]["bed_temper"])
    ),
    BambuLabSensorEntityDescription(
        key="bed_target_temper",
        name="Target Bed Temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda device: to_whole(device["print"]["bed_target_temper"])
    ),

)
