import logging
from datetime import timedelta

from homeassistant.const import Platform

# Integration domain
DOMAIN = "bambu_lab"
BRAND = "Bambu Lab"

LOGGER = logging.getLogger(__package__)
SCAN_INTERVAL = timedelta(seconds=60)

PLATFORMS = (
    Platform.LIGHT,
    Platform.SENSOR,
    Platform.BINARY_SENSOR,
    Platform.BUTTON
)
