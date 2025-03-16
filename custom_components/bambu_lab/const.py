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
BRAND = "Bambu Lab"
URL_BASE = "/bambu_lab"

LOGGER = logging.getLogger(__package__)
LOGGERFORHA = logging.getLogger(f"{__package__}_HA")

SERVICE_CALL_EVENT = "bambu_lab_service_call"

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
        'version': '0.3.31'
    }
]

class Options(IntEnum):
    CAMERA = 1,
    IMAGECAMERA = 2,
    FTP = 3,
    TIMELAPSE = 4,
    MANUALREFRESH = 5,
    FIRMWAREUPDATE = 6,
    DOWNLOAD_GCODE_FILE = 7

OPTION_NAME = {
    Options.CAMERA:         "enable_camera",
    Options.IMAGECAMERA:    "camera_as_image_sensor",
    Options.FIRMWAREUPDATE: "enable_firmware_update",
    Options.FTP:            "enable_ftp",
    Options.TIMELAPSE:      "enable_timelapse",
    Options.MANUALREFRESH:  "manual_refresh_mode",
    Options.DOWNLOAD_GCODE_FILE: "enable_download_gcode_file"
}

def load_dict(filename: str) -> dict:
    with open(filename) as f:
        return json.load(f);

FILAMENT_DATA = load_dict(Path(__file__).with_name('filaments_detail.json'))
