import logging
from datetime import timedelta

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
        "name": "Bambu Lab Cards",
        "filename": "ha-bambulab-cards.js",
        "version": "1.0.0"
    }
]