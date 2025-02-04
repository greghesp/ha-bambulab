import asyncio
import math
import os
import re
import threading

from dataclasses import dataclass, field
from datetime import datetime
from dateutil import parser, tz
from packaging import version
from zipfile import ZipFile
import tempfile
import xml.etree.ElementTree as ElementTree

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
    get_start_time,
    get_end_time,
    get_HMS_error_text,
    get_print_error_text,
    get_HMS_severity,
    get_HMS_module,
    set_temperature_to_gcode,
)
from .const import (
    LOGGER,
    Features,
    FansEnum,
    Home_Flag_Values,
    SdcardState,
    SPEED_PROFILE,
    GCODE_STATE_OPTIONS,
    PRINT_TYPE_OPTIONS,
    TempEnum,
)
from .commands import (
    CHAMBER_LIGHT_ON,
    CHAMBER_LIGHT_OFF,
    PROMPT_SOUND_ENABLE,
    PROMPT_SOUND_DISABLE,
    SPEED_PROFILE_TEMPLATE,
)

class Device:
    def __init__(self, client):
        self._client = client
        self.temperature = Temperature(client = client)
        self.lights = Lights(client = client)
        self.info = Info(client = client)
        self.print_job = PrintJob(client = client)
        self.fans = Fans(client = client)
        self.speed = Speed(client = client)
        self.stage = StageAction()
        self.ams = AMSList(client = client)
        self.external_spool = ExternalSpool(client = client)
        self.hms = HMSList(client = client)
        self.print_error = PrintError(client = client)
        self.camera = Camera(client = client)
        self.home_flag = HomeFlag(client=client)
        self.push_all_data = None
        self.get_version_data = None
        if self.supports_feature(Features.CAMERA_IMAGE):
            self.chamber_image = ChamberImage(client = client)
        self.cover_image = CoverImage(client = client)

    def print_update(self, data) -> bool:
        send_event = False
        send_event = send_event | self.info.print_update(data = data)
        send_event = send_event | self.print_job.print_update(data = data)
        send_event = send_event | self.temperature.print_update(data = data)
        send_event = send_event | self.lights.print_update(data = data)
        send_event = send_event | self.fans.print_update(data = data)
        send_event = send_event | self.speed.print_update(data = data)
        send_event = send_event | self.stage.print_update(data = data)
        send_event = send_event | self.ams.print_update(data = data)
        send_event = send_event | self.external_spool.print_update(data = data)
        send_event = send_event | self.hms.print_update(data = data)
        send_event = send_event | self.print_error.print_update(data = data)
        send_event = send_event | self.camera.print_update(data = data)
        send_event = send_event | self.home_flag.print_update(data = data)

        self._client.callback("event_printer_data_update")

        if data.get("msg", 0) == 0:
            self.push_all_data = data

    def info_update(self, data):
        self.info.info_update(data = data)
        self.home_flag.info_update(data = data)
        self.ams.info_update(data = data)
        if data.get("command") == "get_version":
            self.get_version_data = data

    def _supports_temperature_set(self):
        # When talking to the Bambu cloud mqtt, setting the temperatures is allowed.
        if self.info.mqtt_mode == "bambu_cloud":
            return True
        # X1* have not yet blocked setting the temperatures when in nybrid connection mode.
        if self.info.device_type == "X1" or self.info.device_type == "X1C" or self.info.device_type == "X1E":
            return True
        # What's left is P1 and A1 printers that we are connecting by local mqtt. These are supported only in pure Lan Mode.
        return not self._client.bambu_cloud.bambu_connected

    def supports_feature(self, feature):
        if feature == Features.AUX_FAN:
            return self.info.device_type != "A1" and self.info.device_type != "A1MINI"
        elif feature == Features.CHAMBER_LIGHT:
            return True
        elif feature == Features.CHAMBER_FAN:
            return self.info.device_type == "X1" or self.info.device_type == "X1C" or self.info.device_type == "X1E" or self.info.device_type == "P1P" or self.info.device_type == "P1S"
        elif feature == Features.CHAMBER_TEMPERATURE:
            return self.info.device_type == "X1" or self.info.device_type == "X1C" or self.info.device_type == "X1E"
        elif feature == Features.CURRENT_STAGE:
            return True
        elif feature == Features.PRINT_LAYERS:
            return True
        elif feature == Features.AMS:
            return len(self.ams.data) != 0
        elif feature == Features.EXTERNAL_SPOOL:
            return True
        elif feature == Features.K_VALUE:
            return self.info.device_type == "P1P" or self.info.device_type == "P1S" or self.info.device_type == "A1" or self.info.device_type == "A1MINI"
        elif feature == Features.START_TIME:
            return False
        elif feature == Features.START_TIME_GENERATED:
            return True
        elif feature == Features.AMS_TEMPERATURE:
            return self.info.device_type == "X1" or self.info.device_type == "X1C" or self.info.device_type == "X1E"
        elif feature == Features.CAMERA_RTSP:
            return self.info.device_type == "X1" or self.info.device_type == "X1C" or self.info.device_type == "X1E"
        elif feature == Features.CAMERA_IMAGE:
            return self.info.device_type == "P1P" or self.info.device_type == "P1S" or self.info.device_type == "A1" or self.info.device_type == "A1MINI"
        elif feature == Features.DOOR_SENSOR:
            return self.info.device_type == "X1" or self.info.device_type == "X1C" or self.info.device_type == "X1E"
        elif feature == Features.MANUAL_MODE:
            return self.info.device_type == "P1P" or self.info.device_type == "P1S" or self.info.device_type == "A1" or self.info.device_type == "A1MINI"
        elif feature == Features.AMS_FILAMENT_REMAINING:
            # Technically this is not the AMS Lite but that's currently tied to only these printer types.
            return self.info.device_type != "A1" and self.info.device_type != "A1MINI"
        elif feature == Features.SET_TEMPERATURE:
            return self._supports_temperature_set()
        elif feature == Features.PROMPT_SOUND:
            return self.info.device_type == "A1" or self.info.device_type == "A1MINI"
        elif feature == Features.FTP:
            return True
        elif feature == Features.TIMELAPSE:
            return False

        return False
    
    def get_active_tray(self):
        if self.supports_feature(Features.AMS):
            if self.ams.tray_now == 255:
                return None
            if self.ams.tray_now == 254:
                return self.external_spool
            active_ams = self.ams.data[math.floor(self.ams.tray_now / 4)]
            active_tray = self.ams.tray_now % 4
            return None if active_ams is None else active_ams.tray[active_tray]
        else:
            return self.external_spool

    @property
    def is_external_spool_active(self) -> bool:
        if self.supports_feature(Features.AMS):
            if self.ams.tray_now == 254:
                return True
        else:
            return True
        return False


@dataclass
class Lights:
    """Return all light related info"""
    chamber_light: str
    chamber_light_override: str
    work_light: str

    def __init__(self, client):
        self._client = client
        self.chamber_light = "unknown"
        self.work_light = "unknown"
        self.chamber_light_override = ""

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
        self.work_light = \
            search(data.get("lights_report", []), lambda x: x.get('node', "") == "work_light",
                   {"mode": self.work_light}).get("mode")
        
        return (old_data != f"{self.__dict__}")

    def TurnChamberLightOn(self):
        self.chamber_light = "on"
        self.chamber_light_override = "on"
        self._client.callback("event_light_update")
        self._client.publish(CHAMBER_LIGHT_ON)

    def TurnChamberLightOff(self):
        self.chamber_light = "off"
        self.chamber_light_override = "off"
        self._client.callback("event_light_update")
        self._client.publish(CHAMBER_LIGHT_OFF)


@dataclass
class Camera:
    """Return camera related info"""
    recording: str
    resolution: str
    rtsp_url: str
    timelapse: str

    def __init__(self, client):
        self._client = client
        self.recording = ''
        self.resolution = ''
        self.rtsp_url = None
        self.timelapse = ''

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
        if self._client._enable_camera:
            self.rtsp_url = data.get("ipcam", {}).get("rtsp_url", self.rtsp_url)
        else:
            self.rtsp_url = None
        
        return (old_data != f"{self.__dict__}")

@dataclass
class Temperature:
    """Return all temperature related info"""
    bed_temp: int
    target_bed_temp: int
    chamber_temp: int
    nozzle_temp: int
    target_nozzle_temp: int

    def __init__(self, client):
        self._client = client
        self.bed_temp = 0
        self.target_bed_temp = 0
        self.chamber_temp = 0
        self.nozzle_temp = 0
        self.target_nozzle_temp = 0

    def print_update(self, data) -> bool:
        old_data = f"{self.__dict__}"

        self.bed_temp = round(data.get("bed_temper", self.bed_temp))
        self.target_bed_temp = round(data.get("bed_target_temper", self.target_bed_temp))
        self.chamber_temp = round(data.get("chamber_temper", self.chamber_temp))
        self.nozzle_temp = round(data.get("nozzle_temper", self.nozzle_temp))
        self.target_nozzle_temp = round(data.get("nozzle_target_temper", self.target_nozzle_temp))
        
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
class PrintJob:
    """Return all information related content"""

    print_percentage: int
    gcode_state: str
    file_type_icon: str
    gcode_file: str
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

    @property
    def get_print_weights(self) -> dict:
        values = {}
        if self._client._device.is_external_spool_active:
            values["External Spool"] = self.print_weight
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
        if self._client._device.is_external_spool_active:
            values["External Spool"] = self.print_length
        else:
            for i in range(16):
                if self._ams_print_lengths[i] != 0:
                    ams_index = (i // 4) + 1
                    ams_tray = (i % 4) + 1
                    values[f"AMS {ams_index} Tray {ams_tray}"] = self._ams_print_lengths[i]
        return values

    def __init__(self, client):
        self._client = client
        self.print_percentage = 0
        self.gcode_state = "unknown"
        self.gcode_file = ""
        self.subtask_name = ""
        self.start_time = None
        self.end_time = None
        self.remaining_time = 0
        self.current_layer = 0
        self.total_layers = 0
        self.print_error = 0
        self.print_weight = 0
        self._ams_print_weights = [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0]
        self._ams_print_lengths = [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0]
        self.print_length = 0
        self.print_bed_type = "unknown"
        self.file_type_icon = "mdi:file"
        self.print_type = ""

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
            LOGGER.error(f"Unknown gcode_state. Please log an issue : '{self.gcode_state}'")
            self.gcode_state = "unknown"
        if previous_gcode_state != self.gcode_state:
            LOGGER.debug(f"GCODE_STATE: {previous_gcode_state} -> {self.gcode_state}")
        self.gcode_file = data.get("gcode_file", self.gcode_file)
        self.print_type = data.get("print_type", self.print_type)
        if self.print_type.lower() not in PRINT_TYPE_OPTIONS:
            if self.print_type != "":
                LOGGER.debug(f"Unknown print_type. Please log an issue : '{self.print_type}'")
            self.print_type = "unknown"
        self.subtask_name = data.get("subtask_name", self.subtask_name)
        self.file_type_icon = "mdi:file" if self.print_type != "cloud" else "mdi:cloud-outline"
        self.current_layer = data.get("layer_num", self.current_layer)
        self.total_layers = data.get("total_layer_num", self.total_layers)

        # Initialize task data at startup.
        if previous_gcode_state == "unknown" and self.gcode_state != "unknown":
            self._update_task_data()
            self._download_timelapse()

        # Calculate start / end time after we update task data so we don't stomp on prepopulated values while idle on integration start.
        if data.get("gcode_start_time") is not None:
            if self.start_time != get_start_time(int(data.get("gcode_start_time"))):
                LOGGER.debug(f"GCODE START TIME: {self.start_time}")
            self.start_time = get_start_time(int(data.get("gcode_start_time")))

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

            # Generate the start_time for P1P/S when printer moves from idle to another state. Original attempt with remaining time
            # becoming non-zero didn't work as it never bounced to zero in at least the scenario where a print was canceled.
            if self._client._device.supports_feature(Features.START_TIME_GENERATED):
                # We can use the existing get_end_time helper to format date.now() as desired by passing 0.
                self.start_time = get_end_time(0)
                # Make sure we don't keep using a stale end time.
                self.end_time = None
                LOGGER.debug(f"GENERATED START TIME: {self.start_time}")

            # Update task data
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
                duration = datetime.now() - self.start_time
                # Round usage hours to 2 decimal places (about 1/2 a minute accuracy)
                new_hours = round((duration.seconds / 60 / 60) * 100) / 100
                LOGGER.debug(f"NEW USAGE HOURS: {new_hours}")
                self._client._device.info.usage_hours += new_hours

        return (old_data != f"{self.__dict__}")

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
    #     "deviceModel": "P1P",
    #     "deviceName": "Bambu P1P",
    #     "bedType": "textured_plate"
    #     },

    def _find_model_path(self, ftp):
        if self.gcode_file != '':
            # Attempt to find the model in one of many known directories
            for search_path in ['/', '/cache', '/models', '/sdcard']:
                try:
                    path_contents = ftp.nlst(f"{search_path}")
                    if self.gcode_file in path_contents:
                        model_path = f"{search_path}/{self.gcode_file}"
                        LOGGER.debug(f"Found model {model_path}")
                        return model_path
                except:
                    pass
        else:
            model_path = self._find_latest_file(ftp, '/Cache', ['.3mf'])
            if model_path is not None:
                return model_path

        LOGGER.debug(f"Model '{self.gcode_file}' count not be found in any known directories")
        return None
    
    def _find_latest_file(self, ftp, path, extensions: list):
        # Look for the newest file with extension in directory.
        LOGGER.debug(f"Looking for latest {extensions} file in {path}")
        file_list = []
        def parse_line(line):
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
                    timestamp = timestamp.replace(year=datetime.now().year)
                    if timestamp > datetime.now():
                        timestamp = timestamp.replace(year=datetime.now().year - 1)
                    return timestamp, filename
                else:
                    return None

            match = re.match(pattern_without_time_just_year, line)
            if match:
                timestamp_str, filename = match.groups()
                _, extension = os.path.splitext(filename)
                if extension in extensions:
                    timestamp = datetime.strptime(timestamp_str, '%b %d %Y')
                    return timestamp, filename
                else:
                    return None
            
            LOGGER.debug(f"UNEXPECTED LIST LINE FORMAT: '{line}'")
            return None

        # Attempt to find the model in one of many known directories
        ftp.retrlines(f"LIST {path}", lambda line: file_list.append(file) if (file := parse_line(line)) is not None else None)
        files = sorted(file_list, key=lambda file: file[0], reverse=True)
        for file in files:
            _, extension = os.path.splitext(file[1])
            if extension in extensions:
                file_path = f"{path}/{file[1]}"
                LOGGER.debug(f"Found file {file_path}")
                return file_path

        return None
    
    def _download_timelapse(self):
        # If we are running in connection test mode, skip updating the last print task data.
        if self._client._test_mode:
            return
        if not self._client.timelapse_enabled:
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
        file_path = self._find_latest_file(ftp, '/timelapse', ['.mp4','.avi'])
        if file_path is not None:
            # timelapse_path is of form '/timelapse/foo.mp4'
            local_file_path = os.path.join(f"/config/www/media/ha-bambulab/{self._client._serial}", file_path.lstrip('/'))
            directory_path = os.path.dirname(local_file_path)
            os.makedirs(directory_path, exist_ok=True)

            if os.path.exists(local_file_path):
                LOGGER.debug("Timelapse already downloaded.")
            else:
                with open(local_file_path, 'wb') as f:
                    # Fetch the video from FTP and close the connection
                    LOGGER.info(f"Downloading '{file_path}'")
                    ftp.retrbinary(f"RETR {file_path}", f.write)
                    f.flush()

            # Convert to the thumbnail path.
            directory = os.path.dirname(file_path)
            filename = os.path.basename(file_path)
            filename_without_extension, _ = os.path.splitext(filename)
            filename = f"{filename_without_extension}.jpg"
            file_path = os.path.join(directory, 'thumbnail', filename)
            local_file_path = os.path.join(f"/config/www/media/ha-bambulab/{self._client._serial}/timelapse", filename)
            if os.path.exists(local_file_path):
                LOGGER.debug("Thumbnail already downloaded.")
            else:
                with open(local_file_path, 'wb') as f:
                    # Fetch the video from FTP and close the connection
                    LOGGER.info(f"Downloading '{file_path}'")
                    ftp.retrbinary(f"RETR {file_path}", f.write)
                    f.flush()

        ftp.quit()

        end_time = datetime.now()
        LOGGER.info(f"Done downloading timelapse by FTP. Elapsed time = {(end_time-start_time).seconds}s") 

    def _update_task_data(self):
        # If we are running in connection test mode, skip updating the last print task data.
        if self._client._test_mode:
            return
        
        if self._client.ftp_enabled:
            self._download_task_data_from_printer()
        else:
            self._download_task_data_from_cloud()

    def _download_task_data_from_printer(self):
        thread = threading.Thread(target=self._async_download_task_data_from_printer)
        thread.start()

    def _async_download_task_data_from_printer(self):
        current_thread = threading.current_thread()
        current_thread.setName(f"{self._client._device.info.device_type}-FTP-{threading.get_native_id()}")
        start_time = datetime.now()
        LOGGER.info(f"Updating task data by FTP")

        # Open the FTP connection
        ftp = self._client.ftp_connection()
        model_path = self._find_model_path(ftp)

        # Create a temporary file we can download the 3mf into
        with tempfile.NamedTemporaryFile(delete=True) as f:
            # Fetch the 3mf from FTP and close the connection
            LOGGER.debug(f"Downloading '{model_path}'")
            ftp.retrbinary(f"RETR {model_path}", f.write)
            f.flush()
            ftp.quit()

            # Open the 3mf zip archive
            with ZipFile(f) as archive:
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
                for metadata in plate:
                    if (metadata.get('key') == 'index'):
                        # Index is the plate number being printed
                        plate = metadata.get('value')
                        LOGGER.debug(f"Plate: {plate}")
                        
                        # Now we have the plate number, extract the cover image from the archive
                        self._client._device.cover_image.set_jpeg(archive.read(f"Metadata/plate_{plate}.png"))
                        LOGGER.debug(f"Cover image: Metadata/plate_{plate}.png")
                    elif (metadata.get('key') == 'weight'):
                        LOGGER.debug(f"Weight: {metadata.get('value')}")
                        self.print_weight = metadata.get('value')
                    elif (metadata.get('key') == 'prediction'):
                        # Estimated print length in seconds
                        LOGGER.debug(f"Print time: {metadata.get('value')}s")
                    elif (metadata.tag == 'filament'):
                        # Filament used for the current print job. The plate info does not distinguish
                        # between AMS and External Spool, both AMS Tray 1 and External Spool have
                        # an ID of 1
                        LOGGER.debug(f"AMS Tray {metadata.get('id')}: {metadata.get('used_m')}m | {metadata.get('used_g')}g")
                        
                        # Print weights and lengths expect zero-indexed allocation, reduce the ID by 1
                        ams_index = int(metadata.get('id')) - 1
                        self._ams_print_weights[ams_index] = metadata.get('used_g')
                        self._ams_print_lengths[ams_index] = metadata.get('used_m')
                        
                        # Increase the total print length
                        print_length += float(metadata.get('used_m'))
                
                self.print_length = print_length

            archive.close()

        end_time = datetime.now()
        LOGGER.info(f"Done updating task data by FTP. Elapsed time = {(end_time-start_time).seconds}s") 
        self._client.callback("event_printer_data_update")

    def _download_task_data_from_cloud(self):
        # Must have an auth token for this to be possible
        if self._client.bambu_cloud.auth_token == "":
            return

        self._task_data = self._client.bambu_cloud.get_latest_task_for_printer(self._client._serial)
        if self._task_data is None:
            LOGGER.debug("No bambu cloud task data found for printer.")
            self._client._device.cover_image.set_jpeg(None)
            self.print_weight = 0
            self._ams_print_weights = [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0]
            self._ams_print_lengths = [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0]
            self.print_length = 0
            self.print_bed_type = "unknown"
            self.start_time = None
            self.end_time = None
        else:
            LOGGER.debug("Updating bambu cloud task data found for printer.")
            url = self._task_data.get('cover', '')
            if url != "":
                data = self._client.bambu_cloud.download(url)
                self._client._device.cover_image.set_jpeg(data)

            self.print_length = self._task_data.get('length', self.print_length * 100) / 100
            self.print_bed_type = self._task_data.get('bedType', self.print_bed_type)
            self.print_weight = self._task_data.get('weight', self.print_weight)
            ams_print_data = self._task_data.get('amsDetailMapping', [])
            self._ams_print_weights = [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0]
            self._ams_print_lengths = [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0]
            if self.print_weight != 0:
                for ams_data in ams_print_data:
                    index = ams_data['ams']
                    weight = ams_data['weight']
                    self._ams_print_weights[index] = weight
                    self._ams_print_lengths[index] = self.print_length * weight / self.print_weight

            status = self._task_data['status']
            LOGGER.debug(f"CLOUD PRINT STATUS: {status}")
            if self._client._device.supports_feature(Features.START_TIME_GENERATED) and (status == 4):
                # If we generate the start time (not X1), then rely more heavily on the cloud task data and
                # do so uniformly so we always have matched start/end times.
                # "startTime": "2023-12-21T19:02:16Z"
                
                cloud_time_str = self._task_data.get('startTime', "")
                LOGGER.debug(f"CLOUD START TIME1: {self.start_time}")
                if cloud_time_str != "":
                    local_dt = parser.parse(cloud_time_str).astimezone(tz.tzlocal())
                    # Convert it to timestamp and back to get rid of timezone in printed output to match datetime objects created from mqtt timestamps.
                    local_dt = datetime.fromtimestamp(local_dt.timestamp())
                    self.start_time = local_dt
                    LOGGER.debug(f"CLOUD START TIME2: {self.start_time}")

                # "endTime": "2023-12-21T19:02:35Z"
                cloud_time_str = self._task_data.get('endTime', "")
                LOGGER.debug(f"CLOUD END TIME1: {self.end_time}")
                if cloud_time_str != "":
                    local_dt = parser.parse(cloud_time_str).astimezone(tz.tzlocal())
                    # Convert it to timestamp and back to get rid of timezone in printed output to match datetime objects created from mqtt timestamps.
                    local_dt = datetime.fromtimestamp(local_dt.timestamp())
                    self.end_time = local_dt
                    LOGGER.debug(f"CLOUD END TIME2: {self.end_time}")


@dataclass
class Info:
    """Return all device related content"""

    # Device state
    serial: str
    device_type: str
    wifi_signal: int
    device_type: str
    hw_ver: str
    sw_ver: str
    online: bool
    new_version_state: int
    mqtt_mode: str
    nozzle_diameter: float
    nozzle_type: str
    usage_hours: float
    _ip_address: str

    def __init__(self, client):
        self._client = client

        self.serial = self._client._serial
        self.device_type = self._client._device_type
        self.wifi_signal = 0
        self.hw_ver = "unknown"
        self.sw_ver = "unknown"
        self.online = False
        self.new_version_state = 0
        self.mqtt_mode = "local" if self._client._local_mqtt else "bambu_cloud"
        self.nozzle_diameter = 0
        self.nozzle_type = "unknown"
        self.usage_hours = client._usage_hours
        self._ip_address = client.host

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
        self.device_type = get_printer_type(modules, self.device_type)
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

        self.wifi_signal = int(data.get("wifi_signal", str(self.wifi_signal)).replace("dBm", ""))

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

        self.new_version_state = data.get("upgrade_state", {}).get("new_version_state", self.new_version_state)

        # "nozzle_diameter": "0.4",
        # "nozzle_type": "hardened_steel",
        self.nozzle_diameter = float(data.get("nozzle_diameter", self.nozzle_diameter))
        self.nozzle_type = data.get("nozzle_type", self.nozzle_type)

        #

        return (old_data != f"{self.__dict__}")

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
       

@dataclass
class AMSInstance:
    """Return all AMS instance related info"""
    serial: str
    sw_version: str
    hw_version: str
    humidity_index: int
    temperature: int
    tray: list["AMSTray"]

    def __init__(self, client):
        self.serial = ""
        self.sw_version = ""
        self.hw_version = ""
        self.humidity_index = 0
        self.temperature = 0
        self.tray = [None] * 4
        self.tray[0] = AMSTray(client)
        self.tray[1] = AMSTray(client)
        self.tray[2] = AMSTray(client)
        self.tray[3] = AMSTray(client)


@dataclass
class AMSList:
    """Return all AMS related info"""
    tray_now: int
    data: list[AMSInstance]

    def __init__(self, client):
        self._client = client
        self.tray_now = 0
        self.data = [None] * 4
        self._first_initialization_done = False

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
            if name.startswith("ams/"):
                index = int(name[4])
            elif name.startswith("ams_f1/"):
                index = int(name[7])
            
            if index != -1:
                # Sometimes we get incomplete version data. We have to skip if that occurs since the serial number is
                # required as part of the home assistant device identity.
                if not module['sn'] == '':
                    # May get data before info so create entries if necessary
                    if self.data[index] is None:
                        self.data[index] = AMSInstance(self._client)

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

        if data_changed:
            self._client.callback("event_ams_info_update")

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

        ams_data = data.get("ams", [])
        if len(ams_data) != 0:
            self.tray_now = int(ams_data.get('tray_now', self.tray_now))

            ams_list = ams_data.get("ams", [])
            for ams in ams_list:
                index = int(ams['id'])
                # May get data before info so create entry if necessary
                if self.data[index] is None:
                    self.data[index] = AMSInstance(self._client)

                if self.data[index].humidity_index != int(ams['humidity']):
                    self.data[index].humidity_index = int(ams['humidity'])
                if self.data[index].temperature != float(ams['temp']):
                    self.data[index].temperature = float(ams['temp'])

                tray_list = ams['tray']
                for tray in tray_list:
                    tray_id = int(tray['id'])
                    self.data[index].tray[tray_id].print_update(tray)

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
    remain: int
    k: float
    tag_uid: str
    tray_uuid: str


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
        self.remain = 0
        self.k = 0
        self.tag_uid = ""
        self.tray_uuid = ""

    def print_update(self, data) -> bool:
        old_data = f"{self.__dict__}"

        if len(data) == 1:
            # If the data is exactly one entry then it's just the ID and the tray is empty.
            self.empty = True
            self.idx = ""
            self.name = "Empty"
            self.type = "Empty"
            self.sub_brands = ""
            self.color = "00000000"  # RRGGBBAA
            self.nozzle_temp_min = 0
            self.nozzle_temp_max = 0
            self.remain = 0
            self.tag_uid = ""
            self.tray_uuid = ""
            self.k = 0
        else:
            self.empty = False
            self.idx = data.get('tray_info_idx', self.idx)
            self.name = get_filament_name(self.idx, self._client.slicer_settings.custom_filaments)
            self.type = data.get('tray_type', self.type)
            self.sub_brands = data.get('tray_sub_brands', self.sub_brands)
            self.color = data.get('tray_color', self.color)
            self.nozzle_temp_min = data.get('nozzle_temp_min', self.nozzle_temp_min)
            self.nozzle_temp_max = data.get('nozzle_temp_max', self.nozzle_temp_max)
            self.remain = data.get('remain', self.remain)
            self.tag_uid = data.get('tag_uid', self.tag_uid)
            self.tray_uuid = data.get('tray_uuid', self.tray_uuid)
            self.k = data.get('k', self.k)
        
        return (old_data != f"{self.__dict__}")


@dataclass
class ExternalSpool(AMSTray):
    """Return the virtual tray related info"""

    def __init__(self, client):
        super().__init__(client)
        self._client = client

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

        received_virtual_tray_data = False
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
        self._id = int(data.get("stg_cur", self._id))
        if (self._print_type == "idle") and (self._id == 0):
            # On boot the printer reports stg_cur == 0 incorrectly instead of 255. Attempt to correct for this.
            self._id = 255
        self.description = get_current_stage(self._id)

        return (old_data != f"{self.__dict__}")

@dataclass
class HMSList:
    """Return all HMS related info"""
    _count: int
    _errors: dict

    def __init__(self, client):
        self._client = client
        self._count = 0
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
            self._count = len(hmsList)
            errors = {}
            errors["Count"] = self._count

            index: int = 0
            for hms in hmsList:
                index = index + 1
                attr = int(hms['attr'])
                code = int(hms['code'])
                hms_notif = HMSNotification(user_language=self._client.user_language, attr=attr, code=code)
                errors[f"{index}-Code"] = f"HMS_{hms_notif.hms_code}"
                errors[f"{index}-Error"] = hms_notif.hms_error
                errors[f"{index}-Wiki"] = hms_notif.wiki_url
                errors[f"{index}-Severity"] = hms_notif.severity
                #LOGGER.debug(f"HMS error for '{hms_notif.module}' and severity '{hms_notif.severity}': HMS_{hms_notif.hms_code}")
                #errors[f"{index}-Module"] = hms_notif.module # commented out to avoid bloat with current structure

            if self._errors != errors:
                LOGGER.debug("Updating HMS error list.")
                self._errors = errors
                if self._count != 0:
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
        return self._count

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
                errors[f"error"] = get_print_error_text(code, self._client.user_language)
                # LOGGER.warning(f"PRINT ERRORS: {errors}") # This will emit a message to home assistant log every 1 second if enabled

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

    def __init__(self, user_language: str, attr: int, code: int):
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
        error_text = get_HMS_error_text(code=self.hms_code, language=self._user_language)
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
        self._image_last_updated = datetime.now()

    def set_jpeg(self, bytes):
        self._bytes = bytes
        self._image_last_updated = datetime.now()
        self._client.callback("event_printer_chamber_image_update")

    def get_jpeg(self) -> bytearray:
        return self._bytes.copy()
    
    def get_last_update_time(self) -> datetime:
        return self._image_last_updated
    
    @property
    def available(self):
        return self._client._enable_camera 
    
@dataclass
class CoverImage:
    """Returns the cover image from the Bambu API or FTP"""

    def __init__(self, client):
        self._client = client
        self._bytes = bytearray()
        self._image_last_updated = datetime.now()
        self._client.callback("event_printer_cover_image_update")

    def set_jpeg(self, bytes):
        self._bytes = bytes
        self._image_last_updated = datetime.now()
    
    def get_jpeg(self) -> bytearray:
        return self._bytes

    def get_last_update_time(self) -> datetime:
        return self._image_last_updated


@dataclass
class HomeFlag:
    """Contains parsed _values from the homeflag sensor"""
    _value: int
    _sw_ver: str
    _device_type: str 

    def __init__(self, client):
        self._value = 0
        self._client = client
        self._sw_ver = ""
        self._device_type = ""

    def info_update(self, data):
        modules = data.get("module", [])
        self._device_type = get_printer_type(modules, self._device_type)
        self._sw_ver = get_sw_version(modules, self._sw_ver)

    def print_update(self, data: dict) -> bool:
        old_data = f"{self.__dict__}"
        self._value = int(data.get("home_flag", str(self._value)))
        return (old_data != f"{self.__dict__}")

    @property
    def door_open(self) -> bool or None:
        if not self.door_open_available:
            return None

        return (self._value & Home_Flag_Values.DOOR_OPEN) != 0

    @property
    def door_open_available(self) -> bool:
        if not self._client._device.supports_feature(Features.DOOR_SENSOR):
            return False
        
        if (self._device_type in ["X1", "X1C"] and version.parse(self._sw_ver) < version.parse("01.07.00.00")):
            return False

        return True

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
    def sdcard_present(self) -> bool:
        return (self._value & Home_Flag_Values.SD_CARD_STATE) != SdcardState.NO_SDCARD

    @property
    def sdcard_normal(self) -> bool:
        return self.sdcard_present and (self._value & Home_Flag_Values.HAS_SDCARD_ABNORMAL) != SdcardState.HAS_SDCARD_ABNORMAL
    
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


class SlicerSettings:
    custom_filaments: dict = field(default_factory=dict)

    def __init__(self, client):
        self._client = client
        self.custom_filaments = {}

    def _load_custom_filaments(self, slicer_settings: dict):
        if 'private' in slicer_settings["filament"]:
            for filament in slicer_settings['filament']['private']:
                name = filament["name"]
                if " @" in name:
                    name = name[:name.index(" @")]
                if filament.get("filament_id", "") != "":
                    self.custom_filaments[filament["filament_id"]] = name
            LOGGER.debug("Got custom filaments: %s", self.custom_filaments)

    def update(self):
        self.custom_filaments = {}
        if self._client.bambu_cloud.auth_token != "":
            LOGGER.debug("Loading slicer settings")
            slicer_settings = self._client.bambu_cloud.get_slicer_settings()
            if slicer_settings is not None:
                self._load_custom_filaments(slicer_settings)
