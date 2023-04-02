"""The Bambu Lab component."""

import asyncio

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from .const import DOMAIN, LOGGER
from .coordinator import BambuDataUpdateCoordinator

PLATFORMS = (
    Platform.LIGHT,
    Platform.SENSOR,
    Platform.BUTTON
)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up the Bambu Lab integration."""
    LOGGER.debug("Async Setup Entry Started")
    coordinator = BambuDataUpdateCoordinator(hass, entry=entry)
    await coordinator.async_config_entry_first_refresh()
    LOGGER.debug(f"Coordinator {coordinator.__dict__}")

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = coordinator

    # Set up all platforms for this device/entry.
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    # Reload entry when its updated.
    entry.async_on_unload(entry.add_update_listener(async_reload_entry))

    LOGGER.debug("Async Setup Entry Complete")
    return True

async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload the Bambu Lab integration."""
    LOGGER.debug("async_unload_entry")

    # Unload the platforms
    LOGGER.debug(f"async_unload_entry: {PLATFORMS}")
    await hass.config_entries.async_unload_platforms(entry, PLATFORMS)

    # Halt the mqtt listener thread
    coordinator: BambuDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]
    coordinator.shutdown()

    # Do this because the sample has us do it. Doesn't seem to do anything.
    del hass.data[DOMAIN][entry.entry_id]

    LOGGER.debug("Async Setup Unload Done")
    return True

async def async_reload_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Reload the config entry when it changed."""
    LOGGER.debug("Async Setup Reload")
    await hass.config_entries.async_reload(entry.entry_id)