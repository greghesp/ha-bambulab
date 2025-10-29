import json
import logging
import math
import requests
import socket
import re

from datetime import datetime, timedelta
from functools import cache
from urllib3.exceptions import ReadTimeoutError
from bs4 import BeautifulSoup
from pathlib import Path

from .const import (
    CURRENT_STAGE_IDS,
    SPEED_PROFILE,
    FILAMENT_NAMES,
    HMS_SEVERITY_LEVELS,
    HMS_MODULES,
    LOGGER,
    BAMBU_URL,
    FansEnum,
    Printers,
    TempEnum
)
from .commands import SEND_GCODE_TEMPLATE, UPGRADE_CONFIRM_TEMPLATE


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

@cache
def get_HMS_error_text(error_code: str, device_type: Printers | str, preferred_language: str) -> str:
    """
    Return the human-readable description for an HMS error
    
    This returns the best available description for the HMS error. First preference
    is to return a string in the requested language; second preference is to return
    an error string tailored for the printer. An English message is better than
    'unknown' when there is no translation, and the error code identifies the affected
    part, so a message for a different printer should provide some clue as to the problem.

    :param error_code: The code to look up from the printer, optionally with underscores,
        e.g. '0300_0C00_0001_0004' or '03000C0000010004'.
    :param device_type: The type of the printer.
    :param preferred_language: The preferred language code, e.g. 'de', 'pt-BR'. This is not
        case-sensitive.
    """
    return _get_error_text("device_hms", error_code, device_type, preferred_language)

@cache
def get_print_error_text(error_code: str, device_type: Printers | str, preferred_language: str) -> str:
    """
    Return the human-readable description for a print error
    
    This returns the best available desription for the error. First preference
    is to return a string in the requested language; second preference is to return
    an error string tailored for the printer. An English message is better than
    'unknown' when there is no translation, and the error code identifies the affected
    part, so a message for a different printer should provide some clue as to the problem.

    :param code: The code to look up from the printer, optionally with underscores, e.g.
        '0300_0C00' or '03000C0000'.
    :param device_type: The type of the printer.
    :param preferred_language: The preferred language code, e.g. 'de', 'pt-BR'. This is not
        case-sensitive.
    """
    return _get_error_text("device_error", error_code, device_type, preferred_language)

@cache
def _get_error_text(error_type: str, error_code: str, device_type: Printers | str, preferred_language: str) -> str:
    """
    Return the human-readable description for an error
    
    This returns the best available desription for the error. First preference
    is to return a string in the requested locale or at least language; second
    preference is to return an error string tailored for the printer. An English
    message is better than 'unknown' when there is no translation, and the error
    code identifies the affected part, so a message for a different printer should
    provide some clue as to the problem.

    :param error_type: The type of error to look up, either "device_hms" or "device_error".
    :param error_code: The error code to look up from the printer, optionally with underscores.
    :param device_type: The type of the printer.
    :param preferred_language: The preferred language code, e.g. 'de', 'pt-BR'. This is not
        case-sensitive.
    """
    LOGGER.debug(f"Looking up {error_type=} {error_code=} {device_type=} {preferred_language=}")
    error_code = error_code.replace("_", "")

    # Candidate locale(s) in priority order
    locales = [preferred_language.lower()]
    if len(preferred_language) > 2:
        locales.append(preferred_language[:2].lower())
    if preferred_language != "en":
        locales.append("en")

    for locale_code in locales:
        for dev_type in (device_type, Printers.H2D):
            LOGGER.debug(f"Looking for HMS error: {locale_code=} {dev_type=} {error_code=}")
            error_data = _load_error_data(dev_type, locale_code)
            try:
                return error_data[error_type][error_code]
            except KeyError:
                pass

    return 'unknown'

@cache
def _load_error_data(device_type: Printers | str, language: str) -> dict:
    """Load error data for a specific device type and language"""
    LOGGER.debug(f"Loading HMS error data for {device_type=} {language=}")
    filename = Path(__file__).parent / "hms_error_text" / f"hms_{str(device_type)}_{language}.json"
    if not filename.exists():
        logging.debug(f"No HMS error data for {device_type=} {language=}")
        return {}

    with open(filename) as f:
        return json.load(f)

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

    if len(search(modules, lambda x: x.get('product_name', "") == "Bambu Lab A1")):
      return 'A1'

    if len(search(modules, lambda x: x.get('product_name', "") == "Bambu Lab A1 Mini")): # Guessed name
      return 'A1MINI'

    if len(search(modules, lambda x: x.get('product_name', "") == "Bambu Lab P1S")):
      return 'P1S'

    if len(search(modules, lambda x: x.get('product_name', "") == "Bambu Lab P2S")):
      return 'P2S'

    if len(search(modules, lambda x: x.get('product_name', "") == "Bambu Lab P1P")):
      return 'P1P'

    if len(search(modules, lambda x: x.get('product_name', "") == "Bambu Lab H2D")):
      return 'H2D'

    if len(search(modules, lambda x: x.get('product_name', "") == "Bambu Lab H2S")):
      return 'H2S'

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

def safe_json_loads(raw_bytes):

    # First try to decode it normally for efficiency.
    try:
        json_data = json.loads(raw_bytes)
        return json_data
    except json.JSONDecodeError as e:
        # Some machines give this error for invalid unicode sequences in the mqtt payload.
        pass
    except json.UnicodeError as e:
        # Some machines give this error instead.
        pass

    # Double up all backslashes to make JSON valid. Decode as non-utf8 to avoid errors and
    # the content being modified.
    text = raw_bytes.decode('latin-1')
    text = text.replace('\\', '\\\\')

    try:
        json_data = json.loads(text)
        return json_data
    except Exception as e:
        LOGGER.error(f"Failed to decode JSON payload: '{text}'")
        LOGGER.error(f"Exception. Type: {type(e)} Args: {e}")
        raise