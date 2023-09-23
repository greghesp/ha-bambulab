"""Definitions for Bambu Lab sensors added to MQTT."""
from __future__ import annotations

import math
from collections.abc import Callable
from dataclasses import dataclass

from homeassistant.helpers.entity import EntityCategory
from homeassistant.const import (
    PERCENTAGE,
    TEMPERATURE,
    SIGNAL_STRENGTH_DECIBELS_MILLIWATT,
    UnitOfTemperature,
    TIME_MINUTES
)

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntityDescription,
    SensorStateClass,
)

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntityDescription
)

from .const import LOGGER
from .pybambu.const import SPEED_PROFILE, Features


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


@dataclass
class BambuLabBinarySensorEntityDescriptionMixIn:
    """Mixin for required keys."""
    is_on_fn: Callable[..., bool]


@dataclass
class BambuLabBinarySensorEntityDescription(BinarySensorEntityDescription, BambuLabBinarySensorEntityDescriptionMixIn):
    """Sensor entity description for Bambu Lab."""
    exists_fn: Callable[..., bool] = lambda _: True
    extra_attributes: Callable[..., dict] = lambda _: {}


PRINTER_BINARY_SENSORS: tuple[BambuLabBinarySensorEntityDescription, ...] = (
    BambuLabBinarySensorEntityDescription(
        key="timelapse",
        translation_key="timelapse",
        icon="mdi:camera",
        device_class=BinarySensorDeviceClass.RUNNING,
        is_on_fn=lambda self: self.coordinator.get_model().camera.timelapse == 'enable'
    ),
    BambuLabBinarySensorEntityDescription(
        key="hms",
        translation_key="hms_errors",
        device_class=BinarySensorDeviceClass.PROBLEM,
        entity_category=EntityCategory.DIAGNOSTIC,
        is_on_fn=lambda self: len(self.coordinator.get_model().hms.errors) != 0,
        extra_attributes=lambda self: self.coordinator.get_model().hms.errors
    ),
    BambuLabBinarySensorEntityDescription(
        key="online",
        translation_key="online",
        device_class=BinarySensorDeviceClass.RUNNING,
        entity_category=EntityCategory.DIAGNOSTIC,
        is_on_fn=lambda self: self.coordinator.get_model().info.online
    ),
    BambuLabBinarySensorEntityDescription(
        key="firmware_update",
        translation_key="firmware_update",
        device_class=BinarySensorDeviceClass.UPDATE,
        entity_category=EntityCategory.DIAGNOSTIC,
        is_on_fn=lambda self: self.coordinator.get_model().info.new_version_state == 1
    ),
)

PRINTER_SENSORS: tuple[BambuLabSensorEntityDescription, ...] = (
    BambuLabSensorEntityDescription(
        key="mqtt_mode",
        translation_key="mqtt_mode",
        entity_category=EntityCategory.DIAGNOSTIC,
        device_class=SensorDeviceClass.ENUM,
        options=["bambu_cloud", "local"],
        value_fn=lambda self: self.coordinator.get_model().info.mqtt_mode
    ),
    BambuLabSensorEntityDescription(
        key="wifi_signal",
        translation_key="wifi_signal",
        native_unit_of_measurement=SIGNAL_STRENGTH_DECIBELS_MILLIWATT,
        device_class=SensorDeviceClass.SIGNAL_STRENGTH,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda self: self.coordinator.get_model().info.wifi_signal
    ),
    BambuLabSensorEntityDescription(
        key="bed_temp",
        translation_key="bed_temp",
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda self: self.coordinator.get_model().temperature.bed_temp
    ),
    BambuLabSensorEntityDescription(
        key="target_bed_temp",
        translation_key="target_bed_temp",
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda self: self.coordinator.get_model().temperature.target_bed_temp
    ),
    BambuLabSensorEntityDescription(
        key="chamber_temp",
        translation_key="chamber_temp",
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda self: self.coordinator.get_model().temperature.chamber_temp,
        exists_fn=lambda coordinator: coordinator.get_model().supports_feature(Features.CHAMBER_TEMPERATURE)
    ),
    BambuLabSensorEntityDescription(
        key="target_nozzle_temp",
        translation_key="target_nozzle_temp",
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        icon="mdi:printer-3d-nozzle",
        value_fn=lambda self: self.coordinator.get_model().temperature.target_nozzle_temp
    ),
    BambuLabSensorEntityDescription(
        key="nozzle_temp",
        translation_key="nozzle_temp",
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        icon="mdi:printer-3d-nozzle",
        value_fn=lambda self: self.coordinator.get_model().temperature.nozzle_temp
    ),
    BambuLabSensorEntityDescription(
        key="aux_fan_speed",
        translation_key="aux_fan_speed",
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        icon="mdi:fan",
        value_fn=lambda self: self.coordinator.get_model().fans.aux_fan_speed
    ),
    BambuLabSensorEntityDescription(
        key="chamber_fan_speed",
        translation_key="chamber_fan_speed",
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        icon="mdi:fan",
        value_fn=lambda self: self.coordinator.get_model().fans.chamber_fan_speed,
        exists_fn=lambda coordinator: coordinator.get_model().supports_feature(Features.CHAMBER_FAN)
    ),
    BambuLabSensorEntityDescription(
        key="cooling_fan_speed",
        translation_key="cooling_fan_speed",
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        icon="mdi:fan",
        value_fn=lambda self: self.coordinator.get_model().fans.cooling_fan_speed
    ),
    BambuLabSensorEntityDescription(
        key="heatbreak_fan_speed",
        translation_key="heatbreak_fan_speed",
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        icon="mdi:fan",
        value_fn=lambda self: self.coordinator.get_model().fans.heatbreak_fan_speed
    ),
    BambuLabSensorEntityDescription(
        key="speed_profile",
        translation_key="speed_profile",
        icon="mdi:speedometer",
        value_fn=lambda self: self.coordinator.get_model().speed.name,
        extra_attributes=lambda self: {"modifier": self.coordinator.get_model().speed.modifier},
        device_class=SensorDeviceClass.ENUM,
        options=[speed for i, speed in SPEED_PROFILE.items()]
    ),
    BambuLabSensorEntityDescription(
        key="stage",
        translation_key="stage",
        icon="mdi:file-tree",
        value_fn=lambda
            self: "offline" if not self.coordinator.get_model().info.online else self.coordinator.get_model().stage.description,
        exists_fn=lambda coordinator: coordinator.get_model().supports_feature(Features.CURRENT_STAGE),
        device_class=SensorDeviceClass.ENUM,
        options=[
            "offline",
            "unknown",
            "printing",
            "auto_bed_leveling",
            "heatbed_preheating",
            "sweeping_xy_mech_mode",
            "changing_filament",
            "m400_pause",
            "paused_filament_runout",
            "heating_hotend",
            "calibrating_extrusion",
            "scanning_bed_surface",
            "inspecting_first_layer",
            "identifying_build_plate_type",
            "calibrating_micro_lidar",
            "homing_toolhead",
            "cleaning_nozzle_tip",
            "checking_extruder_temperature",
            "paused_user",
            "paused_front_cover_falling",
            "calibrating_extrusion_flow",
            "paused_nozzle_temperature_malfunction",
            "paused_heat_bed_temperature_malfunction",
            "idle"
        ]
    ),
    BambuLabSensorEntityDescription(
        key="print_progress",
        translation_key="print_progress",
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        icon="mdi:progress-clock",
        value_fn=lambda self: self.coordinator.get_model().info.print_percentage
    ),
    BambuLabSensorEntityDescription(
        key="print_status",
        translation_key="print_status",
        icon="mdi:list-status",
        value_fn=lambda
            self: "offline" if not self.coordinator.get_model().info.online else self.coordinator.get_model().info.gcode_state.lower(),
        device_class=SensorDeviceClass.ENUM,
        options=["failed", "finish", "idle", "init", "offline", "pause","prepare", "running", "slicing", "unknown"],
    ),
    BambuLabSensorEntityDescription(
        key="start_time",
        translation_key="start_time",
        icon="mdi:clock",
        available_fn=lambda self: self.coordinator.get_model().info.start_time != "",
        value_fn=lambda self: self.coordinator.get_model().info.start_time,
        exists_fn=lambda coordinator: coordinator.get_model().supports_feature(Features.START_TIME) or coordinator.get_model().supports_feature(Features.START_TIME_GENERATED),
    ),
    BambuLabSensorEntityDescription(
        key="remaining_time",
        translation_key="remaining_time",
        icon="mdi:timer-sand",
        native_unit_of_measurement=TIME_MINUTES,
        device_class=SensorDeviceClass.DURATION,
        value_fn=lambda self: self.coordinator.get_model().info.remaining_time
    ),
    BambuLabSensorEntityDescription(
        key="end_time",
        translation_key="end_time",
        icon="mdi:clock",
        available_fn=lambda self: self.coordinator.get_model().info.end_time != "",
        value_fn=lambda self: self.coordinator.get_model().info.end_time,
    ),
    BambuLabSensorEntityDescription(
        key="current_layer",
        translation_key="current_layer",
        icon="mdi:printer-3d-nozzle",
        value_fn=lambda self: self.coordinator.get_model().info.current_layer,
        exists_fn=lambda coordinator: coordinator.get_model().supports_feature(Features.PRINT_LAYERS),
        native_unit_of_measurement="layers",
    ),
    BambuLabSensorEntityDescription(
        key="total_layers",
        translation_key="total_layers",
        icon="mdi:printer-3d-nozzle",
        value_fn=lambda self: self.coordinator.get_model().info.total_layers,
        exists_fn=lambda coordinator: coordinator.get_model().supports_feature(Features.PRINT_LAYERS),
        native_unit_of_measurement="layers",
    ),
    BambuLabSensorEntityDescription(
        key="tray_now",
        translation_key="active_tray_index",
        icon="mdi:printer-3d-nozzle",
        available_fn=lambda self: self.coordinator.get_model().supports_feature(
            Features.AMS) and self.coordinator.get_model().ams.tray_now != 255,
        value_fn=lambda self: self.coordinator.get_model().ams.tray_now + 1,
        exists_fn=lambda coordinator: coordinator.get_model().supports_feature(Features.AMS)
    ),
    BambuLabSensorEntityDescription(
        key="gcode_file",
        translation_key="gcode_file",
        icon="mdi:file",
        available_fn=lambda self: self.coordinator.get_model().info.gcode_file != "",
        value_fn=lambda self: self.coordinator.get_model().info.gcode_file
    ),
    BambuLabSensorEntityDescription(
        key="subtask_name",
        translation_key="subtask_name",
        icon="mdi:file",
        available_fn=lambda self: self.coordinator.get_model().info.subtask_name != "",
        value_fn=lambda self: self.coordinator.get_model().info.subtask_name
    ),
    BambuLabSensorEntityDescription(
        key="active_tray",
        translation_key="active_tray",
        icon="mdi:printer-3d-nozzle",
        value_fn=lambda self: self.coordinator.get_model().get_active_tray().name,
        extra_attributes=lambda self:
        {
            "color": f"#{self.coordinator.get_model().get_active_tray().color}",
            "name": self.coordinator.get_model().get_active_tray().name,
            "nozzle_temp_min": self.coordinator.get_model().get_active_tray().nozzle_temp_min,
            "nozzle_temp_max": self.coordinator.get_model().get_active_tray().nozzle_temp_max,
            "type": self.coordinator.get_model().get_active_tray().type,
        },
        available_fn=lambda self: self.coordinator.get_model().get_active_tray() is not None,
        exists_fn=lambda coordinator: coordinator.get_model().supports_feature(Features.AMS) and not coordinator.get_model().supports_feature(Features.K_VALUE)
    ),
    BambuLabSensorEntityDescription(
        key="active_tray",
        translation_key="active_tray",
        icon="mdi:printer-3d-nozzle",
        value_fn=lambda self: self.coordinator.get_model().get_active_tray().name,
        extra_attributes=lambda self:
        {
            "color": f"#{self.coordinator.get_model().get_active_tray().color}",
            "k_value": self.coordinator.get_model().get_active_tray().k,
            "name": self.coordinator.get_model().get_active_tray().name,
            "nozzle_temp_min": self.coordinator.get_model().get_active_tray().nozzle_temp_min,
            "nozzle_temp_max": self.coordinator.get_model().get_active_tray().nozzle_temp_max,
            "type": self.coordinator.get_model().get_active_tray().type,
        },
        available_fn=lambda self: self.coordinator.get_model().get_active_tray() is not None,
        exists_fn=lambda coordinator: coordinator.get_model().supports_feature(Features.AMS) and coordinator.get_model().supports_feature(Features.K_VALUE)
    ),
)

VIRTUAL_TRAY_SENSORS: tuple[BambuLabSensorEntityDescription, ...] = (
    BambuLabSensorEntityDescription(
        key="external_spool",
        translation_key="external_spool",
        icon="mdi:printer-3d-nozzle",
        value_fn=lambda self: self.coordinator.get_model().external_spool.name,
        extra_attributes=lambda self:
        {
            "active": not self.coordinator.get_model().supports_feature(Features.AMS) or (
                    self.coordinator.get_model().ams.tray_now == 254),
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
        translation_key="external_spool",
        icon="mdi:printer-3d-nozzle",
        value_fn=lambda self: self.coordinator.get_model().external_spool.name,
        extra_attributes=lambda self:
        {
            "active": not self.coordinator.get_model().supports_feature(Features.AMS) or (
                    self.coordinator.get_model().ams.tray_now == 254),
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
        key="humidity_index",
        translation_key="humidity_index",
        icon="mdi:water-percent",
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda self: self.coordinator.get_model().ams.data[self.index].humidity_index
    ),
    BambuLabSensorEntityDescription(
        key="temperature",
        translation_key="ams_temp",
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda self: self.coordinator.get_model().ams.data[self.index].temperature,
        exists_fn=lambda coordinator: coordinator.get_model().supports_feature(Features.AMS_TEMPERATURE)
    ),
    BambuLabSensorEntityDescription(
        key="tray_1",
        translation_key="tray_1",
        icon="mdi:printer-3d-nozzle",
        value_fn=lambda self: self.coordinator.get_model().ams.data[self.index].tray[0].name,
        extra_attributes=lambda self:
        {
            "active": (self.coordinator.get_model().ams.tray_now % 4 == 0) and (
                    math.floor(self.coordinator.get_model().ams.tray_now / 4) == self.index),
            "empty": self.coordinator.get_model().ams.data[self.index].tray[0].empty,
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
        translation_key="tray_2",
        icon="mdi:printer-3d-nozzle",
        value_fn=lambda self: self.coordinator.get_model().ams.data[self.index].tray[1].name,
        extra_attributes=lambda self:
        {
            "active": (self.coordinator.get_model().ams.tray_now % 4 == 1) and (
                    math.floor(self.coordinator.get_model().ams.tray_now / 4) == self.index),
            "color": f"#{self.coordinator.get_model().ams.data[self.index].tray[1].color}",
            "empty": self.coordinator.get_model().ams.data[self.index].tray[1].empty,
            "name": self.coordinator.get_model().ams.data[self.index].tray[1].name,
            "nozzle_temp_min": self.coordinator.get_model().ams.data[self.index].tray[1].nozzle_temp_min,
            "nozzle_temp_max": self.coordinator.get_model().ams.data[self.index].tray[1].nozzle_temp_max,
            "type": self.coordinator.get_model().ams.data[self.index].tray[1].type,
        },
        exists_fn=lambda coordinator: not coordinator.get_model().supports_feature(Features.K_VALUE)
    ),
    BambuLabSensorEntityDescription(
        key="tray_3",
        translation_key="tray_3",
        icon="mdi:printer-3d-nozzle",
        value_fn=lambda self: self.coordinator.get_model().ams.data[self.index].tray[2].name,
        extra_attributes=lambda self:
        {
            "active": (self.coordinator.get_model().ams.tray_now % 4 == 2) and (
                    math.floor(self.coordinator.get_model().ams.tray_now / 4) == self.index),
            "color": f"#{self.coordinator.get_model().ams.data[self.index].tray[2].color}",
            "empty": self.coordinator.get_model().ams.data[self.index].tray[2].empty,
            "name": self.coordinator.get_model().ams.data[self.index].tray[2].name,
            "nozzle_temp_min": self.coordinator.get_model().ams.data[self.index].tray[2].nozzle_temp_min,
            "nozzle_temp_max": self.coordinator.get_model().ams.data[self.index].tray[2].nozzle_temp_max,
            "type": self.coordinator.get_model().ams.data[self.index].tray[2].type,
        },
        exists_fn=lambda coordinator: not coordinator.get_model().supports_feature(Features.K_VALUE)
    ),
    BambuLabSensorEntityDescription(
        key="tray_4",
        translation_key="tray_4",
        icon="mdi:printer-3d-nozzle",
        value_fn=lambda self: self.coordinator.get_model().ams.data[self.index].tray[3].name,
        extra_attributes=lambda self:
        {
            "active": (self.coordinator.get_model().ams.tray_now % 4 == 3) and (
                    math.floor(self.coordinator.get_model().ams.tray_now / 4) == self.index),
            "color": f"#{self.coordinator.get_model().ams.data[self.index].tray[3].color}",
            "empty": self.coordinator.get_model().ams.data[self.index].tray[3].empty,
            "name": self.coordinator.get_model().ams.data[self.index].tray[3].name,
            "nozzle_temp_min": self.coordinator.get_model().ams.data[self.index].tray[3].nozzle_temp_min,
            "nozzle_temp_max": self.coordinator.get_model().ams.data[self.index].tray[3].nozzle_temp_max,
            "type": self.coordinator.get_model().ams.data[self.index].tray[3].type,
        },
        exists_fn=lambda coordinator: not coordinator.get_model().supports_feature(Features.K_VALUE)
    ),
    BambuLabSensorEntityDescription(
        key="tray_1",
        translation_key="tray_1",
        icon="mdi:printer-3d-nozzle",
        value_fn=lambda self: self.coordinator.get_model().ams.data[self.index].tray[0].name,
        extra_attributes=lambda self:
        {
            "active": (self.coordinator.get_model().ams.tray_now % 4 == 0) and (
                    math.floor(self.coordinator.get_model().ams.tray_now / 4) == self.index),
            "color": f"#{self.coordinator.get_model().ams.data[self.index].tray[0].color}",
            "empty": self.coordinator.get_model().ams.data[self.index].tray[0].empty,
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
        translation_key="tray_2",
        icon="mdi:printer-3d-nozzle",
        value_fn=lambda self: self.coordinator.get_model().ams.data[self.index].tray[1].name,
        extra_attributes=lambda self:
        {
            "active": (self.coordinator.get_model().ams.tray_now % 4 == 1) and (
                    math.floor(self.coordinator.get_model().ams.tray_now / 4) == self.index),
            "color": f"#{self.coordinator.get_model().ams.data[self.index].tray[1].color}",
            "empty": self.coordinator.get_model().ams.data[self.index].tray[1].empty,
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
        translation_key="tray_3",
        icon="mdi:printer-3d-nozzle",
        value_fn=lambda self: self.coordinator.get_model().ams.data[self.index].tray[2].name,
        extra_attributes=lambda self:
        {
            "active": (self.coordinator.get_model().ams.tray_now % 4 == 2) and (
                    math.floor(self.coordinator.get_model().ams.tray_now / 4) == self.index),
            "color": f"#{self.coordinator.get_model().ams.data[self.index].tray[2].color}",
            "empty": self.coordinator.get_model().ams.data[self.index].tray[2].empty,
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
        translation_key="tray_4",
        icon="mdi:printer-3d-nozzle",
        value_fn=lambda self: self.coordinator.get_model().ams.data[self.index].tray[3].name,
        extra_attributes=lambda self:
        {
            "active": (self.coordinator.get_model().ams.tray_now % 4 == 3) and (
                    math.floor(self.coordinator.get_model().ams.tray_now / 4) == self.index),
            "color": f"#{self.coordinator.get_model().ams.data[self.index].tray[3].color}",
            "empty": self.coordinator.get_model().ams.data[self.index].tray[3].empty,
            "k_value": self.coordinator.get_model().ams.data[self.index].tray[3].k,
            "name": self.coordinator.get_model().ams.data[self.index].tray[3].name,
            "nozzle_temp_min": self.coordinator.get_model().ams.data[self.index].tray[3].nozzle_temp_min,
            "nozzle_temp_max": self.coordinator.get_model().ams.data[self.index].tray[3].nozzle_temp_max,
            "type": self.coordinator.get_model().ams.data[self.index].tray[3].type,
        },
        exists_fn=lambda coordinator: coordinator.get_model().supports_feature(Features.K_VALUE)
    ),
)
