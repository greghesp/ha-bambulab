"""The Bambu Lab component."""

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.helpers import entity_platform
from .const import DOMAIN, LOGGER, PLATFORMS
from .coordinator import BambuDataUpdateCoordinator
from .frontend import BambuLabCardRegistration
from .config_flow import CONFIG_VERSION
from .pybambu.commands import SEND_GCODE_TEMPLATE, PRINT_PROJECT_FILE_TEMPLATE

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up the Bambu Lab integration."""
    LOGGER.debug("async_setup_entry Start")
    coordinator = BambuDataUpdateCoordinator(hass, entry=entry)
    await coordinator.async_config_entry_first_refresh()

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = coordinator

    async def send_command(call: ServiceCall):
        """Handle the service call."""
        command = SEND_GCODE_TEMPLATE
        command['print']['param'] = f"{call.data.get('command')}\n"
        coordinator.client.publish(command)


    # Register the service with Home Assistant
    hass.services.async_register(
        DOMAIN,
        "send_command",  # Service name
        send_command    # Handler function
    )

    async def print_project_file(call: ServiceCall):
        """Handle the service call."""
        command = PRINT_PROJECT_FILE_TEMPLATE
        file = call.data.get("filepath")
        plate = call.data.get("plate")
        timelapse = call.data.get("timelapse")
        bed_leveling = call.data.get("bed_leveling")
        flow_cali = call.data.get("flow_cali")
        vibration_cali = call.data.get("vibration_cali")
        layer_inspect = call.data.get("layer_inspect")
        use_ams = call.data.get("use_ams")
        ams_mapping = call.data.get("ams_mapping")

        command["print"]["param"] = f"Metadata/plate_{plate}.gcode"
        command["print"]["url"] = f"ftp://{file}"
        command["print"]["timelapse"] = timelapse
        command["print"]["bed_leveling"] = bed_leveling
        command["print"]["flow_cali"] = flow_cali
        command["print"]["vibration_cali"] = vibration_cali
        command["print"]["layer_inspect"] = layer_inspect
        command["print"]["use_ams"] = use_ams
        command["print"]["ams_mapping"] = [int(x) for x in ams_mapping.split(',')]

        coordinator.client.publish(command)

    # Register the service with Home Assistant
    hass.services.async_register(
        DOMAIN,
        "print_project_file",  # Service name
        print_project_file  # Handler function
    )

    # Set up all platforms for this device/entry.
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    # Reload entry when its updated.
    #entry.async_on_unload(entry.add_update_listener(async_reload_entry))

    LOGGER.debug("async_setup_entry Complete")

    # Now that we've finished initialization fully, start the MQTT connection so that any necessary
    # sensor reinitialization happens entirely after the initial setup.
    await coordinator.start_mqtt()

    cards = BambuLabCardRegistration(hass)
    await cards.async_register()

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

    LOGGER.debug("Async Setup Unload Done")
    return True

async def async_reload_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Reload the config entry when it changed."""
    LOGGER.debug("Async Setup Reload")
    await hass.config_entries.async_reload(entry.entry_id)

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