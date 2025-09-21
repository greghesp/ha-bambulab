from __future__ import annotations

from .const import (
    BRAND,
    DOMAIN,
    LOGGER,
    LOGGERFORHA,
    Options,
    OPTION_NAME,
    SERVICE_CALL_EVENT,
    FILAMENT_DATA,
)
import asyncio
import re
import time
import os
from pathlib import Path
from datetime import datetime
from typing import Any, Optional, List, Dict

from homeassistant import config_entries
from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers import (
    device_registry,
    entity_registry
)
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator
from homeassistant.core import Event, HomeAssistant, callback
from homeassistant.const import (
    EVENT_HOMEASSISTANT_STOP,
    Platform
)
from homeassistant.helpers import issue_registry

from .pybambu import BambuClient
from .pybambu.const import (
    Features,
    Printers
)
from .pybambu.commands import (
    PRINT_PROJECT_FILE_TEMPLATE,
    SEND_GCODE_TEMPLATE,
    SKIP_OBJECTS_TEMPLATE,
    MOVE_AXIS_GCODE,
    HOME_GCODE,
    EXTRUDER_GCODE,
    SWITCH_AMS_TEMPLATE,
    AMS_FILAMENT_SETTING_TEMPLATE,
)

class BambuDataUpdateCoordinator(DataUpdateCoordinator):
    hass: HomeAssistant
    _updatedDevice: bool
    latest_usage_hours: float

    def __init__(self, hass, *, entry: ConfigEntry) -> None:
        self._hass = hass
        self._entry = entry
        LOGGER.debug(f"ConfigEntry.Id: {entry.entry_id}")

        self.latest_usage_hours = float(entry.options.get('usage_hours', 0))
        config = entry.data.copy()
        config.update(entry.options.items())
        config['user_language'] = hass.config.language
        self.client = BambuClient(config)
            
        self._updatedDevice = False
        self._shutdown = False
        self.data = self.get_model()
        self._eventloop = asyncio.get_running_loop()
        # Pass LOGGERFORHA logger into HA as otherwise it generates a debug output line every single time we tell it we have an update
        # which fills the logs and makes the useful logging data less accessible.
        super().__init__(
            hass,
            LOGGERFORHA,
            name=DOMAIN
        )

        self.hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, self._async_shutdown)
        self._service_call_listener = self.hass.bus.async_listen(SERVICE_CALL_EVENT, self._handle_service_call_event)

    @callback
    def _async_shutdown(self, event: Event) -> None:
        """Call when Home Assistant is stopping."""
        LOGGER.debug(f"HOME ASSISTANT IS SHUTTING DOWN")
        self.shutdown()

    def event_handler(self, event: str):
        if self._shutdown:
            # Handle race conditions when the integration is being deleted by re-registering and existing device.
            return
        
        # The callback comes in on the MQTT thread. Need to jump to the HA main thread to guarantee thread safety.
        self._eventloop.call_soon_threadsafe(self.event_handler_internal, event)

    def event_handler_internal(self, event: str):
        if self._shutdown:
            # Handle race conditions when the integration is being deleted by re-registering and existing device.
            return
        
        if event == "event_printer_bambu_authentication_failed":
            self._report_authentication_issue();

        if event == "event_printer_info_update":
            self._update_device_info()
            if self.get_model().supports_feature(Features.EXTERNAL_SPOOL):
                self._update_external_spool_info()

        elif event == "event_ams_info_update":
            self._update_ams_info()

        elif event == "event_light_update":
            self._update_data()

        elif event == "event_speed_update":
            self._update_data()

        elif event == "event_printer_data_update":
            self._update_data()

            # Check is usage hours change and persist to config entry if it did.
            if self.latest_usage_hours != self.get_model().info.usage_hours:
                self.latest_usage_hours = self.get_model().info.usage_hours
                LOGGER.debug(f"OVERWRITING USAGE_HOURS WITH : {self.latest_usage_hours}")
                options = dict(self.config_entry.options)
                options['usage_hours'] = self.latest_usage_hours
                self._hass.config_entries.async_update_entry(
                    entry=self.config_entry,
                    title=self.get_model().info.serial,
                    data=self.config_entry.data,
                    options=options)

        elif event == "event_printer_chamber_image_update":
            if self.get_option_enabled(Options.IMAGECAMERA):
                self._update_data()

        elif event == "event_printer_cover_image_update":
            self._update_data()

        elif event == "event_printer_error":
            self._update_printer_error()

        elif event == "event_print_error":
            self._update_print_error()

        # event_print_started
        # event_print_finished
        # event_print_canceled
        # event_print_failed
        elif 'event_print_' in event:
            self.PublishDeviceTriggerEvent(event)

    async def listen(self):
        LOGGER.debug("Starting listen()")
        await self.client.connect(callback=self.event_handler)

    async def start_mqtt(self) -> None:
        """Use MQTT for updates."""
        LOGGER.debug("Starting MQTT")
        asyncio.create_task(self.listen())

    def shutdown(self) -> None:
        """ Halt the MQTT listener thread """
        self._shutdown = True
        
        # Remove event listeners
        self._service_call_listener()
        
        # Disconnect client - this will handle its own thread cleanup
        self.client.disconnect()

    async def _publish(self, msg):
        return self.client.publish(msg)

    def _is_service_call_for_me(self, data: dict):
        dev_reg = device_registry.async_get(self._hass)
        hadevice = dev_reg.async_get_device(identifiers={(DOMAIN, self.get_model().info.serial)})

        device_id = data.get('device_id', [])
        if len(device_id) == 1:
            return (device_id[0] == hadevice.id)

        # Next test if an entity_id is specified and if so, get it's device_id, check if it matches
        entity_id = data.get('entity_id', [])
        if len(entity_id) == 1:
            entity_device = self._get_device_from_entity(entity_id[0])
            if entity_device is None:
                LOGGER.error("Unable to find device from entity")
                return False
            if entity_device.id == hadevice.id:
                return True
            
            # Next test if a via_device_id is specified and if so, check if it matches
            via_device_id = entity_device.via_device_id
            if via_device_id == hadevice.id:
                return True
        else:
            LOGGER.error(f"Invalid data payload: {data}")

        return False

    def _get_device_from_entity(self, entity_id):
        """Get the device associated with a given entity_id."""
        er = entity_registry.async_get(self._hass)
        entity_entry = er.async_get(entity_id)

        if not entity_entry or not entity_entry.device_id:
            return None  # No associated device

        dr = device_registry.async_get(self._hass)
        device_entry = dr.async_get(entity_entry.device_id)

        return device_entry  # Returns a DeviceEntry object or None

    async def _handle_service_call_event(self, event: Event) -> Any:
        data = event.data

        if not self._is_service_call_for_me(data):
            # Call is not for this instance.
            return

        future = self._hass.data[DOMAIN]['service_call_future']
        if future is None:
            LOGGER.error("Future is None")
            future.set_result(False)
            return
        
        result = None
        match data['service']:
            case "skip_objects":
                result = self._service_call_skip_objects(data)
            case "move_axis":
                result = self._service_call_move_axis(data)
            case "extrude_retract":
                result = self._service_call_extrude_retract(data)
            case "load_filament":
                result = self._service_call_load_filament(data)
            case "unload_filament":
                result = self._service_call_unload_filament(data)
            case "set_filament":
                result = self._service_call_set_filament(data)
            case "get_filament_data":
                result = self._service_call_get_filament_data(data)
            case "print_project_file":
                result = self._service_call_print_project_file(data)
            case "send_command":
                result = self._service_call_send_gcode(data)
            case _:
                LOGGER.error(f"Unknown service call: {data}")

        if result is None:
            result = False

        future.set_result(result)
        
    def _service_call_skip_objects(self, data: dict):
        command = SKIP_OBJECTS_TEMPLATE
        object_ids = data.get("objects")
        command["print"]["obj_list"] = [int(x) for x in object_ids.split(',')]
        self.client.publish(command)

    def _service_call_send_gcode(self, data: dict):
        command = SEND_GCODE_TEMPLATE
        command['print']['param'] = f"{data.get('command')}\n"
        self.client.publish(command)

    def _service_call_move_axis(self, data: dict):
        axis = data.get('axis').upper()
        distance = int(data.get('distance') or 10)

        if axis not in ['X', 'Y', 'Z', 'HOME'] or abs(distance) > 100:
            LOGGER.error(f"Invalid axis '{axis}' or distance out of range '{distance}'")
            return False
        
        command = SEND_GCODE_TEMPLATE
        gcode = HOME_GCODE if axis == 'HOME' else MOVE_AXIS_GCODE
        speed = 900 if axis == 'Z' else 3000
        if axis != 'HOME':
            if axis in ['Y', 'Z'] and not self.get_model().is_core_xy:
                LOGGER.debug(f"Non-core XY, reversing '{axis}' axis distance")
                distance = -1 * distance
            gcode = gcode.format(axis=axis, distance=distance, speed=speed)
        
        command['print']['param'] = gcode
        self.client.publish(command)

    def _service_call_extrude_retract(self, data: dict) -> dict:
        move = data.get('type').upper()
        force = data.get('force')

        if move not in ['EXTRUDE', 'RETRACT']:
            LOGGER.error(f"Invalid extrusion move '{move}'")
            return { "Success": False,
                     "Error": "Invalid type specified: '{move}'." }

        nozzle_temp = self.get_model().temperature.nozzle_temp
        if force is not True and nozzle_temp < 170:
            LOGGER.error(f"Nozzle temperature too low to perform extrusion: {nozzle_temp}ºC")
            return { "Success": False,
                     "Error": f"Nozzle temperature too low to perform extrusion: {nozzle_temp}ºC" }

        command = SEND_GCODE_TEMPLATE
        gcode = EXTRUDER_GCODE
        distance = (1 if move == 'EXTRUDE' else -1) * 10

        gcode = gcode.format(distance=distance)

        command['print']['param'] = gcode
        self.client.publish(command)

        return { "Success": True }

    def _get_ams_and_tray_index_from_entity_entry(self, ams_device, entity_entry):
        match = re.search(r"tray_([1-4])$", entity_entry.unique_id)
        # Zero-index the tray ID and find the AMS index
        tray = int(match.group(1)) - 1
        # identifiers is a set of tuples. We only have one tuple in the set - DOMAIN + serial.
        ams_serial = next(iter(ams_device.identifiers))[1]
        ams_index = None
        for key in self.get_model().ams.data.keys():
            ams = self.get_model().ams.data[key]
            if ams is not None:
                if ams.serial == ams_serial:
                    # We found the right AMS.
                    ams_index = key
                    break

        full_tray = tray + ams_index * 4
        LOGGER.debug(f"FINAL TRAY VALUE: {full_tray + 1}/16 = Tray {tray + 1}/4 on AMS {ams_index}")

        return ams_index, tray

    def _service_call_set_filament(self, data: dict):
        device_id = data.get('device_id', [])
        if len(device_id) != 0:
            LOGGER.error("Invalid entity data payload: {data}")
            return False
        entity_id = data.get('entity_id', [])
        if len(entity_id) != 1:
            LOGGER.error("Invalid entity data payload: {data}")
            return False
        entity_id = entity_id[0]

        # Get the AMS device
        ams_device = self._get_device_from_entity(entity_id)
        if ams_device is None:
            LOGGER.error("Unable to find AMS or external spool from entity")
            return None

        # Get the device the AMS is connected to.
        ams_parent_device_id = ams_device.via_device_id

        # Get my device id
        dr = device_registry.async_get(self._hass)
        hadevice = dr.async_get_device(identifiers={(DOMAIN, self.get_model().info.serial)})

        if ams_parent_device_id != hadevice.id:
            return
        
        # This call is for us.
        # Get the entity details.
        er = entity_registry.async_get(self._hass)
        entity_entry = er.async_get(entity_id)
        entity_unique_id = entity_entry.unique_id
        # entity_entry.unique_id is of the form:
        #   X1C_<PRINTERSERIAL>_AMS_<AMSSERIAL>_tray_1
        # or
        #   X1C_<PRINTERSERIAL>_ExternalSpool_external_spool

        if entity_unique_id.endswith('_external_spool'):
            ams_index = 255
            tray = 254
        elif not self.get_model().supports_feature(Features.AMS):
            LOGGER.error(f"AMS not available")
            return False
        elif re.search(r"tray_([1-4])$", entity_unique_id):
            ams_index, tray = self._get_ams_and_tray_index_from_entity_entry(ams_device, entity_entry)
            if ams_index is None:
                LOGGER.error("Unable to locate AMS.")
                return
            ams_tray = self.get_model().ams.data[ams_index].tray[tray]
            if ams_tray.empty:
                LOGGER.error(f"AMS {ams_index + 1} tray {tray + 1} is empty")
                return
        else:
            LOGGER.error(f"An AMS tray or external spool is required")
            return False
        
        tray_color = data.get('tray_color', '')
        # Allow them to include the preceding # in the provided color string.
        tray_color = tray_color.replace('#', '')
        if len(tray_color) == 6:
            # If the provided string is RRGGBB, we need to add the AA value to make it an opaque RRGGBBAA
            tray_color = f"{tray_color}FF"
        # String must be upper case
        tray_color = tray_color.upper()

        command = AMS_FILAMENT_SETTING_TEMPLATE
        command['print']['ams_id'] = ams_index
        command['print']['tray_info_idx'] = data.get('tray_info_idx', '')
        command['print']['tray_id'] = tray
        command['print']['tray_color'] = data.get('tray_color', '')
        command['print']['tray_type'] = data.get('tray_type', '')
        command['print']['nozzle_temp_min'] = data.get('nozzle_temp_min', '200')
        command['print']['nozzle_temp_max'] = data.get('nozzle_temp_max', '240')

        self.client.publish(command)

    def _service_call_get_filament_data(self, data: dict):
        # Create a copy of FILAMENT_DATA
        combined_data = FILAMENT_DATA.copy()
        
        # Only add entries from slicer_settings that don't exist in FILAMENT_DATA otherwise named custom settings entries
        # overwrite the default settings. We can only support one entry per filament id.
        for filament_id, filament_data in self.client.slicer_settings.filaments.items():
            if filament_id not in FILAMENT_DATA:
                combined_data[filament_id] = filament_data
        
        return combined_data

    def _service_call_load_filament(self, data: dict):
        device_id = data.get('device_id', [])
        if len(device_id) != 0:
            LOGGER.error("Invalid entity data payload: {data}")
            return False
        entity_id = data.get('entity_id', [])
        if len(entity_id) != 1:
            LOGGER.error("Invalid entity data payload: {data}")
            return False
        entity_id = entity_id[0]

        # Get the AMS device
        ams_device = self._get_device_from_entity(entity_id)
        if ams_device is None:
            LOGGER.error("Unable to find AMS or external spool from entity")
            return None

        # Get the device the AMS is connected to.
        ams_parent_device_id = ams_device.via_device_id

        # Get my device id
        dr = device_registry.async_get(self._hass)
        hadevice = dr.async_get_device(identifiers={(DOMAIN, self.get_model().info.serial)})

        # This call is for us.

        # Printers with older firmware require a different method to change
        # filament. For now, only support newer firmware.
        if not self.get_model().supports_feature(Features.AMS_SWITCH_COMMAND):
            LOGGER.error(f"Loading filament is not available for this printer's firmware version, please update it")
            return False

        # Get the entity details.
        er = entity_registry.async_get(self._hass)
        entity_entry = er.async_get(entity_id)
        entity_unique_id = entity_entry.unique_id
        # entity_entry.unique_id is of the form:
        #   X1C_<PRINTERSERIAL>_AMS_<AMSSERIAL>_tray_1
        # or
        #   X1C_<PRINTERSERIAL>_ExternalSpool_external_spool

        temperature = int(data.get('temperature', 0))

        if entity_unique_id.endswith('_external_spool'):
            tray = 254
            # Unless a target temperature override is set, try and find the
            # midway temperature of the filament set in the ext spool
            ext_spool = self.get_model().external_spool[0]
            if data.get('temperature') is None and not ext_spool.empty:
                temperature = (int(ext_spool.nozzle_temp_min) + int(ext_spool.nozzle_temp_max)) / 2
        elif not self.get_model().supports_feature(Features.AMS):
            LOGGER.error(f"AMS not available")
            return False
        elif re.search(r"tray_([1-4])$", entity_unique_id):
            ams_index, tray = self._get_ams_and_tray_index_from_entity_entry(ams_device, entity_entry)
            if ams_index is None:
                LOGGER.error("Unable to locate AMS.")
                return

            ams_tray = self.get_model().ams.data[ams_index].tray[tray]
            if ams_tray.empty:
                LOGGER.error(f"AMS {ams_index + 1} tray {tray + 1} is empty")
                return

            # Unless a target temperature override is set, try and find the
            # midway temperature of the filament set in the ext spool
            if data.get('temperature') is None:
                temperature = (int(ams_tray.nozzle_temp_min) + int(ams_tray.nozzle_temp_max)) // 2
        else:
            LOGGER.error(f"An AMS tray or external spool is required")
            return False

        command = SWITCH_AMS_TEMPLATE
        command['print']['target'] = tray
        command['print']['tar_temp'] = temperature
        self.client.publish(command)

    def _service_call_unload_filament(self, data: dict):
        if not self.get_model().supports_feature(Features.AMS_SWITCH_COMMAND):
            LOGGER.error(f"Loading filament is not available for this printer's firmware version, please update it")
            return
        
        command = SWITCH_AMS_TEMPLATE
        command['print']['target'] = 255
        self.client.publish(command)

    def _service_call_print_project_file(self, data: dict):
        command = PRINT_PROJECT_FILE_TEMPLATE
        filepath = data.get("filepath")
        plate = data.get("plate", 1)
        timelapse = data.get("timelapse", False)
        bed_leveling = data.get("bed_leveling", False)
        flow_cali = data.get("flow_cali", False)
        vibration_cali = data.get("vibration_cali", False)
        layer_inspect = data.get("layer_inspect", False)
        use_ams = data.get("use_ams", False)
        ams_mapping = data.get("ams_mapping")

        command["print"]["param"] = f"Metadata/plate_{plate}.gcode"
        if '//' in filepath:
            command["print"]["url"] = filepath
        else:
            if self.config_entry.data["device_type"] in [Printers.H2S, Printers.H2D]:
                command["print"]["url"] = f"ftp:///{filepath}"
            else:
                command["print"]["url"] = f"file:///sdcard/{filepath}"

        command["print"]["timelapse"] = timelapse
        command["print"]["bed_leveling"] = bed_leveling
        command["print"]["flow_cali"] = flow_cali
        command["print"]["vibration_cali"] = vibration_cali
        command["print"]["layer_inspect"] = layer_inspect
        command["print"]["use_ams"] = use_ams
        command["print"]["ams_mapping"] = [int(x) for x in ams_mapping.split(',')]
        command["print"]["subtask_name"] = os.path.basename(filepath)

        self.client.publish(command)

    async def _async_update_data(self):
        LOGGER.debug(f"_async_update_data() called")
        device = self.get_model()
        return device
    
    def _update_data(self):
        device = self.get_model()
        try:
            self.async_set_updated_data(device)
        except Exception as e:
            LOGGER.error("An exception occurred calling async_set_updated_data():")
            LOGGER.error(f"Exception type: {type(e)}")
            LOGGER.error(f"Exception data: {e}")

    def _update_printer_error(self):
        dev_reg = device_registry.async_get(self._hass)
        hadevice = dev_reg.async_get_device(identifiers={(DOMAIN, self.get_model().info.serial)})
        device = self.get_model()
        if device.hms.error_count == 0:
            event_data = {
                "device_id": hadevice.id,
                "name": self.config_entry.options.get('name', ''),
                "type": "event_printer_error_cleared",
            }
            LOGGER.debug(f"EVENT: HMS errors cleared: {event_data}")
            self._hass.bus.async_fire(f"{DOMAIN}_event", event_data)
        else:
            event_data = {
                "device_id": hadevice.id,
                "name": self.config_entry.options.get('name', ''),
                "type": "event_printer_error",
            }
            event_data["code"] = device.hms.errors[f"1-Code"]
            event_data["error"] = device.hms.errors[f"1-Error"]
            event_data["url"] = device.hms.errors[f"1-Wiki"]
            LOGGER.debug(f"EVENT: HMS errors: {event_data}")
            self._hass.bus.async_fire(f"{DOMAIN}_event", event_data)

    def _update_print_error(self):
        dev_reg = device_registry.async_get(self._hass)
        hadevice = dev_reg.async_get_device(identifiers={(DOMAIN, self.get_model().info.serial)})

        device = self.get_model()
        if device.print_error.on == 0:
            event_data = {
                "device_id": hadevice.id,
                "name": self.config_entry.options.get('name', ''),
                "type": "event_print_error_cleared",
            }
            LOGGER.debug(f"EVENT: print_error cleared: {event_data}")
        else:
            event_data = {
                "device_id": hadevice.id,
                "name": self.config_entry.options.get('name', ''),
                "type": "event_print_error",
            }
            event_data["code"] = device.print_error.error['code']
            event_data["error"] = device.print_error.error['error']
            LOGGER.debug(f"EVENT: print_error: {event_data}")
        self._hass.bus.async_fire(f"{DOMAIN}_event", event_data)

    def _update_device_info(self):
        if not self._updatedDevice:
            device = self.get_model()
            new_sw_ver = device.info.sw_ver
            new_hw_ver = device.info.hw_ver
            LOGGER.debug(f"'{new_sw_ver}' '{new_hw_ver}'")
            if (new_sw_ver != "unknown"):
                dev_reg = device_registry.async_get(self._hass)
                hadevice = dev_reg.async_get_device(identifiers={(DOMAIN, self.get_model().info.serial)})
                dev_reg.async_update_device(hadevice.id, sw_version=new_sw_ver, hw_version=new_hw_ver)
                self._updatedDevice = True

    async def _reinitialize_sensors(self):
        LOGGER.debug("_reinitialize_sensors START")
        LOGGER.debug("async_forward_entry_unload")
        await self.hass.config_entries.async_forward_entry_unload(self.config_entry, Platform.SENSOR)
        await self.hass.config_entries.async_forward_entry_unload(self.config_entry, Platform.BINARY_SENSOR)
        LOGGER.debug("async_forward_entry_setups")
        await self.hass.config_entries.async_forward_entry_setups(self.config_entry, [Platform.SENSOR, Platform.BINARY_SENSOR])
        LOGGER.debug("_reinitialize_sensors DONE")

    def _update_ams_info(self):
        LOGGER.debug("_update_ams_info")

        # We don't need to add the AMS devices here as home assistant will ignore devices with no sensors and
        # automatically add devices when we add sensors linked to them with the device we pass when adding the
        # sensors - which is controlled in the single get_ams_device() method.

        # But we can use this to clean up orphaned AMS devices such as when an AMS is moved between printers.
        existing_ams_devices = []
        for index in self.get_model().ams.data.keys():
            ams_entry = self.get_model().ams.data[index]
            if ams_entry is not None:
                existing_ams_devices.append(ams_entry.serial)

        config_entry_id=self.config_entry.entry_id
        dev_reg = device_registry.async_get(self._hass)
        ams_devices_to_remove = []
        for device in dev_reg.devices.values():
            if config_entry_id in device.config_entries:
                # This device is associated with this printer.
                if device.model == 'AMS' or device.model == 'AMS Lite' or device.model == 'AMS 2 Pro' or device.model == 'AMS HT':
                    # And it's an AMS device
                    ams_serial = list(device.identifiers)[0][1]
                    if ams_serial not in existing_ams_devices:
                        LOGGER.debug(f"Found stale attached AMS with serial {ams_serial}")
                        ams_devices_to_remove.append(device.id)

        for device in ams_devices_to_remove:
            LOGGER.debug(f"Removing stale AMS.")
            dev_reg.async_remove_device(device)

        # And now we can reinitialize the sensors, which will trigger device creation as necessary.
        self.hass.async_create_task(self._reinitialize_sensors())

    def _update_external_spool_info(self):
        dev_reg = device_registry.async_get(self._hass)
        hadevice = dev_reg.async_get_or_create(config_entry_id=self.config_entry.entry_id,
                                               identifiers={(DOMAIN, f"{self.get_model().info.serial}_ExternalSpool")})
        serial = self.config_entry.data["serial"]
        device_type = self.config_entry.data["device_type"]
        dev_reg.async_update_device(hadevice.id,
                                    name=f"{device_type}_{serial}_ExternalSpool",
                                    model="External Spool",
                                    manufacturer=BRAND,
                                    sw_version="",
                                    hw_version="")

    def PublishDeviceTriggerEvent(self, event: str):
        dev_reg = device_registry.async_get(self._hass)
        hadevice = dev_reg.async_get_device(identifiers={(DOMAIN, self.get_model().info.serial)})

        event_data = {
            "device_id": hadevice.id,
            "name": self.config_entry.options.get('name', ''),
            "type": event,
        }
        LOGGER.debug(f"BUS EVENT: {event}: {event_data}")
        self._hass.bus.async_fire(f"{DOMAIN}_event", event_data)

    def get_model(self):
        return self.client.get_device()

    def get_printer_device(self):
        printer_serial = self.config_entry.data["serial"]
        device_type = self.config_entry.data["device_type"]

        return DeviceInfo(
            identifiers={(DOMAIN, printer_serial)},
            name=f"{device_type}_{printer_serial}",
            manufacturer=BRAND,
            model=device_type,
            hw_version=self.get_model().info.hw_ver,
            sw_version=self.get_model().info.sw_ver,
        )

    def get_ams_device(self, index):
        # Adjust indices to be 1-based for normal AMS, 128-based for HT.
        ams_index = index
        if ams_index < 128:
            ams_index = index + 1
        printer_serial = self.config_entry.data["serial"]
        device_type = self.config_entry.data["device_type"]
        device_name = f"{device_type}_{printer_serial}_AMS_{ams_index}"
        ams_serial = self.get_model().ams.data[index].serial
        model = self.get_model().ams.data[index].model

        return DeviceInfo(
            identifiers={(DOMAIN, ams_serial)},
            via_device=(DOMAIN, printer_serial),
            name=device_name,
            model=model,
            manufacturer=BRAND,
            hw_version=self.get_model().ams.data[index].hw_version,
            sw_version=self.get_model().ams.data[index].sw_version
        )

    def get_virtual_tray_device(self, index: int):
        printer_serial = self.config_entry.data["serial"]
        device_type = self.config_entry.data["device_type"]
        device_name=f"{device_type}_{printer_serial}_ExternalSpool{'2' if index==1 else ''}"

        return DeviceInfo(
            identifiers={(DOMAIN, f"{printer_serial}_ExternalSpool{'2' if index==1 else ''}")},
            via_device=(DOMAIN, printer_serial),
            name=device_name,
            model="External Spool",
            manufacturer=BRAND,
            hw_version="",
            sw_version=""
        )

    def get_option_enabled(self, option: Options):
        options = dict(self.config_entry.options)

        default = False
        match option:
            case Options.CAMERA:
                default = True
            case Options.FTP:
                default = options.get('local_mqtt', False)

        return options.get(OPTION_NAME[option], default)
        
    async def set_option_enabled(self, option: Options, enable: bool):
        LOGGER.debug(f"Setting {OPTION_NAME[option]} to {enable}")
        options = dict(self.config_entry.options)
                
        options[OPTION_NAME[option]] = enable
        self._hass.config_entries.async_update_entry(
            entry=self.config_entry,
            title=self.get_model().info.serial,
            data=self.config_entry.data,
            options=options)
        
        force_reload = False
        match option:
            case Options.CAMERA:
                force_reload = True
            case Options.IMAGECAMERA:
                force_reload = True
            case Options.FTP:
                force_reload = True

        if force_reload:
            # Force reload of sensors.
            return await self.hass.config_entries.async_reload(self._entry.entry_id)

    def get_option_value(self, option: Options) -> int:
        options = dict(self.config_entry.options)
        default = 0
        return options.get(OPTION_NAME[option], default)
        
    async def set_option_value(self, option: Options, value: int):
        LOGGER.debug(f"Setting {OPTION_NAME[option]} to {value}")
        options = dict(self.config_entry.options)
                
        options[OPTION_NAME[option]] = value
        self._hass.config_entries.async_update_entry(
            entry=self.config_entry,
            title=self.get_model().info.serial,
            data=self.config_entry.data,
            options=options)

        # Force reload of integration to effect cache update.
        return await self.hass.config_entries.async_reload(self._entry.entry_id)

    def _report_authentication_issue(self):
        # issue_id's are permanent - once ignore they will never show again so we need a unique id 
        # per occurrence per integration instance. That does mean we'll fire a new issue every single
        # print attempt since that's when we'll typically encounter the authentication failure as we
        # attempt to get slicer settings.
        timestamp = int(time.time())
        issue_id = f"authentication_failed_{self.get_model().info.serial}_{timestamp}"

        # Report the issue
        LOGGER.debug("Creating issue for authentication failure")
        issue_registry.async_create_issue(
            hass=self._hass,
            domain=DOMAIN,
            issue_id=issue_id,
            is_fixable=False,
            severity=issue_registry.IssueSeverity.ERROR,
            translation_key="authentication_failed",
            translation_placeholders = {"device": self.config_entry.options.get('name', '')},
        )

    def get_file_cache_directory(self) -> Optional[str]:
        """Get the file cache directory for this printer."""
        serial = self.get_model().info.serial
        return f"/config/www/media/ha-bambulab/{serial}"
    
    async def get_cached_files(self, file_type: str) -> List[Dict[str, Any]]:
        """Get list of cached files with metadata."""
        cache_dir = self.get_file_cache_directory()
        if not cache_dir:
            return []
            
        cache_dir = os.path.join(cache_dir, file_type)
        if not os.path.exists(cache_dir):
            return []
        
        files = []
        cache_path = Path(cache_dir)
        cache_root = Path(self.get_file_cache_directory())  # Get the root cache directory
        
        # Define file type patterns
        type_patterns = {
            'prints': ['*.3mf'],
            'gcode': ['*.gcode'],
            'timelapse': ['*.mp4', '*.avi', '*.mov'],
        }
        
        patterns = type_patterns.get(file_type, ['*'])
        
        for pattern in patterns:
            for file_path in cache_path.rglob(pattern):
                if file_path.is_file():
                    # Get file stats
                    stat = file_path.stat()
                    
                    # Determine file type
                    file_ext = file_path.suffix.lower()
                    if file_ext == '.3mf':
                        detected_type = 'prints'
                    elif file_ext == '.gcode':
                        detected_type = 'gcode'
                    elif file_ext in ['.mp4', '.avi', '.mov']:
                        detected_type = 'timelapse'
                    else:
                        detected_type = 'unknown'
                    
                    if detected_type != file_type:
                        continue
                    
                    # Look for thumbnail
                    thumbnail_path = None
                    if detected_type in ['timelapse', 'prints', 'gcode']:
                        # Create thumbnail candidates relative to cache root
                        file_relative_path = file_path.relative_to(cache_root)
                        thumbnail_candidates = [
                            cache_root / file_relative_path.parent / (file_path.stem + '.jpg'),
                            cache_root / file_relative_path.parent / (file_path.stem + '.png'),
                            cache_root / file_relative_path.parent / (file_path.stem + '.jpeg'),
                        ]
                        for thumb_path in thumbnail_candidates:
                            if thumb_path.exists():
                                thumbnail_path = thumb_path  # Store the real path
                                break
                    
                    # Format file size
                    size_bytes = stat.st_size
                    if size_bytes < 1024:
                        size_human = f"{size_bytes} B"
                    elif size_bytes < 1024 * 1024:
                        size_human = f"{size_bytes / 1024:.1f} KB"
                    elif size_bytes < 1024 * 1024 * 1024:
                        size_human = f"{size_bytes / (1024 * 1024):.1f} MB"
                    else:
                        size_human = f"{size_bytes / (1024 * 1024 * 1024):.1f} GB"

                    # Build API path relative to cache root (preserves subdirs like 'cache/')
                    api_path = f"{self.get_model().info.serial}/{file_path.relative_to(cache_root)}"
                    api_thumbnail_path = None
                    if thumbnail_path:
                        api_thumbnail_path = f"{self.get_model().info.serial}/{thumbnail_path.relative_to(cache_root)}"

                    file_info = {
                        'filename': file_path.name,
                        'path': api_path,
                        'type': detected_type,
                        'size': size_bytes,
                        'size_human': size_human,
                        'modified': datetime.fromtimestamp(stat.st_mtime).isoformat(),
                        'thumbnail_path': api_thumbnail_path
                    }
                    
                    files.append(file_info)
        
        # Sort by modification time (newest first)
        files.sort(key=lambda x: x['modified'], reverse=True)
        
        return files
    
    async def clear_file_cache(self, file_type: str = 'all') -> Dict[str, Any]:
        """Clear the file cache."""
        cache_dir = self.get_file_cache_directory()
        if not cache_dir or not os.path.exists(cache_dir):
            return {"success": False, "error": "File cache not enabled or directory not found"}
        
        try:
            cache_path = Path(cache_dir)
            deleted_count = 0
            
            if file_type == 'all':
                # Delete all files in cache directory
                for file_path in cache_path.rglob('*'):
                    if file_path.is_file():
                        file_path.unlink()
                        deleted_count += 1
            else:
                # Delete only specific file type
                type_patterns = {
                    'prints': ['*.3mf'],
                    'gcode': ['*.gcode'],
                    'timelapse': ['*.mp4', '*.avi', '*.mov'],
                }
                
                patterns = type_patterns.get(file_type, [])
                for pattern in patterns:
                    for file_path in cache_path.rglob(pattern):
                        if file_path.is_file():
                            file_path.unlink()
                            deleted_count += 1
            
            return {
                "success": True,
                "deleted_count": deleted_count,
                "file_type": file_type
            }
            
        except Exception as e:
            LOGGER.error(f"Error clearing file cache: {e}")
            return {"success": False, "error": str(e)}

    def check_service_call_payload_for_device(call: ServiceCall):
        LOGGER.debug(call)

        area_ids = call.data.get("area_id", [])
        device_ids = call.data.get("device_id", [])
        entity_ids = call.data.get("entity_id", [])
        label_ids = call.data.get("label_ids", [])

        # Ensure only one device ID is passed
        if not isinstance(area_ids, list) or len(area_ids) != 0:
            LOGGER.error("A single device id must be specified as the target.")
            return False
        if not isinstance(device_ids, list) or len(device_ids) != 1:
            LOGGER.error("A single device id must be specified as the target.")
            return False
        if not isinstance(entity_ids, list) or len(entity_ids) != 0:
            LOGGER.error("A single device id must be specified as the target.")
            return False
        if not isinstance(label_ids, list) or len(label_ids) != 0:
            LOGGER.error("A single device id must be specified as the target.")
            return False
        
        return True

    def check_service_call_payload_for_entity(call: ServiceCall):
        LOGGER.debug(call)

        area_ids = call.data.get("area_id", [])
        device_ids = call.data.get("device_id", [])
        entity_ids = call.data.get("entity_id", [])
        label_ids = call.data.get("label_ids", [])

        # Ensure only one entity ID is passed
        if not isinstance(area_ids, list) or len(area_ids) != 0:
            LOGGER.error("A single entity id must be specified as the target.")
            return False
        if not isinstance(device_ids, list) or len(device_ids) != 0:
            LOGGER.error("A single entity id must be specified as the target.")
            return False
        if not isinstance(entity_ids, list) or len(entity_ids) != 1:
            LOGGER.error("A single entity id must be specified as the target.")
            return False
        if not isinstance(label_ids, list) or len(label_ids) != 0:
            LOGGER.error("A single entity id must be specified as the target.")
            return False
        
        return True
