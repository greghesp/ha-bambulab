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


PRINTER_SENSORS: tuple[BambuLabSensorEntityDescription, ...] = (
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
    ),
    BambuLabSensorEntityDescription(
        key="chamber_temp",
        name="Chamber Temperature",
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda device: device.temperature.chamber_temp,
        exists_fn=lambda device: device.supports_feature(Features.CHAMBER_TEMPERATURE)
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
        value_fn=lambda device: device.fans.chamber_fan_speed,
        exists_fn=lambda device: device.supports_feature(Features.CHAMBER_FAN)
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
        value_fn=lambda device: device.stage.description,
        exists_fn=lambda device: device.supports_feature(Features.CURRENT_STAGE)
    ),
    BambuLabSensorEntityDescription(
        key="print_progress",
        name="Print Progress",
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        icon="mdi:progress-clock",
        value_fn=lambda device: device.info.print_percentage
    ),
    BambuLabSensorEntityDescription(
        key="print_status",
        name="Print Status",
        icon="mdi:list-status",
        value_fn=lambda device: device.info.gcode_state.title()
    ),
    BambuLabSensorEntityDescription(
        key="start_time",
        name="Start Time",
        icon="mdi:clock",
        value_fn=lambda device: device.info.start_time
    ),
    BambuLabSensorEntityDescription(
        key="remaining_time",
        name="Remaining Time",
        icon="mdi:timer-sand",
        native_unit_of_measurement=TIME_MINUTES,
        device_class=SensorDeviceClass.DURATION,
        value_fn=lambda device: device.info.remaining_time
    ),
    BambuLabSensorEntityDescription(
        key="end_time",
        name="End Time",
        icon="mdi:clock",
        value_fn=lambda device: device.info.end_time
    ),
    BambuLabSensorEntityDescription(
        key="current_layer",
        name="Current Layer",
        icon="mdi:printer-3d-nozzle",
        value_fn=lambda device: device.info.current_layer,
        exists_fn= lambda device: device.supports_feature(Features.PRINT_LAYERS)
    ),
    BambuLabSensorEntityDescription(
        key="total_layers",
        name="Total Layer Count",
        icon="mdi:printer-3d-nozzle",
        value_fn=lambda device: device.info.total_layers,
        exists_fn=lambda device: device.supports_feature(Features.PRINT_LAYERS)
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
        key="tray_name_1",
        name="Tray 1 Name",
        icon="mdi:printer-3d-nozzle",
        value_fn=lambda self: self.coordinator.get_model().ams.data[self.index].tray[0].name
    ),
    BambuLabSensorEntityDescription(
        key="tray_name_2",
        name="Tray 2 Name",
        icon="mdi:printer-3d-nozzle",
        value_fn=lambda self: self.coordinator.get_model().ams.data[self.index].tray[1].name
    ),
    BambuLabSensorEntityDescription(
        key="tray_name_3",
        name="Tray 3 Name",
        icon="mdi:printer-3d-nozzle",
        value_fn=lambda self: self.coordinator.get_model().ams.data[self.index].tray[2].name
    ),
    BambuLabSensorEntityDescription(
        key="tray_name_4",
        name="Tray 4 Name",
        icon="mdi:printer-3d-nozzle",
        value_fn=lambda self: self.coordinator.get_model().ams.data[self.index].tray[3].name
    ),
    BambuLabSensorEntityDescription(
        key="tray_type_1",
        name="Tray 1 Type",
        icon="mdi:printer-3d-nozzle",
        value_fn=lambda self: self.coordinator.get_model().ams.data[self.index].tray[0].type
    ),
    BambuLabSensorEntityDescription(
        key="tray_type_2",
        name="Tray 2 Type",
        icon="mdi:printer-3d-nozzle",
        value_fn=lambda self: self.coordinator.get_model().ams.data[self.index].tray[1].type
    ),
    BambuLabSensorEntityDescription(
        key="tray_type_3",
        name="Tray 3 Type",
        icon="mdi:printer-3d-nozzle",
        value_fn=lambda self: self.coordinator.get_model().ams.data[self.index].tray[2].type
    ),
    BambuLabSensorEntityDescription(
        key="tray_type_4",
        name="Tray 4 Type",
        icon="mdi:printer-3d-nozzle",
        value_fn=lambda self: self.coordinator.get_model().ams.data[self.index].tray[3].type
    ),
    BambuLabSensorEntityDescription(
        key="tray_sub_brands_1",
        name="Tray 1 Sub Brands",
        icon="mdi:printer-3d-nozzle",
        value_fn=lambda self: self.coordinator.get_model().ams.data[self.index].tray[0].sub_brands
    ),
    BambuLabSensorEntityDescription(
        key="tray_sub_brands_2",
        name="Tray 2 Sub Brands",
        icon="mdi:printer-3d-nozzle",
        value_fn=lambda self: self.coordinator.get_model().ams.data[self.index].tray[1].sub_brands
    ),
    BambuLabSensorEntityDescription(
        key="tray_sub_brands_3",
        name="Tray 3 Sub Brands",
        icon="mdi:printer-3d-nozzle",
        value_fn=lambda self: self.coordinator.get_model().ams.data[self.index].tray[2].sub_brands
    ),
    BambuLabSensorEntityDescription(
        key="tray_sub_brands_4",
        name="Tray 4 Sub Brands",
        icon="mdi:printer-3d-nozzle",
        value_fn=lambda self: self.coordinator.get_model().ams.data[self.index].tray[3].sub_brands
    ),
    BambuLabSensorEntityDescription(
        key="tray_color_1",
        name="Tray 1 Color",
        icon="mdi:palette",
        value_fn=lambda self: self.coordinator.get_model().ams.data[self.index].tray[0].color
    ),
    BambuLabSensorEntityDescription(
        key="tray_color_2",
        name="Tray 2 Color",
        icon="mdi:palette",
        value_fn=lambda self: self.coordinator.get_model().ams.data[self.index].tray[1].color
    ),
    BambuLabSensorEntityDescription(
        key="tray_color_3",
        name="Tray 3 Color",
        icon="mdi:palette",
        value_fn=lambda self: self.coordinator.get_model().ams.data[self.index].tray[2].color
    ),
    BambuLabSensorEntityDescription(
        key="tray_color_4",
        name="Tray 4 Color",
        icon="mdi:palette",
        value_fn=lambda self: self.coordinator.get_model().ams.data[self.index].tray[3].color
    ),
    BambuLabSensorEntityDescription(
        key="tray_nozzle_temp_min_1",
        name="Tray 1 Min Nozzle Temp",
        icon="mdi:printer-3d-nozzle-heat",
        value_fn=lambda self: self.coordinator.get_model().ams.data[self.index].tray[0].nozzle_temp_min
    ),
    BambuLabSensorEntityDescription(
        key="tray_nozzle_temp_min_2",
        name="Tray 2 Min Nozzle Temp",
        icon="mdi:printer-3d-nozzle-heat",
        value_fn=lambda self: self.coordinator.get_model().ams.data[self.index].tray[1].nozzle_temp_min
    ),
    BambuLabSensorEntityDescription(
        key="tray_nozzle_temp_min_3",
        name="Tray 3 Min Nozzle Temp",
        icon="mdi:printer-3d-nozzle-heat",
        value_fn=lambda self: self.coordinator.get_model().ams.data[self.index].tray[2].nozzle_temp_min
    ),
    BambuLabSensorEntityDescription(
        key="tray_nozzle_temp_min_4",
        name="Tray 4 Min Nozzle Temp",
        icon="mdi:printer-3d-nozzle-heat",
        value_fn=lambda self: self.coordinator.get_model().ams.data[self.index].tray[3].nozzle_temp_min
    ),
    BambuLabSensorEntityDescription(
        key="tray_nozzle_temp_max_1",
        name="Tray 1 Max Nozzle Temp",
        icon="mdi:printer-3d-nozzle-heat",
        value_fn=lambda self: self.coordinator.get_model().ams.data[self.index].tray[0].nozzle_temp_max
    ),
    BambuLabSensorEntityDescription(
        key="tray_nozzle_temp_max_2",
        name="Tray 2 Max Nozzle Temp",
        icon="mdi:printer-3d-nozzle-heat",
        value_fn=lambda self: self.coordinator.get_model().ams.data[self.index].tray[1].nozzle_temp_max
    ),
    BambuLabSensorEntityDescription(
        key="tray_nozzle_temp_max_3",
        name="Tray 3 Max Nozzle Temp",
        icon="mdi:printer-3d-nozzle-heat",
        value_fn=lambda self: self.coordinator.get_model().ams.data[self.index].tray[2].nozzle_temp_max
    ),
    BambuLabSensorEntityDescription(
        key="tray_nozzle_temp_max_4",
        name="Tray 4 Max Nozzle Temp",
        icon="mdi:printer-3d-nozzle-heat",
        value_fn=lambda self: self.coordinator.get_model().ams.data[self.index].tray[3].nozzle_temp_max
    ),
    BambuLabSensorEntityDescription(
        key="tray_1_active",
        name="Tray 1 Active",
        icon="mdi:printer-3d-nozzle",
        value_fn=lambda self: (self.coordinator.get_model().ams.tray_now%4 == 0) and (math.floor(self.coordinator.get_model().ams.tray_now / 4) == self.index)
    ),
    BambuLabSensorEntityDescription(
        key="tray_2_active",
        name="Tray 2 Active",
        icon="mdi:printer-3d-nozzle",
        value_fn=lambda self: (self.coordinator.get_model().ams.tray_now%4 == 1) and (math.floor(self.coordinator.get_model().ams.tray_now / 4) == self.index)
    ),
    BambuLabSensorEntityDescription(
        key="tray_3_active",
        name="Tray 3 Active",
        icon="mdi:printer-3d-nozzle",
        value_fn=lambda self: (self.coordinator.get_model().ams.tray_now%4 == 2) and (math.floor(self.coordinator.get_model().ams.tray_now / 4) == self.index)
    ),
    BambuLabSensorEntityDescription(
        key="tray_4_active",
        name="Tray 4 Active",
        icon="mdi:printer-3d-nozzle",
        value_fn=lambda self: (self.coordinator.get_model().ams.tray_now%4 == 3) and (math.floor(self.coordinator.get_model().ams.tray_now / 4) == self.index)
    ),
)
