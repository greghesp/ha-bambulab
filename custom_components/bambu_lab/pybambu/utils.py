import math
from datetime import datetime, timedelta

from .const import (
    CURRENT_STAGE_IDS,
    SPEED_PROFILE,
    FILAMENT_NAMES,
    HMS_ERRORS,
    HMS_AMS_ERRORS,
    PRINT_ERROR_ERRORS,
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


def get_filament_name(idx, custom_filaments: dict):
    """Converts a filament idx to a human-readable name"""
    result = FILAMENT_NAMES.get(idx, "unknown")
    if result == "unknown" and idx != "":
        result = custom_filaments.get(idx, "unknown")
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


def get_print_error_text(print_error_code: str):
    """Return the human-readable description for a print error"""

    hex_conversion = f'0{int(print_error_code):x}'
    print_error_code = hex_conversion[slice(0,4,1)] + "_" + hex_conversion[slice(4,8,1)]
    print_error = PRINT_ERROR_ERRORS.get(print_error_code.upper(), "")
    if print_error != "":
        return print_error

    return PRINT_ERROR_ERRORS.get(print_error_code, "unknown")


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
    # Known possible values:
    # 
    # A1/P1 printers are of the form:
    # {
    #     "name": "esp32",
    #     "project_name": "C11",
    #     "sw_ver": "01.07.23.47",
    #     "hw_ver": "AP04",
    #     "sn": "**REDACTED**",
    #     "flag": 0
    # },
    # P1P    = AP04 / C11
    # P1S    = AP04 / C12
    # A1Mini = AP05 / N1 or AP04 / N1 or AP07 / N1
    # A1     = AP05 / N2S
    #
    # X1C printers are of the form:
    # {
    #     "hw_ver": "AP05",
    #     "name": "rv1126",
    #     "sn": "**REDACTED**",
    #     "sw_ver": "00.00.28.55"
    # },
    # X1C = AP05
    #
    # X1E printers are of the form:
    # {
    #     "flag": 0,
    #     "hw_ver": "AP02",
    #     "name": "ap",
    #     "sn": "**REDACTED**",
    #     "sw_ver": "00.00.32.14"
    # }
    # X1E = AP02

    apNode = search(modules, lambda x: x.get('hw_ver', "").find("AP0") == 0)
    if len(apNode.keys()) > 1:
        hw_ver = apNode['hw_ver']
        project_name = apNode.get('project_name', '')
        if hw_ver == 'AP02':
            return 'X1E'
        elif project_name == 'N1':
            return 'A1MINI'
        elif hw_ver == 'AP04':
            if project_name == 'C11':
                return 'P1P'
            if project_name == 'C12':
                return 'P1S'
        elif hw_ver == 'AP05':
            if project_name == 'N2S':
                return 'A1'
            if project_name == '':
                return 'X1C'
        LOGGER.debug(f"UNKNOWN DEVICE: hw_ver='{hw_ver}' / project_name='{project_name}'")
    return default


def get_hw_version(modules, default):
    """Retrieve hardware version of printer"""
    apNode = search(modules, lambda x: x.get('hw_ver', "").find("AP0") == 0)
    if len(apNode.keys()) > 1:
        return apNode.get("hw_ver")
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
