"""Definitions for Bambu Lab sensors added to MQTT."""
from __future__ import annotations

import math
from collections.abc import Callable
from dataclasses import dataclass

from homeassistant.helpers.entity import EntityCategory
from homeassistant.const import (
    PERCENTAGE,
    SIGNAL_STRENGTH_DECIBELS_MILLIWATT,
    UnitOfTemperature,
    UnitOfMass,
    UnitOfLength,
    UnitOfTime
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
from .pybambu.const import PRINT_TYPE_OPTIONS, SPEED_PROFILE, Features, FansEnum, CURRENT_STAGE_OPTIONS, GCODE_STATE_OPTIONS


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
    icon_fn: Callable[..., str] = lambda _: None


@dataclass
class BambuLabBinarySensorEntityDescriptionMixIn:
    """Mixin for required keys."""
    is_on_fn: Callable[..., bool]


@dataclass
class BambuLabBinarySensorEntityDescription(BinarySensorEntityDescription, BambuLabBinarySensorEntityDescriptionMixIn):
    """Sensor entity description for Bambu Lab."""
    available_fn: Callable[..., bool] = lambda _: True
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
        is_on_fn=lambda self: self.coordinator.get_model().hms.error_count != 0,
        extra_attributes=lambda self: self.coordinator.get_model().hms.errors
    ),
    BambuLabBinarySensorEntityDescription(
        key="print_error",
        translation_key="print_error",
        device_class=BinarySensorDeviceClass.PROBLEM,
        entity_category=EntityCategory.DIAGNOSTIC,
        is_on_fn=lambda self: self.coordinator.get_model().print_error.on != 0,
        extra_attributes=lambda self: self.coordinator.get_model().print_error.error
    ),
    BambuLabBinarySensorEntityDescription(
        key="online",
        translation_key="online",
        device_class=BinarySensorDeviceClass.RUNNING,
        entity_category=EntityCategory.DIAGNOSTIC,
        is_on_fn=lambda self: self.coordinator.get_model().info.online or self.coordinator.client.manual_refresh_mode
    ),
    BambuLabBinarySensorEntityDescription(
        key="firmware_update",
        translation_key="firmware_update",
        device_class=BinarySensorDeviceClass.UPDATE,
        entity_category=EntityCategory.DIAGNOSTIC,
        is_on_fn=lambda self: self.coordinator.get_model().info.new_version_state == 1
    ),
    BambuLabBinarySensorEntityDescription(
        key="door_open",
        translation_key="door_open",
        device_class=BinarySensorDeviceClass.DOOR,
        entity_category=EntityCategory.DIAGNOSTIC,
        available_fn=lambda self: self.coordinator.get_model().home_flag.door_open_available,
        is_on_fn=lambda self: self.coordinator.get_model().home_flag.door_open,
        exists_fn=lambda coordinator: coordinator.get_model().supports_feature(Features.DOOR_SENSOR),
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
        value_fn=lambda self: self.coordinator.get_model().fans.get_fan_speed(FansEnum.AUXILIARY)
    ),
    BambuLabSensorEntityDescription(
        key="chamber_fan_speed",
        translation_key="chamber_fan_speed",
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        icon="mdi:fan",
        value_fn=lambda self: self.coordinator.get_model().fans.get_fan_speed(FansEnum.CHAMBER),
        exists_fn=lambda coordinator: coordinator.get_model().supports_feature(Features.CHAMBER_FAN)
    ),
    BambuLabSensorEntityDescription(
        key="cooling_fan_speed",
        translation_key="cooling_fan_speed",
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        icon="mdi:fan",
        value_fn=lambda self: self.coordinator.get_model().fans.get_fan_speed(FansEnum.PART_COOLING)
    ),
    BambuLabSensorEntityDescription(
        key="heatbreak_fan_speed",
        translation_key="heatbreak_fan_speed",
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        icon="mdi:fan",
        value_fn=lambda self: self.coordinator.get_model().fans.get_fan_speed(FansEnum.HEATBREAK)
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
            self: "offline" if (not self.coordinator.get_model().info.online and not self.coordinator.client.manual_refresh_mode) else self.coordinator.get_model().stage.description,
        exists_fn=lambda coordinator: coordinator.get_model().supports_feature(Features.CURRENT_STAGE),
        device_class=SensorDeviceClass.ENUM,
        options=CURRENT_STAGE_OPTIONS + ["offline"]
    ),
    BambuLabSensorEntityDescription(
        key="print_progress",
        translation_key="print_progress",
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        icon="mdi:progress-clock",
        value_fn=lambda self: self.coordinator.get_model().print_job.print_percentage
    ),
    BambuLabSensorEntityDescription(
        key="print_status",
        translation_key="print_status",
        icon="mdi:list-status",
        value_fn=lambda
            self: "offline" if (not self.coordinator.get_model().info.online and not self.coordinator.client.manual_refresh_mode) else self.coordinator.get_model().print_job.gcode_state.lower(),
        device_class=SensorDeviceClass.ENUM,
        options=GCODE_STATE_OPTIONS + ["offline"]
    ),
    BambuLabSensorEntityDescription(
        key="start_time",
        translation_key="start_time",
        icon="mdi:clock",
        available_fn=lambda self: self.coordinator.get_model().print_job.start_time is not None,
        value_fn=lambda self: self.coordinator.get_model().print_job.start_time,
        exists_fn=lambda coordinator: coordinator.get_model().supports_feature(Features.START_TIME) or coordinator.get_model().supports_feature(Features.START_TIME_GENERATED),
    ),
    BambuLabSensorEntityDescription(
        key="remaining_time",
        translation_key="remaining_time",
        icon="mdi:timer-sand",
        native_unit_of_measurement=UnitOfTime.MINUTES,
        device_class=SensorDeviceClass.DURATION,
        value_fn=lambda self: self.coordinator.get_model().print_job.remaining_time
    ),
    BambuLabSensorEntityDescription(
        key="end_time",
        translation_key="end_time",
        icon="mdi:clock",
        available_fn=lambda self: self.coordinator.get_model().print_job.end_time is not None,
        value_fn=lambda self: self.coordinator.get_model().print_job.end_time,
    ),
    BambuLabSensorEntityDescription(
        key="total_usage_hours",
        translation_key="total_usage_hours",
        icon="mdi:clock",
        native_unit_of_measurement=UnitOfTime.HOURS,
        suggested_display_precision=0,
        entity_category=EntityCategory.DIAGNOSTIC,
        available_fn=lambda self: self.coordinator.get_model().info.usage_hours is not None,
        value_fn=lambda self: self.coordinator.get_model().info.usage_hours,
    ),
    BambuLabSensorEntityDescription(
        key="current_layer",
        translation_key="current_layer",
        icon="mdi:printer-3d-nozzle",
        native_unit_of_measurement=" ",
        value_fn=lambda self: self.coordinator.get_model().print_job.current_layer,
        exists_fn=lambda coordinator: coordinator.get_model().supports_feature(Features.PRINT_LAYERS),
    ),
    BambuLabSensorEntityDescription(
        key="total_layers",
        translation_key="total_layers",
        icon="mdi:printer-3d-nozzle",
        native_unit_of_measurement=" ",
        value_fn=lambda self: self.coordinator.get_model().print_job.total_layers,
        exists_fn=lambda coordinator: coordinator.get_model().supports_feature(Features.PRINT_LAYERS),
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
        available_fn=lambda self: self.coordinator.get_model().print_job.gcode_file != "",
        value_fn=lambda self: self.coordinator.get_model().print_job.gcode_file,
        icon_fn=lambda self: self.coordinator.get_model().print_job.file_type_icon
    ),
    BambuLabSensorEntityDescription(
        key="subtask_name",
        translation_key="subtask_name",
        available_fn=lambda self: self.coordinator.get_model().print_job.subtask_name != "",
        value_fn=lambda self: self.coordinator.get_model().print_job.subtask_name,
        icon_fn=lambda self: self.coordinator.get_model().print_job.file_type_icon
    ),
    BambuLabSensorEntityDescription(
        key="print_type",
        translation_key="print_type",
        available_fn=lambda self: self.coordinator.get_model().print_job.print_type != "",
        value_fn=lambda self: self.coordinator.get_model().print_job.print_type,
        icon_fn=lambda self: self.coordinator.get_model().print_job.file_type_icon,
        options=PRINT_TYPE_OPTIONS,
        device_class=SensorDeviceClass.ENUM,
    ),
    BambuLabSensorEntityDescription(
        key="name",
        translation_key="printer_name",
        value_fn=lambda self: self.coordinator.config_entry.options.get('name', ''),
        exists_fn=lambda coordinator: coordinator.config_entry.options.get('name', '') != ''
    ),
    BambuLabSensorEntityDescription(
        key="print_length",
        translation_key="print_length",
        native_unit_of_measurement=UnitOfLength.METERS,
        device_class=SensorDeviceClass.DISTANCE,
        state_class=SensorStateClass.MEASUREMENT,
        icon="mdi:file",
        value_fn=lambda self: self.coordinator.get_model().print_job.print_length,
        extra_attributes=lambda self: self.coordinator.get_model().print_job.get_ams_print_lengths,
        exists_fn=lambda coordinator: coordinator.get_model().info.has_bambu_cloud_connection
    ),
    BambuLabSensorEntityDescription(
        key="print_bed_type",
        translation_key="print_bed_type",
        icon="mdi:file",
        value_fn=lambda self: self.coordinator.get_model().print_job.print_bed_type,
        exists_fn=lambda coordinator: coordinator.get_model().info.has_bambu_cloud_connection
    ),
    BambuLabSensorEntityDescription(
        key="print_weight",
        translation_key="print_weight",
        native_unit_of_measurement=UnitOfMass.GRAMS,
        device_class=SensorDeviceClass.WEIGHT,
        state_class=SensorStateClass.MEASUREMENT,
        icon="mdi:file",
        value_fn=lambda self: self.coordinator.get_model().print_job.print_weight,
        extra_attributes=lambda self: self.coordinator.get_model().print_job.get_ams_print_weights,
        exists_fn=lambda coordinator: coordinator.get_model().info.has_bambu_cloud_connection
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
            "remain": self.coordinator.get_model().get_active_tray().remain,
            "tag_uid": self.coordinator.get_model().get_active_tray().tag_uid,
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
            "remain": self.coordinator.get_model().get_active_tray().remain,
            "tag_uid": self.coordinator.get_model().get_active_tray().tag_uid,
            "type": self.coordinator.get_model().get_active_tray().type,
        },
        available_fn=lambda self: self.coordinator.get_model().get_active_tray() is not None,
        exists_fn=lambda coordinator: coordinator.get_model().supports_feature(Features.AMS) and coordinator.get_model().supports_feature(Features.K_VALUE)
    ),
    BambuLabSensorEntityDescription(
        key="nozzle_diameter",
        translation_key="nozzle_diameter",
        native_unit_of_measurement=UnitOfLength.MILLIMETERS,
        device_class=SensorDeviceClass.DISTANCE,
        icon="mdi:printer-3d-nozzle",
        value_fn=lambda self: self.coordinator.get_model().info.nozzle_diameter
    ),
    BambuLabSensorEntityDescription(
        key="nozzle_type",
        translation_key="nozzle_type",
        icon="mdi:printer-3d-nozzle",
        value_fn=lambda self: self.coordinator.get_model().info.nozzle_type
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
        value_fn=lambda self: 6 - self.coordinator.get_model().ams.data[self.index].humidity_index
        # We subtract from 6 to match the new Bambu Handy/Studio presentation of 1 = dry, 5 = wet while the printer sends 1 = wet, 5 = dry
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
            "remain": self.coordinator.get_model().ams.data[self.index].tray[0].remain,
            "tag_uid": self.coordinator.get_model().ams.data[self.index].tray[0].tag_uid,
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
            "remain": self.coordinator.get_model().ams.data[self.index].tray[1].remain,
            "tag_uid": self.coordinator.get_model().ams.data[self.index].tray[1].tag_uid,
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
            "remain": self.coordinator.get_model().ams.data[self.index].tray[2].remain,
            "tag_uid": self.coordinator.get_model().ams.data[self.index].tray[2].tag_uid,
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
            "remain": self.coordinator.get_model().ams.data[self.index].tray[3].remain,
            "tag_uid": self.coordinator.get_model().ams.data[self.index].tray[3].tag_uid,
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
            "remain": self.coordinator.get_model().ams.data[self.index].tray[0].remain,
            "tag_uid": self.coordinator.get_model().ams.data[self.index].tray[0].tag_uid,
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
            "remain": self.coordinator.get_model().ams.data[self.index].tray[1].remain,
            "tag_uid": self.coordinator.get_model().ams.data[self.index].tray[1].tag_uid,
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
            "remain": self.coordinator.get_model().ams.data[self.index].tray[2].remain,
            "tag_uid": self.coordinator.get_model().ams.data[self.index].tray[2].tag_uid,
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
            "remain": self.coordinator.get_model().ams.data[self.index].tray[3].remain,
            "tag_uid": self.coordinator.get_model().ams.data[self.index].tray[3].tag_uid,
            "type": self.coordinator.get_model().ams.data[self.index].tray[3].type,
        },
        exists_fn=lambda coordinator: coordinator.get_model().supports_feature(Features.K_VALUE)
    ),
)

CHAMBER_IMAGE_SENSOR = BambuLabSensorEntityDescription(
        key="p1p_camera",
        translation_key="p1p_camera",
        value_fn=lambda self: self.coordinator.get_model().get_camera_image(),
        exists_fn=lambda coordinator: coordinator.get_model().supports_feature(Features.CAMERA_IMAGE),
    )

COVER_IMAGE_SENSOR = BambuLabSensorEntityDescription(
        key="cover_image",
        translation_key="cover_image",
        value_fn=lambda self: self.coordinator.get_model().print_job.get_cover_image(),
        exists_fn=lambda coordinator: coordinator.get_model().info.has_bambu_cloud_connection
    )
