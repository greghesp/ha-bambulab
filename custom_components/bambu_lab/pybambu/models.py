import math

from dataclasses import dataclass
from datetime import datetime

from .utils import \
    search, \
    fan_percentage, \
    fan_percentage_to_gcode, \
    get_filament_name, \
    get_printer_type, \
    get_speed_name, \
    get_stage_action, \
    get_hw_version, \
    get_sw_version, \
    get_start_time, \
    get_end_time, \
    get_HMS_error_text, \
    get_generic_AMS_HMS_error_code
    
from .const import LOGGER, Features, FansEnum, SPEED_PROFILE
from .commands import CHAMBER_LIGHT_ON, CHAMBER_LIGHT_OFF, SPEED_PROFILE_TEMPLATE

class Device:
    def __init__(self, client, device_type, serial):
        self.client = client
        self.temperature = Temperature()
        self.lights = Lights(client)
        self.info = Info(client = client, device = self, device_type = device_type, serial = serial)
        self.fans = Fans(client)
        self.speed = Speed(client)
        self.stage = StageAction()
        self.ams = AMSList(client)
        self.external_spool = ExternalSpool(client)
        self.hms = HMSList(client)
        self.camera = Camera()
        self.push_all_data = None
        self.get_version_data = None
        if self.supports_feature(Features.CAMERA_IMAGE):
            self.chamber_image = ChamberImage(client)
        self.cover_image = CoverImage(client)

    def print_update(self, data) -> bool:
        """Update from dict"""

        send_event = False
        send_event = send_event | self.info.print_update(self, data)
        send_event = send_event | self.temperature.print_update(data)
        send_event = send_event | self.lights.print_update(data)
        send_event = send_event | self.fans.print_update(data)
        send_event = send_event | self.speed.print_update(data)
        send_event = send_event | self.stage.print_update(data)
        send_event = send_event | self.ams.print_update(data)
        send_event = send_event | self.external_spool.print_update(data)
        send_event = send_event | self.hms.print_update(data)
        send_event = send_event | self.camera.print_update(data)

        if send_event and self.client.callback is not None:
            self.client.callback("event_printer_data_update")

        if data.get("msg", 0) == 0:
            self.push_all_data = data

    def info_update(self, data):
        """Update from dict"""
        self.info.info_update(data)
        self.ams.info_update(data)
        if data.get("command") == "get_version":
            self.get_version_data = data

    def supports_feature(self, feature):
        match feature:
            case Features.AUX_FAN:
                return True
            case Features.CHAMBER_LIGHT:
                return True
            case Features.CHAMBER_FAN:
                return self.info.device_type == "X1" or self.info.device_type == "X1C" or self.info.device_type == "X1E" or self.info.device_type == "P1P" or self.info.device_type == "P1S"
            case Features.CHAMBER_TEMPERATURE:
                return self.info.device_type == "X1" or self.info.device_type == "X1C" or self.info.device_type == "X1E"
            case Features.CURRENT_STAGE:
                return True
            case Features.PRINT_LAYERS:
                return True
            case Features.AMS:
                return len(self.ams.data) != 0
            case Features.EXTERNAL_SPOOL:
                return True
            case Features.K_VALUE:
                return self.info.device_type == "P1P" or self.info.device_type == "P1S" or self.info.device_type == "A1" or self.info.device_type == "A1Mini"
            case Features.START_TIME:
                return self.info.device_type == "X1" or self.info.device_type == "X1C" or self.info.device_type == "X1E"
            case Features.START_TIME_GENERATED:
                return self.info.device_type == "P1P" or self.info.device_type == "P1S" or self.info.device_type == "A1" or self.info.device_type == "A1Mini"
            case Features.AMS_TEMPERATURE:
                return self.info.device_type == "X1" or self.info.device_type == "X1C" or self.info.device_type == "X1E"
            case Features.CAMERA_RTSP:
                return self.info.device_type == "X1" or self.info.device_type == "X1C" or self.info.device_type == "X1E"
            case Features.CAMERA_IMAGE:
                return (self.client.host != "") and (self.client._access_code != "") and (self.info.device_type == "P1P" or self.info.device_type == "P1S" or self.info.device_type == "A1" or self.info.device_type == "A1Mini")
            case Features.MANUAL_MODE:
                return self.info.device_type == "P1P" or self.info.device_type == "P1S" or self.info.device_type == "A1" or self.info.device_type == "A1Mini"

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

@dataclass
class Lights:
    """Return all light related info"""
    chamber_light: str
    chamber_light_override: str
    work_light: str

    def __init__(self, client):
        self.client = client
        self.chamber_light = "unknown"
        self.work_light = "unknown"
        self.chamber_light_override = ""

    def print_update(self, data) -> bool:
        """Update from dict"""
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
        if self.client.callback is not None:
            self.client.callback("event_light_update")
        self.client.publish(CHAMBER_LIGHT_ON)

    def TurnChamberLightOff(self):
        self.chamber_light = "off"
        self.chamber_light_override = "off"
        if self.client.callback is not None:
            self.client.callback("event_light_update")
        self.client.publish(CHAMBER_LIGHT_OFF)


@dataclass
class Camera:
    """Return camera related info"""
    recording: str
    resolution: str
    rtsp_url: str
    timelapse: str

    def __init__(self):
        self.recording = ''
        self.resolution = ''
        self.rtsp_url = None
        self.timelapse = ''

    def print_update(self, data) -> bool:
        """Update from dict"""
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
        
        return (old_data != f"{self.__dict__}")

@dataclass
class Temperature:
    """Return all temperature related info"""
    bed_temp: int
    target_bed_temp: int
    chamber_temp: int
    nozzle_temp: int
    target_nozzle_temp: int

    def __init__(self):
        self.bed_temp = 0
        self.target_bed_temp = 0
        self.chamber_temp = 0
        self.nozzle_temp = 0
        self.target_nozzle_temp = 0

    def print_update(self, data) -> bool:
        """Update from dict"""
        old_data = f"{self.__dict__}"

        self.bed_temp = round(data.get("bed_temper", self.bed_temp))
        self.target_bed_temp = round(data.get("bed_target_temper", self.target_bed_temp))
        self.chamber_temp = round(data.get("chamber_temper", self.chamber_temp))
        self.nozzle_temp = round(data.get("nozzle_temper", self.nozzle_temp))
        self.target_nozzle_temp = round(data.get("nozzle_target_temper", self.target_nozzle_temp))
        
        return (old_data != f"{self.__dict__}")

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
        self.client = client
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
        """Update from dict"""
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

        match fan:
            case FansEnum.PART_COOLING:
                self._cooling_fan_speed = percentage
                self._cooling_fan_speed_override_time = datetime.now()
            case FansEnum.AUXILIARY:
                self._aux_fan_speed_override = percentage
                self._aux_fan_speed_override_time = datetime.now()
            case FansEnum.CHAMBER:
                self._chamber_fan_speed_override = percentage
                self._chamber_fan_speed_override_time = datetime.now()

        LOGGER.debug(command)
        self.client.publish(command)

        if self.client.callback is not None:
            self.client.callback("event_printer_data_update")

    def get_fan_speed(self, fan: FansEnum) -> int:
        match fan:
            case FansEnum.PART_COOLING:
                if self._cooling_fan_speed_override_time is not None:
                    return self._cooling_fan_speed_override
                else:
                    return self._cooling_fan_speed_percentage
            case FansEnum.AUXILIARY:
                if self._aux_fan_speed_override_time is not None:
                    return self._aux_fan_speed_override
                else:
                    return self._aux_fan_speed_percentage
            case FansEnum.CHAMBER:
                if self._chamber_fan_speed_override_time is not None:
                    return self._chamber_fan_speed_override
                else:
                    return self._chamber_fan_speed_percentage
            case FansEnum.HEATBREAK:
                return self._heatbreak_fan_speed_percentage

@dataclass
class Info:
    """Return all information related content"""
    wifi_signal: int
    print_percentage: int
    device_type: str
    hw_ver: str
    sw_ver: str
    gcode_state: str
    remaining_time: int
    start_time: datetime
    end_time: datetime
    current_layer: int
    total_layers: int
    online: bool
    new_version_state: int
    print_error: int
    _cover_url: str

    def __init__(self, device, client, device_type, serial):
        self.client = client
        self.device = device
        self.wifi_signal = 0
        self.print_percentage = 0
        self.device_type = device_type
        self.hw_ver = "unknown"
        self.sw_ver = "unknown"
        self.gcode_state = "unknown"
        self.gcode_file = ""
        self.subtask_name = ""
        self.serial = serial
        self.remaining_time = -1
        self.end_time = None
        self.start_time = None
        self.current_layer = 0
        self.total_layers = 0
        self.online = False
        self.mqtt_mode = "local" if self.client._local_mqtt else "bambu_cloud"
        self.new_version_state = 0
        self.print_error = 0
        self._cover_url = ""
        self.print_weight = 0
        self.print_length = 0
        self.print_bed_type = "unknown"

    def set_online(self, online):
        if self.online != online:
            self.online = online
            if self.client.callback is not None:
                self.client.callback("event_printer_data_update")

    def info_update(self, data):
        """Update from dict"""

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
        self.hw_ver = get_hw_version(modules, self.hw_ver)
        self.sw_ver = get_sw_version(modules, self.sw_ver)
        if self.client.callback is not None:
            self.client.callback("event_printer_info_update")

    def print_update(self, device, data) -> bool:
        """Update from dict"""
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
        self.print_percentage = data.get("mc_percent", self.print_percentage)
        previous_gcode_state = self.gcode_state
        self.gcode_state = data.get("gcode_state", self.gcode_state)
        if self.gcode_state == "":
            self.gcode_state = "unknown"
        self.gcode_file = data.get("gcode_file", self.gcode_file)
        self.subtask_name = data.get("subtask_name", self.subtask_name)

        if data.get("mc_remaining_time") is not None:
            existing_remaining_time = self.remaining_time
            self.remaining_time = data.get("mc_remaining_time")
            if existing_remaining_time != self.remaining_time:
                self.end_time = get_end_time(self.remaining_time)

        self.current_layer = data.get("layer_num", self.current_layer)
        self.total_layers = data.get("total_layer_num", self.total_layers)

        # Generate the end_time from the remaining_time mqtt payload value if present.
        if data.get("gcode_start_time") is not None:
            self.start_time = get_start_time(int(data.get("gcode_start_time")))

        # Initialize task data at startup.
        if previous_gcode_state == "unknown" and self.gcode_state != "unknown":
            self._update_task_data()

        # Handle print start
        previously_idle = previous_gcode_state == "IDLE" or previous_gcode_state == "FAILED" or previous_gcode_state == "FINISH"
        currently_idle = self.gcode_state == "IDLE" or self.gcode_state == "FAILED" or self.gcode_state == "FINISH"

        if previously_idle and not currently_idle:
            if self.client.callback is not None:
               self.client.callback("event_print_started")

            # Generate the start_time for P1P/S when printer moves from idle to another state. Original attempt with remaining time
            # becoming non-zero didn't work as it never bounced to zero in at least the scenario where a print was canceled.
            if device.supports_feature(Features.START_TIME_GENERATED):
                # We can use the existing get_end_time helper to format date.now() as desired by passing 0.
                self.start_time = get_end_time(0)

            # Update task data if bambu cloud connected
            self._update_task_data()

        # When a print is canceled by the user, this is the payload that's sent. A couple of seconds later
        # print_error will be reset to zero.
        # {
        #     "print": {
        #         "print_error": 50348044,
        #     }
        # }
        isCanceledPrint = False
        if data.get("print_error") == 50348044 and self.print_error == 0:
            isCanceledPrint = True
            if self.client.callback is not None:
               self.client.callback("event_print_canceled")
        self.print_error = data.get("print_error", self.print_error)

        # Handle print failed
        if previous_gcode_state != "unknown" and previous_gcode_state != "FAILED" and self.gcode_state == "FAILED":
            if not isCanceledPrint:
                if self.client.callback is not None:
                   self.client.callback("event_print_failed")

        # Handle print finish
        if previous_gcode_state != "unknown" and previous_gcode_state != "FINISH" and self.gcode_state == "FINISH":
            if self.client.callback is not None:
               self.client.callback("event_print_finished")

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

    def _update_task_data(self):
        if self.has_bambu_cloud_connection:
            LOGGER.debug("Updating cloud task data")
            self._task_data = self.client.bambu_cloud.get_tasklist_for_printer(self.serial)
            url = self._task_data.get('cover', '')
            if url != "":
                data = self.client.bambu_cloud.download(url)
                self.device.cover_image.set_jpeg(data)

            self.print_weight = self._task_data.get('weight', self.print_weight)
            self.print_length = self._task_data.get('length', self.print_length)
            self.print_bed_type = self._task_data.get('bedType', self.print_bed_type)

    @property
    def has_bambu_cloud_connection(self) -> bool:
        return self.client.bambu_cloud.auth_token != ""

@dataclass
class AMSInstance:
    """Return all AMS instance related info"""

    def __init__(self):
        self.serial = ""
        self.sw_version = ""
        self.hw_version = ""
        self.humidity_index = 0
        self.temperature = 0
        self.tray = [None] * 4
        self.tray[0] = AMSTray()
        self.tray[1] = AMSTray()
        self.tray[2] = AMSTray()
        self.tray[3] = AMSTray()


@dataclass
class AMSList:
    """Return all AMS related info"""

    def __init__(self, client):
        self.client = client
        self.tray_now = 0
        self.data = [None] * 4

    def info_update(self, data):
        """Update from dict"""

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

        received_ams_info = False
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
                # requires as part of the home assistant device identity.
                if not module['sn'] == '':
                    # May get data before info so create entries if necessary
                    if self.data[index] is None:
                        self.data[index] = AMSInstance()

                    if self.data[index].serial != module['sn']:
                        received_ams_info = True
                        self.data[index].serial = module['sn']
                    if self.data[index].sw_version != module['sw_ver']:
                        received_ams_info = True
                        self.data[index].sw_version = module['sw_ver']
                    if self.data[index].hw_version != module['hw_ver']:
                        received_ams_info = True
                        self.data[index].hw_version = module['hw_ver']

        if received_ams_info:
            if self.client.callback is not None:
                self.client.callback("event_ams_info_update")

    def print_update(self, data) -> bool:
        """Update from dict"""
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

        received_ams_data = False
        ams_data = data.get("ams", [])
        if len(ams_data) != 0:
            self.tray_now = int(ams_data.get('tray_now', self.tray_now))

            ams_list = ams_data.get("ams", [])
            for ams in ams_list:
                index = int(ams['id'])
                # May get data before info so create entry if necessary
                if self.data[index] is None:
                    self.data[index] = AMSInstance()

                if self.data[index].humidity_index != int(ams['humidity']):
                    received_ams_data = True
                    self.data[index].humidity_index = int(ams['humidity'])
                if self.data[index].temperature != float(ams['temp']):
                    received_ams_data = True
                    self.data[index].temperature = float(ams['temp'])

                tray_list = ams['tray']
                for tray in tray_list:
                    tray_id = int(tray['id'])
                    received_ams_data = received_ams_data | self.data[index].tray[tray_id].print_update(tray)

        return received_ams_data

@dataclass
class AMSTray:
    """Return all AMS tray related info"""

    def __init__(self):
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
        self.tag_uid = "0000000000000000"

    def print_update(self, data) -> bool:
        """Update from dict"""
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
            self.tag_uid = "0000000000000000"
            self.k = 0
        else:
            self.empty = False
            self.idx = data.get('tray_info_idx', self.idx)
            self.name = get_filament_name(self.idx)
            self.type = data.get('tray_type', self.type)
            self.sub_brands = data.get('tray_sub_brands', self.sub_brands)
            self.color = data.get('tray_color', self.color)
            self.nozzle_temp_min = data.get('nozzle_temp_min', self.nozzle_temp_min)
            self.nozzle_temp_max = data.get('nozzle_temp_max', self.nozzle_temp_max)
            self.remain = data.get('remain', self.remain)
            self.tag_uid = data.get('tag_uid', self.tag_uid)
            self.k = data.get('k', self.k)
        
        return (old_data != f"{self.__dict__}")


@dataclass
class ExternalSpool(AMSTray):
    """Return the virtual tray related info"""

    def __init__(self, client):
        super().__init__()
        self.client = client

    def print_update(self, data) -> bool:
        """Update from dict"""

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
        """Load from dict"""
        self.client = client
        self._id = 2
        self.name = get_speed_name(2)
        self.modifier = 100

    def print_update(self, data) -> bool:
        """Update from dict"""
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
                self.client.publish(command)
                if self.client.callback is not None:
                    self.client.callback("event_speed_update")


@dataclass
class StageAction:
    """Return Stage Action information"""
    _id: int
    _print_type: str
    description: str

    def __init__(self):
        """Load from dict"""
        self._id = 255
        self._print_type = ""
        self.description = get_stage_action(self._id)

    def print_update(self, data) -> bool:
        """Update from dict"""
        old_data = f"{self.__dict__}"

        self._print_type = data.get("print_type", self._print_type)
        self._id = int(data.get("stg_cur", self._id))
        if (self._print_type == "idle") and (self._id == 0):
            # On boot the printer reports stg_cur == 0 incorrectly instead of 255. Attempt to correct for this.
            self._id = 255
        self.description = get_stage_action(self._id)

        return (old_data != f"{self.__dict__}")

@dataclass
class HMSList:
    """Return all HMS related info"""

    def __init__(self, client):
        self.client = client
        self.count = 0
        self.errors = {}
        self.errors["Count"] = 0
        
    def print_update(self, data) -> bool:
        """Update from dict"""

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
            self.count = len(hmsList)
            errors = {}
            errors["Count"] = self.count

            index: int = 0
            for hms in hmsList:
                index = index + 1
                attr = hms['attr']
                code = hms['code']
                hms_error = f'{int(attr / 0x10000):0>4X}_{attr & 0xFFFF:0>4X}_{int(code / 0x10000):0>4X}_{code & 0xFFFF:0>4X}'  # 0300_0100_0001_0007
                errors[f"{index}-Error"] = f"HMS_{hms_error}: {get_HMS_error_text(hms_error)}"
                errors[f"{index}-Wiki"] = f"https://wiki.bambulab.com/en/x1/troubleshooting/hmscode/{get_generic_AMS_HMS_error_code(hms_error)}"

            if self.errors != errors:
                self.errors = errors
                if self.count != 0:
                    LOGGER.warning(f"HMS ERRORS: {errors}")
                if self.client.callback is not None:
                    self.client.callback("event_hms_errors")
                return True
        
        return False

@dataclass
class ChamberImage:
    """Returns the latest jpeg data from the P1P camera"""
    def __init__(self, client):
        self.client = client
        self._bytes = bytearray()
        self._image_last_updated = datetime.now()

    def set_jpeg(self, bytes):
        LOGGER.debug(f"JPEG RECEIVED: {self.client._device.info.device_type}")
        self._bytes = bytes
        self._image_last_updated = datetime.now()
        if self.client.callback is not None:
            self.client.callback("event_printer_chamber_image_update")
    
    def get_jpeg(self) -> bytearray:
        return self._bytes
    
    def get_last_update_time(self) -> datetime:
        return self._image_last_updated
    
@dataclass
class CoverImage:
    """Returns the cover image from the Bambu API"""

    def __init__(self, client):
        self.client = client
        self._bytes = bytearray()
        self._image_last_updated = datetime.now()
        if self.client.callback is not None:
            self.client.callback("event_printer_cover_image_update")

    def set_jpeg(self, bytes):
        self._bytes = bytes
        self._image_last_updated = datetime.now()
    
    def get_jpeg(self) -> bytearray:
        return self._bytes

    def get_last_update_time(self) -> datetime:
        return self._image_last_updated