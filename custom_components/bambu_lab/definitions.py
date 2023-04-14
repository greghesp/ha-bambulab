"""Definitions for Bambu Lab sensors added to MQTT."""
from __future__ import annotations

import math

from .const import LOGGER
from .pybambu.const import Features
from collections.abc import Callable
from dataclasses import dataclass
from homeassistant.helpers.entity import EntityCategory
from homeassistant.const import (
    POWER_WATT,
    PERCENTAGE,
    TEMPERATURE,
    SIGNAL_STRENGTH_DECIBELS_MILLIWATT,
    SPEED,
    UnitOfTemperature,
    TIME_MINUTES
)

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)


def fan_to_percent(speed):
    percentage = (int(speed) / 15) * 100
    return math.ceil(percentage / 10) * 10


@dataclass
class BambuLabSensorEntityDescriptionMixin:
    """Mixin for required keys."""
    value_fn: Callable[..., datetime | StateType]


@dataclass
class BambuLabSensorEntityDescription(SensorEntityDescription, BambuLabSensorEntityDescriptionMixin):
    """Sensor entity description for Bambu Lab."""
    available_fn: Callable[..., bool] = lambda _: True
    exists_fn: Callable[..., bool] = lambda _: True
    extra_attributes: Callable[..., dict] = lambda _: {}


PRINTER_SENSORS: tuple[BambuLabSensorEntityDescription, ...] = (
    BambuLabSensorEntityDescription(
        key="wifi_signal",
        name="Wi-Fi Signal",
        native_unit_of_measurement=SIGNAL_STRENGTH_DECIBELS_MILLIWATT,
        device_class=SensorDeviceClass.SIGNAL_STRENGTH,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda self: self.coordinator.get_model().info.wifi_signal
    ),
    BambuLabSensorEntityDescription(
        key="bed_temp",
        name="Bed Temperature",
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda self: self.coordinator.get_model().temperature.bed_temp
    ),
    BambuLabSensorEntityDescription(
        key="target_bed_temp",
        name="Target Bed Temperature",
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda self: self.coordinator.get_model().temperature.target_bed_temp
    ),
    BambuLabSensorEntityDescription(
        key="chamber_temp",
        name="Chamber Temperature",
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda self: self.coordinator.get_model().temperature.chamber_temp,
        exists_fn=lambda coordinator: coordinator.get_model().supports_feature(Features.CHAMBER_TEMPERATURE)
    ),
    BambuLabSensorEntityDescription(
        key="target_nozzle_temp",
        name="Nozzle Target Temperature",
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        icon="mdi:printer-3d-nozzle",
        value_fn=lambda self: self.coordinator.get_model().temperature.target_nozzle_temp
    ),
    BambuLabSensorEntityDescription(
        key="nozzle_temp",
        name="Nozzle Temperature",
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        icon="mdi:printer-3d-nozzle",
        value_fn=lambda self: self.coordinator.get_model().temperature.nozzle_temp
    ),
    BambuLabSensorEntityDescription(
        key="aux_fan_speed",
        name="Aux Fan Speed",
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        icon="mdi:fan",
        value_fn=lambda self: self.coordinator.get_model().fans.aux_fan_speed
    ),
    BambuLabSensorEntityDescription(
        key="chamber_fan_speed",
        name="Chamber Fan Speed",
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        icon="mdi:fan",
        value_fn=lambda self: self.coordinator.get_model().fans.chamber_fan_speed,
        exists_fn=lambda coordinator: coordinator.get_model().supports_feature(Features.CHAMBER_FAN)
    ),
    BambuLabSensorEntityDescription(
        key="cooling_fan_speed",
        name="Cooling Fan Speed",
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        icon="mdi:fan",
        value_fn=lambda self: self.coordinator.get_model().fans.cooling_fan_speed
    ),
    BambuLabSensorEntityDescription(
        key="heatbreak_fan_speed",
        name="Heatbreak Fan Speed",
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        icon="mdi:fan",
        value_fn=lambda self: self.coordinator.get_model().fans.heatbreak_fan_speed
    ),
    BambuLabSensorEntityDescription(
        key="speed_profile",
        name="Speed Profile",
        icon="mdi:speedometer",
        value_fn=lambda self: self.coordinator.get_model().speed.name,
        extra_attributes=lambda self: {"modifier": self.coordinator.get_model().speed.modifier}
    ),
    BambuLabSensorEntityDescription(
        key="stage",
        name="Current Stage",
        icon="mdi:file-tree",
        value_fn=lambda self: self.coordinator.get_model().stage.description,
        exists_fn=lambda coordinator: coordinator.get_model().supports_feature(Features.CURRENT_STAGE)
    ),
    BambuLabSensorEntityDescription(
        key="print_progress",
        name="Print Progress",
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        icon="mdi:progress-clock",
        value_fn=lambda self: self.coordinator.get_model().info.print_percentage
    ),
    BambuLabSensorEntityDescription(
        key="print_status",
        name="Print Status",
        icon="mdi:list-status",
        value_fn=lambda self: self.coordinator.get_model().info.gcode_state.title()
    ),
    BambuLabSensorEntityDescription(
        key="start_time",
        name="Start Time",
        icon="mdi:clock",
        value_fn=lambda self: self.coordinator.get_model().info.start_time
    ),
    BambuLabSensorEntityDescription(
        key="remaining_time",
        name="Remaining Time",
        icon="mdi:timer-sand",
        native_unit_of_measurement=TIME_MINUTES,
        device_class=SensorDeviceClass.DURATION,
        value_fn=lambda self: self.coordinator.get_model().info.remaining_time
    ),
    BambuLabSensorEntityDescription(
        key="end_time",
        name="End Time",
        icon="mdi:clock",
        value_fn=lambda self: self.coordinator.get_model().info.end_time
    ),
    BambuLabSensorEntityDescription(
        key="current_layer",
        name="Current Layer",
        icon="mdi:printer-3d-nozzle",
        value_fn=lambda self: self.coordinator.get_model().info.current_layer,
        exists_fn=lambda coordinator: coordinator.get_model().supports_feature(Features.PRINT_LAYERS)
    ),
    BambuLabSensorEntityDescription(
        key="total_layers",
        name="Total Layer Count",
        icon="mdi:printer-3d-nozzle",
        value_fn=lambda self: self.coordinator.get_model().info.total_layers,
        exists_fn=lambda coordinator: coordinator.get_model().supports_feature(Features.PRINT_LAYERS)
    ),
    BambuLabSensorEntityDescription(
        key="tray_now",
        name="Active Tray",
        icon="mdi:printer-3d-nozzle",
        available_fn = lambda self: self.coordinator.get_model().supports_feature(Features.AMS) and self.coordinator.get_model().ams.tray_now != 255,
        value_fn=lambda self: self.coordinator.get_model().ams.tray_now + 1,
        exists_fn=lambda coordinator: coordinator.get_model().supports_feature(Features.AMS)
    ),
)

VIRTUAL_TRAY_SENSORS: tuple[BambuLabSensorEntityDescription, ...] = (
    BambuLabSensorEntityDescription(
        key="external_spool",
        name="External Spool",
        icon="mdi:printer-3d-nozzle",
        value_fn=lambda self: self.coordinator.get_model().external_spool.name,
        extra_attributes=lambda self: 
          {
            "active": not self.coordinator.get_model().supports_feature(Features.AMS) or (self.coordinator.get_model().ams.tray_now == 254),
            "brand": self.coordinator.get_model().external_spool.sub_brands,
            "color": f"#{self.coordinator.get_model().external_spool.color}",
            "name": self.coordinator.get_model().external_spool.name,
            "nozzle_temp_min": self.coordinator.get_model().external_spool.nozzle_temp_min,
            "nozzle_temp_max": self.coordinator.get_model().external_spool.nozzle_temp_max,
            "type": self.coordinator.get_model().external_spool.type,
          },
        exists_fn=lambda coordinator: not coordinator.get_model().supports_feature(Features.K_VALUE)
    ),
    BambuLabSensorEntityDescription(
        key="external_spool",
        name="External Spool",
        icon="mdi:printer-3d-nozzle",
        value_fn=lambda self: self.coordinator.get_model().external_spool.name,
        extra_attributes=lambda self: 
          {
            "active": not self.coordinator.get_model().supports_feature(Features.AMS) or (self.coordinator.get_model().ams.tray_now == 254),
            "brand": self.coordinator.get_model().external_spool.sub_brands,
            "color": f"#{self.coordinator.get_model().external_spool.color}",
            "k_value": self.coordinator.get_model().external_spool.k,
            "name": self.coordinator.get_model().external_spool.name,
            "nozzle_temp_min": self.coordinator.get_model().external_spool.nozzle_temp_min,
            "nozzle_temp_max": self.coordinator.get_model().external_spool.nozzle_temp_max,
            "type": self.coordinator.get_model().external_spool.type,
          },
        exists_fn=lambda coordinator: coordinator.get_model().supports_feature(Features.K_VALUE)
    ),
)

AMS_SENSORS: tuple[BambuLabSensorEntityDescription, ...] = (
    BambuLabSensorEntityDescription(
        key="version",
        name="Version",
        icon="mdi:identifier",
        value_fn=lambda self: self.coordinator.get_model().ams.version
    ),
    BambuLabSensorEntityDescription(
        key="humidify_index",
        name="Humidity Index",
        icon="mdi:cloud-percent",
        value_fn=lambda self: self.coordinator.get_model().ams.data[self.index].humidity_index
    ),
    BambuLabSensorEntityDescription(
        key="tray_1",
        name="Tray 1",
        icon="mdi:printer-3d-nozzle",
        value_fn=lambda self: self.coordinator.get_model().ams.data[self.index].tray[0].name,
        extra_attributes=lambda self: 
          {
            "active": (self.coordinator.get_model().ams.tray_now%4 == 0) and (math.floor(self.coordinator.get_model().ams.tray_now / 4) == self.index),
            "brand": self.coordinator.get_model().ams.data[self.index].tray[0].sub_brands,
            "color": f"#{self.coordinator.get_model().ams.data[self.index].tray[0].color}",
            "name": self.coordinator.get_model().ams.data[self.index].tray[0].name,
            "nozzle_temp_min": self.coordinator.get_model().ams.data[self.index].tray[0].nozzle_temp_min,
            "nozzle_temp_max": self.coordinator.get_model().ams.data[self.index].tray[0].nozzle_temp_max,
            "type": self.coordinator.get_model().ams.data[self.index].tray[0].type,
          },
        exists_fn=lambda coordinator: not coordinator.get_model().supports_feature(Features.K_VALUE)
    ),
    BambuLabSensorEntityDescription(
        key="tray_2",
        name="Tray 2",
        icon="mdi:printer-3d-nozzle",
        value_fn=lambda self: self.coordinator.get_model().ams.data[self.index].tray[1].name,
        extra_attributes=lambda self: 
          {
            "active": (self.coordinator.get_model().ams.tray_now%4 == 0) and (math.floor(self.coordinator.get_model().ams.tray_now / 4) == self.index),
            "brand": self.coordinator.get_model().ams.data[self.index].tray[1].sub_brands,
            "color": f"#{self.coordinator.get_model().ams.data[self.index].tray[1].color}",
            "name": self.coordinator.get_model().ams.data[self.index].tray[1].name,
            "nozzle_temp_min": self.coordinator.get_model().ams.data[self.index].tray[1].nozzle_temp_min,
            "nozzle_temp_max": self.coordinator.get_model().ams.data[self.index].tray[1].nozzle_temp_max,
            "type": self.coordinator.get_model().ams.data[self.index].tray[1].type,
          },
        exists_fn=lambda coordinator: not coordinator.get_model().supports_feature(Features.K_VALUE)
    ),
    BambuLabSensorEntityDescription(
        key="tray_3",
        name="Tray 3",
        icon="mdi:printer-3d-nozzle",
        value_fn=lambda self: self.coordinator.get_model().ams.data[self.index].tray[2].name,
        extra_attributes=lambda self: 
          {
            "active": (self.coordinator.get_model().ams.tray_now%4 == 0) and (math.floor(self.coordinator.get_model().ams.tray_now / 4) == self.index),
            "brand": self.coordinator.get_model().ams.data[self.index].tray[2].sub_brands,
            "color": f"#{self.coordinator.get_model().ams.data[self.index].tray[2].color}",
            "name": self.coordinator.get_model().ams.data[self.index].tray[2].name,
            "nozzle_temp_min": self.coordinator.get_model().ams.data[self.index].tray[2].nozzle_temp_min,
            "nozzle_temp_max": self.coordinator.get_model().ams.data[self.index].tray[2].nozzle_temp_max,
            "type": self.coordinator.get_model().ams.data[self.index].tray[2].type,
          },
        exists_fn=lambda coordinator: not coordinator.get_model().supports_feature(Features.K_VALUE)
    ),
    BambuLabSensorEntityDescription(
        key="tray_4",
        name="Tray 4",
        icon="mdi:printer-3d-nozzle",
        value_fn=lambda self: self.coordinator.get_model().ams.data[self.index].tray[3].name,
        extra_attributes=lambda self: 
          {
            "active": (self.coordinator.get_model().ams.tray_now%4 == 0) and (math.floor(self.coordinator.get_model().ams.tray_now / 4) == self.index),
            "brand": self.coordinator.get_model().ams.data[self.index].tray[3].sub_brands,
            "color": f"#{self.coordinator.get_model().ams.data[self.index].tray[3].color}",
            "name": self.coordinator.get_model().ams.data[self.index].tray[3].name,
            "nozzle_temp_min": self.coordinator.get_model().ams.data[self.index].tray[3].nozzle_temp_min,
            "nozzle_temp_max": self.coordinator.get_model().ams.data[self.index].tray[3].nozzle_temp_max,
            "type": self.coordinator.get_model().ams.data[self.index].tray[3].type,
          },
        exists_fn=lambda coordinator: not coordinator.get_model().supports_feature(Features.K_VALUE)
    ),
    BambuLabSensorEntityDescription(
        key="tray_1",
        name="Tray 1",
        icon="mdi:printer-3d-nozzle",
        value_fn=lambda self: self.coordinator.get_model().ams.data[self.index].tray[0].name,
        extra_attributes=lambda self: 
          {
            "active": (self.coordinator.get_model().ams.tray_now%4 == 0) and (math.floor(self.coordinator.get_model().ams.tray_now / 4) == self.index),
            "brand": self.coordinator.get_model().ams.data[self.index].tray[0].sub_brands,
            "color": f"#{self.coordinator.get_model().ams.data[self.index].tray[0].color}",
            "k_value": self.coordinator.get_model().ams.data[self.index].tray[0].k,
            "name": self.coordinator.get_model().ams.data[self.index].tray[0].name,
            "nozzle_temp_min": self.coordinator.get_model().ams.data[self.index].tray[0].nozzle_temp_min,
            "nozzle_temp_max": self.coordinator.get_model().ams.data[self.index].tray[0].nozzle_temp_max,
            "type": self.coordinator.get_model().ams.data[self.index].tray[0].type,
          },
        exists_fn=lambda coordinator: coordinator.get_model().supports_feature(Features.K_VALUE)
    ),
    BambuLabSensorEntityDescription(
        key="tray_2",
        name="Tray 2",
        icon="mdi:printer-3d-nozzle",
        value_fn=lambda self: self.coordinator.get_model().ams.data[self.index].tray[1].name,
        extra_attributes=lambda self: 
          {
            "active": (self.coordinator.get_model().ams.tray_now%4 == 1) and (math.floor(self.coordinator.get_model().ams.tray_now / 4) == self.index),
            "brand": self.coordinator.get_model().ams.data[self.index].tray[1].sub_brands,
            "color": f"#{self.coordinator.get_model().ams.data[self.index].tray[1].color}",
            "k_value": self.coordinator.get_model().ams.data[self.index].tray[1].k,
            "name": self.coordinator.get_model().ams.data[self.index].tray[1].name,
            "nozzle_temp_min": self.coordinator.get_model().ams.data[self.index].tray[1].nozzle_temp_min,
            "nozzle_temp_max": self.coordinator.get_model().ams.data[self.index].tray[1].nozzle_temp_max,
            "type": self.coordinator.get_model().ams.data[self.index].tray[1].type,
          },
        exists_fn=lambda coordinator: coordinator.get_model().supports_feature(Features.K_VALUE)
    ),
    BambuLabSensorEntityDescription(
        key="tray_3",
        name="Tray 3",
        icon="mdi:printer-3d-nozzle",
        value_fn=lambda self: self.coordinator.get_model().ams.data[self.index].tray[2].name,
        extra_attributes=lambda self: 
          {
            "active": (self.coordinator.get_model().ams.tray_now%4 == 2) and (math.floor(self.coordinator.get_model().ams.tray_now / 4) == self.index),
            "brand": self.coordinator.get_model().ams.data[self.index].tray[2].sub_brands,
            "color": f"#{self.coordinator.get_model().ams.data[self.index].tray[2].color}",
            "k_value": self.coordinator.get_model().ams.data[self.index].tray[2].k,
            "name": self.coordinator.get_model().ams.data[self.index].tray[2].name,
            "nozzle_temp_min": self.coordinator.get_model().ams.data[self.index].tray[2].nozzle_temp_min,
            "nozzle_temp_max": self.coordinator.get_model().ams.data[self.index].tray[2].nozzle_temp_max,
            "type": self.coordinator.get_model().ams.data[self.index].tray[2].type,
          },
        exists_fn=lambda coordinator: coordinator.get_model().supports_feature(Features.K_VALUE)
    ),
    BambuLabSensorEntityDescription(
        key="tray_4",
        name="Tray 4",
        icon="mdi:printer-3d-nozzle",
        value_fn=lambda self: self.coordinator.get_model().ams.data[self.index].tray[3].name,
        extra_attributes=lambda self: 
          {
            "active": (self.coordinator.get_model().ams.tray_now%4 == 3) and (math.floor(self.coordinator.get_model().ams.tray_now / 4) == self.index),
            "brand": self.coordinator.get_model().ams.data[self.index].tray[3].sub_brands,
            "color": f"#{self.coordinator.get_model().ams.data[self.index].tray[3].color}",
            "k_value": self.coordinator.get_model().ams.data[self.index].tray[3].k,
            "name": self.coordinator.get_model().ams.data[self.index].tray[3].name,
            "nozzle_temp_min": self.coordinator.get_model().ams.data[self.index].tray[3].nozzle_temp_min,
            "nozzle_temp_max": self.coordinator.get_model().ams.data[self.index].tray[3].nozzle_temp_max,
            "type": self.coordinator.get_model().ams.data[self.index].tray[3].type,
          },
        exists_fn=lambda coordinator: coordinator.get_model().supports_feature(Features.K_VALUE)
    ),
)
