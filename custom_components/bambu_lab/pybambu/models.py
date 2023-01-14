from dataclasses import dataclass
from .utils import search, fan_percentage
from .const import LOGGER


class Device:
    """Returns the device class for a Bambu printer"""

    def __init__(self, data):
        self.temperature = Temperature.from_dict(data)
        self.light = Lights.from_dict(data)
        self.fans = Fans.from_dict(data)

    def update_from_dict(self, data):
        """Update from dict"""
        self.temperature.update_from_dict(data)
        self.light.update_from_dict(data)
        self.fans.update_from_dict(data)


@dataclass
class Lights:
    """Return all light related info"""
    chamber_light_on: str
    work_light: str

    @staticmethod
    def from_dict(data):
        """Loads from dict"""

        return Lights(
            chamber_light_on=search(data["lights_report"], lambda x: x['node'] == "chamber_light")["mode"],
            work_light=search(data["lights_report"], lambda x: x['node'] == "work_light")["mode"],
        )

    def update_from_dict(self, data):
        """Update from dict"""

        self.chamber_light_on = search(data["lights_report"], lambda x: x['node'] == "chamber_light", self.chamber_light_on)["mode"]
        self.work_light = search(data["lights_report"], lambda x: x['node'] == "work_light", self.work_light)["mode"]


@dataclass
class Temperature:
    """Return all temperature related info"""
    bed_temp: int
    target_bed_temp: int
    chamber_temp: int
    nozzle_temp: int
    target_nozzle_temp: int

    @staticmethod
    def from_dict(data):
        """Load from dict"""
        return Temperature(
            bed_temp=data.get("bed_temper"),
            target_bed_temp=data.get("bed_target_temper"),
            chamber_temp=data.get("chamber_temper"),
            nozzle_temp=data.get("nozzle_temper"),
            target_nozzle_temp=data.get("nozzle_target_temper"),
        )

    def update_from_dict(self, data):
        """Update from dict"""
        self.bed_temp = data.get("bed_temper", self.bed_temp)
        self.target_bed_temp = data.get("bed_target_temper", self.target_bed_temp)
        self.chamber_temp = data.get("chamber_temper", self.chamber_temp)
        self.nozzle_temp = data.get("nozzle_temper", self.nozzle_temp)
        self.target_nozzle_temp = data.get("nozzle_target_temper", self.target_nozzle_temp)


@dataclass
class Fans:
    """Return all temperature related info"""
    big_fan1_speed: int
    big_fan2_speed: int
    cooling_fan_speed: int
    heatbreak_fan_speed: int

    @staticmethod
    def from_dict(data):
        """Load from dict"""

        return Fans(
            big_fan1_speed=fan_percentage(data.get("big_fan1_speed")),
            big_fan2_speed=fan_percentage(data.get("big_fan2_speed")),
            cooling_fan_speed=fan_percentage(data.get("cooling_fan_speed")),
            heatbreak_fan_speed=fan_percentage(data.get("heatbreak_fan_speed")),
        )

    def update_from_dict(self, data):
        """Update from dict"""

        self.big_fan1_speed = fan_percentage(data.get("big_fan1_speed", self.big_fan1_speed))
        self.big_fan2_speed = fan_percentage(data.get("big_fan2_speed", self.big_fan2_speed))
        self.cooling_fan_speed = fan_percentage(data.get("cooling_fan_speed", self.cooling_fan_speed))
        self.heatbreak_fan_speed = fan_percentage(data.get("heatbreak_fan_speed", self.heatbreak_fan_speed))
