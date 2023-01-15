from dataclasses import dataclass
from .utils import search, fan_percentage, to_whole, get_speed_name, get_stage_action
from .const import LOGGER


class Device:
    """Returns the device class for a Bambu printer"""

    def __init__(self, data):
        self.temperature = Temperature.from_dict(data)
        self.light = Lights.from_dict(data)
        self.fans = Fans.from_dict(data)
        self.info = Info.from_dict(data)
        self.ams = AMS.from_dict(data)
        self.speed = Speed.from_dict(data)
        self.stage = StageAction.from_dict(data)

    def update_from_dict(self, data):
        """Update from dict"""
        self.temperature.update_from_dict(data)
        self.light.update_from_dict(data)
        self.fans.update_from_dict(data)
        self.info.update_from_dict(data)
        self.ams.update_from_dict(data)
        self.speed.update_from_dict(data)
        self.stage.update_from_dict(data)



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

        self.chamber_light_on = \
            search(data.get("lights_report", []), lambda x: x.get('node', "") == "chamber_light", {"mode":self.chamber_light_on}).get("mode", "Unknown")
        self.work_light = search(data.get("lights_report", []), lambda x: x.get('node', "") == "work_light", {"mode":self.work_light}).get("mode", "Unknown")


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
            bed_temp=to_whole(data.get("bed_temper", 0)),
            target_bed_temp=to_whole(data.get("bed_target_temper", 0)),
            chamber_temp=to_whole(data.get("chamber_temper", 0)),
            nozzle_temp=to_whole(data.get("nozzle_temper", 0)),
            target_nozzle_temp=to_whole(data.get("nozzle_target_temper", 0)),
        )

    def update_from_dict(self, data):
        """Update from dict"""
        self.bed_temp = to_whole(data.get("bed_temper", self.bed_temp))
        self.target_bed_temp = to_whole(data.get("bed_target_temper", self.target_bed_temp))
        self.chamber_temp = to_whole(data.get("chamber_temper", self.chamber_temp))
        self.nozzle_temp = to_whole(data.get("nozzle_temper", self.nozzle_temp))
        self.target_nozzle_temp = to_whole(data.get("nozzle_target_temper", self.target_nozzle_temp))


@dataclass
class Fans:
    """Return all temperature related info"""
    aux_fan_speed: int
    chamber_fan_speed: int
    cooling_fan_speed: int
    heatbreak_fan_speed: int

    @staticmethod
    def from_dict(data):
        """Load from dict"""

        return Fans(
            aux_fan_speed=fan_percentage(data.get("big_fan1_speed")),
            chamber_fan_speed=fan_percentage(data.get("big_fan2_speed")),
            cooling_fan_speed=fan_percentage(data.get("cooling_fan_speed")),
            heatbreak_fan_speed=fan_percentage(data.get("heatbreak_fan_speed")),
        )

    def update_from_dict(self, data):
        """Update from dict"""

        self.aux_fan_speed = fan_percentage(data.get("big_fan1_speed", self.aux_fan_speed))
        self.chamber_fan_speed = fan_percentage(data.get("big_fan2_speed", self.chamber_fan_speed))
        self.cooling_fan_speed = fan_percentage(data.get("cooling_fan_speed", self.cooling_fan_speed))
        self.heatbreak_fan_speed = fan_percentage(data.get("heatbreak_fan_speed", self.heatbreak_fan_speed))


@dataclass
class Info:
    """Return all temperature related info"""
    wifi_signal: int

    @staticmethod
    def from_dict(data):
        """Load from dict"""

        return Info(
            wifi_signal=int(data.get("wifi_signal").replace("dBm", "")),
        )

    def update_from_dict(self, data):
        """Update from dict"""
        self.wifi_signal = int(data.get("wifi_signal", str(self.wifi_signal)).replace("dBm", ""))


@dataclass
class AMS:
    """Return all AMS related info"""
    version: int

    @staticmethod
    def from_dict(data):
        """Load from dict"""
        return AMS(
            version=int(data.get("ams").get("version")),
        )
        
    def update_from_dict(self, data):
        """Update from dict"""
        self.version = int(data.get("ams").get("version")) 


@dataclass
class Speed:
    """Return speed profile information"""
    _id: int
    name: str
    modifier: int

    def from_dict(data):
        """Load from dict"""
        return Speed(
            _id=int(data.get("spd_lvl")),
            name=get_speed_name(int(data.get("spd_lvl"))),
            modifier=int(data.get("spd_mag"))
        )
    
    def update_from_dict(self, data):
        """Update from dict"""
        self._id = int(data.get("spd_lvl", self._id))
        self.name = get_speed_name(int(data.get("spd_lvl", self._id)))
        self.modifier=int(data.get("spd_mag", self.modifier))


@dataclass
class StageAction:
    """Return Stage Action information"""
    _id: int
    description: str

    @staticmethod
    def from_dict(data):
        """Load from dict"""
        return StageAction(
            _id=int(data.get("stg_cur")),
            description=get_stage_action(int(data.get("stg_cur")))
        )
    
    def update_from_dict(self, data):
        """Update from dict"""
        self._id=int(data.get("stg_cur", self._id))
        self.description=get_stage_action(int(data.get("stg_cur", self._id)))

