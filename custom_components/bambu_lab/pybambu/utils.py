import math
import requests
import socket
import re

from datetime import datetime, timedelta
from urllib3.exceptions import ReadTimeoutError
from bs4 import BeautifulSoup

from .const import (
    CURRENT_STAGE_IDS,
    SPEED_PROFILE,
    FILAMENT_NAMES,
    HMS_SEVERITY_LEVELS,
    HMS_MODULES,
    LOGGER,
    BAMBU_URL,
    FansEnum,
    TempEnum
)
from .commands import SEND_GCODE_TEMPLATE, UPGRADE_CONFIRM_TEMPLATE
from .const_hms_errors import HMS_ERRORS
from .const_print_errors import PRINT_ERROR_ERRORS


def search(lst, predicate, default={}):
    """Search an array for a string"""
    if lst is None:
        return default
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


def set_temperature_to_gcode(temp: TempEnum, temperature: int):
    """Converts a temperature to the gcode command to set that"""
    if temp == TempEnum.NOZZLE:
        tempCommand = "M104"
    elif temp == TempEnum.HEATBED:
        tempCommand = "M140"

    command = SEND_GCODE_TEMPLATE
    command['print']['param'] = f"{tempCommand} S{temperature}\n"
    return command


def to_whole(number):
    if not number:
        return 0
    return round(number)


def get_filament_name(idx, custom_filaments: dict):
    """Converts a filament idx to a human-readable name"""
    result = FILAMENT_NAMES.get(idx, "unknown")
    if result == "unknown" and idx != "":
        custom = custom_filaments.get(idx, None)
        if custom is not None:
            result = custom.name
    return result


def get_ip_address_from_int(ip_int: int):
    packed_ip = ip_int.to_bytes(4, 'little')
    return socket.inet_ntoa(packed_ip)


def get_speed_name(id):
    """Return the human-readable name for a speed id"""
    return SPEED_PROFILE.get(int(id), "standard")


def get_current_stage(id) -> str:
    """Return the human-readable description for a stage action"""
    return CURRENT_STAGE_IDS.get(int(id), "unknown")


def get_HMS_error_text(code: str, language: str):
    """Return the human-readable description for an HMS error"""
    code = code.replace("_", "")
    error = HMS_ERRORS.get(code, 'unknown')
    if '' == error:
        return 'unknown'
    return error


def get_print_error_text(code: str, language: str):
    """Return the human-readable description for a print error"""
    code = code.replace("_", "")
    error = PRINT_ERROR_ERRORS.get(code, 'unknown')
    if '' == error:
        return 'unknown'
    return error


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
    # P1S with newer firmare is different - esp32 product_name is now empty but ota product_name is distinct.
    # {
    #     "name": "ota",
    #     "sw_ver": "01.08.00.00",
    #     "hw_ver": "OTA",
    #     "loader_ver": "00.00.00.00",
    #     "sn": "**REDACTED**",
    #     "product_name": "Bambu Lab P1S",
    #     "visible": true,
    #     "flag": 0
    # },
    # {
    #     "name": "esp32",
    #     "sw_ver": "01.11.35.43",
    #     "hw_ver": "AP04",
    #     "loader_ver": "00.00.00.00",
    #     "sn": "**REDACTED**",
    #     "product_name": "",
    #     "visible": false,
    #     "flag": 0
    # },    
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

    if len(search(modules, lambda x: x.get('product_name', "") == "Bambu Lab P1S")):
      return 'P1S'

    if len(search(modules, lambda x: x.get('product_name', "") == "Bambu Lab P1P")):
      return 'P1P'

    if len(search(modules, lambda x: x.get('product_name', "") == "Bambu Lab H2D")):
      return 'H2D'

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

def compare_version(version_max, version_min):
    maxver = list(map(int, version_max.split('.')))
    minver = list(map(int, version_min.split('.')))

    # Returns 1 if max > min, -1 if max < min, 0 if equal
    return (maxver > minver) - (maxver < minver)

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


def get_Url(url: str, region: str):
    urlstr = BAMBU_URL[url]
    if region == "China":
        urlstr = urlstr.replace('.com', '.cn')
    return urlstr


def get_upgrade_url(name: str):
    """Retrieve upgrade URL from BambuLab website"""
    response = requests.get(f"https://bambulab.com/en/support/firmware-download/{name}")
    soup = BeautifulSoup(response.text, 'html.parser')
    selector = soup.select_one(
        "#__next > div > div > div > "
        "div.portal-css-npiem8 > "
        "div.pageContent.MuiBox-root.portal-css-0 > "
        "div > div > div.portal-css-1v0qi56 > "
        "div.flex > div.detailContent > div > "
        "div > div.portal-css-kyyjle > div.top > "
        "div.versionContent > div > "
        "div.linkContent.pc > a:nth-child(2)"
    )
    if selector:
        return selector.get("href")
    return None

def upgrade_template(url: str) -> dict:
    """Template for firmware upgrade"""
    pattern = (
        r"offline\/([\w-]+)\/([\d\.]+)\/([\w]+)\/"
        r"offline-([\w\-\.]+)\.zip"
    )
    info = re.search(pattern, url).groups()
    if not info:
        LOGGER.warning(f"Could not parse firmware url: {url}")
        return None
    
    model, version, hash, stamp = info
    template = UPGRADE_CONFIRM_TEMPLATE.copy()
    template["upgrade"]["url"] = template["upgrade"]["url"].format(
        model=model, version=version, hash=hash, stamp=stamp
    )
    template["upgrade"]["version"] = version
    return template
