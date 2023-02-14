"""The Bambu Lab component."""

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
    await coordinator.wait_for_data_ready()
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    # Reload entry when its updated.
    entry.async_on_unload(entry.add_update_listener(async_reload_entry))
    LOGGER.debug("Async Setup Entry Complete")
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload the Bambu Lab integration."""
    # no data stored in hass.data
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        coordinator: BambuDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]
        del hass.data[DOMAIN][entry.entry_id]

    LOGGER.debug("Async Setup Unload")
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


async def async_reload_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Reload the config entry when it changed."""
    LOGGER.debug("Async Setup Reload")
    await hass.config_entries.async_reload(entry.entry_id)
