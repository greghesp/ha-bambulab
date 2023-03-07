from dataclasses import dataclass
from .utils import search, fan_percentage, get_speed_name, get_stage_action, get_printer_type, get_hw_version, \
    get_sw_version, start_time, end_time
from .const import LOGGER, Features

import asyncio

class Device:
    def __init__(self):
        self.temperature = Temperature()
        self.lights = Lights()
        self.info = Info()
        self.fans = Fans()
        self.speed = Speed()
        self.stage = StageAction()

    def update(self, data):
        """Update from dict"""
        self.temperature.update(data)
        self.lights.update(data)
        self.fans.update(data)
        self.info.update(data)
        # self.ams.update(data)
        self.speed.update(data)
        self.stage.update(data)

    def add_serial(self, data):
        self.info.add_serial(data)

    def supports_feature(self, feature):
        if feature == Features.AUX_FAN:
            return self.info.device_type == "X1C" or self.info.device_type == "P1P"
        if feature == Features.CHAMBER_LIGHT:
            return self.info.device_type == "X1C" or self.info.device_type == "P1P"
        if feature == Features.CHAMBER_TEMPERATURE:
            return self.info.device_type == "X1C"
        if feature == Features.CURRENT_STAGE:
            return self.info.device_type == "X1C"
        return False


@dataclass
class Lights:
    """Return all light related info"""
    chamber_light: str
    work_light: str

    def __init__(self):
        self.chamber_light = "Unknown"
        self.work_light = "Unknown"

    def update(self, data):
        """Update from dict"""

        self.chamber_light = \
            search(data.get("lights_report", []), lambda x: x.get('node', "") == "chamber_light",
                   {"mode": self.chamber_light}).get("mode")
        self.work_light = \
            search(data.get("lights_report", []), lambda x: x.get('node', "") == "work_light",
                   {"mode": self.work_light}).get("mode")


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

    def update(self, data):
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

    def update(self, data):
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

    def __init__(self):
        self.wifi_signal = 0
        self.print_percentage = 0
        self.device_type = "Unknown"
        self.hw_ver = "Unknown"
        self.sw_ver = "Unknown"
        self.gcode_state = "Unknown"
        self.serial = "Unknown"
        self.remaining_time = 0
        self.end_time = 000
        self.start_time = 000

    def update(self, data):
        """Update from dict"""
        self.wifi_signal = int(data.get("wifi_signal", str(self.wifi_signal)).replace("dBm", ""))
        self.print_percentage = data.get("mc_percent", self.print_percentage)
        self.device_type = get_printer_type(data.get("module", []), self.device_type)
        self.hw_ver = get_hw_version(data.get("module", []), self.hw_ver)
        self.sw_ver = get_sw_version(data.get("module", []), self.sw_ver)
        self.gcode_state = data.get("gcode_state", self.gcode_state)
        self.remaining_time = data.get("mc_remaining_time", self.remaining_time)
        self.start_time = start_time(int(data.get("gcode_start_time", self.remaining_time)))
        self.end_time = end_time(data.get("mc_remaining_time", self.remaining_time))

    def add_serial(self, data):
        self.serial = data or self.serial


# @dataclass
# class AMS:
#     """Return all AMS related info"""
#     version: int
#
#     # TODO: Handle if AMS doesn't exist
#     @staticmethod
#     def from_dict(data):
#         """Load from dict"""
#         return AMS(
#             version=int(data.get("ams").get("version")),
#         )
#
#     def update_from_dict(self, data):
#         """Update from dict"""
#         self.version = int(data.get("ams").get("version"))


@dataclass
class Speed:
    """Return speed profile information"""
    _id: int
    name: str
    modifier: int

    def __init__(self):
        """Load from dict"""
        self._id = 0
        self.name = get_speed_name(0),
        self.modifier = 0

    def update(self, data):
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

    def update(self, data):
        """Update from dict"""
        self._id = int(data.get("stg_cur", self._id))
        self.description = get_stage_action(self._id)
