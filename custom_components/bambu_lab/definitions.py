"""Definitions for Bambu Lab sensors added to MQTT."""
from __future__ import annotations

import math
from collections.abc import Callable
from dataclasses import dataclass

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntityDescription
)
from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.components.update import (
    UpdateDeviceClass,
    UpdateEntityDescription
)
from homeassistant.const import (
    PERCENTAGE,
    SIGNAL_STRENGTH_DECIBELS_MILLIWATT,
    UnitOfTemperature,
    UnitOfMass,
    UnitOfLength,
    UnitOfTime
)
from homeassistant.helpers.entity import EntityCategory
from homeassistant.util import dt as dt_util

from .const import (
    LOGGER,
    Options,
)
from .coordinator import BambuDataUpdateCoordinator
from .pybambu.const import (
    PRINT_TYPE_OPTIONS,
    SPEED_PROFILE,
    CURRENT_STAGE_OPTIONS,
    GCODE_STATE_OPTIONS,
    SDCARD_STATUS,
    FansEnum,
    Features,
)

def fan_to_percent(speed):
    percentage = (int(speed) / 15) * 100
    return math.ceil(percentage / 10) * 10

@dataclass
class BambuLabUpdateEntityDescription(UpdateEntityDescription):
    """Update entity description for Bambu Lab."""
    device_class: UpdateDeviceClass = UpdateDeviceClass.FIRMWARE
    entity_category: EntityCategory = EntityCategory.DIAGNOSTIC
    latest_ver_fn: Callable[..., str] = lambda _: None
    installed_ver_fn: Callable[..., str] = lambda _: None


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
class BambuLabAMSSensorEntityDescription(
    SensorEntityDescription, BambuLabSensorEntityDescriptionMixin
):
    """Sensor entity description for Bambu Lab."""

    available_fn: Callable[..., bool] = lambda _: True
    exists_fn: Callable[[BambuDataUpdateCoordinator, int], bool] = lambda coordinator, index: True
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


@dataclass
class BambuLabAMSBinarySensorEntityDescription(BinarySensorEntityDescription, BambuLabBinarySensorEntityDescriptionMixIn):
    """Binary sensor entity description for Bambu Lab AMS."""
    available_fn: Callable[..., bool] = lambda _: True
    exists_fn: Callable[[BambuDataUpdateCoordinator, int], bool] = lambda coordinator, index: True
    extra_attributes: Callable[..., dict] = lambda _: {}


AMS_BINARY_SENSORS: tuple[BambuLabAMSBinarySensorEntityDescription, ...] = (
    BambuLabAMSBinarySensorEntityDescription(
        key="active_ams",
        translation_key="active_ams",
        icon="mdi:check",
        device_class=BinarySensorDeviceClass.RUNNING,
        is_on_fn=lambda self: self.coordinator.get_model().ams.data[self.index].active,
    ),
    BambuLabAMSBinarySensorEntityDescription(
        key="drying",
        translation_key="drying",
        icon="mdi:heat-wave",
        device_class=BinarySensorDeviceClass.RUNNING,
        is_on_fn=lambda self: self.coordinator.get_model().ams.data[self.index].remaining_drying_time > 0,
        exists_fn=lambda coordinator, index: coordinator.get_model().supports_feature(Features.AMS_DRYING)
        and (
            coordinator.get_model().ams.data[index].model == "AMS 2 Pro"
            or coordinator.get_model().ams.data[index].model == "AMS HT"
        ),
    ),
)


PRINTER_BINARY_SENSORS: tuple[BambuLabBinarySensorEntityDescription, ...] = (
    BambuLabBinarySensorEntityDescription(
        key="timelapse",
        translation_key="timelapse",
        icon="mdi:camera",
        device_class=BinarySensorDeviceClass.RUNNING,
        is_on_fn=lambda self: self.coordinator.get_model().camera.timelapse == 'enable'
    ),
    BambuLabBinarySensorEntityDescription(
        key="extruder_filament_state",
        translation_key="extruder_filament_state",
        is_on_fn=lambda self: self.coordinator.get_model().info.extruder_filament_state,
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
        is_on_fn=lambda self: self.coordinator.get_model().info.online
    ),
    BambuLabBinarySensorEntityDescription(
        key="firmware_update",
        translation_key="firmware_update",
        device_class=BinarySensorDeviceClass.UPDATE,
        entity_category=EntityCategory.DIAGNOSTIC,
        is_on_fn=lambda self: self.coordinator.get_model().info.new_version_state == 1,
        exists_fn=lambda coordinator: not coordinator.get_option_enabled(Options.FIRMWAREUPDATE),
    ),
    BambuLabBinarySensorEntityDescription(
        key="door_open",
        translation_key="door_open",
        device_class=BinarySensorDeviceClass.DOOR,
        entity_category=EntityCategory.DIAGNOSTIC,
        is_on_fn=lambda self: self.coordinator.get_model().info.door_open,
        exists_fn=lambda coordinator: coordinator.get_model().supports_feature(Features.DOOR_SENSOR),
    ),
    BambuLabBinarySensorEntityDescription(
        key="airduct_mode",
        translation_key="airduct_mode",
        device_class=BinarySensorDeviceClass.OPENING,
        entity_category=EntityCategory.DIAGNOSTIC,
        is_on_fn=lambda self: self.coordinator.get_model().info.airduct_mode == False,
        exists_fn=lambda coordinator: coordinator.get_model().supports_feature(Features.AIRDUCT_MODE),
    ),
    BambuLabBinarySensorEntityDescription(
        key="developer_lan_mode",
        translation_key="developer_lan_mode",
        device_class=BinarySensorDeviceClass.RUNNING,
        entity_category=EntityCategory.DIAGNOSTIC,
        is_on_fn=lambda self: self.coordinator.get_model().supports_feature(Features.MQTT_ENCRYPTION_FIRMWARE)
                          and not self.coordinator.get_model().print_fun.mqtt_signature_required,
    ),
    BambuLabBinarySensorEntityDescription(
        key="mqtt_encryption",
        translation_key="mqtt_encryption",
        device_class=BinarySensorDeviceClass.RUNNING,
        entity_category=EntityCategory.DIAGNOSTIC,
        is_on_fn=lambda self: self.coordinator.get_model().supports_feature(Features.MQTT_ENCRYPTION_FIRMWARE),
    ),
    BambuLabBinarySensorEntityDescription(
        key="hybrid_mode_blocks_control",
        translation_key="hybrid_mode_blocks_control",
        device_class=BinarySensorDeviceClass.RUNNING,
        entity_category=EntityCategory.DIAGNOSTIC,
        is_on_fn=lambda self: self.coordinator.get_model().info.is_hybrid_mode_blocking,
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
        key="tool_module",
        translation_key="tool_module",
        icon="mdi:printer-3d-nozzle",
        device_class=SensorDeviceClass.ENUM,
        options=["none", "laser10", "laser40", "cutter"],
        value_fn=lambda self: self.coordinator.get_model().extruder_tool.state,
        exists_fn=lambda coordinator: coordinator.get_model().supports_feature(Features.EXTRUDER_TOOL),
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
        suggested_unit_of_measurement=UnitOfTemperature.CELSIUS,
        suggested_display_precision=0,
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda self: self.coordinator.get_model().temperature.bed_temp
    ),
    BambuLabSensorEntityDescription(
        key="target_bed_temp",
        translation_key="target_bed_temp",
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        suggested_unit_of_measurement=UnitOfTemperature.CELSIUS,
        suggested_display_precision=0,
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda self: self.coordinator.get_model().temperature.target_bed_temp
    ),
    BambuLabSensorEntityDescription(
        key="chamber_temp",
        translation_key="chamber_temp",
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        suggested_unit_of_measurement=UnitOfTemperature.CELSIUS,
        suggested_display_precision=0,
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda self: self.coordinator.get_model().temperature.chamber_temp,
        exists_fn=lambda coordinator: coordinator.get_model().supports_feature(Features.CHAMBER_TEMPERATURE)
    ),
    BambuLabSensorEntityDescription(
        key="nozzle_temp",
        translation_key="nozzle_temp",
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        suggested_unit_of_measurement=UnitOfTemperature.CELSIUS,
        suggested_display_precision=0,
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        icon="mdi:printer-3d-nozzle",
        value_fn=lambda self: self.coordinator.get_model().temperature.active_nozzle_temperature
    ),
    BambuLabSensorEntityDescription(
        key="target_nozzle_temp",
        translation_key="target_nozzle_temp",
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        suggested_unit_of_measurement=UnitOfTemperature.CELSIUS,
        suggested_display_precision=0,
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        icon="mdi:printer-3d-nozzle",
        value_fn=lambda self: self.coordinator.get_model().temperature.active_nozzle_target_temperature
    ),
    BambuLabSensorEntityDescription(
        key="left_nozzle_temp",
        translation_key="left_nozzle_temp",
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        suggested_unit_of_measurement=UnitOfTemperature.CELSIUS,
        suggested_display_precision=0,
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        icon="mdi:printer-3d-nozzle",
        value_fn=lambda self: self.coordinator.get_model().temperature.left_nozzle_temperature,
        exists_fn=lambda coordinator: coordinator.get_model().supports_feature(Features.DUAL_NOZZLES),
    ),
    BambuLabSensorEntityDescription(
        key="left_target_nozzle_temp",
        translation_key="left_target_nozzle_temp",
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        suggested_unit_of_measurement=UnitOfTemperature.CELSIUS,
        suggested_display_precision=0,
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        icon="mdi:printer-3d-nozzle",
        value_fn=lambda self: self.coordinator.get_model().temperature.left_nozzle_target_temperature,
        exists_fn=lambda coordinator: coordinator.get_model().supports_feature(Features.DUAL_NOZZLES),
    ),
    BambuLabSensorEntityDescription(
        key="right_nozzle_temp",
        translation_key="right_nozzle_temp",
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        suggested_unit_of_measurement=UnitOfTemperature.CELSIUS,
        suggested_display_precision=0,
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        icon="mdi:printer-3d-nozzle",
        value_fn=lambda self: self.coordinator.get_model().temperature.right_nozzle_temperature,
        exists_fn=lambda coordinator: coordinator.get_model().supports_feature(Features.DUAL_NOZZLES),
    ),
    BambuLabSensorEntityDescription(
        key="right_target_nozzle_temp",
        translation_key="right_target_nozzle_temp",
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        suggested_unit_of_measurement=UnitOfTemperature.CELSIUS,
        suggested_display_precision=0,
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        icon="mdi:printer-3d-nozzle",
        value_fn=lambda self: self.coordinator.get_model().temperature.right_nozzle_target_temperature,
        exists_fn=lambda coordinator: coordinator.get_model().supports_feature(Features.DUAL_NOZZLES),
    ),
    BambuLabSensorEntityDescription(
        key="aux_fan_speed",
        translation_key="aux_fan_speed",
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        icon="mdi:fan",
        value_fn=lambda self: self.coordinator.get_model().fans.get_fan_speed(FansEnum.AUXILIARY),
        exists_fn=lambda coordinator: coordinator.get_model().supports_feature(Features.AUX_FAN),
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
        key="model_download_percentage",
        translation_key="model_download_percentage",
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        icon="mdi:percent",
        value_fn=lambda self: self.coordinator.get_model().print_job.model_download_percentage,
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
        value_fn=lambda self: "offline" if not self.coordinator.get_model().info.online else self.coordinator.get_model().stage.description,
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
            self: "offline" if not self.coordinator.get_model().info.online else self.coordinator.get_model().print_job.gcode_state.lower(),
        device_class=SensorDeviceClass.ENUM,
        options=GCODE_STATE_OPTIONS + ["offline"]
    ),
    BambuLabSensorEntityDescription(
        key="printable_objects",
        translation_key="printable_objects",
        icon="mdi:cube-unfolded",
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda self: len(self.coordinator.get_model().print_job.get_printable_objects),
        extra_attributes=lambda self: {"objects": self.coordinator.get_model().print_job.get_printable_objects},
    ),
    BambuLabSensorEntityDescription(
        key="sdcard_status",
        translation_key="sdcard_status",
        icon="mdi:list-status",
        value_fn=lambda
            self: self.coordinator.get_model().home_flag.sdcard_status,
        device_class=SensorDeviceClass.ENUM,
        entity_category=EntityCategory.DIAGNOSTIC,
        options=SDCARD_STATUS
    ),
    BambuLabSensorEntityDescription(
        key="skipped_objects",
        translation_key="skipped_objects",
        icon="mdi:cube-unfolded",
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda self: len(self.coordinator.get_model().print_job.get_skipped_objects),
        extra_attributes=lambda self: {"objects": self.coordinator.get_model().print_job.get_skipped_objects},
    ),
    BambuLabSensorEntityDescription(
        key="start_time",
        translation_key="start_time",
        icon="mdi:clock",
        available_fn=lambda self: self.coordinator.get_model().print_job.start_time is not None,
        value_fn=lambda self: dt_util.as_local(self.coordinator.get_model().print_job.start_time).replace(tzinfo=None),
    ),
    BambuLabSensorEntityDescription(
        key="remaining_time",
        translation_key="remaining_time",
        icon="mdi:timer-sand",
        native_unit_of_measurement=UnitOfTime.MINUTES,
        suggested_unit_of_measurement=UnitOfTime.HOURS,
        suggested_display_precision=3,
        device_class=SensorDeviceClass.DURATION,
        value_fn=lambda self: self.coordinator.get_model().print_job.remaining_time
    ),
    BambuLabSensorEntityDescription(
        key="end_time",
        translation_key="end_time",
        icon="mdi:clock",
        available_fn=lambda self: self.coordinator.get_model().print_job.end_time is not None,
        value_fn=lambda self: dt_util.as_local(self.coordinator.get_model().print_job.end_time).replace(tzinfo=None),
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
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda self: self.coordinator.get_model().print_job.current_layer,
    ),
    BambuLabSensorEntityDescription(
        key="total_layers",
        translation_key="total_layers",
        icon="mdi:printer-3d-nozzle",
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda self: self.coordinator.get_model().print_job.total_layers,
    ),
    BambuLabSensorEntityDescription(
        key="gcode_file",
        translation_key="gcode_file",
        available_fn=lambda self: self.coordinator.get_model().print_job.gcode_file != "",
        value_fn=lambda self: self.coordinator.get_model().print_job.gcode_file,
        icon_fn=lambda self: self.coordinator.get_model().print_job.file_type_icon
    ),
    BambuLabSensorEntityDescription(
        key="gcode_file_downloaded",
        translation_key="gcode_file_downloaded",
        available_fn=lambda self: self.coordinator.get_model().print_job.gcode_file_downloaded != "",
        value_fn=lambda self: self.coordinator.get_model().print_job.gcode_file_downloaded,
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
        value_fn=lambda self: self.coordinator.config_entry.options.get('name'),
        exists_fn=lambda coordinator: coordinator.config_entry.options.get('name') != None
    ),
    BambuLabSensorEntityDescription(
        key="print_length",
        translation_key="print_length",
        native_unit_of_measurement=UnitOfLength.METERS,
        suggested_unit_of_measurement=UnitOfLength.METERS,
        suggested_display_precision=2,
        device_class=SensorDeviceClass.DISTANCE,
        state_class=SensorStateClass.MEASUREMENT,
        icon="mdi:file",
        value_fn=lambda self: self.coordinator.get_model().print_job.print_length,
        extra_attributes=lambda self: self.coordinator.get_model().print_job.get_print_lengths,
    ),
    BambuLabSensorEntityDescription(
        key="print_bed_type",
        translation_key="print_bed_type",
        icon="mdi:file",
        value_fn=lambda self: self.coordinator.get_model().print_job.print_bed_type,
    ),
    BambuLabSensorEntityDescription(
        key="print_weight",
        translation_key="print_weight",
        native_unit_of_measurement=UnitOfMass.GRAMS,
        suggested_unit_of_measurement=UnitOfMass.GRAMS,
        suggested_display_precision=1,
        device_class=SensorDeviceClass.WEIGHT,
        state_class=SensorStateClass.MEASUREMENT,
        icon="mdi:file",
        value_fn=lambda self: self.coordinator.get_model().print_job.print_weight,
        extra_attributes=lambda self: self.coordinator.get_model().print_job.get_print_weights,
    ),
    BambuLabSensorEntityDescription(
        key="active_tray",
        translation_key="active_tray",
        icon="mdi:printer-3d-nozzle",
        value_fn=lambda self: "none" if self.coordinator.get_model().ams.active_tray is None else self.coordinator.get_model().ams.active_tray.name,
        extra_attributes=lambda self:
        {} if self.coordinator.get_model().ams.active_tray is  None else
        {
            "ams_index": self.coordinator.get_model().ams.active_ams_index,
            "color": f"#{self.coordinator.get_model().ams.active_tray.color}",
            "filament_id": self.coordinator.get_model().ams.active_tray.idx,
            **({"k_value": self.coordinator.get_model().ams.active_tray.k} if self.coordinator.get_model().supports_feature(Features.K_VALUE) else {}),
            "tray_weight": self.coordinator.get_model().ams.active_tray.tray_weight,
            "name": self.coordinator.get_model().ams.active_tray.name,
            "nozzle_temp_min": self.coordinator.get_model().ams.active_tray.nozzle_temp_min,
            "nozzle_temp_max": self.coordinator.get_model().ams.active_tray.nozzle_temp_max,
            "remain": self.coordinator.get_model().ams.active_tray.remain,
            "remain_enabled": self.coordinator.get_model().ams.active_tray.remain_enabled,
            "tag_uid": self.coordinator.get_model().ams.active_tray.tag_uid,
            "tray_index": self.coordinator.get_model().ams.active_tray_index,
            "tray_uuid": self.coordinator.get_model().ams.active_tray.tray_uuid,
            "type": self.coordinator.get_model().ams.active_tray.type,
        },
        exists_fn=lambda coordinator: coordinator.get_model().supports_feature(Features.AMS)
    ),
    BambuLabSensorEntityDescription(
        key="nozzle_diameter",
        translation_key="nozzle_diameter",
        native_unit_of_measurement=UnitOfLength.MILLIMETERS,
        suggested_unit_of_measurement=UnitOfLength.MILLIMETERS,
        suggested_display_precision=1,
        device_class=SensorDeviceClass.DISTANCE,
        icon="mdi:printer-3d-nozzle",
        value_fn=lambda self: self.coordinator.get_model().info.active_nozzle_diameter
    ),
    BambuLabSensorEntityDescription(
        key="nozzle_type",
        translation_key="nozzle_type",
        icon="mdi:printer-3d-nozzle",
        value_fn=lambda self: self.coordinator.get_model().info.active_nozzle_type
    ),
    BambuLabSensorEntityDescription(
        key="left_nozzle_diameter",
        translation_key="left_nozzle_diameter",
        native_unit_of_measurement=UnitOfLength.MILLIMETERS,
        suggested_unit_of_measurement=UnitOfLength.MILLIMETERS,
        suggested_display_precision=1,
        device_class=SensorDeviceClass.DISTANCE,
        icon="mdi:printer-3d-nozzle",
        value_fn=lambda self: self.coordinator.get_model().info.left_nozzle_diameter,
        exists_fn=lambda coordinator: coordinator.get_model().supports_feature(Features.DUAL_NOZZLES),
    ),
    BambuLabSensorEntityDescription(
        key="left_nozzle_type",
        translation_key="left_nozzle_type",
        icon="mdi:printer-3d-nozzle",
        value_fn=lambda self: self.coordinator.get_model().info.left_nozzle_type,
        exists_fn=lambda coordinator: coordinator.get_model().supports_feature(Features.DUAL_NOZZLES),
    ),
    BambuLabSensorEntityDescription(
        key="right_nozzle_diameter",
        translation_key="right_nozzle_diameter",
        native_unit_of_measurement=UnitOfLength.MILLIMETERS,
        suggested_unit_of_measurement=UnitOfLength.MILLIMETERS,
        suggested_display_precision=1,
        device_class=SensorDeviceClass.DISTANCE,
        icon="mdi:printer-3d-nozzle",
        value_fn=lambda self: self.coordinator.get_model().info.right_nozzle_diameter,
        exists_fn=lambda coordinator: coordinator.get_model().supports_feature(Features.DUAL_NOZZLES),
    ),
    BambuLabSensorEntityDescription(
        key="right_nozzle_type",
        translation_key="right_nozzle_type",
        icon="mdi:printer-3d-nozzle",
        value_fn=lambda self: self.coordinator.get_model().info.right_nozzle_type,
        exists_fn=lambda coordinator: coordinator.get_model().supports_feature(Features.DUAL_NOZZLES),
    ),
    BambuLabSensorEntityDescription(
        key="ip_address",
        translation_key="ip_address",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda self: self.coordinator.get_model().info.ip_address
    ),
)

VIRTUAL_TRAY_BINARY_SENSORS: tuple[BambuLabSensorEntityDescription, ...] = (
    BambuLabBinarySensorEntityDescription(
        key="active_ams",
        translation_key="active_ams",
        icon="mdi:check",
        device_class=BinarySensorDeviceClass.RUNNING,
        is_on_fn=lambda self: self.coordinator.get_model().external_spool[self.index].active,
    ),
)

VIRTUAL_TRAY_SENSORS: tuple[BambuLabSensorEntityDescription, ...] = (
    BambuLabSensorEntityDescription(
        key="external_spool",
        translation_key="external_spool",
        icon="mdi:printer-3d-nozzle",
        value_fn=lambda self: self.coordinator.get_model().external_spool[self.index].name,
        extra_attributes=lambda self:
        {
            "active": self.coordinator.get_model().external_spool[self.index].active,
            "color": f"#{self.coordinator.get_model().external_spool[self.index].color}",
            "empty": self.coordinator.get_model().external_spool[self.index].empty,
            "filament_id": self.coordinator.get_model().external_spool[self.index].idx,
            **({"k_value": self.coordinator.get_model().external_spool[self.index].k} if self.coordinator.get_model().supports_feature(Features.K_VALUE) else {}),
            "tray_weight": self.coordinator.get_model().external_spool[self.index].tray_weight,
            "name": self.coordinator.get_model().external_spool[self.index].name,
            "nozzle_temp_min": self.coordinator.get_model().external_spool[self.index].nozzle_temp_min,
            "nozzle_temp_max": self.coordinator.get_model().external_spool[self.index].nozzle_temp_max,
            "remain": self.coordinator.get_model().external_spool[self.index].remain,
            "remain_enabled": self.coordinator.get_model().external_spool[self.index].remain_enabled,
            "tag_uid": self.coordinator.get_model().external_spool[self.index].tag_uid,
            "tray_uuid": self.coordinator.get_model().external_spool[self.index].tray_uuid,
            "type": self.coordinator.get_model().external_spool[self.index].type,
        },
    ),
)

AMS_SENSORS: tuple[BambuLabAMSSensorEntityDescription, ...] = (
    BambuLabAMSSensorEntityDescription(
        key="humidity_index",
        translation_key="humidity_index",
        icon="mdi:water-percent",
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda self: 6 - self.coordinator.get_model().ams.data[self.index].humidity_index
        # We subtract from 6 to match the new Bambu Handy/Studio presentation of 1 = dry, 5 = wet while the printer sends 1 = wet, 5 = dry
    ),
    BambuLabAMSSensorEntityDescription(
        key="humidity",
        translation_key="humidity",
        native_unit_of_measurement=PERCENTAGE,
        device_class=SensorDeviceClass.HUMIDITY,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda self: self.coordinator.get_model().ams.data[self.index].humidity,
        exists_fn=lambda coordinator, index: coordinator.get_model().supports_feature(Features.AMS_HUMIDITY)
    ),
    BambuLabAMSSensorEntityDescription(
        key="temperature",
        translation_key="ams_temp",
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        suggested_unit_of_measurement=UnitOfTemperature.CELSIUS,
        suggested_display_precision=0,
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda self: self.coordinator.get_model().ams.data[self.index].temperature,
        exists_fn=lambda coordinator, index: coordinator.get_model().supports_feature(Features.AMS_TEMPERATURE)
    ),
    BambuLabAMSSensorEntityDescription(
        key="remaining_drying_time",
        translation_key="remaining_drying_time",
        native_unit_of_measurement=UnitOfTime.MINUTES,
        suggested_unit_of_measurement=UnitOfTime.HOURS,
        suggested_display_precision=3,
        icon="mdi:fan-clock",
        device_class=SensorDeviceClass.DURATION,
        value_fn=lambda self: self.coordinator.get_model().ams.data[self.index].remaining_drying_time,
        exists_fn=lambda coordinator, index: coordinator.get_model().supports_feature(Features.AMS_DRYING) and
                                             coordinator.get_model().ams.data[index].model in ["AMS 2 Pro", "AMS HT"],
    ),
    BambuLabAMSSensorEntityDescription(
        key="tray_1",
        translation_key="tray_1",
        icon="mdi:printer-3d-nozzle",
        value_fn=lambda self: self.coordinator.get_model().ams.data[self.index].tray[0].name,
        extra_attributes=lambda self:
        {
            "active": self.coordinator.get_model().ams.data[self.index].tray[0].active,
            "color": f"#{self.coordinator.get_model().ams.data[self.index].tray[0].color}",
            "empty": self.coordinator.get_model().ams.data[self.index].tray[0].empty,
            "filament_id": self.coordinator.get_model().ams.data[self.index].tray[0].idx,
            **({"k_value": self.coordinator.get_model().ams.data[self.index].tray[0].k} if self.coordinator.get_model().supports_feature(Features.K_VALUE) else {}),
            "tray_weight": self.coordinator.get_model().ams.data[self.index].tray[0].tray_weight,
            "name": self.coordinator.get_model().ams.data[self.index].tray[0].name,
            "nozzle_temp_min": self.coordinator.get_model().ams.data[self.index].tray[0].nozzle_temp_min,
            "nozzle_temp_max": self.coordinator.get_model().ams.data[self.index].tray[0].nozzle_temp_max,
            "remain": self.coordinator.get_model().ams.data[self.index].tray[0].remain,
            "remain_enabled": self.coordinator.get_model().ams.data[self.index].tray[0].remain_enabled,
            "tag_uid": self.coordinator.get_model().ams.data[self.index].tray[0].tag_uid,
            "tray_uuid": self.coordinator.get_model().ams.data[self.index].tray[0].tray_uuid,
            "type": self.coordinator.get_model().ams.data[self.index].tray[0].type,
        },
    ),
    BambuLabAMSSensorEntityDescription(
        key="tray_2",
        translation_key="tray_2",
        icon="mdi:printer-3d-nozzle",
        value_fn=lambda self: self.coordinator.get_model().ams.data[self.index].tray[1].name,
        extra_attributes=lambda self:
        {
            "active": self.coordinator.get_model().ams.data[self.index].tray[1].active,
            "color": f"#{self.coordinator.get_model().ams.data[self.index].tray[1].color}",
            "empty": self.coordinator.get_model().ams.data[self.index].tray[1].empty,
            "filament_id": self.coordinator.get_model().ams.data[self.index].tray[1].idx,
            **({"k_value": self.coordinator.get_model().ams.data[self.index].tray[1].k} if self.coordinator.get_model().supports_feature(Features.K_VALUE) else {}),
            "tray_weight": self.coordinator.get_model().ams.data[self.index].tray[1].tray_weight,
            "name": self.coordinator.get_model().ams.data[self.index].tray[1].name,
            "nozzle_temp_min": self.coordinator.get_model().ams.data[self.index].tray[1].nozzle_temp_min,
            "nozzle_temp_max": self.coordinator.get_model().ams.data[self.index].tray[1].nozzle_temp_max,
            **({"remain": self.coordinator.get_model().ams.data[self.index].tray[1].remain} if self.coordinator.get_model().ams.data[self.index].tray[1].remain_enabled else {"remain": -1}),
            "remain_enabled": self.coordinator.get_model().ams.data[self.index].tray[1].remain_enabled,
            "tag_uid": self.coordinator.get_model().ams.data[self.index].tray[1].tag_uid,
            "tray_uuid": self.coordinator.get_model().ams.data[self.index].tray[1].tray_uuid,
            "type": self.coordinator.get_model().ams.data[self.index].tray[1].type,
        },
        exists_fn=lambda coordinator, index: coordinator.get_model().ams.data[index].model != "AMS HT",
    ),
    BambuLabAMSSensorEntityDescription(
        key="tray_3",
        translation_key="tray_3",
        icon="mdi:printer-3d-nozzle",
        value_fn=lambda self: self.coordinator.get_model().ams.data[self.index].tray[2].name,
        extra_attributes=lambda self:
        {
            "active": self.coordinator.get_model().ams.data[self.index].tray[2].active,
            "color": f"#{self.coordinator.get_model().ams.data[self.index].tray[2].color}",
            "empty": self.coordinator.get_model().ams.data[self.index].tray[2].empty,
            "filament_id": self.coordinator.get_model().ams.data[self.index].tray[2].idx,
            **({"k_value": self.coordinator.get_model().ams.data[self.index].tray[2].k} if self.coordinator.get_model().supports_feature(Features.K_VALUE) else {}),
            "tray_weight": self.coordinator.get_model().ams.data[self.index].tray[2].tray_weight,
            "name": self.coordinator.get_model().ams.data[self.index].tray[2].name,
            "nozzle_temp_min": self.coordinator.get_model().ams.data[self.index].tray[2].nozzle_temp_min,
            "nozzle_temp_max": self.coordinator.get_model().ams.data[self.index].tray[2].nozzle_temp_max,
            "remain": self.coordinator.get_model().ams.data[self.index].tray[2].remain,
            "remain_enabled": self.coordinator.get_model().ams.data[self.index].tray[2].remain_enabled,
            "tag_uid": self.coordinator.get_model().ams.data[self.index].tray[2].tag_uid,
            "tray_uuid": self.coordinator.get_model().ams.data[self.index].tray[2].tray_uuid,
            "type": self.coordinator.get_model().ams.data[self.index].tray[2].type,
        },
        exists_fn=lambda coordinator, index: coordinator.get_model().ams.data[index].model != "AMS HT",
    ),
    BambuLabAMSSensorEntityDescription(
        key="tray_4",
        translation_key="tray_4",
        icon="mdi:printer-3d-nozzle",
        value_fn=lambda self: self.coordinator.get_model().ams.data[self.index].tray[3].name,
        extra_attributes=lambda self:
        {
            "active": self.coordinator.get_model().ams.data[self.index].tray[3].active,
            "color": f"#{self.coordinator.get_model().ams.data[self.index].tray[3].color}",
            "empty": self.coordinator.get_model().ams.data[self.index].tray[3].empty,
            "filament_id": self.coordinator.get_model().ams.data[self.index].tray[3].idx,
            **({"k_value": self.coordinator.get_model().ams.data[self.index].tray[3].k} if self.coordinator.get_model().supports_feature(Features.K_VALUE) else {}),
            "tray_weight": self.coordinator.get_model().ams.data[self.index].tray[3].tray_weight,
            "name": self.coordinator.get_model().ams.data[self.index].tray[3].name,
            "nozzle_temp_min": self.coordinator.get_model().ams.data[self.index].tray[3].nozzle_temp_min,
            "nozzle_temp_max": self.coordinator.get_model().ams.data[self.index].tray[3].nozzle_temp_max,
            "remain": self.coordinator.get_model().ams.data[self.index].tray[3].remain,
            "remain_enabled": self.coordinator.get_model().ams.data[self.index].tray[3].remain_enabled,
            "tag_uid": self.coordinator.get_model().ams.data[self.index].tray[3].tag_uid,
            "tray_uuid": self.coordinator.get_model().ams.data[self.index].tray[3].tray_uuid,
            "type": self.coordinator.get_model().ams.data[self.index].tray[3].type,
        },
        exists_fn=lambda coordinator, index: coordinator.get_model().ams.data[index].model != "AMS HT",
    ),
)
