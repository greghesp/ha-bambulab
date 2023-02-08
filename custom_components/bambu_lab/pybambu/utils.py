import math

from .const import ACTION_IDS, SPEED_PROFILE, FILAMENT_NAMES

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
    return math.ceil( percentage / 10) * 10

def to_whole(number):
    if not number:
        return 0
    return round(number)

def get_filament_name(idx):
    """Converts a filament idx to a human-readable name"""
    return FILAMENT_NAMES.get(idx, "Unknown")

def get_speed_name(_id):
    """Return the human-readable name for a speed id"""
    return SPEED_PROFILE.get(int(_id), "Unknown")

def get_stage_action(_id):
    """Return the human-readable description for a stage action"""
    return ACTION_IDS.get(_id, "Unknown")
