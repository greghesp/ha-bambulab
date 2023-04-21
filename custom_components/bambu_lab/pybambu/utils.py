import math
from datetime import datetime, timezone, timedelta

from .const import ACTION_IDS, SPEED_PROFILE, FILAMENT_NAMES, HMS_ERRORS, LOGGER


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


def to_whole(number):
    if not number:
        return 0
    return round(number)


def get_filament_name(idx):
    """Converts a filament idx to a human-readable name"""
    result = FILAMENT_NAMES.get(idx, "Unknown")
    if result == "Unknown":
        LOGGER.debug(f"UNKNOWN FILAMENT IDX: {idx}")
    return result


def get_speed_name(_id):
    """Return the human-readable name for a speed id"""
    return SPEED_PROFILE.get(int(_id), "Unknown")


def get_stage_action(_id):
    """Return the human-readable description for a stage action"""
    return ACTION_IDS.get(_id, "Unknown")


def get_HMS_error_text(_id):
    """Return the human-readable description for an HMS error"""
    return HMS_ERRORS.get(_id, "Unknown")


def get_printer_type(modules, default):
    """Retrieve printer type"""
    esp32 = search(modules, lambda x: x.get('name', "") == "esp32")
    rv1126 = search(modules, lambda x: x.get('name', "") == "rv1126")
    if len(esp32.keys()) > 1:
        if esp32.get("hw_ver") == "AP04":
            LOGGER.debug("Device is P1P")
            return "P1P"
    elif len(rv1126.keys()) > 1:
        if rv1126.get("hw_ver") == "AP05":
            LOGGER.debug("Device is X1C")
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


def start_time(timestamp):
    """Return start time of a print"""
    if timestamp == 0:
        return "N/A"
    return datetime.fromtimestamp(timestamp).strftime('%d %B %Y %H:%M:%S')


def end_time(remaining_time):
    """Calculate the end time of a print"""
    if remaining_time <= 0:
        return "N/A"
    endtime = datetime.now() + timedelta(minutes=remaining_time)
    return round_minute(endtime).strftime('%d %B %Y %H:%M:%S')


def round_minute(date: datetime = None, round_to: int = 1):
    """ Round datetime object to minutes"""
    if not date:
        date = datetime.now()
    date = date.replace(second=0, microsecond=0)
    delta = date.minute % round_to
    return date.replace(minute=date.minute - delta)


def timelapse_state(value):
    if not value:
        return value
    return f"{value}d".capitalize()
