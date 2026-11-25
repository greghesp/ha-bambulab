import json
import logging

from datetime import timedelta
from enum import (
    IntEnum,
)
from pathlib import Path

from homeassistant.const import Platform

# Integration domain
DOMAIN = "bambu_lab"
ENTRY_TYPE = "entry_type"
ENTRY_TYPE_MAKERWORLD = "makerworld"
ENTRY_TYPE_FILAMENT_INVENTORY = "filament_inventory"
MAKERWORLD_DATA = f"{DOMAIN}_makerworld"
FILAMENT_INVENTORY_DATA = f"{DOMAIN}_filament_inventory"
BRAND = "Bambu Lab"
URL_BASE = "/bambu_lab"

LOGGER = logging.getLogger(__package__)
LOGGERFORHA = logging.getLogger(f"{__package__}_HA")

SERVICE_CALL_EVENT = "bambu_lab_service_call"
# hass.data[DOMAIN] key holding the pending service calls, by the id sent in the event data.
SERVICE_CALL_FUTURES = "service_call_futures"
SERVICE_CALL_ID = "service_call_id"

# file_type values accepted by the clear_file_cache service.
CLEAR_FILE_CACHE_PRINTS = "prints"
CLEAR_FILE_CACHE_TIMELAPSE = "timelapse"
CLEAR_FILE_CACHE_ALL = "all"
CLEAR_FILE_CACHE_TYPES = (CLEAR_FILE_CACHE_PRINTS, CLEAR_FILE_CACHE_TIMELAPSE, CLEAR_FILE_CACHE_ALL)

# Default total size limit (MB) for the print cache offered when a printer is added.
# Existing printers without the option keep a count-only limit (0 = no size limit).
DEFAULT_PRINT_CACHE_MAX_MB = 2048

# Options key mapping AMS serial -> switch entity_id of the smart plug powering an
# external AMS heater or dryer (e.g. SUNLU AMS Heater, EIBOS Series X).
CONF_AMS_HEATERS = "ams_heaters"

PLATFORMS = (
    Platform.BINARY_SENSOR,
    Platform.BUTTON,
    Platform.CAMERA,
    Platform.FAN,
    Platform.IMAGE,
    Platform.LIGHT,
    Platform.NUMBER,
    Platform.SELECT,
    Platform.SENSOR,
    Platform.SWITCH,
    Platform.UPDATE,
)

BAMBU_LAB_CARDS = [
    {
        'name': 'Bambu Lab Cards',
        'filename': 'ha-bambulab-cards.js',
        'version': '0.8.9'
    }
]

class Options(IntEnum):
    CAMERA = 1,
    IMAGECAMERA = 2,
    FIRMWAREUPDATE = 6

OPTION_NAME = {
    Options.CAMERA:         "enable_camera",
    Options.IMAGECAMERA:    "camera_as_image_sensor",
    Options.FIRMWAREUPDATE: "enable_firmware_update",
}

# Filament inventory ("Filament Manager") options.
OPTION_FILAMENT_INVENTORY_INTERVAL = "filament_inventory_interval"
DEFAULT_FILAMENT_INVENTORY_INTERVAL = 60  # minutes

def load_dict(filename: str) -> dict:
    with open(filename) as f:
        return json.load(f);

FILAMENT_DATA = load_dict(Path(__file__).with_name('filaments_detail.json'))
