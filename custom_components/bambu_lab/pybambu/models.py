import math

from dataclasses import dataclass
from datetime import datetime

from .utils import \
    search, \
    fan_percentage, \
    fan_percentage_to_gcode, \
    get_filament_name, \
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
        self.info = Info(client, device_type, serial)
        self.fans = Fans(client)
        self.speed = Speed(client)
        self.stage = StageAction()
        self.ams = AMSList(client)
        self.external_spool = ExternalSpool(client)
        self.hms = HMSList(client)
        self.camera = Camera()
        self._active_tray = None
        self.push_all_data = None
        self.get_version_data = None
        if self.supports_feature(Features.CAMERA_IMAGE):
            self.p1p_camera = P1PCamera(client)

    def print_update(self, data):
        """Update from dict"""
        self.info.print_update(self, data)
        self.temperature.print_update(data)
        self.lights.print_update(data)
        self.fans.print_update(data)
        self.speed.print_update(data)
        self.stage.print_update(data)
        self.ams.print_update(data)
        self.external_spool.print_update(data)
        self.hms.print_update(data)
        self.camera.print_update(data)
        if self.client.callback is not None:
            self.client.callback("event_printer_data_update")
        if data.get("msg") == 0:
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
                return self.info.device_type == "X1" or self.info.device_type == "X1C" or self.info.device_type == "P1P" or self.info.device_type == "P1S"
            case Features.CHAMBER_TEMPERATURE:
                return self.info.device_type == "X1" or self.info.device_type == "X1C"
            case Features.CURRENT_STAGE:
                return True
            case Features.PRINT_LAYERS:
                return True
            case Features.AMS:
                return len(self.ams.data) != 0
            case Features.EXTERNAL_SPOOL:
                return True
            case Features.K_VALUE:
                return self.info.device_type == "P1P" or self.info.device_type == "P1S" or self.info.device_type == "A1Mini"
            case Features.START_TIME:
                return self.info.device_type == "X1" or self.info.device_type == "X1C"
            case Features.START_TIME_GENERATED:
                return self.info.device_type == "P1P" or self.info.device_type == "P1S" or self.info.device_type == "A1Mini"
            case Features.AMS_TEMPERATURE:
                return self.info.device_type == "X1" or self.info.device_type == "X1C"
            case Features.CAMERA_RTSP:
                return self.info.device_type == "X1" or self.info.device_type == "X1C"
            case Features.CAMERA_IMAGE:
                return (self.client.host != "us.mqtt.bambulab.com") and (self.info.device_type == "P1P" or self.info.device_type == "P1S" or self.info.device_type == "A1Mini")
        return False
    
    def get_active_tray(self):
        if self.supports_feature(Features.AMS):
            if self.ams.tray_now == 255:
                return None
            if self.ams.tray_now == 254:
                return self.external_spool
            active_ams = self.ams.data[math.floor(self.ams.tray_now / 4)]
            active_tray = self.ams.tray_now % 4
            return active_ams.tray[active_tray]
        else:
            return self.external_spool

@dataclass
class Lights:
    """Return all light related info"""
    chamber_light: str
    work_light: str

    def __init__(self, client):
        self.client = client
        self.chamber_light = "unknown"
        self.work_light = "unknown"

    def print_update(self, data):
        """Update from dict"""

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

        self.chamber_light = \
            search(data.get("lights_report", []), lambda x: x.get('node', "") == "chamber_light",
                   {"mode": self.chamber_light}).get("mode")
        self.work_light = \
            search(data.get("lights_report", []), lambda x: x.get('node', "") == "work_light",
                   {"mode": self.work_light}).get("mode")

    def TurnChamberLightOn(self):
        self.chamber_light = "on"
        if self.client.callback is not None:
            self.client.callback("event_light_update")
        self.client.publish(CHAMBER_LIGHT_ON)

    def TurnChamberLightOff(self):
        self.chamber_light = "off"
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

    def print_update(self, data):
        """Update from dict"""
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

    def print_update(self, data):
        """Update from dict"""

        self.bed_temp = round(data.get("bed_temper", self.bed_temp))
        self.target_bed_temp = round(data.get("bed_target_temper", self.target_bed_temp))
        self.chamber_temp = round(data.get("chamber_temper", self.chamber_temp))
        self.nozzle_temp = round(data.get("nozzle_temper", self.nozzle_temp))
        self.target_nozzle_temp = round(data.get("nozzle_target_temper", self.target_nozzle_temp))


@dataclass
class Fans:
    """Return all fan related info"""
    aux_fan_speed: int
    _aux_fan_speed: int
    chamber_fan_speed: int
    _chamber_fan_speed: int
    cooling_fan_speed: int
    _cooling_fan_speed: int
    heatbreak_fan_speed: int
    _heatbreak_fan_speed: int

    def __init__(self, client):
        self.client = client
        self.aux_fan_speed = 0
        self._aux_fan_speed = 0
        self.chamber_fan_speed = 0
        self._chamber_fan_speed = 0
        self.cooling_fan_speed = 0
        self._cooling_fan_speed = 0
        self.heatbreak_fan_speed = 0
        self._heatbreak_fan_speed = 0

    def print_update(self, data):
        """Update from dict"""
        self._aux_fan_speed = data.get("big_fan1_speed", self._aux_fan_speed)
        self.aux_fan_speed = fan_percentage(self._aux_fan_speed)
        self._chamber_fan_speed = data.get("big_fan2_speed", self._chamber_fan_speed)
        self.chamber_fan_speed = fan_percentage(self._chamber_fan_speed)
        self._cooling_fan_speed = data.get("cooling_fan_speed", self._cooling_fan_speed)
        self.cooling_fan_speed = fan_percentage(self._cooling_fan_speed)
        self._heatbreak_fan_speed = data.get("heatbreak_fan_speed", self._heatbreak_fan_speed)
        self.heatbreak_fan_speed = fan_percentage(self._heatbreak_fan_speed)

    def SetFanSpeed(self, fan: FansEnum, percentage: int):
        """Set fan speed"""
        command = fan_percentage_to_gcode(fan, percentage)
        LOGGER.debug(command)
        self.client.publish(command)


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
    start_time: str
    end_time: str
    current_layer: int
    total_layers: int
    online: bool
    new_version_state: int
    print_error: int

    def __init__(self, client, device_type, serial):
        self.client = client
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
        self.end_time = ""
        self.start_time = ""
        self.current_layer = 0
        self.total_layers = 0
        self.online = False
        self.mqtt_mode = "local" if self.client._username == "bblp" else "bambu_cloud"
        self.new_version_state = 0
        self.print_error = 0

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

        self.hw_ver = get_hw_version(data.get("module", []), self.hw_ver)
        self.sw_ver = get_sw_version(data.get("module", []), self.sw_ver)
        if self.client.callback is not None:
            self.client.callback("event_printer_info_update")

    def print_update(self, device, data):
        """Update from dict"""

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

        # Handle print start
        if previous_gcode_state != "PREPARE" and self.gcode_state == "PREPARE":
            if self.client.callback is not None:
               self.client.callback("event_print_started")

            # Generate the start_time for P1P/S when printer moves from idle to another state. Original attempt with remaining time
            # becoming non-zero didn't work as it never bounced to zero in at least the scenario where a print was canceled.
            if device.supports_feature(Features.START_TIME_GENERATED):
                # We can use the existing get_end_time helper to format date.now() as desired by passing 0.
                self.start_time = get_end_time(0)

        # Handle print failed
        if previous_gcode_state != "unknown" and previous_gcode_state != "FAILED" and self.gcode_state == "FAILED":
            if self.client.callback is not None:
               self.client.callback("event_print_failed")

        # Handle print finish
        if previous_gcode_state != "unknown" and previous_gcode_state != "FINISH" and self.gcode_state == "FINISH":
            if self.client.callback is not None:
               self.client.callback("event_print_finished")

        # When a print is canceled by the user, this is the payload that's sent. A couple of seconds later
        # print_error will be reset to zero.
        # {
        #     "print": {
        #         "print_error": 50348044,
        #     }
        # }
        if data.get("print_error") == 50348044 and self.print_error == 0:
            if self.client.callback is not None:
               self.client.callback("event_print_canceled")
        self.print_error = data.get("print_error", self.print_error)

        # Version data is provided differently for X1 and P1
        # P!P example:
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
        self.data = []

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
                    # May get data before info so create entry if necessary
                    if len(self.data) <= index:
                        received_ams_info = True
                        self.data.append(AMSInstance())
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

    def print_update(self, data):
        """Update from dict"""

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
                received_ams_data = True
                index = int(ams['id'])
                # May get data before info so create entry if necessary
                if len(self.data) <= index:
                    self.data.append(AMSInstance())
                self.data[index].humidity_index = int(ams['humidity'])
                self.data[index].temperature = float(ams['temp'])

                tray_list = ams['tray']
                for tray in tray_list:
                    tray_id = int(tray['id'])
                    self.data[index].tray[tray_id].print_update(tray)

        if received_ams_data:
            if self.client.callback is not None:
                self.client.callback("event_ams_data_update")


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
        self.k = 0

    def print_update(self, data):
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
            self.k = data.get('k', self.k)


@dataclass
class ExternalSpool(AMSTray):
    """Return the virtual tray related info"""

    def __init__(self, client):
        super().__init__()
        self.client = client

    def print_update(self, data):
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
            received_virtual_tray_data = True
            super().print_update(tray_data)

        if received_virtual_tray_data:
            if self.client.callback is not None:
                self.client.callback("event_virtual_tray_data_update")


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

    def print_update(self, data):
        """Update from dict"""
        self._id = int(data.get("spd_lvl", self._id))
        self.name = get_speed_name(self._id)
        self.modifier = int(data.get("spd_mag", self.modifier))

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
        self._id = 99
        self._print_type = ""
        self.description = get_stage_action(self._id)

    def print_update(self, data):
        """Update from dict"""
        self._print_type = data.get("print_type", self._print_type)
        self._id = int(data.get("stg_cur", self._id))
        if (self._print_type == "idle") and (self._id == 0):
            # On boot the printer reports stg_cur == 0 incorrectly instead of 255. Attempt to correct for this.
            self._id = 255
        self.description = get_stage_action(self._id)


@dataclass
class HMSList:
    """Return all HMS related info"""

    def __init__(self, client):
        self.client = client
        self.count = 0
        self.errors = {}

    def print_update(self, data):
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
                LOGGER.warning(f"HMS ERROR: HMS_{hms_error} : {get_HMS_error_text(hms_error)}")
                errors[f"{index}-Error"] = f"HMS_{hms_error}: {get_HMS_error_text(hms_error)}"
                errors[f"{index}-Wiki"] = f"https://wiki.bambulab.com/en/x1/troubleshooting/hmscode/{get_generic_AMS_HMS_error_code(hms_error)}"

            if self.errors != errors:
                self.errors = errors
                if self.client.callback is not None:
                    self.client.callback("event_hms_errors")

@dataclass
class P1PCamera:
    """Returns the latest jpeg date from the P1P camera"""
    def __init__(self, client):
        self.client = client
        self._bytes = bytearray()

    def on_jpeg_received(self, bytes):
        self._bytes = bytes
        self.client.callback("p1p_jpeg_received")
    
    def get_jpeg(self) -> bytearray:
        return self._bytes