import math
from datetime import datetime, timedelta

from .const import ACTION_IDS, SPEED_PROFILE, FILAMENT_NAMES, HMS_ERRORS, LOGGER, FansEnum
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
    return math.ceil(percentage / 10) * 10


def fan_percentage_to_gcode(fan: FansEnum, percentage: int):
    """Converts a fan speed percentage to the gcode command to set that"""
    match fan:
        case FansEnum.PART_COOLING:
            fanString = "P1"
        case FansEnum.AUXILIARY:
            fanString = "P2"
        case FansEnum.CHAMBER:
            fanString = "P3"

    percentage = math.ceil(percentage / 10) * 10
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


def get_speed_name(_id):
    """Return the human-readable name for a speed id"""
    return SPEED_PROFILE.get(int(_id), "standard")


def get_stage_action(_id):
    """Return the human-readable description for a stage action"""
    return ACTION_IDS.get(_id, "unknown")


def get_HMS_error_text(_id):
    """Return the human-readable description for an HMS error"""
    return HMS_ERRORS.get(_id, "unknown")


def get_printer_type(modules, default):
    """Retrieve printer type"""
    esp32 = search(modules, lambda x: x.get('name', "") == "esp32")
    rv1126 = search(modules, lambda x: x.get('name', "") == "rv1126")
    if len(esp32.keys()) > 1:
        if esp32.get("hw_ver") == "AP04":
            LOGGER.debug("Device is P1P/S")
            return "P1P"
    elif len(rv1126.keys()) > 1:
        if rv1126.get("hw_ver") == "AP05":
            LOGGER.debug("Device is X1/C")
            return "X1C"
    return default


def get_hw_version(modules, default):
    """Retrieve hardware version of printer"""
    esp32 = search(modules, lambda x: x.get('name', "") == "esp32")
    rv1126 = search(modules, lambda x: x.get('name', "") == "rv1126")
    if len(esp32.keys()) > 1:
        if esp32.get("hw_ver") == "AP04":
            return esp32.get("hw_ver")
    elif len(rv1126.keys()) > 1:
        if rv1126.get("hw_ver") == "AP05":
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
        return ""
    return datetime.fromtimestamp(timestamp).strftime('%d %B %Y %H:%M:%S')


def get_end_time(remaining_time):
    """Calculate the end time of a print"""
    endtime = datetime.now() + timedelta(minutes=remaining_time)
    return round_minute(endtime).strftime('%d %B %Y %H:%M:%S')


def round_minute(date: datetime = None, round_to: int = 1):
    """ Round datetime object to minutes"""
    if not date:
        date = datetime.now()
    date = date.replace(second=0, microsecond=0)
    delta = date.minute % round_to
    return date.replace(minute=date.minute - delta)
