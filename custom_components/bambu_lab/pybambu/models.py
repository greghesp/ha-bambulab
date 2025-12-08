from __future__ import annotations

import ftplib
import json
import math
import os
import re
import threading
import shutil
import time

from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
from dateutil import parser, tz
from pathlib import Path
from zipfile import ZipFile
from typing import List, Union
import xml.etree.ElementTree as ElementTree
from PIL import Image
import asyncio

from .utils import (
    search,
    fan_percentage,
    fan_percentage_to_gcode,
    get_current_stage,
    get_filament_name,
    get_ip_address_from_int,
    get_printer_type,
    get_speed_name,
    get_hw_version,
    get_sw_version,
    compare_version,
    get_end_time,
    get_HMS_error_text,
    get_print_error_text,
    get_HMS_severity,
    get_HMS_module,
    set_temperature_to_gcode,
    get_upgrade_url,
    upgrade_template,
)
from .const import (
    LOGGER,
    Features,
    FansEnum,
    Home_Flag_Values,
    Stat_Flag_Values,
    Printers,
    SPEED_PROFILE,
    GCODE_STATE_OPTIONS,
    PRINT_TYPE_OPTIONS,
    TempEnum, Print_Fun_Values,
)
from .commands import (
    CHAMBER_LIGHT_ON,
    CHAMBER_LIGHT_OFF,
    CHAMBER_LIGHT_2_ON,
    CHAMBER_LIGHT_2_OFF,
    PROMPT_SOUND_ENABLE,
    PROMPT_SOUND_DISABLE,
    AIRDUCT_SET_COOLING,
    AIRDUCT_SET_HEATING_FILTER,
    SPEED_PROFILE_TEMPLATE, BUZZER_SET_SILENT, BUZZER_SET_ALARM, BUZZER_SET_BEEPING, HEATBED_LIGHT_ON,
    HEATBED_LIGHT_OFF,
)

class Device:
    def __init__(self, client):
        self._client = client
        self.temperature = Temperature(client = client)
        self.lights = Lights(client = client)
        self.info = Info(client = client)
        self.upgrade = Upgrade(client = client)
        self.print_job = PrintJob(client = client)
        self.fans = Fans(client = client)
        self.speed = Speed(client = client)
        self.stage = StageAction()
        self.ams = AMSList(client = client)
        self.external_spool = [ ExternalSpool(client = client, index = 0), ExternalSpool(client = client, index = 1) ]
        self.hms = HMSList(client = client)
        self.print_error = PrintError(client = client)
        self.camera = Camera(client = client)
        self.home_flag = HomeFlag(client=client)
        self.extruder = Extruder(client=client)
        self.extruder_tool = ExtruderTool(client=client)
        self.push_all_data = None
        self.get_version_data = None
        self.chamber_image = ChamberImage(client = client)
        self.cover_image = CoverImage(client = client)
        self.pick_image = PickImage(client = client)
        self.print_fun = PrintFun(client = client)

    def print_update(self, data) -> bool:
        send_event = False
        send_event = send_event | self.info.print_update(data = data)
        send_event = send_event | self.upgrade.print_update(data = data)
        send_event = send_event | self.print_job.print_update(data = data)
        send_event = send_event | self.lights.print_update(data = data)
        send_event = send_event | self.fans.print_update(data = data)
        send_event = send_event | self.speed.print_update(data = data)
        send_event = send_event | self.stage.print_update(data = data)
        send_event = send_event | self.extruder.print_update(data = data) # Must be before the AMS and external spools and temperature
        send_event = send_event | self.temperature.print_update(data = data)
        send_event = send_event | self.ams.print_update(data = data)
        send_event = send_event | self.external_spool[0].print_update(data = data)
        send_event = send_event | self.external_spool[1].print_update(data = data)
        send_event = send_event | self.hms.print_update(data = data)
        send_event = send_event | self.print_error.print_update(data = data)
        send_event = send_event | self.camera.print_update(data = data)
        send_event = send_event | self.home_flag.print_update(data = data)
        send_event = send_event | self.print_fun.print_update(data = data)
        send_event = send_event | self.extruder_tool.print_update(data = data)

        send_ready_event = self.get_version_data is not None and self.push_all_data is None
        if data.get("command") == "push_status":
            if data.get("msg", 0) == 0:
                self.push_all_data = data
                if send_ready_event:
                    self._client.callback("event_printer_ready")

        self._client.callback("event_printer_data_update")

    @property
    def has_full_printer_data(self):
        return (self.push_all_data != None) and (self.get_version_data != None)

    def info_update(self, data):
        self.info.info_update(data = data)
        self.home_flag.info_update(data = data)
        self.ams.info_update(data = data)

        if data.get("command") == "get_version":
            send_ready_event = self.get_version_data is None and self.push_all_data is not None
            self.get_version_data = data
            if send_ready_event:
                self._client.callback("event_printer_ready")


    def observe_system_command(self, data):
        if data.get("command") == "ledctrl" and data.get("led_node") == "heatbed_light":
            self.lights.observe_system_command(data)

    def supports_feature(self, feature):

        # First check known early feature check scenarios:
        if feature == Features.CAMERA_RTSP:
            return (self.info.device_type == Printers.H2C or
                    self.info.device_type == Printers.H2D or
                    self.info.device_type == Printers.H2DPRO or
                    self.info.device_type == Printers.H2S or
                    self.info.device_type == Printers.P2S or
                    self.info.device_type == Printers.X1 or
                    self.info.device_type == Printers.X1C or
                    self.info.device_type == Printers.X1E)
        elif feature == Features.CAMERA_IMAGE:
            return (self.info.device_type == Printers.A1 or
                    self.info.device_type == Printers.A1MINI or
                    self.info.device_type == Printers.P1P or
                    self.info.device_type == Printers.P1S)

        # Now check that we have a version. All tests after this are expected to only be called after the
        # first full set of data from the printer has been received and so version will be available.
        if self.info.sw_ver == "unknown":
            LOGGER.error(f"supports_feature queried for {feature} before printer firmware version is known.")
            return False

        # All following features should only be every checked after full initialization data is available.
        if feature == Features.AUX_FAN:
            return not (self.info.device_type == Printers.A1 or
                        self.info.device_type == Printers.A1MINI)
        elif feature == Features.CHAMBER_FAN:
            # The P1P may not have a fan but we don't have a perfectly reliable way to detect that. The p1s upgrade
            # flag would largely be good though but not accessible here.
            return not (self.info.device_type == Printers.A1 or
                        self.info.device_type == Printers.A1MINI)
        elif feature == Features.CHAMBER_TEMPERATURE:
            return (self.info.device_type == Printers.H2C or
                    self.info.device_type == Printers.H2D or
                    self.info.device_type == Printers.H2DPRO or
                    self.info.device_type == Printers.H2S or
                    self.info.device_type == Printers.P2S or
                    self.info.device_type == Printers.X1 or
                    self.info.device_type == Printers.X1C or
                    self.info.device_type == Printers.X1E)
        elif feature == Features.AMS:
            return len(self.ams.data) != 0
        elif feature == Features.K_VALUE:
            return (self.info.device_type == Printers.A1 or
                    self.info.device_type == Printers.A1MINI or
                    self.info.device_type == Printers.P1P or
                    self.info.device_type == Printers.P1S)
        elif feature == Features.AMS_TEMPERATURE:
            if (self.info.device_type == Printers.A1 or
                self.info.device_type == Printers.A1MINI):
                return self.supports_sw_version("01.06.10.33")
            elif (self.info.device_type == Printers.H2C or
                  self.info.device_type == Printers.H2D or
                  self.info.device_type == Printers.H2DPRO or
                  self.info.device_type == Printers.H2S or 
                  self.info.device_type == Printers.P2S or
                  self.info.device_type == Printers.X1 or
                  self.info.device_type == Printers.X1C or
                  self.info.device_type == Printers.X1E):
                return True
            elif (self.info.device_type == Printers.P1S or
                  self.info.device_type == Printers.P1P):
                return self.supports_sw_version("01.07.50.18")
            return False
        elif feature == Features.AIRDUCT_MODE:
            # Airduct mode (Filter/Heating and Cooling) is currently only present on P2S
            if self.info.device_type == Printers.P2S:
                return True
            
            return False
        elif feature == Features.HYBRID_MODE_BLOCKS_CONTROL:
            if (self.info.device_type == Printers.P1S or
                self.info.device_type == Printers.P1P):
                # Not sure what the first version that did this was. At least this - could be earlier.
                return self.supports_sw_version("01.07.00.00")
            # Only the P1 firmware did this as far as I know. Not the A1.
            return False
        elif feature == Features.DOOR_SENSOR:
            if (self.info.device_type in [Printers.X1,
                                          Printers.X1C]):
                return self.supports_sw_version("01.07.00.00")
            return (self.info.device_type == Printers.H2C or
                    self.info.device_type == Printers.H2D or
                    self.info.device_type == Printers.H2DPRO or
                    self.info.device_type == Printers.H2S or
                    self.info.device_type == Printers.P2S or
                    self.info.device_type == Printers.X1E)
        elif feature == Features.AMS_READ_RFID_COMMAND:
            if (self.info.device_type == Printers.A1 or
                self.info.device_type == Printers.A1MINI):
                return self.supports_sw_version("01.06.00.00")
            if (self.info.device_type == Printers.P1P or
                self.info.device_type == Printers.P1S):
                return self.supports_sw_version("01.08.01.00")
            if (self.info.device_type == Printers.X1 or
                self.info.device_type == Printers.X1C or
                self.info.device_type == Printers.X1E):
                return self.supports_sw_version("01.09.00.00")
            return True
        elif feature == Features.AMS_FILAMENT_REMAINING:
            if (self.info.device_type == Printers.A1 or
                self.info.device_type == Printers.A1MINI):
                # Technically this is not the AMS Lite but that's currently tied to only these printer types.
                # This needs fixing now the A1 printers support the other AMS models.
                return False
            return True
        elif feature == Features.PROMPT_SOUND:
            if (self.info.device_type == Printers.A1 or
                self.info.device_type == Printers.A1MINI or
                self.info.device_type == Printers.H2C or
                self.info.device_type == Printers.H2D or
                self.info.device_type == Printers.H2DPRO or
                self.info.device_type == Printers.H2S or
                self.info.device_type == Printers.P2S):
                return not self.print_fun.mqtt_signature_required
            return False
        elif feature == Features.AMS_SWITCH_COMMAND:
            if (self.info.device_type == Printers.A1 or
                self.info.device_type == Printers.A1MINI or
                self.info.device_type == Printers.H2C or
                self.info.device_type == Printers.H2D or
                self.info.device_type == Printers.H2DPRO or
                self.info.device_type == Printers.P2S or
                self.info.device_type == Printers.X1E):
                return True
            elif (self.info.device_type == Printers.P1S or
                  self.info.device_type == Printers.P1P):
                return self.supports_sw_version("01.02.99.10")
            elif (self.info.device_type == Printers.X1 or
                  self.info.device_type == Printers.X1C):
                return self.supports_sw_version("01.05.06.01")
            return False
        elif feature == Features.AMS_HUMIDITY:
            if (self.info.device_type == Printers.A1 or
                self.info.device_type == Printers.A1MINI):
                return self.supports_sw_version("01.06.10.33")
            elif (self.info.device_type == Printers.H2C or
                  self.info.device_type == Printers.H2D or
                  self.info.device_type == Printers.H2DPRO or
                  self.info.device_type == Printers.H2S or
                  self.info.device_type == Printers.P2S):
                return True
            elif (self.info.device_type == Printers.X1 or
                  self.info.device_type == Printers.X1C):
                return self.supports_sw_version("01.08.50.18")
            elif (self.info.device_type == Printers.P1S or
                  self.info.device_type == Printers.P1P):
                return self.supports_sw_version("01.07.50.18")
            return False
        elif feature == Features.AMS_DRYING:
            if (self.info.device_type == Printers.A1 or
                  self.info.device_type == Printers.A1MINI):
                return self.supports_sw_version("01.06.10.33")
            elif (self.info.device_type == Printers.H2C or
                self.info.device_type == Printers.H2D or
                self.info.device_type == Printers.H2DPRO or
                self.info.device_type == Printers.H2S or
                self.info.device_type == Printers.P2S):
                return True
            elif (self.info.device_type == Printers.X1 or
                  self.info.device_type == Printers.X1C):
                return self.supports_sw_version("01.08.50.18")
            elif (self.info.device_type == Printers.P1S or
                  self.info.device_type == Printers.P1P):
                return self.supports_sw_version("01.07.50.18")
            # This needs fixing now the A1 printers support the other AMS models.
            return False
        elif feature == Features.CHAMBER_LIGHT_2:
            return (self.info.device_type == Printers.H2C or
                    self.info.device_type == Printers.H2D or
                    self.info.device_type == Printers.H2DPRO or
                    self.info.device_type == Printers.H2S)
        elif feature == Features.DUAL_NOZZLES:
            return (self.info.device_type == Printers.H2C or
                    self.info.device_type == Printers.H2D or
                    self.info.device_type == Printers.H2DPRO)
        elif feature == Features.EXTRUDER_TOOL:
            return (self.info.device_type == Printers.H2C or
                    self.info.device_type == Printers.H2D or
                    self.info.device_type == Printers.H2DPRO or
                    self.info.device_type == Printers.H2S)
        elif feature == Features.MQTT_ENCRYPTION_FIRMWARE:
            if (self.info.device_type == Printers.A1 or
                self.info.device_type == Printers.A1MINI):
                return self.supports_sw_version("01.05.00.00")
            elif (self.info.device_type == Printers.H2D):
                return self.supports_sw_version("01.01.01.00")
            elif (self.info.device_type == Printers.H2DPRO):
                return self.supports_sw_version("01.01.01.00")
            elif (self.info.device_type == Printers.H2S or
                  self.info.device_type == Printers.P2S):
                return True
            elif (self.info.device_type == Printers.P1S or
                  self.info.device_type == Printers.P1P):
                return self.supports_sw_version("01.08.02.00")
            elif (self.info.device_type == Printers.X1 or 
                  self.info.device_type == Printers.X1C):
                return self.supports_sw_version("01.08.50.32")
            return False
        elif feature == Features.FIRE_ALARM_BUZZER:
            return (self.info.device_type == Printers.H2D or
                    self.info.device_type == Printers.H2DPRO or
                    self.info.device_type == Printers.H2S)
        elif feature == Features.HEATBED_LIGHT:
            return (self.info.device_type == Printers.H2C or
                    self.info.device_type == Printers.H2D or
                    self.info.device_type == Printers.H2DPRO or
                    self.info.device_type == Printers.H2S)
        elif feature == Features.SUPPORTS_EARLY_FTP_DOWNLOAD:
            return (self.info.device_type == Printers.A1 or
                    self.info.device_type == Printers.A1MINI or
                    self.info.device_type == Printers.P1P or
                    self.info.device_type == Printers.P1S)
        return False
    
    def supports_sw_version(self, version: str) -> bool:
        if compare_version(self.info.sw_ver, "99.0.0.0") >= 0:
            # This is an X1+ firmware version. Treat it as 01.08.02.00.
            return compare_version("01.08.02.00", version) >= 0
        return compare_version(self.info.sw_ver, version) >= 0
    
    @property
    def is_core_xy(self) -> bool:
        return (self.info.device_type != Printers.A1 and
                self.info.device_type != Printers.A1MINI)

@dataclass
class Lights:
    """Return all light related info"""
    chamber_light: str
    chamber_light2: str
    chamber_light_override: str
    chamber_light2_override: str
    heatbed_light: str
    work_light: str

    def __init__(self, client):
        self._client = client
        self.chamber_light = "unknown"
        self.chamber_light2 = "unknown"
        self.heatbed_light = "unknown"
        self.work_light = "unknown"
        self.chamber_light_override = ""
        self.chamber_light2_override = ""

    @property
    def is_chamber_light_on(self):
        return self.chamber_light == "on" or self.chamber_light2 == "on"

    @property
    def is_heatbed_light_on(self) -> bool | None:
        if self.heatbed_light == "unknown":
            return None
        return self.heatbed_light == "on"

    def print_update(self, data) -> bool:
        old_data = f"{self.__dict__}"

        # "lights_report": [
        #     {
        #         "node": "chamber_light",
        #         "mode": "on"
        #     },
        #     {
        #         "node": "work_light",  # X1 only
        #         "mode": "flashing"
        #     }
        # ],

        chamber_light = \
            search(data.get("lights_report", []), lambda x: x.get('node', "") == "chamber_light",
                   {"mode": self.chamber_light}).get("mode")
        if self.chamber_light_override != "":
            if self.chamber_light_override == chamber_light:
                self.chamber_light_override = ""
        else:
            self.chamber_light = chamber_light

        chamber_light2 = \
            search(data.get("lights_report", []), lambda x: x.get('node', "") == "chamber_light2",
                   {"mode": self.chamber_light2}).get("mode")
        if self.chamber_light2_override != "":
            if self.chamber_light2_override == chamber_light2:
                self.chamber_light2_override = ""
        else:
            self.chamber_light2 = chamber_light2

        self.work_light = \
            search(data.get("lights_report", []), lambda x: x.get('node', "") == "work_light",
                   {"mode": self.work_light}).get("mode")

        # Currently, the status of headbed light is not available (even switching it using printer UI shows an
        #   error in MQTT: "did not find the valid led: heatbed_light"). Therefore, it is initially in an unknown state.

        return (old_data != f"{self.__dict__}")

    def observe_system_command(self, data):
        # State can be inferred from system->command = ledctrl, but the initial state is still not known.
        # Even printer UI causes such a message to be sent as the "command execution result".
        if data.get("led_node") == "heatbed_light":
            self.heatbed_light = data.get("led_mode")
        # Should be replaced with proper reading in print_update once fixed in the actual firmware

    def TurnChamberLightOn(self):
        self.chamber_light = "on"
        self.chamber_light_override = "on"
        self._client.callback("event_light_update")
        self._client.publish(CHAMBER_LIGHT_ON)
        if self._client._device.supports_feature(Features.CHAMBER_LIGHT_2):
            self._client.publish(CHAMBER_LIGHT_2_ON)

    def TurnChamberLightOff(self):
        self.chamber_light = "off"
        self.chamber_light_override = "off"
        self._client.callback("event_light_update")
        self._client.publish(CHAMBER_LIGHT_OFF)
        if self._client._device.supports_feature(Features.CHAMBER_LIGHT_2):
            self._client.publish(CHAMBER_LIGHT_2_OFF)

    def TurnHeatbedLightOn(self):
        self.heatbed_light = "on"
        self._client.callback("event_light_update")
        self._client.publish(HEATBED_LIGHT_ON)

    def TurnHeatbedLightOff(self):
        self.heatbed_light = "off"
        self._client.callback("event_light_update")
        self._client.publish(HEATBED_LIGHT_OFF)


@dataclass
class Camera:
    """Return camera related info"""
    recording: str
    resolution: str
    rtsp_url: str
    timelapse: str
    _fired_camera_disabled_event: bool

    def __init__(self, client):
        self._client = client
        self.recording = ''
        self.resolution = ''
        self.rtsp_url = None
        self.timelapse = ''
        self._fired_camera_disabled_event = False

    def print_update(self, data) -> bool:
        old_data = f"{self.__dict__}"

        # "ipcam": {
        #   "ipcam_dev": "1",
        #   "ipcam_record": "enable",
        #   "mode_bits": 2,
        #   "resolution": "1080p",
        #   "rtsp_url": "rtsps://192.168.1.64/streaming/live/1",
        #   "timelapse": "disable",
        #   "tutk_server": "disable"
        # }

        self.timelapse = data.get("ipcam", {}).get("timelapse", self.timelapse)
        self.recording = data.get("ipcam", {}).get("ipcam_record", self.recording)
        self.resolution = data.get("ipcam", {}).get("resolution", self.resolution)
        self.rtsp_url = data.get("ipcam", {}).get("rtsp_url", self.rtsp_url)
        if self._client._enable_camera:
            if self.rtsp_url == "disable":
                if not self._fired_camera_disabled_event:
                    self._fired_camera_disabled_event = True
                    self._client.callback("event_printer_live_view_disabled")
        
        return (old_data != f"{self.__dict__}")

@dataclass
class Temperature:
    """Return all temperature related info"""
    bed_temp: int
    target_bed_temp: int
    chamber_temp: int
    nozzle_temps: dict
    nozzle_target_temps: dict

    def __init__(self, client):
        self._client = client
        self.bed_temp = 0
        self.target_bed_temp = 0
        self.chamber_temp = 0
        self.nozzle_temps = { 0: 0, 1: 0}
        self.target_nozzle_temps = { 0:0, 1: 0}

    @property
    def active_nozzle_temperature(self):
        active_nozzle = self._client._device.extruder.active_nozzle_index
        return self.nozzle_temps[active_nozzle]

    @property
    def active_nozzle_target_temperature(self):
        active_nozzle = self._client._device.extruder.active_nozzle_index
        return self.target_nozzle_temps[active_nozzle]

    @property
    def left_nozzle_temperature(self):
        return self.nozzle_temps[1]

    @property
    def left_nozzle_target_temperature(self):
        return self.target_nozzle_temps[1]

    @property
    def right_nozzle_temperature(self):
        return self.nozzle_temps[0]

    @property
    def right_nozzle_target_temperature(self):
        return self.target_nozzle_temps[0]

    def print_update(self, data) -> bool:
        old_data = f"{self.__dict__}"

        # New firmware puts bed temperature in two different places. Low word is current value. High word is the target.
        # "device": {
        #     "bed": {
        #       "info": {
        #         "temp": 6553700
        #       },
        #       "state": 2
        #     },
        #     "bed_temp": 6553700,
            
        bed_temp = data.get("device", {}).get("bed", {}).get("info", {}).get("temp", None)
        if bed_temp is not None:
            self.bed_temp = bed_temp & 0xFFFF
            self.target_bed_temp = (bed_temp >> 16) & 0xFFFF
        else:
            self.bed_temp = round(data.get("bed_temper", self.bed_temp))
            # Bambu Studio floors the value so match it.
            self.target_bed_temp = math.floor(data.get("bed_target_temper", self.target_bed_temp))

        # New firmware puts the chamber temperature in a different place.
        # "device": {
        #     "ctc": {
        #       "info": {
        #         "temp": 43
        #       },
        #       "state": 0
        #     },
        chamber_temp = data.get("device", {}).get("ctc", {}).get("info", {}).get("temp", None)
        if chamber_temp is not None:
            self.chamber_temp = chamber_temp & 0xFFFF
        else:
            self.chamber_temp = round(data.get("chamber_temper", self.chamber_temp))

        # H2D has two nozzles in the extruder data block.
        # "extruder": {
        #   "info": [
        #     {
        #       ...
        #       "id": 0,
        #       "snow": 259,    // bottom 4 bits is tray, remainder is ams index - not sure about ams HT 128+ though
        #       "temp": 14418140 // low word is current, high word is target
        #     },
        #     {
        #       ...
        #       "id": 1,
        #       "snow": 3,      // bottom 4 bits is tray, remainder is ams index - not sure about ams HT 128+ though
        #       "temp": 5767327  // low word is current, high word is target
        #     }
        #   ],
        #   "state": 2 // low 4 bits is count of extruders; active extruder is next 4 bits
        # },
        extruder_data = data.get("device", {}).get("extruder", {}).get("info")
        if extruder_data is not None:
            for entry in extruder_data:
                if entry.get("id") in (0, 1):
                    if "temp" in entry:
                        self.nozzle_temps[entry["id"]] = entry["temp"] & 0xFFFF
                        self.target_nozzle_temps[entry["id"]] = (entry["temp"] >> 16) & 0xFFFF
        else:
            self.nozzle_temps[0] = round(data.get("nozzle_temper", self.nozzle_temps[0]))
            self.target_nozzle_temps[0] = round(data.get("nozzle_target_temper", self.target_nozzle_temps[0]))

        return (old_data != f"{self.__dict__}")

    def set_target_temp(self, temp: TempEnum, temperature: int):
        command = set_temperature_to_gcode(temp, temperature)

        # if type == TempEnum.HEATBED:
        #     self.bed_temp = temperature
        # elif type == TempEnum.NOZZLE:
        #     self.nozzle_temp = temperature

        LOGGER.debug(command)
        self._client.publish(command)

        self._client.callback("event_printer_data_update")


@dataclass
class Fans:
    """Return all fan related info"""
    _aux_fan_speed_percentage: int
    _aux_fan_speed: int
    _aux_fan_speed_override: int
    _aux_fan_speed_override_time: datetime
    _chamber_fan_speed_percentage: int
    _chamber_fan_speed: int
    _chamber_fan_speed_override: int
    _chamber_fan_speed_override_time: datetime
    _cooling_fan_speed_percentage: int
    _cooling_fan_speed: int
    _cooling_fan_speed_override: int
    _cooling_fan_speed_override_time: datetime
    _heatbreak_fan_speed_percentage: int
    _heatbreak_fan_speed: int

    def __init__(self, client):
        self._client = client
        self._aux_fan_speed_percentage = 0
        self._aux_fan_speed = 0
        self._aux_fan_speed_override = 0
        self._aux_fan_speed_override_time = None
        self._chamber_fan_speed_percentage = 0
        self._chamber_fan_speed = 0
        self._chamber_fan_speed_override = 0
        self._chamber_fan_speed_override_time = None
        self._cooling_fan_speed_percentage = 0
        self._cooling_fan_speed = 0
        self._cooling_fan_speed_override = 0
        self._cooling_fan_speed_override_time = None
        self._heatbreak_fan_speed_percentage = 0
        self._heatbreak_fan_speed = 0

    def print_update(self, data) -> bool:
        old_data = f"{self.__dict__}"

        self._aux_fan_speed = data.get("big_fan1_speed", self._aux_fan_speed)
        self._aux_fan_speed_percentage = fan_percentage(self._aux_fan_speed)
        if self._aux_fan_speed_override_time is not None:
            delta = datetime.now() - self._aux_fan_speed_override_time
            if delta.seconds > 5:
                self._aux_fan_speed_override_time = None
        self._chamber_fan_speed = data.get("big_fan2_speed", self._chamber_fan_speed)
        self._chamber_fan_speed_percentage = fan_percentage(self._chamber_fan_speed)
        if self._chamber_fan_speed_override_time is not None:
            delta = datetime.now() - self._chamber_fan_speed_override_time
            if delta.seconds > 5:
                self._chamber_fan_speed_override_time = None
        self._cooling_fan_speed = data.get("cooling_fan_speed", self._cooling_fan_speed)
        self._cooling_fan_speed_percentage = fan_percentage(self._cooling_fan_speed)
        if self._cooling_fan_speed_override_time is not None:
            delta = datetime.now() - self._cooling_fan_speed_override_time
            if delta.seconds > 5:
                self._cooling_fan_speed_override_time = None
        self._heatbreak_fan_speed = data.get("heatbreak_fan_speed", self._heatbreak_fan_speed)
        self._heatbreak_fan_speed_percentage = fan_percentage(self._heatbreak_fan_speed)
        
        return (old_data != f"{self.__dict__}")

    def set_fan_speed(self, fan: FansEnum, percentage: int):
        """Set fan speed"""
        percentage = round(percentage / 10) * 10
        command = fan_percentage_to_gcode(fan, percentage)

        if fan == FansEnum.PART_COOLING:
            self._cooling_fan_speed = percentage
            self._cooling_fan_speed_override_time = datetime.now()
        elif fan == FansEnum.AUXILIARY:
            self._aux_fan_speed_override = percentage
            self._aux_fan_speed_override_time = datetime.now()
        elif fan == FansEnum.CHAMBER:
            self._chamber_fan_speed_override = percentage
            self._chamber_fan_speed_override_time = datetime.now()

        LOGGER.debug(command)
        self._client.publish(command)

        self._client.callback("event_printer_data_update")

    def get_fan_speed(self, fan: FansEnum) -> int:
        if fan == FansEnum.PART_COOLING:
            if self._cooling_fan_speed_override_time is not None:
                return self._cooling_fan_speed_override
            else:
                return self._cooling_fan_speed_percentage
        elif fan == FansEnum.AUXILIARY:
            if self._aux_fan_speed_override_time is not None:
                return self._aux_fan_speed_override
            else:
                return self._aux_fan_speed_percentage
        elif fan == FansEnum.CHAMBER:
            if self._chamber_fan_speed_override_time is not None:
                return self._chamber_fan_speed_override
            else:
                return self._chamber_fan_speed_percentage
        elif fan == FansEnum.HEATBREAK:
            return self._heatbreak_fan_speed_percentage


@dataclass
class Upgrade:
    """ Upgrade class """
    printer_name: str
    upgrade_progress: int
    new_version_state: int
    new_ver_list: list
    cur_version: str
    new_version: str

    def __init__(self, client):
        self._client = client
        self.printer_name = None
        self.upgrade_progress = 0
        self.new_version_state = 0
        self.new_ver_list = []
        self.cur_version = None
        self.new_version = None
    
    def release_url(self) -> str:
        """Return the release url"""
        device_mapping = {
            Printers.P1P: "p1",
            Printers.P1S: "p1",
            Printers.A1MINI: "a1-mini",
            Printers.A1: "a1",
            Printers.X1C: "x1",
            Printers.X1E: "x1e"
        }
        self.printer_name = device_mapping.get(self._client._device.info.device_type)
        if self.printer_name is None:
            return None
        return f"https://bambulab.com/en/support/firmware-download/{self.printer_name}"
    
    def install(self):
        """Install the update"""
        if self.printer_name is None:
            LOGGER.error("Printer name not found for firmware update.")
            return

        url = get_upgrade_url(self.printer_name)
        if url is not None:
            template = upgrade_template(url)
            if template is not None:
                LOGGER.debug(template)
                self._client.publish(template)
                self._client.callback("event_printer_data_update")
                
    def print_update(self, data) -> bool:
        """Update the upgrade state"""
        old_data = f"{self.__dict__}"
        
        # Example payload for P1 printer
        # "upgrade_state": {
        #   "sequence_id": 0,
        #   "progress": "100",
        #   "status": "UPGRADE_SUCCESS",
        #   "consistency_request": false,
        #   "dis_state": 1,
        #   "err_code": 0,
        #   "force_upgrade": false,
        #   "message": "0%, 0B/s",
        #   "module": "ota",
        #   "new_version_state": 1,
        #   "cur_state_code": 0,
        #   "new_ver_list": [
        #     {
        #       "name": "ota",
        #       "cur_ver": "01.06.01.02",
        #       "new_ver": "01.07.00.00",
        #       "cur_release_type": 3,
        #       "new_release_type": 3
        #     }
        #   ]
        # },
        #
        # Example payload for P1 printer with outstanding AMS firmware update:
        # "upgrade_state": {
        #   "sequence_id": 0,
        #   "progress": "100",
        #   "status": "UPGRADE_SUCCESS",
        #   "consistency_request": false,
        #   "dis_state": 1,
        #   "err_code": 0,
        #   "force_upgrade": false,
        #   "message": "0%, 0B/s",
        #   "module": "ota",
        #   "new_version_state": 1,
        #   "cur_state_code": 0,
        #   "idx2": 2118490042,
        #   "new_ver_list": [
        #     {
        #       "name": "ams/0",
        #       "cur_ver": "00.00.06.44",
        #       "new_ver": "00.00.06.49",
        #       "cur_release_type": 0,
        #       "new_release_type": 1
        #      }
        #   ]
        # },
        #
        # Example payload for X1 printer
        # "upgrade_state": {
        #   "ahb_new_version_number": "",
        #   "ams_new_version_number": "",
        #   "consistency_request": false,
        #   "dis_state": 3,
        #   "err_code": 0,
        #   "ext_new_version_number": "",
        #   "force_upgrade": false,
        #   "idx": 4,
        #   "idx1": 3,
        #   "message": "RK1126 start write flash success",
        #   "module": "",
        #   "new_version_state": 1,
        #   "ota_new_version_number": "01.08.02.00",
        #   "progress": "100",
        #   "sequence_id": 0,
        #   "sn": "**REDACTED**",
        #   "status": "UPGRADE_SUCCESS"
        # },
        
        # Cross-validation on the remaining series is required. 
        # Data values ​​for the upgrade_state dictionary
        state = data.get("upgrade_state", None)
        if state is not None:
            try:
                self.upgrade_progress = int(state.get("progress", self.upgrade_progress))
            except ValueError:
                # Prevents unexpected "" strings from being empty.
                self.upgrade_progress = 0
            self.new_version_state = state.get("new_version_state", self.new_version_state)
            self.cur_version = self._client._device.info.sw_ver
            self.new_version = self._client._device.info.sw_ver
            self.new_ver_list = state.get("new_ver_list", self.new_ver_list)
            if self.new_version_state == 1:
                if len(self.new_ver_list) > 0:
                    ota_info = next(filter(
                        lambda x: x["name"] == "ota", self.new_ver_list
                    ), {})
                    if ota_info:
                        self.cur_version = ota_info["cur_ver"]
                        self.new_version = ota_info["new_ver"]
                    if self.upgrade_progress == 100 and state.get("message") == "0%, 0B/s":
                        self.upgrade_progress = 0
                elif state.get("ota_new_version_number", None) != None:
                    self.new_version = state.get("ota_new_version_number")
                    if self.upgrade_progress == 100 and state.get("message") == "RK1126 start write flash success":
                        self.upgrade_progress = 0
                else:
                    LOGGER.error(f"Unable to interpret {state}")
            
        return (old_data != f"{self.__dict__}")


@dataclass
class PrintJob:
    """Return all information related content"""

    print_percentage: int
    gcode_state: str
    file_type_icon: str
    gcode_file: str
    gcode_file_downloaded: str
    subtask_name: str
    start_time: datetime
    end_time: datetime
    remaining_time: int
    current_layer: int
    total_layers: int
    print_error: int
    print_weight: float
    print_length: int
    print_bed_type: str
    print_type: str
    _ams_print_weights: float
    _ams_print_lengths: float
    _skipped_objects: list
    _printable_objects: dict
    _gcode_file_prepare_percent: int
    _loaded_model_data: bool
    _ftpRunAgain: bool
    _ftpThread: threading.Thread
    _ftp_download_percentage: int

    def __init__(self, client):
        self._client = client
        self.print_percentage = 0
        self.gcode_state = "unknown"
        self.gcode_file = ""
        self.gcode_file_downloaded = ""
        self.subtask_name = ""
        self.start_time = None
        self.end_time = None
        self.remaining_time = 0
        self.current_layer = 0
        self.total_layers = 0
        self.print_error = 0
        self.print_weight = 0
        self.ams_mapping = []
        self._ams_print_weights = [0.0] * 136 # TODO: Convert to a dict in the future?
        self._ams_print_lengths = [0.0] * 136 # TODO: Convert to a dict in the future?
        self.print_length = 0
        self.print_bed_type = "unknown"
        self.file_type_icon = "mdi:file"
        self.print_type = ""
        self._printable_objects = {}
        self._skipped_objects = []
        self._gcode_file_prepare_percent = -1
        self._loaded_model_data = False
        self._ftpRunAgain = False
        self._ftpThread = None
        self._ftp_download_percentage = 100

    @property
    def model_download_percentage(self) -> int:
        return self._ftp_download_percentage

    @property
    def get_printable_objects(self) -> json:
        return self._printable_objects

    @property
    def get_skipped_objects(self) -> str:
        return self._skipped_objects
    
    @property
    def get_print_weights(self) -> dict:
        values = {}
        if self._client._device.external_spool[0].active:
            values["External Spool"] = self.print_weight
        elif self._client._device.external_spool[1].active:
            values["External Spool 2"] = self.print_weight
        else:
            for i in range(16):
                if self._ams_print_weights[i] != 0:
                    ams_index = (i // 4) + 1
                    ams_tray = (i % 4) + 1
                    values[f"AMS {ams_index} Tray {ams_tray}"] = self._ams_print_weights[i]
        return values

    @property
    def get_print_lengths(self) -> dict:
        values = {}
        if self._client._device.external_spool[0].active:
            values["External Spool"] = self.print_length
        elif self._client._device.external_spool[1].active:
            values["External Spool 2"] = self.print_length
        else:
            for i in range(16):
                if self._ams_print_lengths[i] != 0:
                    ams_index = (i // 4) + 1
                    ams_tray = (i % 4) + 1
                    values[f"AMS {ams_index} Tray {ams_tray}"] = self._ams_print_lengths[i]
        return values

    def print_update(self, data) -> bool:
        old_data = f"{self.__dict__}"

        # Example payload:
        # {
        #     "print": {
        #         "gcode_start_time": "1681479206",
        #         "gcode_state": "IDLE",
        #         "mc_print_stage": "1",
        #         "mc_percent": 100,
        #         "mc_remaining_time": 0,
        #         "wifi_signal": "-53dBm",
        #         "print_type": "idle",
        #         "ipcam": {
        #             "ipcam_dev": "1",
        #             "ipcam_record": "enable"
        #             "resolution": "1080p",        # X1 only
        #             "timelapse": "disable"
        #         },
        #         "layer_num": 0,
        #         "total_layer_num": 0,

        self.print_percentage = data.get("mc_percent", self.print_percentage)
        previous_gcode_state = self.gcode_state
        self.gcode_state = data.get("gcode_state", self.gcode_state)
        if self.gcode_state.lower() not in GCODE_STATE_OPTIONS:
            if self.gcode_state != '':
                LOGGER.error(f"Unknown gcode_state. Please log an issue : '{self.gcode_state}'")
            self.gcode_state = "unknown"
        if previous_gcode_state != self.gcode_state:
            LOGGER.debug(f"GCODE_STATE: {previous_gcode_state} -> {self.gcode_state}")
        old_gcode_file = self.gcode_file
        self.gcode_file = data.get("gcode_file", self.gcode_file)
        if old_gcode_file != self.gcode_file:
            LOGGER.debug(f"GCODE_FILE: {self.gcode_file}")
        self.print_type = data.get("print_type", self.print_type)
        if self.print_type.lower() not in PRINT_TYPE_OPTIONS:
            if self.print_type != "":
                LOGGER.debug(f"Unknown print_type. Please log an issue : '{self.print_type}'")
            self.print_type = "unknown"
        old_subtask_name = self.subtask_name
        self.subtask_name = data.get("subtask_name", self.subtask_name)
        if old_subtask_name != self.subtask_name:
            LOGGER.debug(f"SUBTASK_NAME: {self.subtask_name}")
        self.file_type_icon = "mdi:file" if self.print_type != "cloud" else "mdi:cloud-outline"
        self.current_layer = data.get("layer_num", self.current_layer)
        self.total_layers = data.get("total_layer_num", self.total_layers)
        self.ams_mapping = data.get("ams_mapping", self.ams_mapping)
        self._skipped_objects = data.get("s_obj", self._skipped_objects)

        # Initialize task data at startup.
        if previous_gcode_state == "unknown" and self.gcode_state != "unknown":
            self._update_task_data()
            self._download_timelapse()

        # Generate the end_time from the remaining_time mqtt payload value if present.
        if data.get("mc_remaining_time") is not None:
            existing_remaining_time = self.remaining_time
            self.remaining_time = data.get("mc_remaining_time")
            if existing_remaining_time != self.remaining_time:
                end_time = get_end_time(self.remaining_time)
                if end_time != self.end_time:
                    self.end_time = end_time
                    LOGGER.debug(f"END TIME2: {self.end_time}")

        # Handle print start
        previously_idle = previous_gcode_state == "IDLE" or previous_gcode_state == "FAILED" or previous_gcode_state == "FINISH"
        currently_idle = self.gcode_state == "IDLE" or self.gcode_state == "FAILED" or self.gcode_state == "FINISH"

        if previously_idle and not currently_idle:
            self._client.callback("event_print_started")

            # Sometimes the download completes so fast we go from a prior print's 100% to 100% for the new print in one update.
            # Make sure we catch that case too. And Lan Mode never sets this - make sure we init it to 0.
            self._gcode_file_prepare_percent = 0

            # Clear existing cover & pick image data before attempting any fresh download.
            self._clear_model_data()

            # Generate the start_time when printer moves from idle to another state. Original attempt with remaining time
            # becoming non-zero didn't work as it never bounced to zero in at least the scenario where a print was canceled.
            # We can use the existing get_end_time helper to format date.now() as desired by passing 0.
            self.start_time = get_end_time(0)
            # Make sure we don't keep using a stale end time.
            self.end_time = None
            LOGGER.debug(f"GENERATED START TIME: {self.start_time}")

            if not self._client.ftp_enabled:
                # We can update task data from the cloud immediately. But ftp has to wait.
                self._update_task_data()

        old_gcode_file_prepare_percent = self._gcode_file_prepare_percent
        self._gcode_file_prepare_percent = int(data.get("gcode_file_prepare_percent", str(self._gcode_file_prepare_percent)))
        if self.gcode_state == "PREPARE":
            LOGGER.debug(f"DOWNLOAD PERCENTAGE: {old_gcode_file_prepare_percent} -> {self._gcode_file_prepare_percent}")

        # If we are FTP enabled and we haven't yet downloaded the model data, see if we can now.
        if not self._loaded_model_data:
            if self._client._device.supports_feature(Features.SUPPORTS_EARLY_FTP_DOWNLOAD):
                if self.gcode_state == "PREPARE" and \
                    old_gcode_file_prepare_percent > 0 and \
                    old_gcode_file_prepare_percent != self._gcode_file_prepare_percent and \
                    self._gcode_file_prepare_percent >= 99:

                    # P1 sometimes only gets to 99% download and never reaches 100% so we treat 99% as complete.

                    # Now we can update the model data by ftp. By this point the model has been successfully loaded to the printer.
                    # and it's network stack is idle and shouldn't timeout or fail on us randomly.
                    LOGGER.debug(f"DOWNLOAD TO PRINTER IS COMPLETE")
                    self._update_task_data()

            if self.gcode_state == "RUNNING" and (previously_idle or previous_gcode_state == "PREPARE"):
                # We haven't yet downloaded model data off the printer. I've observed three scenarios where this happens:
                # 1. This is a lan mode print where the gcode was pushed to the printer before the print ever started so
                # 2. On the P1 I've observed a bug where the download completes but the gcode_file_prepare_percent never reaches 100.
                # If we transition to the running gcode_state without observing 100% we assume the download did actually complete.
                # 3. On the X1C for a local Bambu Studio slice sent via the cloud we see the download percentage immediately
                # jump to 100% at the same time we see the PREPARE phase start but if we try and download then, the model file
                # is not present.
                LOGGER.debug("REACHED RUNNING WITHOUT DOWNLOADING MODEL")
                self._update_task_data()

        # When a print is canceled by the user, this is the payload that's sent. A couple of seconds later
        # print_error will be reset to zero.
        # {
        #     "print": {
        #         "print_error": 50348044,
        #     }
        # }
        timelapseDownloaded = False
        isCanceledPrint = False
        if data.get("print_error") == 50348044 and self.print_error == 0:
            isCanceledPrint = True
            self._download_timelapse()
            timelapseDownloaded = True
            self._client.callback("event_print_canceled")
        self.print_error = data.get("print_error", self.print_error)

        # Handle print failed
        if previous_gcode_state != "unknown" and previous_gcode_state != "FAILED" and self.gcode_state == "FAILED":
            if not isCanceledPrint:
                self._client.callback("event_print_failed")
                if not timelapseDownloaded:
                    self._download_timelapse()
                    timelapseDownloaded = True

        # Handle print finish
        if previous_gcode_state != "unknown" and previous_gcode_state != "FINISH" and self.gcode_state == "FINISH":
            if not timelapseDownloaded:
                self._download_timelapse()
                timelapseDownloaded = True
            self._client.callback("event_print_finished")

        if currently_idle and not previously_idle and previous_gcode_state != "unknown":
            if self.start_time != None:
                # self.end_time isn't updated if we hit an AMS retract at print end but the printer does count that entire
                # paused time as usage hours. So we need to use the current time instead of the last recorded end time in
                # our calculation here.
                duration = get_end_time(0) - self.start_time
                # Round usage hours to 2 decimal places (about 1/2 a minute accuracy)
                new_hours = round((duration.seconds / 60 / 60) * 100) / 100
                LOGGER.debug(f"NEW USAGE HOURS: {new_hours}")
                self._client._device.info.usage_hours += new_hours

        return (old_data != f"{self.__dict__}")

    # FTP implementation differences between P1 and X1 printers:
    # - X1 includes the path in the returned filenames for the NLST command
    # - P1 just returns the bare filename
    #
    # Known filepath configurations:
    # 
    # X1 lan mode print
    #   Orca 2.2.0 'print' of 3mf file
    #     "gcode_file": "/data/Metadata/plate_1.gcode",
    #     "subtask_name": "Clamshell Parts Box",
    #     FILE: /Clamshell Parts Box.gcode.3mf
    #
    # P1 lan mode print:
    #   Bambu Studio 'print' of 3mf file
    #     "gcode_file": "36mm.gcode.3mf",
    #     "subtask_name": "36mm",
    #     FILE: /36mm.gcode.3mf
    #
    # X1C cloud print:
    #   Bambu Studio 'print' of unsaved workspace
    #     gcode_filename = data/metadata/plate_1.gcode (ramdisk - not accessible via ftp)
    #     subtask_name = FILENAME
    #     FILE: /cache/FILENAME.3mf
    #
    # P1 cloud print:
    #   Bambu Studio 'print' of unsaved workspace
    #     gcode_filename = Cube + Cube + Cube + Cube + Cube.3mf
    #     subtask_name = Cube + Cube + Cube + Cube + Cube
    #     FILE: /cache/Cube + Cube + Cube + Cube + Cube.3mf
    #
    # X1 cloud print:
    #   Makerworld print
    #     gcode_filename = /data/metadata/plate_3.gcode
    #     subtask_name = Lovers Valentine Day Shadowbox
    #     FILE: /cache/Lovers Valentine Day Shadowbox.3mf
    # 
    # P1 cloud print:
    #   Makerworld print
    #     gcode_filename = Lovers Valentine Day Shadowbox.3mf
    #     subtask_name = Lovers Valentine Day Shadowbox
    #     FILE: /cache/Lovers Valentine Day Shadowbox.3mf
    # 

    ftp_search_paths = ['/cache/', '/']
    def _attempt_ftp_download_of_file(self, ftp, file_path, progress_callback=None):
        if 'Metadata' in file_path:
            # This is a ram drive on the X1 and is not accessible via FTP
            return None

        try:
            LOGGER.debug(f"Looking for '{file_path}'")
            size = ftp.size(file_path)
            LOGGER.debug(f"File exists. Size: {size} bytes.")
            
            relative_path = file_path.lstrip('/')
            cache_dir = os.path.join(self._client.cache_path, "prints")
            cache_file_path = os.path.join(cache_dir, relative_path)

            # Ensure the directory exists
            os.makedirs(os.path.dirname(cache_file_path), exist_ok=True)

            # Check if file already exists in cache with same size
            try:
                cache_file_size = os.path.getsize(cache_file_path)
                if cache_file_size == size:
                    LOGGER.debug(f"File already in cache with same size.")
                    # Update last edited time to refresh it's cache lifetime.
                    os.utime(cache_file_path, None)
                    return cache_file_path
            except FileNotFoundError:
                # File doesn't exist in the cache.
                pass

            # Download to cache with progress tracking
            total_downloaded = 0
            start_time = time.time()
            last_log_percentage = 0

            self._ftp_download_percentage = 0
            def download_progress_callback(data):
                nonlocal total_downloaded, last_log_percentage
                try:
                    total_downloaded += len(data)
                    percentage = int((total_downloaded / size) * 100)
                    
                    # Only log every 10 seconds
                    current_time = time.time()
                    if last_log_percentage != percentage:
                        LOGGER.debug(f"FTP download progress: {percentage:.0f}% ({total_downloaded//1024}/{size//1024} KB)")
                        self._ftp_download_percentage = int(percentage)
                        last_log_percentage = percentage
                        self._client.callback("event_printer_data_update")
                    
                    if progress_callback:
                        progress_callback(percentage)
                except Exception as e:
                    LOGGER.debug(f"Error in progress callback: {e}")
                    # Don't let progress callback errors break the download

            with open(cache_file_path, 'wb') as f:
                # Create a wrapper function that combines file writing and progress tracking
                def write_with_progress(data):
                    f.write(data)
                    download_progress_callback(data)
                
                ftp.retrbinary(f"RETR {file_path}", write_with_progress)
                f.flush()
            
            # Calculate download statistics
            self._ftp_download_percentage = 100
            end_time = time.time()
            download_time = end_time - start_time
            download_speed = size / download_time if download_time > 0 else 0
            
            LOGGER.debug(f"Successfully downloaded '{file_path}' to cache. Time: {download_time:.0f}s, Speed: {download_speed/1024:.0f} KB/s")
            return cache_file_path
                    
        except ftplib.error_perm as e:
             if '550' not in str(e.args): # 550 is unavailable.
                 LOGGER.debug(f"Failed to download model at '{file_path}': {e}")
        except Exception as e:
            LOGGER.debug(f"Unexpected exception at '{file_path}': {type(e)} Args: {e}")
            # Optionally add retry logic here
            pass
        return None

    def _attempt_ftp_download_of_file_from_search_path(self, ftp, filename):
        for path in self.ftp_search_paths:
            file_path = f"{path}{filename.lstrip('/')}"
            result = self._attempt_ftp_download_of_file(ftp, file_path)
            if result is not None:
                return result
        return None

    def _attempt_ftp_download(self, ftp) -> Union[str, None]:

        filenames_to_try = []

        # First test if the subtaskname exists as a 3mf
        if self.subtask_name != '':
            if self.subtask_name.endswith('.3mf'):
                filenames_to_try.append(self.subtask_name)
            else:
                filenames_to_try.append(f"{self.subtask_name}.3mf")
                filenames_to_try.append(f"{self.subtask_name}.gcode.3mf")


        # If we didn't find it then try the gcode file
        if (self.gcode_file != '') and (self.subtask_name != self.gcode_file):
            if self.gcode_file.endswith('.3mf'):
                filenames_to_try.append(self.gcode_file)
            else:
                filenames_to_try.append(f"{self.gcode_file}.3mf")
                filenames_to_try.append(f"{self.gcode_file}.gcode.3mf")

        # Try each candidate filename in order
        for filename in filenames_to_try:
            model_file = self._attempt_ftp_download_of_file_from_search_path(ftp, filename=filename)
            if model_file is not None:
                return model_file

        if self.subtask_name == "":
            # Fall back to find the latest file by timestamp but only if we don't have a subtask name set - printer must have been rebooted.
            LOGGER.debug("Falling back to searching for latest 3mf file.")
            model_path = self._find_latest_file(ftp, self.ftp_search_paths, ['.3mf'])
            if model_path is not None:
                model_file_path = self._attempt_ftp_download_of_file(ftp, model_path)
                return model_file_path

        return None
    
    def _find_latest_file(self, ftp, search_paths, extensions: list):
        # Look for the newest file with extension in directory.
        file_list = []
        def parse_line(path: str, line: str):
            # Match the line format: '-rw-rw-rw- 1 user group 1234 Jan 01 12:34 filename'
            pattern_with_time_no_year      = r'^\S+\s+\d+\s+\S+\s+\S+\s+\d+\s+(\S+\s+\d+\s+\d+:\d+)\s+(.+)$'
            # Match the line format: '-rw-rw-rw- 1 user group 1234 Jan 01 2024 filename'
            pattern_without_time_just_year = r'^\S+\s+\d+\s+\S+\s+\S+\s+\d+\s+(\S+\s+\d+\s+\d+)\s+(.+)$'
            match = re.match(pattern_with_time_no_year, line)
            if match:
                timestamp_str, filename = match.groups()
                _, extension = os.path.splitext(filename)
                if extension in extensions:
                    # Since these dates don't have the year we have to work it out. If the date is earlier in 
                    # the year than now then it's this year. If it's later it's last year.
                    timestamp = datetime.strptime(timestamp_str, '%b %d %H:%M')
                    timestamp = timestamp.replace(tzinfo=timezone.utc)
                    utc_time_now = datetime.now().astimezone(timezone.utc)
                    timestamp = timestamp.replace(year=utc_time_now.year)
                    if timestamp > utc_time_now:
                        timestamp = timestamp.replace(year=datetime.now().year - 1)
                    return timestamp, f"{path}/{filename}" if path != '/' else f"/{filename}"
                else:
                    return None

            match = re.match(pattern_without_time_just_year, line)
            if match:
                timestamp_str, filename = match.groups()
                _, extension = os.path.splitext(filename)
                if extension in extensions:
                    timestamp = datetime.strptime(timestamp_str, '%b %d %Y')
                    timestamp = timestamp.replace(tzinfo=timezone.utc)
                    return timestamp, f"{path}/{filename}" if path != '/' else f"/{filename}"
                else:
                    return None
            
            LOGGER.debug(f"UNEXPECTED LIST LINE FORMAT: '{line}'")
            return None

        # Attempt to find the model in one of many known directories
        for path in search_paths:
            try:
                LOGGER.debug(f"Looking for latest {extensions} file in {path}")
                ftp.retrlines(f"LIST {path}", lambda line: file_list.append(file) if (file := parse_line(path, line)) is not None else None)
                LOGGER.debug(f"Completed FTP list for {path}")
            except Exception as e:
                LOGGER.error(f"FTP list Exception. Type: {type(e)} Args: {e}")
                pass

        files = sorted(file_list, key=lambda file: file[0], reverse=True)
        for file in files:
            for extension in extensions:
                if file[1].endswith(extension):
                    if extension in extensions:
                        LOGGER.debug(f"Found latest file {file[1]} with timestamp {file[0]}")
                        return file[1]

        return None
    
    def prune_print_history_files(self):
        if self._client._test_mode:
            return
        cache_file_path = os.path.join(self._client.cache_path, "prints")
        self._prune_old_files(directory=cache_file_path,
                              extensions=['.3mf'],
                              keep=self._client._print_cache_count,
                              extra_extensions=['.jpg', '.png', '.slice_info.config', '.gcode'])

    def prune_timelapse_files(self):
        if self._client._test_mode:
            return
        LOGGER.debug("Pruning timelapse history")
        cache_file_path = os.path.join(self._client.cache_path, "timelapse")
        self._prune_old_files(directory=cache_file_path,
                              extensions=['.mp4','.avi'],
                              keep=self._client._timelapse_cache_count,
                              extra_extensions=['.jpg', '.png'])
            
    def _prune_old_files(self, directory: str, extensions: List[str], keep: int, extra_extensions=[]):

        if keep == -1:
            # Cache pruning is disabled.
            LOGGER.debug("Skipping as pruning is disabled.")
            return

        dir_path = Path(directory)
        if not dir_path.is_dir():
            return
        
        LOGGER.debug(f"{dir_path}")
        
        # Get list of files matching the provided list of extensions
        matching_files = [
            f for f in dir_path.rglob('*')            
            if f.is_file() and f.suffix in extensions
        ]
        
        # Sort files by last modification time, newest first
        matching_files.sort(key=lambda x: os.path.getmtime(x), reverse=True)

        # Files to delete: those beyond the 'keep' most recent
        old_files = matching_files[keep:]

        LOGGER.debug(f"Keeping {keep} files. Deleting {len(old_files)} files.")
        
        for primary_file in old_files:
            try:
                os.remove(primary_file )
                LOGGER.debug(f"Deleted: {primary_file }")
            except Exception as e:
                LOGGER.error(f"Failed to delete {primary_file}: {e}")
                continue

            # Get base name without extension
            base_name = os.path.splitext(primary_file)[0]

            # Delete associated files with alternate extensions
            for ext in extra_extensions:
                assoc_file = base_name + ext
                if os.path.exists(assoc_file):
                    try:
                        os.remove(assoc_file)
                        LOGGER.debug(f"Deleted associated: {assoc_file}")
                    except Exception as e:
                        LOGGER.error(f"Failed to delete associated {assoc_file}: {e}")
    
    def _download_timelapse(self):
        # If we are running in connection test mode, skip updating the last print task data.
        if self._client._test_mode:
            return
        if not self._client.ftp_enabled:
            return
        if self._client._timelapse_cache_count == 0:
            return
        thread = threading.Thread(target=self._async_download_timelapse)
        thread.start()
        
    def _async_download_timelapse(self):
        current_thread = threading.current_thread()
        current_thread.setName(f"{self._client._device.info.device_type}-FTP-{threading.get_native_id()}")
        start_time = datetime.now()
        LOGGER.debug(f"Downloading latest timelapse by FTP")

        # Open the FTP connection
        ftp = self._client.ftp_connection()
        video_extensions = ['.mp4','.avi']
        file_path = self._find_latest_file(ftp, ['/timelapse'], video_extensions)
        if file_path is not None:
            # timelapse_path is of form '/timelapse/foo.mp4'
            local_file_path = os.path.join(self._client.cache_path, file_path.lstrip('/'))
            directory_path = os.path.dirname(local_file_path)
            os.makedirs(directory_path, exist_ok=True)

            try:
                # Get the file size from FTP
                size = ftp.size(file_path)
                LOGGER.debug(f"Timelapse file exists. Size: {size} bytes.")
                
                # Check if file already exists with same size
                should_download = False
                if os.path.exists(local_file_path):
                    local_file_size = os.path.getsize(local_file_path)
                    if local_file_size == size:
                        LOGGER.debug(f"Timelapse file found in cache.")
                    else:
                        LOGGER.debug(f"Timelapse file size differs (local: {local_file_size}, remote: {size}). Re-downloading.")
                        should_download = True
                else:
                    LOGGER.debug(f"Timelapse file doesn't exist locally. Downloading.")
                    should_download = True
                
                if should_download:
                    # Download video
                    with open(local_file_path, 'wb') as f:
                        LOGGER.debug(f"Downloading '{file_path}'")
                        ftp.retrbinary(f"RETR {file_path}", f.write)
                        f.flush()
                    
                    # Download thumbnail
                    filename = os.path.basename(file_path)
                    filename_without_extension, _ = os.path.splitext(filename)
                    thumbnail_filename = f"{filename_without_extension}.jpg"
                    thumbnail_path = os.path.join(os.path.dirname(file_path), 'thumbnail', thumbnail_filename)
                    thumbnail_local_path = os.path.join(os.path.dirname(local_file_path), thumbnail_filename)
                    with open(thumbnail_local_path, 'wb') as f:
                        LOGGER.info(f"Downloading '{thumbnail_path}'")
                        ftp.retrbinary(f"RETR {thumbnail_path}", f.write)
                        f.flush()
                    
            except ftplib.error_perm as e:
                if '550' not in str(e.args): # 550 is unavailable.
                    LOGGER.debug(f"Failed to download timelapse at '{file_path}': {e}")
            except Exception as e:
                LOGGER.debug(f"Unexpected exception downloading timelapse at '{file_path}': {type(e)} Args: {e}")

        ftp.quit()

        end_time = datetime.now()

        self.prune_timelapse_files()

        LOGGER.debug(f"Done downloading timelapse by FTP. Elapsed time = {(end_time-start_time).seconds}s") 

    def _update_task_data(self):
        self._loaded_model_data = True

        # If we are running in connection test mode, skip updating the last print task data.
        if self._client._test_mode:
            return
        
        self._download_task_data_from_cloud()
        if self._client.ftp_enabled:
            self._download_task_data_from_printer()

    def _download_task_data_from_printer(self):
        if self._ftpThread is None:
            # Only start a new thread if there
            LOGGER.debug("Starting FTP thread.")
            self._ftpThread = threading.Thread(target=self._async_download_task_data_from_printer)
            self._ftpThread.start()
        else:
            LOGGER.debug("FTP thread already running.")
            self._ftpRunAgain = True

    def _clear_model_data(self):
        LOGGER.debug("Clearing model data")
        self._loaded_model_data = False
        self._client._device.cover_image.set_image(None)
        self._clear_pick_data()

    def _clear_pick_data(self):
        LOGGER.debug("Clearing pick data")
        self._client._device.pick_image.set_image(None)
        self._printable_objects = {}

    def _async_download_task_data_from_printer(self):
        current_thread = threading.current_thread()
        current_thread.setName(f"{self._client._device.info.device_type}-FTP-{threading.get_native_id()}")
        LOGGER.debug(f"FTP thread starting.")

        try:
            while True:
                self._ftpRunAgain = False
                start_time = datetime.now()
                self._async_download_task_data_from_printer_worker()
                if not self._ftpRunAgain:
                    break
                end_time = datetime.now()
                LOGGER.debug("FTP thread re-running. Elapsed time = {(end_time-start_time).seconds}s")
        except Exception as e:
            LOGGER.error(f"FTP thread failed with exception {e}")

        end_time = datetime.now()
        LOGGER.info(f"FTP thread exiting. Elapsed time = {(end_time-start_time).seconds}s")
        self._ftpThread = None

    def _async_download_task_data_from_printer_worker(self):
        # Open the FTP connection
        ftp = self._client.ftp_connection()

        for i in range(1,13):
            model_file_path = self._attempt_ftp_download(ftp)
            if model_file_path is not None:
                break

            if not self._client._device.supports_feature(Features.SUPPORTS_EARLY_FTP_DOWNLOAD):
                # The X1 has a weird behavior where the downloaded file doesn't exist for several seconds into the RUNNING phase and even
                # then it is still being downloaded in place so we might try to grab it mid-download and get a corrupt file. Try 13 times
                # 5 seconds apart over 60s.
                if i != 12:
                    LOGGER.debug(f"Sleeping 5s for X1/H2/P2 retry")
                    time.sleep(5)
                    LOGGER.debug(f"Try #{i+1} for X1/H2/P2")
            else:
                break

        ftp.quit()

        if model_file_path is None:
            LOGGER.debug("No model file found.")
            return

        result = False
        
        try:
            LOGGER.debug(f"File size is {os.path.getsize(model_file_path)} bytes")

            model_dir = os.path.dirname(model_file_path)

            # Open the 3mf zip archive
            with ZipFile(model_file_path) as archive:
                # Extract the slicer XML config and parse the plate tree
                plate = ElementTree.fromstring(archive.read('Metadata/slice_info.config')).find('plate')
                
                # Iterate through each config element and extract the data
                # Example contents:
                # {'key': 'index', 'value': '2'}
                # {'key': 'printer_model_id', 'value': 'C12'}
                # {'key': 'nozzle_diameters', 'value': '0.4'}
                # {'key': 'timelapse_type', 'value': '0'}
                # {'key': 'prediction', 'value': '5935'}
                # {'key': 'weight', 'value': '20.91'}
                # {'key': 'outside', 'value': 'false'}
                # {'key': 'support_used', 'value': 'false'}
                # {'key': 'label_object_enabled', 'value': 'true'}
                # {'identify_id': '123', 'name': 'ModelObjectOne.stl', 'skipped': 'false'}
                # {'identify_id': '394', 'name': 'ModelObjectTwo.stl', 'skipped': 'false'}
                # {'id': '1', 'tray_info_idx': 'GFA01', 'type': 'PLA', 'color': '#000000', 'used_m': '5.45', 'used_g': '17.32'}
                # {'id': '2', 'tray_info_idx': 'GFA01', 'type': 'PLA', 'color': '#8D8C8F', 'used_m': '0.84', 'used_g': '2.66'}
                # {'id': '3', 'tray_info_idx': 'GFA01', 'type': 'PLA', 'color': '#FFFFFF', 'used_m': '0.29', 'used_g': '0.93'}
                
                # Start a total print length count to be compiled from each filament
                print_length = 0
                plate_number = None
                _printable_objects = {}
                filament_count = len(self.ams_mapping)
                plate_filament_count = len(plate.findall('filament'))

                # Reset filament data
                self._ams_print_weights = [0.0] * 136 # TODO: Convert to a dict in the future?
                self._ams_print_lengths = [0.0] * 136 # TODO: Convert to a dict in the future?

                for metadata in plate:
                    if (metadata.get('key') == 'index'):
                        # Index is the plate number being printed
                        plate_number = metadata.get('value')
                        LOGGER.debug(f"Plate: {plate_number}")
                        
                        # Now we have the plate number, extract the cover image from the archive
                        self._client._device.cover_image.set_image(archive.read(f"Metadata/plate_{plate_number}.png"))
                        LOGGER.debug(f"Cover image: Metadata/plate_{plate_number}.png")

                        # Save the cover image to the cache
                        try:
                            # Save the cover image directly to the cache
                            cover_filename = os.path.splitext(os.path.basename(model_file_path))[0] + '.png'
                            cover_path = os.path.join(model_dir, cover_filename)
                            with archive.open(f"Metadata/plate_{plate_number}.png") as cover_entry, open(cover_path, "wb") as target_path:
                                shutil.copyfileobj(cover_entry, target_path)
                            LOGGER.debug(f"Cover image saved to: {cover_path}")
                        except Exception as e:
                            LOGGER.error(f"Failed to save cover image: {e}")

                        try:
                            # Save the gcode file to the cache
                            gcode_filename = os.path.splitext(os.path.basename(model_file_path))[0] + '.gcode'
                            gcode_path = os.path.join(model_dir, gcode_filename)
                            with archive.open(f"Metadata/plate_{plate_number}.gcode") as gcode_entry, open(gcode_path, "wb") as target_path:
                                shutil.copyfileobj(gcode_entry, target_path)
                                self.gcode_file_downloaded = gcode_filename
                        except Exception as e:
                            self.gcode_file_downloaded = "ERROR"
                            LOGGER.error(f"Error while extracting gcode zip entry to target path. {repr(e)}")
                        
                        # And extract the plate type from the plate json.
                        self.print_bed_type = json.loads(archive.read(f"Metadata/plate_{plate_number}.json")).get('bed_type')
                    elif (metadata.get('key') == 'weight'):
                        LOGGER.debug(f"Weight: {metadata.get('value')}")
                        self.print_weight = metadata.get('value')
                    elif (metadata.get('key') == 'prediction'):
                        # Estimated print length in seconds
                        LOGGER.debug(f"Print time: {metadata.get('value')}s")
                    elif (metadata.tag == 'object'):
                        # Get the list of printable objects present on the plate before slicing.
                        # This includes hidden objects which need to be filtered out later.
                        if metadata.get('skipped') == f"false":
                            _printable_objects[metadata.get('identify_id')] = metadata.get('name')
                    elif (metadata.tag == 'filament'):
                        try:
                            # Filament used for the current print job. The plate info contains filaments
                            # identified in the order they appear in the slicer. These IDs must be
                            # mapped to the AMS tray mappings provided by MQTT print.ams_mapping

                            # Zero-index the filament ID
                            filament_index = int(metadata.get('id')) - 1
                            log_label = f"External spool"
                            
                            # Filament count should be greater than the zero-indexed filament ID
                            if filament_count > filament_index:
                                ams_index = self.ams_mapping[filament_index]
                                if ams_index < 16: # BUG - This will not yet handle AMS HT devices
                                    # We add the filament as you can map multiple slicer filaments to the same physical filament.
                                    self._ams_print_weights[ams_index] += float(metadata.get('used_g'))
                                    self._ams_print_lengths[ams_index] += float(metadata.get('used_m'))
                                    log_label = f"AMS Tray {ams_index + 1}"
                                else:
                                    LOGGER.debug(f"ams_mapping: {self.ams_mapping}")
                            elif plate_filament_count > 0:
                                # Multi filament print but the AMS mapping is unknown
                                # The data is only sent in the mqtt payload once and isn't part of the 'full' data so the integration must be
                                # live and listening to capture it.
                                LOGGER.debug(f"filament_index: {filament_index}")
                                log_label = f"AMS Tray unknown"
                            else:
                                LOGGER.debug(f"plate_filament_count: {plate_filament_count}")

                            LOGGER.debug(f"{log_label}: {metadata.get('used_m')}m | {metadata.get('used_g')}g")

                            # Increase the total print length
                            print_length += float(metadata.get('used_m'))
                        except Exception as e:
                            LOGGER.error(f"Failed to parse filament data: {e}")
                
                self.print_length = print_length

                if plate_number is not None:
                    try:
                        image = archive.read(f"Metadata/pick_{plate_number}.png")
                        self._client._device.pick_image.set_image(image)
                        # Process the pick image for objects
                        pick_image = Image.open(archive.open(f"Metadata/pick_{plate_number}.png"))
                        identify_ids = self._identify_objects_in_pick_image(image=pick_image)
                        
                        # Filter the printable objects from slice_info.config, removing
                        # any that weren't detected in the pick image
                        self._printable_objects = {k: _printable_objects[k] for k in identify_ids if k in _printable_objects}
                    except:
                        LOGGER.debug(f"Unable to load 'Metadata/pick_{plate_number}.png' from archive")

                # Save the slice_info.config file only if file cache is enabled
                try:
                    slice_info_bytes = archive.read('Metadata/slice_info.config')
                    # Save the slice_info.config in the same directory as the model file
                    slice_info_filename = os.path.splitext(os.path.basename(model_file_path))[0] + '.slice_info.config'
                    slice_info_path = os.path.join(model_dir, slice_info_filename)
                    with open(slice_info_path, "wb") as f:
                        f.write(slice_info_bytes)
                except Exception as e:
                    LOGGER.error(f"Failed to save slice_info.config: {e}")

            archive.close()

            self._client.callback("event_printer_data_update")
            result = True
        except Exception as e:
            LOGGER.error(f"Unexpected error parsing model data: {e}")
        
        self.prune_print_history_files()

        return result

    # The task list is of the following form with a 'hits' array with typical 20 entries.
    #
    # "total": 531,
    # "hits": [
    #     {
    #     "id": 35237965,
    #     "designId": 0,
    #     "designTitle": "",
    #     "instanceId": 0,
    #     "modelId": "REDACTED",
    #     "title": "REDACTED",
    #     "cover": "REDACTED",
    #     "status": 4,
    #     "feedbackStatus": 0,
    #     "startTime": "2023-12-21T19:02:16Z",
    #     "endTime": "2023-12-21T19:02:35Z",
    #     "weight": 34.62,
    #     "length": 1161,
    #     "costTime": 10346,
    #     "profileId": 35276233,
    #     "plateIndex": 1,
    #     "plateName": "",
    #     "deviceId": "REDACTED",
    #     "amsDetailMapping": [
    #         {
    #         "ams": 4,
    #         "sourceColor": "F4D976FF",
    #         "targetColor": "F4D976FF",
    #         "filamentId": "GFL99",
    #         "filamentType": "PLA",
    #         "targetFilamentType": "",
    #         "weight": 34.62
    #         }
    #     ],
    #     "mode": "cloud_file",
    #     "isPublicProfile": false,
    #     "isPrintable": true,
    #     "deviceModel": Printers.P1P,
    #     "deviceName": "Bambu P1P",
    #     "bedType": "textured_plate"
    #     },

    def _download_task_data_from_cloud(self):
        # Must have an auth token for this to be possible
        if self._client.bambu_cloud.auth_token == "":
            return

        self._task_data = self._client.bambu_cloud.get_latest_task_for_printer(self._client._serial)
        self._ams_print_weights = [0.0] * 136 # TODO: Convert to a dict in the future?
        self._ams_print_lengths = [0.0] * 136 # TODO: Convert to a dict in the future?
        if self._task_data is None:
            LOGGER.debug("No bambu cloud task data found for printer.")
            self._client._device.cover_image.set_image(None)
            self.print_weight = 0
            self.print_length = 0
            self.print_bed_type = "unknown"
            self.start_time = None
            self.end_time = None
        else:
            LOGGER.debug("Updating bambu cloud task data found for printer.")
            url = self._task_data.get('cover', '')
            if url != "":
                data = self._client.bambu_cloud.download(url)
                self._client._device.cover_image.set_image(data)

            self.print_length = self._task_data.get('length', self.print_length * 100) / 100
            self.print_bed_type = self._task_data.get('bedType', self.print_bed_type)
            self.print_weight = self._task_data.get('weight', self.print_weight)
            ams_print_data = self._task_data.get('amsDetailMapping', [])
            if self.print_weight != 0:
                for ams_data in ams_print_data:
                    index = ams_data['ams']
                    weight = ams_data['weight']
                    if 0 <= index < len(self._ams_print_weights):
                        self._ams_print_weights[index] = weight
                        self._ams_print_lengths[index] = self.print_length * weight / self.print_weight
                    else:
                        # Common case is this is a machine without an AMS and we get index == 255 (not 254 as might be expected)
                        # And probably also a machine with an AMS but you did a print from the external spool.
                        # This could also hit if you have reconfigured your printer and removed an AMS.
                        LOGGER.debug(f"AMS tray {index} not found in _ams_print_weights")
                        LOGGER.debug(f"ams_print_data: {ams_print_data}")

            status = self._task_data['status']
            LOGGER.debug(f"CLOUD PRINT STATUS: {status}")
            if status == 4:
                # If we generate the start time (not X1), then rely more heavily on the cloud task data and
                # do so uniformly so we always have matched start/end times.
                # "startTime": "2023-12-21T19:02:16Z"
                
                cloud_time_str = self._task_data.get('startTime', "")
                LOGGER.debug(f"CLOUD START TIME1: {self.start_time}")
                if cloud_time_str != "":
                    cloud_dt = parser.parse(cloud_time_str)
                    if cloud_dt.tzinfo is None:
                        cloud_dt = cloud_dt.replace(tzinfo=tz.UTC)
                    # Convert everything to UTC-aware datetime
                    self.start_time = cloud_dt.astimezone(tz.UTC)
                    LOGGER.debug(f"CLOUD START TIME2: {self.start_time}")

                # "endTime": "2023-12-21T19:02:35Z"
                cloud_time_str = self._task_data.get('endTime', "")
                LOGGER.debug(f"CLOUD END TIME1: {self.end_time}")
                if cloud_time_str != "":
                    cloud_dt = parser.parse(cloud_time_str)
                    if cloud_dt.tzinfo is None:
                        cloud_dt = cloud_dt.replace(tzinfo=tz.UTC)
                    # Convert everything to UTC-aware datetime
                    self.start_time = cloud_dt.astimezone(tz.UTC)
                    LOGGER.debug(f"CLOUD END TIME2: {self.end_time}")

    def _identify_objects_in_pick_image(self, image: Image) -> set:
        LOGGER.debug(f"Processing the pick image for objects")
        # Open the pick image so we can detect objects present
        image_width, image_height = image.size
        
        seen_colors = set()
        seen_identify_ids = set()

        # Loop through every pixel and label the first occurrence of each unique color
        pixels = image.load()
        for y in range(image_height):
            for x in range(image_width):
                current_color = pixels[x, y]
                r, g, b, a = current_color

                # Skip this pixel if it's transparent or already identified
                if a == 0 or current_color in seen_colors:
                    continue

                # Convert the colour to the decimal representation of its hex value
                identify_id = int(f"0x{b:02X}{g:02X}{r:02X}", 16)
                seen_colors.add(current_color)
                seen_identify_ids.add(str(identify_id))
        
        object_count = len(seen_identify_ids)
        LOGGER.debug(f"Finished proccessing pick image, found {object_count} object{'s'[:object_count^1]}")
        return seen_identify_ids

    async def async_ftp_file_check(self, file_path: str, expected_size: int) -> bool:
        """Async check if a file exists on the printer via FTP and matches the expected size."""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, self._sync_ftp_check, file_path, expected_size)

    def _sync_ftp_check(self, file_path: str, expected_size: int) -> bool:
        """Synchronous FTP check method to run in executor."""
        ftp = None
        try:
            # Use the connection helper from bambu_client
            ftp = self._client.ftp_connection()
            
            LOGGER.debug(f"FTP file check: Getting file size for {file_path}")
            # Get file size
            size = ftp.size(file_path)
            LOGGER.debug(f"FTP file check: File size is {size}, expected {expected_size}")
            
            return int(size) == expected_size
            
        except Exception as e:
            LOGGER.debug(f"FTP file check failed for {file_path}: {e}")
            return False
        finally:
            if ftp:
                try:
                    ftp.quit()
                except Exception:
                    pass

    async def async_ftp_upload_file(self, local_path: str, remote_path: str, progress_callback=None) -> bool:
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, self._sync_ftp_upload, local_path, remote_path, progress_callback)

    def _sync_ftp_upload(self, local_path: str, remote_path: str, progress_callback=None) -> bool:
        try:
            # Before we upload, make sure the file is present in this printer's local cache directory
            relative_path = remote_path.lstrip('/')
            this_printer_cache_file_path = Path(self._client.cache_path) / "prints" / relative_path
            this_printer_cache_file_path.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(local_path, this_printer_cache_file_path)
            LOGGER.debug(f"Copied file to local cache: {this_printer_cache_file_path}")
        except Exception as e:
            LOGGER.error(f"Failed to copy file to local cache: {e}")

        ftp = None
        try:
            ftp = self._client.ftp_connection()

            # Ensure remote directory exists
            dirs = remote_path.strip('/').split('/')[:-1]
            current = ''
            for d in dirs:
                current += f'/{d}'
                try:
                    ftp.mkd(current)
                except Exception:
                    pass  # Directory may already exist which is fine

            LOGGER.debug(f"FTP upload: Starting file upload")
            file_size = os.path.getsize(local_path)
            filename = os.path.basename(local_path)
            total_sent = 0
            chunk_size = 8192

            def internal_progress_callback(data):
                nonlocal total_sent
                total_sent += len(data)
                if progress_callback:
                    progress_callback({
                        "serial": self._client._serial,
                        "filename": filename,
                        "bytes_sent": total_sent,
                        "total": file_size,
                    })

            with open(local_path, 'rb') as f:
                try:
                    ftp.storbinary_no_unwrap(f'STOR {remote_path}', f, blocksize=chunk_size, callback=internal_progress_callback)
                except Exception as e:
                    # Handle the benign 426 “Failure reading network stream” case
                    if "426" in str(e):
                        LOGGER.warning(f"Ignoring benign FTP 426 for {remote_path}: {e}")
                    else:
                        raise

            # Verify upload really succeeded by comparing file size
            remote_size = ftp.size(remote_path)
            if remote_size != file_size:
                LOGGER.error(f"Size mismatch after FTP upload ({remote_size} != expected {file_size})")
                raise ValueError(f"FTP upload verification failed: remote={remote_size}, local={file_size}")

            LOGGER.debug(f"FTP upload: Upload completed successfully")

            return True

        except Exception as e:
            LOGGER.debug(f"FTP upload failed for {local_path} to {remote_path}: {e}")
            return False
        finally:
            if ftp:
                try:
                    ftp.quit()
                except Exception:
                    pass

@dataclass
class Info:
    """Return all device related content"""

    # Device state
    serial: str
    device_type: str
    wifi_signal: int
    wifi_sent: datetime
    hw_ver: str
    sw_ver: str
    online: bool
    new_version_state: int
    mqtt_mode: str
    nozzle_diameters: dict[int, float|None]
    nozzle_types: dict[int, str|None]
    usage_hours: float
    extruder_filament_state: bool
    door_open: bool
    airduct_mode: int
        
    _ip_address: str
    _force_ip: bool

    def __init__(self, client):
        self._client = client

        self.serial = self._client._serial
        self.device_type = self._client._device_type
        self.wifi_signal = 0
        self.wifi_sent = datetime.now()
        self.hw_ver = "unknown"
        self.sw_ver = "unknown"
        self.online = False
        self.new_version_state = 0
        self.mqtt_mode = "local" if self._client._local_mqtt else "bambu_cloud"
        self.nozzle_diameters = {0: None, 1: None}
        self.nozzle_types = {0: None, 1: None}
        self.usage_hours = client._usage_hours
        self.extruder_filament_state = False
        self.door_open = False
        self.airduct_mode = 0
        self._ip_address = client.host
        self._force_ip = client.settings.get('force_ip', False)                

    @property
    def is_hybrid_mode_blocking(self) -> bool:
        if not self.mqtt_mode == "local":
            return False
        if not self._client._device.supports_feature(Features.HYBRID_MODE_BLOCKS_CONTROL):
            return False
        return self._client.bambu_cloud.bambu_connected

    def set_online(self, online):
        if self.online != online:
            self.online = online
            self._client.callback("event_printer_data_update")

    def info_update(self, data):

        # Example payload:
        # {
        # "info": {
        #     "command": "get_version",
        #     "sequence_id": "20004",
        #     "module": [
        #     {
        #         "name": "ota",
        #         "project_name": "C11",
        #         "sw_ver": "01.02.03.00",
        #         "hw_ver": "OTA",
        #         "sn": "..."
        #     },
        #     {
        #         "name": "esp32",
        #         "project_name": "C11",
        #         "sw_ver": "00.03.12.31",
        #         "hw_ver": "AP04",
        #         "sn": "..."
        #     },
        modules = data.get("module", [])
        old_device_type = self.device_type
        self.device_type = get_printer_type(modules, self.device_type)
        if old_device_type != self.device_type:
            LOGGER.debug(f"Device is {self.device_type}")
        self.hw_ver = get_hw_version(modules, self.hw_ver)
        self.sw_ver = get_sw_version(modules, self.sw_ver)
        self._client.callback("event_printer_info_update")

    def print_update(self, data) -> bool:
        old_data = f"{self.__dict__}"

        # Example payload:
        # {
        #     "print": {
        #         "gcode_start_time": "1681479206",
        #         "gcode_state": "IDLE",
        #         "mc_print_stage": "1",
        #         "mc_percent": 100,
        #         "mc_remaining_time": 0,
        #         "wifi_signal": "-53dBm",
        #         "print_type": "idle",
        #         "ipcam": {
        #             "ipcam_dev": "1",
        #             "ipcam_record": "enable"
        #             "resolution": "1080p",        # X1 only
        #             "timelapse": "disable"
        #         },
        #         "layer_num": 0,
        #         "total_layer_num": 0,

        # "print": {
        #   "net": {
        #     "conf": 16,
        #     "info": [
        #       {
        #         "ip": 1594493450,
        #         "mask": 16777215
        #       },
        #       {
        #         "ip": 0,
        #         "mask": 0
        #       }
        #     ]
        #   },

        if not self._force_ip:
            info = data.get('net', {}).get('info', [])
            for net in info:
                ip_int = net.get("ip", 0)
                if ip_int != 0:
                    prev_ip_address = self._ip_address
                    self._ip_address = get_ip_address_from_int(ip_int)
                    if self._ip_address != prev_ip_address:
                        # IP address was retrieved from the initial mqtt payload or has changed.
                        self._client.stop_camera()
                        self._client.start_camera()                    
                    break

        # Version data is provided differently for X1 and P1
        # P1P example:
        # "upgrade_state": {
        #   "sequence_id": 0,
        #   "progress": "",
        #   "status": "",
        #   "consistency_request": false,
        #   "dis_state": 1,
        #   "err_code": 0,
        #   "force_upgrade": false,
        #   "message": "",
        #   "module": "",
        #   "new_version_state": 1,
        #   "new_ver_list": [
        #     {
        #       "name": "ota",
        #       "cur_ver": "01.02.03.00",
        #       "new_ver": "01.03.00.00"
        #     },
        #     {
        #       "name": "ams/0",
        #       "cur_ver": "00.00.05.96",
        #       "new_ver": "00.00.06.32"
        #     }
        #   ]
        # },
        # X1 example:
        # "upgrade_state": {
        #     "ahb_new_version_number": "",
        #     "ams_new_version_number": "",
        #     "consistency_request": false,
        #     "dis_state": 0,
        #     "err_code": 0,
        #     "force_upgrade": false,
        #     "message": "",
        #     "module": "null",
        #     "new_version_state": 2,
        #     "ota_new_version_number": "",
        #     "progress": "0",
        #     "sequence_id": 0,
        #     "status": "IDLE"
        # },
        # The 'new_version_state' value is common to indicate a new upgrade is available.
        # Observed values so far are:
        # 1 - upgrade available
        # 2 - no upgrades available
        # And the P1P lists it's versions in new_ver_list as a structured set of data with old
        # and new versions provided for each component. While the X1 lists only the new version
        # in separate string properties.

        self.new_version_state = data.get("upgrade_state",{}).get("new_version_state", self.new_version_state)

        # Nozzle data is provided differently for dual-nozzle printers (at least)
        # New (H2D):
        #  "nozzle": {
        #    "info": [
        #      {"id": 0, "diameter": "0.4", "type": "HS01"},
        #      {"id": 1, "diameter": "0.4", "type": "HS01"}
        #    ]
        # },
        # Old (X1C v1.08.02.00 firmware):
        #  "nozzle": {
        #    "0": {
        #      "info": 8,
        #      "temp": 23
        #    },
        #    "info": 69
        #  }
        # Old:
        #   "nozzle_diameter": "0.4",
        #   "nozzle_type": "hardened_steel",
        nozzle_data = data.get("device", {}).get("nozzle", {}).get("info")
        if nozzle_data is not None and isinstance(nozzle_data, list):
            for entry in nozzle_data:
                if entry.get("id") in (0, 1):
                    self.nozzle_diameters[entry["id"]] = float(entry.get("diameter", 0))
                    self.nozzle_types[entry["id"]] = Info._nozzle_type_name(entry.get("type", ""))
        else:
            if "nozzle_diameter" in data:
                self.nozzle_diameters[0] = float(data["nozzle_diameter"])
            if "nozzle_type" in data:
                self.nozzle_types[0] = data["nozzle_type"]

        # Door status may be provided in two places depending on printer model.
        # X1 example:
        #   "home_flag": -1066934785,   # closed
        #   "home_flag": -1058546177,   # open
        # H2 example:
        #   "stat": "46258008",  # closed
        #   "stat": "46A58008",  # open
        if self.device_type in [Printers.X1, Printers.X1C]:
            if "home_flag" in data:
                self.door_open = (data["home_flag"] & Home_Flag_Values.DOOR_OPEN) != 0
        elif "stat" in data:
            stat_value = int(data["stat"], 16)
            self.door_open = (stat_value & Stat_Flag_Values.DOOR_OPEN) != 0


        # Airduct mode is provided under print/device/airduct
        # P2S example:
        #   "modeCur": 0, // 0 = Cooling only, 1 = Heating/Filter
        #   "modeFunc": 0, // 0 = Cooling only, 1 = Heating/Filter        
        self.airduct_mode = data.get("device", {}).get("airduct", {}).get("modeCur", self.airduct_mode)

        # Compute if there's a delta before we check the wifi_signal value.
        changed = (old_data != f"{self.__dict__}")

        # Now test the wifi signal to minimize how frequently we sent data upates to home assistant. We want
        # these changes to be done outside the delta test above so that we don't trigger an update every 2-3s
        # due the noise in this value on A1/P1 printers.
        old_wifi_signal = self.wifi_signal
        self.wifi_signal = int(data.get("wifi_signal", str(self.wifi_signal)).replace("dBm", ""))
        if (self.wifi_signal != old_wifi_signal) :
            if (datetime.now() - self.wifi_sent) > timedelta(seconds=60):
                # It's been long enough. We can send this one.
                self.wifi_sent = datetime.now()
                changed = True
        
        # "hw_switch_state": 1,
        self.extruder_filament_state = bool(data.get("hw_switch_state", self.extruder_filament_state))

        return changed

    @property
    def active_nozzle_diameter(self) -> float | None:
        return self.nozzle_diameters[self._client._device.extruder.active_nozzle_index]

    @property
    def active_nozzle_type(self) -> str | None:
        return self.nozzle_types[self._client._device.extruder.active_nozzle_index]

    @property
    def left_nozzle_diameter(self) -> float | None:
        return self.nozzle_diameters[1]

    @property
    def left_nozzle_type(self) -> str | None:
        return self.nozzle_types[1]

    @property
    def right_nozzle_diameter(self) -> float | None:
        return self.nozzle_diameters[0]

    @property
    def right_nozzle_type(self) -> str | None:
        return self.nozzle_types[0]

    @property
    def is_local_mqtt(self):
        return self._client._local_mqtt

    @property
    def has_bambu_cloud_connection(self) -> bool:
        return self._client.bambu_cloud.auth_token != ""
    
    @property
    def ip_address(self) -> str:
        return self._ip_address
    
    def set_prompt_sound(self, enable: bool):
        if enable:
            self._client.publish(PROMPT_SOUND_ENABLE)
        else:
            self._client.publish(PROMPT_SOUND_DISABLE)
            
    def set_airduct_mode(self, enable: bool):
        if enable:
            self._client.publish(AIRDUCT_SET_COOLING)            
        else:
            self._client.publish(AIRDUCT_SET_HEATING_FILTER)            
            

    def buzzer_silence(self):
        self._client.publish(BUZZER_SET_SILENT)

    def buzzer_fire_alarm(self):
        self._client.publish(BUZZER_SET_ALARM)

    def buzzer_attention_beep(self):
        self._client.publish(BUZZER_SET_SILENT) # need to reset first for it to work properly
        self._client.publish(BUZZER_SET_BEEPING)
       
    @staticmethod
    def _nozzle_type_name(nozzle_type_code: str) -> str:
        if str == "":
            return "unknown"

        # Second character indicates standard vs high flow
        if nozzle_type_code[1] == "H":
            flow_prefix = "high_flow_"
        else:
            flow_prefix = ""

        # Last two digits indicate the material
        material_code = nozzle_type_code[2:4]
        _MATERIALS = {
            "00": "stainless_steel",
            "01": "hardened_steel",
            "05": "tungsten_carbide",
        }
        return flow_prefix + _MATERIALS.get(material_code, "unknown")


@dataclass
class AMSInstance:
    """Return all AMS instance related info"""
    model: str
    tray: list[AMSTray]

    _active: bool = False
    serial: str = ""
    sw_version: str = ""
    hw_version: str = ""
    index: int = 0
    humidity_index: int = 0
    humidity: int = 0
    temperature: int = 0
    remaining_drying_time: int = 0

    def __init__(self, client, model, index):
        self.model = model
        self.index = index
        if index >= 128:
            self.tray = [None]
            self.tray[0] = AMSTray(client)
        else:
            self.tray = [None] * 4
            self.tray[0] = AMSTray(client)
            self.tray[1] = AMSTray(client)
            self.tray[2] = AMSTray(client)
            self.tray[3] = AMSTray(client)

    @property
    def active(self):
        return self._active


@dataclass
class AMSList:
    """Return all AMS related info"""
    data: dict[int, AMSInstance]

    _nozzle_tray_index: dict
    _nozzle_ams_index: dict
    _first_initialization_done: bool = False

    def __init__(self, client):
        self._client = client
        self._nozzle_tray_index = { 0: 0, 1: 0}
        self._nozzle_ams_index = { 0: 0, 1: 0}
        self.data = {}

    @property
    def active_ams_index(self):
        active_nozzle = self._client._device.extruder.active_nozzle_index
        return self._nozzle_ams_index[active_nozzle]
    
    @property
    def active_tray_index(self):
        active_nozzle = self._client._device.extruder.active_nozzle_index
        return self._nozzle_tray_index[active_nozzle]
    
    @property
    def active_tray(self):
        if self.active_ams_index == 255:
            if self.active_tray_index == 255:
                return None
            else:
                return self._client._device.external_spool[0]
        elif self.active_ams_index == 254:
            if self.active_tray_index == 255:
                return None
            else:
                return self._client._device.external_spool[1]
        elif self.data[self.active_ams_index] is None:
            return None
        else:
            return self.data[self.active_ams_index].tray[self.active_tray_index]

    def info_update(self, data):
        old_data = f"{self.__dict__}"

        # First determine if this the version info data or the json payload data. We use the version info to determine
        # what devices to add to humidity_index assistant and add all the sensors as entities. And then then json payload data
        # to populate the values for all those entities.

        # The module entries are of this form (P1/X1):
        # {
        #     "name": "ams/0",
        #     "project_name": "",
        #     "sw_ver": "00.00.05.96",
        #     "loader_ver": "00.00.00.00",
        #     "ota_ver": "00.00.00.00",
        #     "hw_ver": "AMS08",
        #     "sn": "<SERIAL>"
        # }
        # AMS Lite of the form:
        # {
        #   "name": "ams_f1/0",
        #   "project_name": "",
        #   "sw_ver": "00.00.07.89",
        #   "loader_ver": "00.00.00.00",
        #   "ota_ver": "00.00.00.00",
        #   "hw_ver": "AMS_F102",
        #   "sn": "**REDACTED**"
        # }

        data_changed = False
        module_list = data.get("module", [])
        for module in module_list:
            name = module["name"]
            index = -1
            model = ""
            if name.startswith("ams/"):
                model = "AMS"
                index = int(name[4:])
            elif name.startswith("ams_f1/"):
                model = "AMS Lite"
                index = int(name[7:])
            elif name.startswith("n3f/"):
                model = "AMS 2 Pro"
                index = int(name[4:])
            elif name.startswith("n3s/"):
                model = "AMS HT"
                index = int(name[4:])
            
            if index != -1:
                # Sometimes we get incomplete version data. We have to skip if that occurs since the serial number is
                # required as part of the home assistant device identity.
                if not module['sn'] == '':
                    # May get data before info so create entries if necessary
                    if index not in self.data:
                        data_changed = True
                        self.data[index] = AMSInstance(self._client, model, index)
                    if self.data[index].model != model:
                        data_changed = True
                        self.data[index].model = model
                    if self.data[index].serial != module['sn']:
                        data_changed = True
                        self.data[index].serial = module['sn']
                    if self.data[index].sw_version != module['sw_ver']:
                        data_changed = True
                        self.data[index].sw_version = module['sw_ver']
                    if self.data[index].hw_version != module['hw_ver']:
                        data_changed = True
                        self.data[index].hw_version = module['hw_ver']
            elif not self._first_initialization_done:
                self._first_initialization_done = True
                data_changed = True

        data_changed = data_changed or (old_data != f"{self.__dict__}")

    def print_update(self, data) -> bool:
        old_data = f"{self.__dict__}"

        # AMS json payload is of the form:
        # "ams": {
        #     "ams": [
        #         {
        #             "id": "0",
        #             "humidity": "4",
        #             "temp": "0.0",
        #             "tray": [
        #                 {
        #                     "id": "0",
        #                     "remain": -1,
        #                     "k": 0.019999999552965164,        # P1P only
        #                     "n": 1.399999976158142,           # P1P only
        #                     "tag_uid": "0000000000000000",
        #                     "tray_id_name": "",
        #                     "tray_info_idx": "GFL99",
        #                     "tray_type": "PLA",
        #                     "tray_sub_brands": "",
        #                     "tray_color": "FFFF00FF",         # RRGGBBAA
        #                     "tray_weight": "0",
        #                     "tray_diameter": "0.00",
        #                     "drying_temp": "0",
        #                     "drying_time": "0",
        #                     "bed_temp_type": "0",
        #                     "bed_temp": "0",
        #                     "nozzle_temp_max": "240",
        #                     "nozzle_temp_min": "190",
        #                     "remain": 100,
        #                     "xcam_info": "000000000000000000000000",
        #                     "tray_uuid": "00000000000000000000000000000000"
        #                 },
        #                 {
        #                     "id": "1",
        #                     ...
        #                 },
        #                 {
        #                     "id": "2",
        #                     ...
        #                 },
        #                 {
        #                     "id": "3",
        #                     ...
        #                 }
        #             ]
        #         }
        #     ],
        #     "ams_exist_bits": "1",
        #     "tray_exist_bits": "f",
        #     "tray_is_bbl_bits": "f",
        #     "tray_now": "255",
        #     "tray_read_done_bits": "f",
        #     "tray_reading_bits": "0",
        #     "tray_tar": "255",
        #     "version": 3,
        #     "insert_flag": true,
        #     "power_on_flag": false
        # },

        ams_data = data.get("ams", {})

        extruder_data = data.get("device", {}).get("extruder", {}).get("info")
        if extruder_data is not None:
            for entry in extruder_data:
                if entry.get("id") in (0, 1):
                    if "snow" in entry:
                        tray_now = entry["snow"]
                        self._nozzle_ams_index[entry["id"]] = tray_now >> 8
                        self._nozzle_tray_index[entry["id"]] = tray_now & 0x3
        else:
            tray_now = ams_data.get('tray_now')
            if tray_now is not None:
                tray_now = int(tray_now)
                if tray_now == 255:
                    # In the legacy mqtt payloads 255 nothing active
                    self._nozzle_ams_index[0] = 255
                    self._nozzle_tray_index[0] = 255
                elif tray_now == 254:
                    # In the legacy mqtt payloads 254 = external spool active
                    self._nozzle_ams_index[0] = 255
                    self._nozzle_tray_index[0] = 0
                elif tray_now >= 80:
                    # AMS HT's are indices 128-135 (0x80-0x87)
                    self._nozzle_ams_index[0] = tray_now
                    self._nozzle_tray_index[0] = 0
                else:
                    # Otherwise we need to shift the index down by 2 to get the correct AMS index
                    self._nozzle_ams_index[0] = tray_now >> 2
                    self._nozzle_tray_index[0] = tray_now & 0x3

        if len(ams_data) != 0:
            ams_list = ams_data.get("ams", [])
            for ams in ams_list:
                index = int(ams['id'])
                # May get data before info so create entry if necessary
                if index not in self.data:
                    self.data[index] = AMSInstance(self._client, "Unknown", index)

                # Sometimes when the AMS is being powered on it may send bogus humidity and temperature values.
                # So ignore these values if they are out of a sensible range.

                humidity_index = int(ams['humidity'])
                if 1 <= humidity_index <= 5 and self.data[index].humidity_index != humidity_index:
                    self.data[index].humidity_index = humidity_index

                humidity = int(ams.get("humidity_raw", 0))
                if 1 <= humidity <= 100 and self.data[index].humidity != humidity:
                    self.data[index].humidity = humidity

                temperature = float(ams['temp'])
                if 0 <= temperature <= 100 and self.data[index].temperature != temperature:
                    self.data[index].temperature = temperature

                if self.data[index].remaining_drying_time != int(ams.get('dry_time', 0)):
                    self.data[index].remaining_drying_time = int(ams.get('dry_time', 0))

                tray_list = ams['tray']
                for tray in tray_list:
                    tray_id = int(tray['id'])
                    self.data[index].tray[tray_id].print_update(tray)

        # Now that we've populated the AMS/Trays (if this is first time through), we must
        # loop over all the ams and trays to set active states correctly.
        for index in self.data:
            self.data[index]._active = (index == self.active_ams_index)
            for tray_id, tray in enumerate(self.data[index].tray):
                active_tray = (index == self.active_ams_index) and (self.active_tray_index == tray_id)
                tray.active = active_tray

        data_changed = (old_data != f"{self.__dict__}")
        return data_changed

@dataclass
class AMSTray:
    """Return all AMS tray related info"""
    empty: bool
    idx: int
    name: str
    type: str
    sub_brands: str
    color: str
    nozzle_temp_min: int
    nozzle_temp_max: int
    _remain: int
    k: float
    tag_uid: str
    tray_uuid: str
    tray_weight: int
    _active: bool

    def __init__(self, client):
        self._client = client
        self.empty = True
        self.idx = ""
        self.name = ""
        self.type = ""
        self.sub_brands = ""
        self.color = "00000000"  # RRGGBBAA
        self.nozzle_temp_min = 0
        self.nozzle_temp_max = 0
        self._remain = -1
        self.k = 0
        self.tag_uid = ""
        self.tray_uuid = ""
        self.tray_weight = 0
        self._active = False

    @property
    def remain(self) -> int:
        return self._remain

    @property
    def active(self) -> bool:
        return self._active
    
    @active.setter
    def active(self, value: bool):
        self._active = value

    @property
    def remain_enabled(self) -> bool:
        return self._client._device.supports_feature(Features.AMS_FILAMENT_REMAINING) and self._client._device.home_flag.ams_calibrate_remaining

    def print_update(self, data) -> bool:
        old_data = f"{self.__dict__}"

        if len(data) <= 2:
            # If the data just id + state then the tray is empty.
            self.empty = True
            self.idx = ""
            self.name = "Empty"
            self.type = "Empty"
            self.sub_brands = ""
            self.color = "00000000"  # RRGGBBAA
            self.nozzle_temp_min = 0
            self.nozzle_temp_max = 0
            self._remain = -1
            self.tag_uid = ""
            self.tray_uuid = ""
            self.k = 0
            self.tray_weight = 0
        else:
            self.empty = False
            self.idx = data.get('tray_info_idx', self.idx)
            self.name = get_filament_name(self.idx, self._client.slicer_settings.custom_filaments)
            self.type = data.get('tray_type', self.type)
            self.sub_brands = data.get('tray_sub_brands', self.sub_brands)
            self.color = data.get('tray_color', self.color)
            self.nozzle_temp_min = data.get('nozzle_temp_min', self.nozzle_temp_min)
            self.nozzle_temp_max = data.get('nozzle_temp_max', self.nozzle_temp_max)
            self._remain = data.get('remain', self._remain)
            self.tag_uid = data.get('tag_uid', self.tag_uid)
            self.tray_uuid = data.get('tray_uuid', self.tray_uuid)
            self.k = data.get('k', self.k)
            self.tray_weight = data.get('tray_weight', self.tray_weight)
            if self.name == "unknown":
                # Fallback to the type if the name is unknown
                self.name = self.type
        return (old_data != f"{self.__dict__}")


@dataclass
class ExternalSpool(AMSTray):
    """Return the virtual tray related info"""
    _index: int

    def __init__(self, client, index: int):
        super().__init__(client)
        self._index = index

    @property
    def active(self) -> bool:
        if self._client._device.supports_feature(Features.AMS):
            active_ams_index = self._client._device.ams.active_ams_index
            active_tray_index = self._client._device.ams.active_tray_index
            if active_ams_index == (255 - self._index) and active_tray_index == 0:
                return True
        else:
            return True
        return False

    @property
    def remain(self) -> int:
        return -1

    @property
    def remain_enabled(self) -> bool:
        return False

    def print_update(self, data) -> bool:

        # P1P virtual tray example
        # "vt_tray": {
        #     "id": "254",
        #     "tag_uid": "0000000000000000",
        #     "tray_id_name": "",
        #     "tray_info_idx": "GFB99",
        #     "tray_type": "ABS",
        #     "tray_sub_brands": "",
        #     "tray_color": "000000FF",
        #     "tray_weight": "0",
        #     "tray_diameter": "0.00",
        #     "tray_temp": "0",
        #     "tray_time": "0",
        #     "bed_temp_type": "0",
        #     "bed_temp": "0",
        #     "nozzle_temp_max": "280",
        #     "nozzle_temp_min": "240",
        #     "remain": 100,
        #     "xcam_info": "000000000000000000000000",
        #     "tray_uuid": "00000000000000000000000000000000",
        #     "remain": 0,
        #     "k": 0.029999999329447746,
        #     "n": 1.399999976158142
        # },
        #
        # This is exact same data as the AMS exposes so we can just defer to the AMSTray object
        # to parse this json.

        # H2D virtual tray example
        # "vir_slot": [
        # {
        #     "bed_temp": "0",
        #     "bed_temp_type": "0",
        #     "cali_idx": -1,
        #     "cols": [
        #     "76D9F4FF"
        #     ],
        #     "ctype": 0,
        #     "drying_temp": "0",
        #     "drying_time": "0",
        #     "id": "254",
        #     "nozzle_temp_max": "240",
        #     "nozzle_temp_min": "190",
        #     "remain": 0,
        #     "tag_uid": "0000000000000000",
        #     "total_len": 330000,
        #     "tray_color": "76D9F4FF",
        #     "tray_diameter": "1.75",
        #     "tray_id_name": "",
        #     "tray_info_idx": "GFA01",
        #     "tray_sub_brands": "",
        #     "tray_type": "PLA",
        #     "tray_uuid": "00000000000000000000000000000000",
        #     "tray_weight": "0",
        #     "xcam_info": "000000000000000000000000"
        # },
        # {
        # ...
        #     "id": "254",

        received_virtual_tray_data = False

        if data.get("vir_slot") is not None:
            for vir_slot in data.get("vir_slot"):
                id = int(vir_slot.get("id"))
                if id == (255 - self._index):
                    tray_data = vir_slot
                    received_virtual_tray_data = super().print_update(tray_data)
        else:
            tray_data = data.get("vt_tray", {})
            if len(tray_data) != 0:
                received_virtual_tray_data = super().print_update(tray_data)

        return received_virtual_tray_data


@dataclass
class Speed:
    """Return speed profile information"""
    _id: int
    name: str
    modifier: int

    def __init__(self, client):
        self._client = client
        self._id = 2
        self.name = get_speed_name(2)
        self.modifier = 100

    def print_update(self, data) -> bool:
        old_data = f"{self.__dict__}"

        self._id = int(data.get("spd_lvl", self._id))
        self.name = get_speed_name(self._id)
        self.modifier = int(data.get("spd_mag", self.modifier))
        
        return (old_data != f"{self.__dict__}")

    def SetSpeed(self, option: str):
        for id, speed in SPEED_PROFILE.items():
            if option == speed:
                self._id = id
                self.name = speed
                command = SPEED_PROFILE_TEMPLATE
                command['print']['param'] = f"{id}"
                self._client.publish(command)
                self._client.callback("event_speed_update")


@dataclass
class StageAction:
    """Return Stage Action information"""
    _id: int
    _print_type: str
    description: str

    def __init__(self):
        self._id = 255
        self._print_type = ""
        self.description = get_current_stage(self._id)

    def print_update(self, data) -> bool:
        old_data = f"{self.__dict__}"

        self._print_type = data.get("print_type", self._print_type)
        if self._print_type.lower() not in PRINT_TYPE_OPTIONS:
            self._print_type = "unknown"

        # New way it is presented
        self._id = int(data.get("stage", {}).get("_id", self._id))
        # Old way it's presented
        self._id = int(data.get("stg_cur", self._id))
        if (self._print_type == "idle") and (self._id == 0):
            # On boot the printer reports stg_cur == 0 incorrectly instead of 255. Attempt to correct for this.
            self._id = 255
        self.description = get_current_stage(self._id)

        return (old_data != f"{self.__dict__}")

@dataclass
class HMSList:
    """Return all HMS related info"""
    _errors: dict

    def __init__(self, client):
        self._client = client
        self._errors = {}
        self._errors["Count"] = 0
        
    def print_update(self, data) -> bool:
        # Example payload:
        # "hms": [
        #     {
        #         "attr": 50331904, # In hex this is 0300 0100
        #         "code": 65543     # In hex this is 0001 0007
        #     }
        # ],
        # So this is HMS_0300_0100_0001_0007:
        # https://wiki.bambulab.com/en/x1/troubleshooting/hmscode/0300_0100_0001_0007
        # 'The heatbed temperature is abnormal; the sensor may have an open circuit.'

        if 'hms' in data.keys():
            hmsList = data.get('hms', [])
            errors = {}

            index: int = 0
            for hms in hmsList:
                attr = int(hms['attr'])
                code = int(hms['code'])
                hms_notif = HMSNotification(
                    device_type=self._client._device.info.device_type,
                    user_language=self._client.user_language,
                    attr=attr,
                    code=code
                    )
                if not hms_notif.hms_error:
                    LOGGER.debug("Skipping HMS notification with code %s (no text).", hms_notif.hms_code)
                    continue  # skip invalid entries

                index = index + 1
                errors[f"{index}-Code"] = f"HMS_{hms_notif.hms_code}"
                errors[f"{index}-Error"] = hms_notif.hms_error
                errors[f"{index}-Wiki"] = hms_notif.wiki_url
                errors[f"{index}-Severity"] = hms_notif.severity
                #LOGGER.debug(f"HMS error for '{hms_notif.module}' and severity '{hms_notif.severity}': HMS_{hms_notif.hms_code}")
                #errors[f"{index}-Module"] = hms_notif.module # commented out to avoid bloat with current structure

            errors["Count"] = index

            if self._errors != errors:
                LOGGER.debug("Updating HMS error list.")
                self._errors = errors
                if self._errors["Count"] != 0:
                    LOGGER.warning(f"HMS ERRORS: {errors}")
                self._client.callback("event_printer_error")
                return True
        
        return False
    
    @property
    def errors(self) -> dict:
        #LOGGER.debug(f"PROPERTYCALL: get_hms_errors")
        return self._errors
    
    @property
    def error_count(self) -> int:
        return self._errors["Count"]

@dataclass
class PrintError:
    """Return all print_error related info"""
    _error: dict

    def __init__(self, client):
        self._error = None
        self._client = client
        
    def print_update(self, data) -> bool:
        # Example payload:
        # "print_error": 117473286 
        # So this is 07008006 which we make more human readable to 0700-8006
        # https://e.bambulab.com/query.php?lang=en
        # 'Unable to feed filament into the extruder. This could be due to entangled filament or a stuck spool. If not, please check if the AMS PTFE tube is connected.'

        if 'print_error' in data.keys():
            errors = None
            code = data.get('print_error')
            if code != 0:
                code = f'0{int(code):x}'
                code = code[slice(0,4,1)] + "_" + code[slice(4,8,1)]
                code = code.upper()
                errors = {}
                errors[f"code"] = code
                error_text = get_print_error_text(code, self._client._device.info.device_type, self._client.user_language)
                errors[f"error"] = error_text
                if error_text == 'unknown':
                    # Suppress unknown errors as they get fired when there are no errors.
                    errors = None

            if self._error != errors:
                self._error = errors
                self._client.callback("event_print_error")

        # We send the error event directly so always return False for the general data event.
        return False
    
    @property
    def error(self) -> dict:
        return self._error
    
    @property
    def on(self) -> int:
        return self._error is not None


@dataclass
class HMSNotification:
    """Return an HMS object and all associated details"""
    attr: int
    code: int

    def __init__(self, device_type: Printers | str, user_language: str, attr: int, code: int):
        self._device_type = device_type
        self._user_language = user_language
        self.attr = attr
        self.code = code

    @property
    def severity(self):
        return get_HMS_severity(self.code)

    @property
    def module(self):
        return get_HMS_module(self.attr)

    @property
    def hms_code(self):
        if self.attr > 0 and self.code > 0:
            return f'{int(self.attr / 0x10000):0>4X}_{self.attr & 0xFFFF:0>4X}_{int(self.code / 0x10000):0>4X}_{self.code & 0xFFFF:0>4X}' # 0300_0100_0001_0007
        return ""
    
    @property
    def hms_error(self) -> str:
        error_text = get_HMS_error_text(self.hms_code, self._device_type, self._user_language)
        return error_text

    @property
    def wiki_url(self):
        if self.attr > 0 and self.code > 0:
            # Only English wiki content seems to exist
            return f"https://wiki.bambulab.com/en/x1/troubleshooting/hmscode/{self.hms_code}"
        return ""


@dataclass
class ChamberImage:
    """Returns the latest jpeg data from the P1P camera"""
    def __init__(self, client):
        self._client = client
        self._bytes = bytearray()
        self._image_last_updated = None

    def set_image(self, bytes):
        self._bytes = bytes
        self._image_last_updated = datetime.now()
        self._client.callback("event_printer_chamber_image_update")

    def get_image(self) -> bytearray:
        return self._bytes.copy()
    
    def get_last_update_time(self) -> datetime:
        return self._image_last_updated

    
@dataclass
class CoverImage:
    """Returns the cover image from the Bambu API or FTP"""

    def __init__(self, client):
        self._client = client
        self._bytes = bytearray()
        self._image_last_updated = None
        self._client.callback("event_printer_cover_image_update")

    def set_image(self, bytes):
        self._bytes = bytes
        self._image_last_updated = datetime.now()
        self._client.callback("event_printer_cover_image_update")
    
    def get_image(self) -> bytearray:
        return self._bytes

    def get_last_update_time(self) -> datetime:
        return self._image_last_updated

    
@dataclass
class PickImage:
    """Returns the object pick image from the FTP"""

    def __init__(self, client):
        self._client = client
        self._bytes = bytearray()
        self._image_last_updated = datetime.now()
        self._client.callback("event_printer_pick_image_update")

    def set_image(self, bytes):
        self._bytes = bytes
        self._image_last_updated = datetime.now()
        self._client.callback("event_printer_pick_image_update")
    
    def get_image(self) -> bytearray:
        return self._bytes

    def get_last_update_time(self) -> datetime:
        return self._image_last_updated


@dataclass
class HomeFlag:
    """Contains parsed _values from the homeflag sensor"""
    _value: int
    _sw_ver: str
    _device_type: str 
    _fired_missing_sdcard_event: bool

    def __init__(self, client):
        self._value = 0
        self._client = client
        self._sw_ver = ""
        self._device_type = ""
        self._fired_missing_sdcard_event = False

    def info_update(self, data):
        modules = data.get("module", [])
        self._device_type = get_printer_type(modules, self._device_type)
        self._sw_ver = get_sw_version(modules, self._sw_ver)

    def print_update(self, data: dict) -> bool:
        old_data = f"{self.__dict__}"
        self._value = int(data.get("home_flag", str(self._value)))
        if self.sdcard_status == "missing":
            if not self._fired_missing_sdcard_event:
                self._fired_missing_sdcard_event = True
                self._client.callback("event_printer_missing_sdcard")
        else:
            self._fired_missing_sdcard_event = False
        return (old_data != f"{self.__dict__}")

    @property
    def sdcard_status(self) -> str:
        if (self._value & Home_Flag_Values.SD_CARD_ABNORMAL) != 0:
            return "abnormal"
        if (self._value & Home_Flag_Values.SD_CARD_PRESENT) != 0:
            return "normal"
        return "missing"

    @property
    def x_axis_homed(self) -> bool:
        return (self._value & Home_Flag_Values.X_AXIS) != 0
    
    @property
    def y_axis_homed(self) -> bool:
        return (self._value & Home_Flag_Values.Y_AXIS) != 0

    @property
    def z_axis_homed(self) -> bool:
        return (self._value & Home_Flag_Values.Z_AXIS) != 0

    @property
    def homed(self) -> bool:
        return self.x_axis_homed and self.y_axis_homed and self.z_axis_homed

    @property
    def is_220V(self) -> bool:
        return (self._value & Home_Flag_Values.VOLTAGE220) != 0

    @property
    def xcam_autorecovery_steploss(self) -> bool:
        return (self._value & Home_Flag_Values.XCAM_AUTO_RECOVERY_STEP_LOSS) != 0

    @property
    def camera_recording(self) -> bool:
        return (self._value & Home_Flag_Values.CAMERA_RECORDING) != 0

    @property
    def ams_calibrate_remaining(self) -> bool:
        return (self._value & Home_Flag_Values.AMS_CALIBRATE_REMAINING) != 0

    @property
    def ams_auto_switch_filament(self) -> bool:
        return (self._value & Home_Flag_Values.AMS_AUTO_SWITCH) != 0

    @property
    def wired_network_connection(self):
        return (self._value & Home_Flag_Values.WIRED_NETWORK) != 0

    @property
    def xcam_prompt_sound(self) -> bool:
        return (self._value & Home_Flag_Values.XCAM_ALLOW_PROMPT_SOUND) != 0

    @property
    def supports_motor_noise_calibration(self) -> bool:
        return (self._value & Home_Flag_Values.SUPPORTS_MOTOR_CALIBRATION) != 0
    
    @property
    def p1s_upgrade_supported(self) -> bool:
        return (self._value & Home_Flag_Values.SUPPORTED_PLUS) !=  0
    
    @property
    def p1s_upgrade_installed(self) -> bool:
        return (self._value & Home_Flag_Values.INSTALLED_PLUS) !=  0


@dataclass
class PrintFun:
    """Contains parsed _values from the print->fun sensor"""
    _value: str
    _int_value: int
    _encryption_enabled: bool
    _fired_encryption_enabled_event: bool
    
    def __init__(self, client):
        self._value = ""
        self._client = client
        self._encryption_enabled = False
        self._int_value: int = 0
        self._fired_encryption_enabled_event = False

    def print_update(self, data: dict) -> bool:
        old_data = f"{self.__dict__}"
        self._value = data.get("fun", str(self._value))
        self._int_value = int(self._value, 16) if self._value else 0
        self._encryption_enabled = (self._int_value & Print_Fun_Values.MQTT_SIGNATURE_REQUIRED) != 0
        if self._encryption_enabled:
            if not self._fired_encryption_enabled_event:
                self._fired_encryption_enabled_event = True
                self._client.callback("event_printer_mqtt_encryption_enabled")

        return (old_data != f"{self.__dict__}")

    @property
    def mqtt_signature_required(self) -> bool:
        return self._encryption_enabled
    

@dataclass
class FilamentInfo:
    name: str
    filament_vendor: str
    filament_type: str
    filament_density: float
    nozzle_temperature: int
    nozzle_temperature_range_high: int
    nozzle_temperature_range_low: int

# Example custom filament;
# {
#   "setting_id": "PFUS9be9e18f81828a",
#   "version": "1.9.0.2",
#   "update_time": "2024-03-30 11:54:22",
#   "name": "ELEGOO PLA Black @Bambu Lab X1 Carbon 0.6 nozzle",
#   "nickname": null,
#   "base_id": null,
#   "filament_vendor": "ELEGOO",
#   "filament_id": "P9816594",
#   "filament_type": "PLA",
#   "filament_is_support": false,
#   "nozzle_temperature": [
#     190,
#     240
#   ],
#   "nozzle_hrc": 3
# },
      
class SlicerSettings:
    custom_filaments: dict = field(default_factory=dict)

    def __init__(self, client):
        self._client = client
        self.custom_filaments = {}

    @property
    def filaments(self):
        return self.custom_filaments

    def _load_custom_filaments(self, slicer_settings: dict):
        filaments = slicer_settings.get("filament")
        if filaments is not None:
            private_filaments = filaments.get("private", {})
            for filament in private_filaments:
                if filament.get("filament_id", "") != "":
                    name = filament["name"]
                    if " @" in name:
                        name = name[:name.index(" @")]
                    id = filament["filament_id"]
                    self.custom_filaments[id] = FilamentInfo(
                        name=name,
                        filament_vendor=filament["filament_vendor"],
                        filament_type=filament["filament_type"],
                        filament_density=0,
                        nozzle_temperature=0,
                        nozzle_temperature_range_high=filament["nozzle_temperature"][1],
                        nozzle_temperature_range_low=filament["nozzle_temperature"][0]
                    )
            LOGGER.debug(f"Got {len(self.custom_filaments)} custom filaments.")
        else:
            LOGGER.debug(f"Received no filament data: {filaments}")

    def update(self):
        self.custom_filaments = {}
        if self._client.bambu_cloud.auth_token != "":
            LOGGER.debug(f"Loading slicer settings for {self._client._device.info.device_type} / {self._client._serial}")
            slicer_settings = self._client.bambu_cloud.get_slicer_settings()
            if slicer_settings is None:
                LOGGER.debug(f"Failed to get slicer settings for {self._client._device.info.device_type} / {self._client._serial}")
                self._client.callback("event_printer_bambu_authentication_failed")
            else:
                self._load_custom_filaments(slicer_settings)

class ExtruderTool:
    """Contains parsed _values from the ext_tool sensor"""
    state: str

    def __init__(self, client):
        self._client = client
        self.state = None

    def print_update (self, data):
        # Handle ext_tool update
        old_data = f"{self.__dict__}"

        if "device" in data and "ext_tool" in data["device"]:
            ext_tool = data["device"]["ext_tool"]
            mount = ext_tool.get("mount")
            tool_type = ext_tool.get("type")
            prev_state = self.state
            if mount == 0:
                self.state = "none"
            elif mount == 1 and tool_type == "LB00":
                self.state = "laser10"
            elif mount == 1 and tool_type == "LB01":
                self.state = "laser40"
            elif mount == 1 and tool_type == "CP00":
                self.state = "cutter"
            elif mount == 1 and tool_type:
                self.state = None
        
        return (old_data != f"{self.__dict__}")
    
class Extruder:
    _active_nozzle_index: int

    def __init__(self, client):
        self._client = client
        self._active_nozzle_index = 0

    def print_update (self, data):
        # Handle ext_tool update
        old_data = f"{self.__dict__}"

        extruder_state = data.get("device", {}).get("extruder", {}).get("state")
        if extruder_state is not None:
            self._active_nozzle_index = (extruder_state >> 4) & 0xF
                        
        return (old_data != f"{self.__dict__}")

    @property
    def active_nozzle_index(self):
        return self._active_nozzle_index