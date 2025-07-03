"""The Bambu Lab component."""

import asyncio

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import (
    HomeAssistant,
    ServiceCall,
    SupportsResponse,
)
from homeassistant.helpers import entity_platform
from .const import (
    DOMAIN,
    LOGGER,
    PLATFORMS,
    SERVICE_CALL_EVENT
)
from .coordinator import BambuDataUpdateCoordinator
from .frontend import BambuLabCardRegistration
from .config_flow import CONFIG_VERSION

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up the Bambu Lab integration."""
    LOGGER.debug("async_setup_entry Start")
    coordinator = BambuDataUpdateCoordinator(hass, entry=entry)
    await coordinator.async_config_entry_first_refresh()

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = coordinator

    async def handle_service_call(call: ServiceCall):
        LOGGER.debug(f"handle_service_call: {call.service}")
        data = dict(call.data)
        data['service'] = call.service
        
        future = asyncio.Future()
        call.hass.data[DOMAIN]['service_call_future'] = future
        hass.bus.fire(SERVICE_CALL_EVENT, data)

        # Wait for the result from the second instance
        try:
            result = await asyncio.wait_for(future, timeout=15)
            LOGGER.debug(f"Service call result: {result}")
            return result
        except asyncio.TimeoutError:
            LOGGER.error("Service call timed out")
            return None
        finally:
            # Clean up the future safely
            try:
                if 'service_call_future' in call.hass.data[DOMAIN]:
                    del call.hass.data[DOMAIN]['service_call_future']
            except (KeyError, TypeError):
                # Integration may have been reloaded, ignore cleanup errors
                pass

    # Register the serviceS with Home Assistant
    services = {
        "send_command": SupportsResponse.NONE,
        "print_project_file": SupportsResponse.NONE,
        "skip_objects": SupportsResponse.NONE,
        "move_axis": SupportsResponse.NONE,
        "unload_filament": SupportsResponse.NONE,
        "load_filament": SupportsResponse.NONE,
        "extrude_retract": SupportsResponse.ONLY,
        "set_filament": SupportsResponse.NONE,
        "get_filament_data": SupportsResponse.ONLY,
    }
    for command in services:
        hass.services.async_register(
            DOMAIN,
            command,
            handle_service_call,
            supports_response=services[command]
        )

    # Set up all platforms for this device/entry.
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    # Reload entry when its updated.
    #entry.async_on_unload(entry.add_update_listener(async_reload_entry))

    # Now that we've finished initialization fully, start the MQTT connection so that any necessary
    # sensor reinitialization happens entirely after the initial setup.
    await coordinator.start_mqtt()

    cards = BambuLabCardRegistration(hass)
    await cards.async_register()

    LOGGER.debug("async_setup_entry Complete")

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

    # Delete existing config entry
    del hass.data[DOMAIN][entry.entry_id]

    cards = BambuLabCardRegistration(hass)
    await cards.async_unregister()

    LOGGER.debug("async_unload_entry Done")
    return True

async def async_reload_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Reload the config entry when it changed."""
    LOGGER.debug("async_reload_entry")
    await async_unload_entry(hass, entry)
    await async_setup_entry(hass, entry)

async def async_migrate_entry(hass, config_entry: ConfigEntry):
    """Migrate old entry."""
    LOGGER.debug(f"async_migrate_entry {config_entry.version}")
    if config_entry.version > CONFIG_VERSION:
        # This means the user has downgraded from a future version
        return False
    
    if config_entry.version == CONFIG_VERSION:
        # This means the major version still matches. We don't currently use minor versions.
        return True

    LOGGER.debug("config_entry migration from version %s", config_entry.version)
    if config_entry.version == 1:
        old_data = {**config_entry.data}
        LOGGER.debug(f"OLD DATA: {old_data}")

        # v1 data had just these entries:
        # "device_type": self.config_data["device_type"],
        # "serial": self.config_data["serial"],
        # "host": "us.mqtt.bambulab.com" / Local IP address
        # "username": username,
        # "access_code": authToken / access_code depending if local mqtt or not
        
        data = {
                "device_type": old_data['device_type'],
                "serial": old_data['serial']
        }
        options = {
                "region": "",
                "email": "",
                "username": old_data['username'] if (old_data.get('username', 'bblp') != "bblp") else "",
                "name": old_data['device_type'], # Default device name to model name
                "host": old_data['host'] if (old_data['host'] != "us.mqtt.bambulab.com") else "",
                "local_mqtt": (old_data['host'] != "us.mqtt.bambulab.com"),
                "auth_token": old_data['access_code'] if (old_data['host'] == "us.mqtt.bambulab.com") else "",
                "access_code": old_data['access_code'] if (old_data['host'] != "us.mqtt.bambulab.com") else ""
        }

        config_entry.version = CONFIG_VERSION
        hass.config_entries.async_update_entry(config_entry, data=data, options=options)

        LOGGER.debug("Migration to version %s successful", config_entry.version)

    return True