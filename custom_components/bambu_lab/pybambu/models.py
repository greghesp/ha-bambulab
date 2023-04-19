from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry

from dataclasses import dataclass
from .utils import search, fan_percentage, get_filament_name, get_speed_name, get_stage_action, get_printer_type, get_hw_version, \
    get_sw_version, start_time, end_time, get_HMS_error_text
from .const import LOGGER, Features
from .commands import CHAMBER_LIGHT_ON, CHAMBER_LIGHT_OFF

import asyncio


class Device:
    def __init__(self, client, device_type, serial):
        self.client = client
        self.temperature = Temperature()
        self.lights = Lights(client)
        self.info = Info(client, device_type, serial)
        self.fans = Fans()
        self.speed = Speed()
        self.stage = StageAction()
        self.ams = AMSList(client)
        self.external_spool = ExternalSpool(client)
        self.hms = HMSList()

    def print_update(self, data):
        """Update from dict"""
        self.info.print_update(data)
        self.temperature.print_update(data)
        self.lights.print_update(data)
        self.fans.print_update(data)
        self.speed.print_update(data)
        self.stage.print_update(data)
        self.ams.print_update(data)
        self.external_spool.print_update(data)
        self.hms.print_update(data)
        self.client.callback("event_printer_data_update")

    def info_update(self, data):
        """Update from dict"""
        self.info.info_update(data)
        self.ams.info_update(data)

    def mc_print_update(self, data):
        """Update from dict"""
        self.ams.mc_print_update(data)

    def supports_feature(self, feature):
        if feature == Features.AUX_FAN:
            return self.info.device_type == "X1" or self.info.device_type == "X1C" or self.info.device_type == "P1P"
        if feature == Features.CHAMBER_LIGHT:
            return self.info.device_type == "X1" or self.info.device_type == "X1C" or self.info.device_type == "P1P"
        if feature == Features.CHAMBER_FAN:
            return self.info.device_type == "X1" or self.info.device_type == "X1C"
        if feature == Features.CHAMBER_TEMPERATURE:
            return self.info.device_type == "X1" or self.info.device_type == "X1C"
        if feature == Features.CURRENT_STAGE:
            return self.info.device_type == "X1" or self.info.device_type == "X1C" or self.info.device_type == "P1P"
        if feature == Features.PRINT_LAYERS:
            return self.info.device_type == "X1" or self.info.device_type == "X1C"
        if feature == Features.AMS:
            return len(self.ams.data) != 0
        if feature == Features.EXTERNAL_SPOOL:
            return self.info.device_type == "P1P"
        if feature == Features.K_VALUE:
            return self.info.device_type == "P1P"
        if feature == Features.START_TIME:
            return self.info.device_type == "X1" or self.info.device_type == "X1C"
        if feature == Features.AMS_TEMPERATURE:
            return self.info.device_type == "X1" or self.info.device_type == "X1C"
        if feature == Features.AMS_RAW_HUMIDITY:
            return self.info.device_type == "X1" or self.info.device_type == "X1C"
        return False


@dataclass
class Lights:
    """Return all light related info"""
    chamber_light: str
    work_light: str

    def __init__(self, client):
        self.client = client
        self.chamber_light = "Unknown"
        self.work_light = "Unknown"

    def print_update(self, data):
        """Update from dict"""

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

    def __init__(self):
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
    timelapse: str

    def __init__(self, client, device_type, serial):
        self.client = client
        self.wifi_signal = 0
        self.print_percentage = 0
        self.device_type = device_type
        self.hw_ver = "Unknown"
        self.sw_ver = "Unknown"
        self.gcode_state = "Unknown"
        self.serial = serial
        self.remaining_time = 0
        self.end_time = 0
        self.start_time = 0
        self.current_layer = 0
        self.total_layers = 0
        self.timelapse = ""

    def info_update(self, data):
        """Update from dict"""
        self.wifi_signal = int(data.get("wifi_signal", str(self.wifi_signal)).replace("dBm", ""))
        self.print_percentage = data.get("mc_percent", self.print_percentage)
        self.device_type = get_printer_type(data.get("module", []), self.device_type)
        self.hw_ver = get_hw_version(data.get("module", []), self.hw_ver)
        self.sw_ver = get_sw_version(data.get("module", []), self.sw_ver)
        self.client.callback("event_printer_info_update")

    def print_update(self, data):
        """Update from dict"""
        self.gcode_state = data.get("gcode_state", self.gcode_state)
        self.remaining_time = data.get("mc_remaining_time", self.remaining_time)
        self.start_time = start_time(int(data.get("gcode_start_time", self.remaining_time)))
        self.end_time = end_time(data.get("mc_remaining_time", self.remaining_time))
        self.current_layer = data.get("layer_num", self.current_layer)
        self.total_layers = data.get("total_layer_num", self.total_layers)
        self.timelapse = data.get("ipcam", {}).get("timelapse", self.timelapse)
        self.client.callback("event_printer_print_update")


@dataclass
class AMSInstance:
    """Return all AMS instance related info"""
    def __init__(self):
        self.serial = ""
        self.sw_version = ""
        self.hw_version = ""
        self.humidity = 0
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
        # what devices to add to humidity_index assistant and add all the sensors as entititied. And then then json payload data
        # to populate the values for all those entities.

        # The module entries are of this form:
        # {
        #     "name": "ams/0",
        #     "project_name": "",
        #     "sw_ver": "00.00.05.96",
        #     "loader_ver": "00.00.00.00",
        #     "ota_ver": "00.00.00.00",
        #     "hw_ver": "AMS08",
        #     "sn": "<SERIAL>"
        # }

        received_ams_info = False
        module_list = data.get("module", [])
        for module in module_list:
            name = module["name"]
            if name.startswith("ams/"):
                received_ams_info = True
                index = int(name[4])
                LOGGER.debug(f"RECEIVED AMS INFO: {index}")
                # May get data before info so create entry if necessary
                if len(self.data) <= index:
                    self.data.append(AMSInstance())
                self.data[index].serial = module['sn']
                self.data[index].sw_version = module['sw_ver']
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
                LOGGER.debug(f"RECEIVED AMS DATA: {index}")
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

    def mc_print_update(self, data):
        """Update from dict"""

        # LOG format we need to parse for this data is like this:
        # {
        #     "mc_print": {
        #         "param": "[AMS][TASK]ams0 temp:27.0;humidity:21%;humidity_idx:4",
        #         "command": "push_info",
        #         "sequence_id": "299889"
        #     }
        # }

        data = data.get('param', '')
        if data.startswith('[AMS][TASK]ams'):
            LOGGER.debug(data)
            data = data[14:]
            LOGGER.debug(data)
            ams_index = int(data.split()[0])
            LOGGER.debug(ams_index)
            self.client.callback("event_ams_data_update")
            data = data[2:]
            data = data.split(';')
            for entry in data:
                entry = entry.split(':')
                if entry[0] == "temp":
                    #self.temperature = float(entry[1])
                    LOGGER.debug(f"GOT RAW AMS TEMP: {float(entry[1])}")
                elif entry[0] == "humidity":
                    self.humidity = int(entry[1][0:2])
                    LOGGER.debug(f"GOT RAW AMS HUMIDITY: {self.humidity}")

@dataclass
class AMSTray:
    """Return all AMS tray related info"""
    def __init__(self):
        self.Empty = True
        self.idx = ""
        self.name = ""
        self.type = ""
        self.sub_brands = ""
        self.color = "00000000" # RRGGBBAA
        self.nozzle_temp_min = 0
        self.nozzle_temp_max = 0
        self.k = 0

    def print_update(self, data):
        if len(data) == 1:
            # If the day is exactly one entry then it's just the ID and the tray is empty.
            self.Empty = True
            self.idx = ""
            self.name = "Empty"
            self.type = "Empty"
            self.sub_brands = ""
            self.color = "00000000" # RRGGBBAA
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
            LOGGER.debug(f"RECEIVED VIRTUAL TRAY DATA")
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

    def __init__(self):
        """Load from dict"""
        self._id = 0
        self.name = get_speed_name(2)
        self.modifier = 100

    def print_update(self, data):
        """Update from dict"""
        self._id = int(data.get("spd_lvl", self._id))
        self.name = get_speed_name(self._id)
        self.modifier = int(data.get("spd_mag", self.modifier))


@dataclass
class StageAction:
    """Return Stage Action information"""
    _id: int
    description: str

    def __init__(self):
        """Load from dict"""
        self._id = 99
        self.description = get_stage_action(self._id)

    def print_update(self, data):
        """Update from dict"""
        self._id = int(data.get("stg_cur", self._id))
        self.description = get_stage_action(self._id)


@dataclass
class HMSList:
    """Return all HMS related info"""
    def __init__(self):
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
            self.errors.clear()
            hmsList = data.get('hms', [])
            index: int = 0
            for hms in hmsList:
                index = index + 1
                attr = hms['attr']
                code = hms['code']
                hms_error = f'{int(attr/0x10000):0>4X}_{attr&0xFFFF:0>4X}_{int(code/0x10000):0>4X}_{code&0xFFFF:0>4X}' # 0300_0100_0001_0007
                LOGGER.warning(f"HMS ERROR: HMS_{hms_error} : {get_HMS_error_text(hms_error)}")
                self.errors[f"{index}-Error"] = f"HMS_{hms_error}: {get_HMS_error_text(hms_error)}"
                self.errors[f"{index}-Wiki"] = f"https://wiki.bambulab.com/en/x1/troubleshooting/hmscode/{hms_error}"
