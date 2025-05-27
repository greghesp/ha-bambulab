"""Diagnostics support for Enphase Envoy."""
from __future__ import annotations

from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .const import DOMAIN
from .coordinator import BambuDataUpdateCoordinator
from .pybambu.commands import PUSH_ALL, GET_VERSION


TO_REDACT = [
    "access_code",
    "auth_token",
    "email",
    "rtsp_url",
    "serial",
    "sn",
    "title",
    "username"
]


async def async_get_config_entry_diagnostics(
        hass: HomeAssistant, entry: ConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    coordinator: BambuDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]

    # Must convert this to a dict for redaction to work correctly. Redaction leaves empty values as empty so we know if a value was present or not.
    entry = coordinator.config_entry.as_dict()

    coordinator.client.publish(PUSH_ALL)
    coordinator.client.publish(GET_VERSION)

    diagnostics_data = {
        "config_entry": async_redact_data(entry, TO_REDACT),
        "push_all": async_redact_data(coordinator.data.push_all_data, TO_REDACT),
        "get_version": async_redact_data(coordinator.data.get_version_data, TO_REDACT),
    }

    return diagnostics_data
