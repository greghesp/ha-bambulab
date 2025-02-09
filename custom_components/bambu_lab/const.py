import logging
from datetime import timedelta
from enum import (
    IntEnum,
)

from homeassistant.const import Platform

# Integration domain
DOMAIN = "bambu_lab"
BRAND = "Bambu Lab"
URL_BASE = "/bambu_lab"

LOGGER = logging.getLogger(__package__)
LOGGERFORHA = logging.getLogger(f"{__package__}_HA")

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
    Platform.SWITCH
)

BAMBU_LAB_CARDS = [
    {
        'name': 'Bambu Lab Cards',
        'filename': 'ha-bambulab-cards.js',
        'version': '0.3.0'
    }
]

class Options(IntEnum):
    CAMERA = 1,
    IMAGECAMERA = 2,
    FTP = 3,
    TIMELAPSE = 4,
    MANUALREFRESH = 5,

OPTION_NAME = {
    Options.CAMERA:         "enable_camera",
    Options.IMAGECAMERA:    "camera_as_image_sensor",
    Options.FTP:            "enable_ftp",
    Options.TIMELAPSE:      "enable_timelapse",
    Options.MANUALREFRESH:  "manual_refresh_mode"
}