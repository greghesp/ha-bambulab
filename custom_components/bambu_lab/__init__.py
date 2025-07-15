"""The Bambu Lab component."""

import asyncio
import json
import os
import mimetypes
from datetime import datetime
from typing import Any, Dict, List, Optional
from pathlib import Path

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import (
    HomeAssistant,
    ServiceCall,
    SupportsResponse,
)
from homeassistant.helpers import entity_platform
from homeassistant.components.http import HomeAssistantView
from aiohttp import web
import aiofiles

from .const import (
    DOMAIN,
    LOGGER,
    PLATFORMS,
    SERVICE_CALL_EVENT
)
from .coordinator import BambuDataUpdateCoordinator
from .frontend import BambuLabCardRegistration
from .config_flow import CONFIG_VERSION


class FileCacheAPIView(HomeAssistantView):
    """API endpoint for file cache data."""
    
    url = "/api/bambu_lab/file_cache/{serial}"
    name = "api:bambu_lab:file_cache"
    requires_auth = True
    
    def __init__(self, hass: HomeAssistant):
        """Initialize the view."""
        self.hass = hass
    
    async def get(self, request: web.Request, serial: str) -> web.Response:
        """Handle GET request for file cache data."""
        try:
            # Find the coordinator for this serial
            coordinator = None
            for entry_id in self.hass.data[DOMAIN]:
                if entry_id == "service_call_future":
                    continue
                coord = self.hass.data[DOMAIN][entry_id]
                if coord.get_model().info.serial == serial:
                    coordinator = coord
                    break
            
            if not coordinator:
                return web.json_response(
                    {"error": f"Printer with serial {serial} not found"}, 
                    status=404
                )
            
            # Get query parameters
            file_type = request.query.get('file_type')
            if file_type is None:
                return web.json_response(
                    {"error": f"file_type not set"}, 
                    status=404
                )
            
            # Get cached files using the coordinator's method
            files = await coordinator.get_cached_files(file_type=file_type)
            
            # Format the response
            response_data = {
                "serial": serial,
                "file_type": file_type,
                "files": files,
                "total_files": len(files),
                "timestamp": datetime.now().isoformat()
            }
            LOGGER.debug(f"Response: {response_data}")
            
            return web.json_response(response_data)
            
        except Exception as e:
            LOGGER.error(f"Error in file cache API: {e}")
            return web.json_response(
                {"error": "Internal server error"}, 
                status=500
            )


class FileCacheFileView(HomeAssistantView):
    """API endpoint for serving any cached file (media or raw)."""
    url = "/api/bambu_lab/file_cache/{serial}/file/{filepath:.*}"
    name = "api:bambu_lab:file_cache_file"
    requires_auth = True

    def __init__(self, hass: HomeAssistant):
        LOGGER.debug(f"FileCacheFileView initialized with URL: {self.url}")
        self.hass = hass

    async def get(self, request: web.Request, serial: str, filepath: str) -> web.Response:
        LOGGER.debug("FileCacheFileView::get()")
        try:
            # Find the coordinator for this serial
            coordinator = None
            for entry_id in self.hass.data[DOMAIN]:
                if entry_id == "service_call_future":
                    continue
                coord = self.hass.data[DOMAIN][entry_id]
                if coord.get_model().info.serial == serial:
                    coordinator = coord
                    break
            if not coordinator:
                return web.json_response({"error": f"Printer with serial {serial} not found"}, status=404)

            # Get the file cache directory
            cache_dir = coordinator.get_file_cache_directory()
            if not cache_dir:
                return web.json_response({"error": "File cache not enabled"}, status=400)

            # Construct the full file path
            full_path = Path(cache_dir) / filepath

            # Security check: ensure the file is within the cache directory
            try:
                full_path.resolve().relative_to(Path(cache_dir).resolve())
            except ValueError:
                return web.json_response({"error": "Access denied"}, status=403)

            # Check if file exists
            if not full_path.exists() or not full_path.is_file():
                return web.json_response({"error": "File not found"}, status=404)

            # Get file info
            stat = full_path.stat()
            content_type, _ = mimetypes.guess_type(str(full_path))
            if not content_type:
                content_type = 'application/octet-stream'

            # Read and serve the file
            async with aiofiles.open(full_path, 'rb') as f:
                content = await f.read()

            # Always set Content-Disposition: attachment
            headers = {
                'Content-Type': content_type,
                'Content-Length': str(stat.st_size),
                'Cache-Control': 'public, max-age=3600',  # Cache for 1 hour
                'Last-Modified': datetime.fromtimestamp(stat.st_mtime).strftime('%a, %d %b %Y %H:%M:%S GMT'),
                'Content-Disposition': f'attachment; filename="{os.path.basename(filepath)}"',
            }

            return web.Response(
                body=content,
                headers=headers
            )
        except Exception as e:
            LOGGER.error(f"Error serving file: {e}")
            return web.json_response({"error": "Internal server error"}, status=500)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up the Bambu Lab integration."""
    LOGGER.debug("async_setup_entry Start")
    coordinator = BambuDataUpdateCoordinator(hass, entry=entry)
    await coordinator.async_config_entry_first_refresh()

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = coordinator

    # Register file cache API endpoints
    LOGGER.info("Registering file cache API endpoints")
    hass.http.register_view(FileCacheAPIView(hass))
    hass.http.register_view(FileCacheFileView(hass))
    LOGGER.info("File cache API endpoints registered successfully")

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