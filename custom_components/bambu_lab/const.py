import logging
from datetime import timedelta

# Integration domain
DOMAIN = "bambu_lab"
BRAND = "Bambu Lab"

LOGGER = logging.getLogger(__package__)
SCAN_INTERVAL = timedelta(seconds=10)
