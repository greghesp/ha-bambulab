import math
from datetime import datetime, timedelta

from .const import (
    CURRENT_STAGE_IDS,
    SPEED_PROFILE,
    FILAMENT_NAMES,
    HMS_ERRORS,
    HMS_AMS_ERRORS,
    HMS_SEVERITY_LEVELS,
    HMS_MODULES,
    LOGGER,
    FansEnum,
)
from .commands import SEND_GCODE_TEMPLATE


def search(lst, predicate, default={}):
    """Search an array for a string"""
    for item in lst:
        if predicate(item):
            return item
    return default


def fan_percentage(speed):
    """Converts a fan speed to percentage"""
    if not speed:
        return 0
    percentage = (int(speed) / 15) * 100
    return round(percentage / 10) * 10


def fan_percentage_to_gcode(fan: FansEnum, percentage: int):
    """Converts a fan speed percentage to the gcode command to set that"""
    if fan == FansEnum.PART_COOLING:
        fanString = "P1"
    elif fan == FansEnum.AUXILIARY:
        fanString = "P2"
    elif fan == FansEnum.CHAMBER:
        fanString = "P3"

    percentage = round(percentage / 10) * 10
    speed = math.ceil(255 * percentage / 100)
    command = SEND_GCODE_TEMPLATE
    command['print']['param'] = f"M106 {fanString} S{speed}\n"
    return command


def to_whole(number):
    if not number:
        return 0
    return round(number)


def get_filament_name(idx):
    """Converts a filament idx to a human-readable name"""
    result = FILAMENT_NAMES.get(idx, "unknown")
    if result == "unknown" and idx != "":
        LOGGER.debug(f"UNKNOWN FILAMENT IDX: '{idx}'")
    return result


def get_speed_name(id):
    """Return the human-readable name for a speed id"""
    return SPEED_PROFILE.get(int(id), "standard")


def get_current_stage(id) -> str:
    """Return the human-readable description for a stage action"""
    return CURRENT_STAGE_IDS.get(int(id), "unknown")


def get_HMS_error_text(hms_code: str):
    """Return the human-readable description for an HMS error"""

    ams_code = get_generic_AMS_HMS_error_code(hms_code)
    ams_error = HMS_AMS_ERRORS.get(ams_code, "")
    if ams_error != "":
        # 070X_xYxx_xxxx_xxxx = AMS X (0 based index) Slot Y (0 based index) has the error
        ams_index = int(hms_code[3:4], 16) + 1
        ams_slot = int(hms_code[6:7], 16) + 1
        ams_error = ams_error.replace('AMS1', f"AMS{ams_index}")
        ams_error = ams_error.replace('slot 1', f"slot {ams_slot}")
        return ams_error

    return HMS_ERRORS.get(hms_code, "unknown")


def get_HMS_severity(code: int) -> str:
    uint_code = code >> 16
    if code > 0 and uint_code in HMS_SEVERITY_LEVELS:
        return HMS_SEVERITY_LEVELS[uint_code]
    return HMS_SEVERITY_LEVELS["default"]


def get_HMS_module(attr: int) -> str:
    uint_attr = (attr >> 24) & 0xFF
    if attr > 0 and uint_attr in HMS_MODULES:
        return HMS_MODULES[uint_attr]
    return HMS_MODULES["default"]


def get_generic_AMS_HMS_error_code(hms_code: str):
    code1 = int(hms_code[0:4], 16)
    code2 = int(hms_code[5:9], 16)
    code3 = int(hms_code[10:14], 16)
    code4 = int(hms_code[15:19], 16)

    # 070X_xYxx_xxxx_xxxx = AMS X (0 based index) Slot Y (0 based index) has the error
    ams_code = f"{code1 & 0xFFF8:0>4X}_{code2 & 0xF8FF:0>4X}_{code3:0>4X}_{code4:0>4X}"
    ams_error = HMS_AMS_ERRORS.get(ams_code, "")
    if ams_error != "":
        return ams_code

    return f"{code1:0>4X}_{code2:0>4X}_{code3:0>4X}_{code4:0>4X}"


def get_printer_type(modules, default):
    """Retrieve printer type"""
    esp32 = search(modules, lambda x: x.get('name', "") == "esp32")
    rv1126 = search(modules, lambda x: x.get('name', "") == "rv1126")
    if len(esp32.keys()) > 1:
        if esp32.get("hw_ver") == "AP04":
            if esp32.get("project_name") == "C11":
                LOGGER.debug("Device is P1P")
                return "P1P"
            elif esp32.get("project_name") == "C12":
                LOGGER.debug("Device is P1S")
                return "P1S"
        if esp32.get("hw_ver") == "AP05":
            if esp32.get("project_name") == "N1":
                LOGGER.debug("Device is A1 Mini")
                return "A1MINI"
            elif esp32.get("project_name") == "N2S":
                LOGGER.debug("Device is A1")
                return "A1"
        LOGGER.debug(f"UNKNOWN DEVICE: esp32 = {esp32.get('hw_ver')}/'{esp32.get('project_name')}'")
    elif len(rv1126.keys()) > 1:
        if rv1126.get("hw_ver") == "AP05":
            LOGGER.debug("Device is X1C")
            return "X1C"
        elif rv1126.get("hw_ver") == "AP02":
            LOGGER.debug("Device is X1E")
            return "X1E"
        LOGGER.debug(f"UNKNOWN DEVICE: rv1126 = {rv1126.get('hw_ver')}")
    return default


def get_hw_version(modules, default):
    """Retrieve hardware version of printer"""
    esp32 = search(modules, lambda x: x.get('name', "") == "esp32")
    rv1126 = search(modules, lambda x: x.get('name', "") == "rv1126")
    if len(esp32.keys()) > 1:
        return esp32.get("hw_ver")
    elif len(rv1126.keys()) > 1:
        return rv1126.get("hw_ver")
    return default


def get_sw_version(modules, default):
    """Retrieve software version of printer"""
    ota = search(modules, lambda x: x.get('name', "") == "ota")
    if len(ota.keys()) > 1:
        return ota.get("sw_ver")
    return default


def get_start_time(timestamp):
    """Return start time of a print"""
    if timestamp == 0:
        return None
    return datetime.fromtimestamp(timestamp)


def get_end_time(remaining_time):
    """Calculate the end time of a print"""
    end_time = round_minute(datetime.now() + timedelta(minutes=remaining_time))
    return end_time


def round_minute(date: datetime = None, round_to: int = 1):
    """ Round datetime object to minutes"""
    if not date:
        date = datetime.now()
    date = date.replace(second=0, microsecond=0)
    delta = date.minute % round_to
    return date.replace(minute=date.minute - delta)
