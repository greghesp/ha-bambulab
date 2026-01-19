from __future__ import annotations

import asyncio
import functools
import os
import re
import time
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
from homeassistant.helpers import entity_registry as er

from .const import (
    BRAND,
    DOMAIN,
    LOGGER,
    LOGGERFORHA,
    Options,
    OPTION_NAME,
    PLATFORMS,
    SERVICE_CALL_EVENT,
    FILAMENT_DATA,
)

from .pybambu import BambuClient
from .pybambu.const import (
    AMS_MODELS,
    AMS_DRYING_MODELS,
    AMS_MODELS_AND_EXTERNAL_SPOOL,
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
    AMS_READ_RFID_TEMPLATE,
    AMS_READ_RFID_GCODE,
    AMS_FILAMENT_DRYING_TEMPLATE,
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
        config['file_cache_path'] = self.get_file_cache_directory(config['serial'])
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
        LOGGER.debug("HOME ASSISTANT IS SHUTTING DOWN")
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
            self._report_authentication_issue()
        
        elif event == "event_printer_no_external_storage":
            self._report_no_external_storage_issue()

        elif event == "event_printer_live_view_disabled":
            self._report_live_view_disabled_issue()
        
        elif event == "event_printer_mqtt_encryption_enabled":
            self._report_encryption_enabled_issue()

        elif event == "event_printer_ready":
            self._printer_ready()

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

        device_id = data.get('device_id')
        entity_id = data.get('entity_id')
        if device_id is None and entity_id is None:
            LOGGER.error(f"Invalid data payload, neither device_id or entity_id provided: {data}")

        if device_id is not None:
            if entity_id is not None:
                LOGGER.error("Either a device_id or an entity_id must be provided for a service call, not both.")
                return False

            if device_id == hadevice.id:
                return True
            ams_device = dev_reg.async_get(device_id)
            via_device_id = ams_device.via_device_id
            if via_device_id is not None and (via_device_id == hadevice.id):
                return True
            return False

        # Next test if an entity_id is specified and if so, get it's device_id, check if it matches
        if entity_id is not None:
            entity_device = self._get_device_from_entity(entity_id)
            if entity_device is None:
                LOGGER.error("Unable to find device from entity")
                return False
            if entity_device.id == hadevice.id:
                return True
            
            # Next test if a via_device_id is specified and if so, check if it matches
            via_device_id = entity_device.via_device_id
            if via_device_id == hadevice.id:
                return True
            
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
        
        service_call_name = data['service']
        write_action = True
        if service_call_name == 'get_filament_data':
            write_action = False

        if write_action:
            if self.get_model().print_fun.mqtt_signature_required:
                LOGGER.error("Printer firmware requires mqtt encryption. All control actions are blocked.")
                self._report_encryption_enabled_issue(True)
                return False

        future = self._hass.data[DOMAIN]['service_call_future']
        if future is None:
            LOGGER.error("Future is None")
            future.set_result(False)
            return
        
        result = None
        match service_call_name:
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
            case "read_rfid":
                result = self._service_call_read_rfid(data)
            case "print_project_file":
                result = self._service_call_print_project_file(data)
            case "send_command":
                result = self._service_call_send_gcode(data)
            case "start_filament_drying":
                result = self._service_call_filament_drying(data)
            case "stop_filament_drying":
                result = self._service_call_filament_drying(data)
            case _:
                LOGGER.error(f"Unknown service call: {data}")

        if result is None:
            result = False

        future.set_result(result)
        
    def _service_call_skip_objects(self, data: dict):
        command = SKIP_OBJECTS_TEMPLATE
        objects = data.get("objects")

        # normalize to list[int]
        try:
            # Normalize objects into a list of strings
            if isinstance(objects, int):
                parts = [str(objects)]
            elif isinstance(objects, str):
                text = objects.strip()
                if text.startswith("[") and text.endswith("]"):
                    text = text[1:-1].strip()
                parts = [p.strip() for p in text.split(",")]
            elif isinstance(objects, (list, tuple)):
                parts = [str(x).strip() for x in objects]
            else:
                raise ValueError()

            # Step 2: convert parts to ints with validation
            obj_list = [int(p) for p in parts if p.isdigit()]
            if len(obj_list) != len(parts):
                raise ValueError()
        except Exception:
            LOGGER.error(f"Invalid objects value, should be comma separated ID list: {objects!r}")
            return

        command["print"]["obj_list"] = obj_list
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

        nozzle_temp = self.get_model().temperature.active_nozzle_temperature
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
    
    def _get_ams_index_from_device(self, ams_device):
        ams_serial = next(iter(ams_device.identifiers))[1]
        ams_index = None
        for key in self.get_model().ams.data.keys():
            ams = self.get_model().ams.data[key]
            if ams is not None:
                if ams.serial == ams_serial:
                    # We found the right AMS.
                    ams_index = key
                    break
        return ams_index

    def _get_ams_and_tray_index_from_entity_entry(self, ams_device, entity_entry):
        match = re.search(r"tray_([1-4])$", entity_entry.unique_id)
        # Zero-index the tray ID and find the AMS index
        tray = int(match.group(1)) - 1
        # identifiers is a set of tuples. We only have one tuple in the set - DOMAIN + serial.
        ams_index = self._get_ams_index_from_device(ams_device)

        full_tray = tray + ams_index * 4
        LOGGER.debug(f"FINAL TRAY VALUE: {full_tray + 1}/16 = Tray {tray + 1}/4 on AMS {ams_index}")

        return ams_index, tray

    def _get_ams_device_id(self, data: dict):
        device_id = data.get('device_id')
        if device_id is None:
            LOGGER.error(f"Invalid data payload, missing device_id: {data}")
            return None

        dev_reg = device_registry.async_get(self._hass)
        ams_device = dev_reg.async_get(device_id)
        model = ams_device.model
        if model not in AMS_MODELS_AND_EXTERNAL_SPOOL:
            LOGGER.error("Passed device is not an AMS or external spool.")
            return None
        
        return device_id

    def _get_ams_device_and_tray(self, data: dict):
        entity_id = data.get('entity_id')
        if entity_id is None:
            LOGGER.error(f"Invalid data payload, missing entity_id: {data}")
            return None

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
            return None

        return ams_device, entity_id        
    
    def _service_call_filament_drying(self, data:dict):
        device_id = data["device_id"]
        if device_id is None:
            LOGGER.error(f"Invalid data payload, missing device_id: {data}")
            return False

        dev_reg = device_registry.async_get(self._hass)
        ams_device = dev_reg.async_get(device_id)
        model = ams_device.model
        if model not in AMS_DRYING_MODELS:
            LOGGER.error("Passed device is not an AMS 2 or AMS HT.")
            return False
        
        ams_index = self._get_ams_index_from_device(ams_device)
        command = AMS_FILAMENT_DRYING_TEMPLATE
        command['print']['ams_id'] = ams_index
        
        start_command = data['service'] == 'start_filament_drying'
        if start_command:
            temp = data.get('temp')
            if temp is None or temp < 45 or temp > 85:
                LOGGER.error(f"Temperature value of '{temp}' not set or out of range.")
                return False
            if model != 'AMS HT' and temp > 65:
                LOGGER.error(f"Temperature value of {temp}C too high for AMS 2.")
                return False
            command['print']['temp'] = temp
            command['print']['cooling_temp'] = 45 # Must be at least 45 or the command is ignored

            duration = data.get('duration')
            if duration is None or duration < 1 or duration > 24:
                LOGGER.error(f"Duration value of '{duration}' not set or out of range.")
                return False
            command['print']['duration'] = duration
            command['print']['mode'] = 1
            command['print']['rotate_tray'] = data.get('rotate_tray', False)
        else:
            command['print']['mode'] = 0

        self.client.publish(command)

        return True

    def _service_call_read_rfid(self, data:dict):
        ams_device, entity_id = self._get_ams_device_and_tray(data)
        if entity_id is None:
            return False

        # Get the entity details.
        er = entity_registry.async_get(self._hass)
        entity_entry = er.async_get(entity_id)

        ams_index, tray_index = self._get_ams_and_tray_index_from_entity_entry(ams_device, entity_entry)
        if ams_index is None:
            LOGGER.error("Unable to locate AMS.")
            return
        
        if self.get_model().supports_feature(Features.AMS_READ_RFID_COMMAND):
            command = AMS_READ_RFID_TEMPLATE
            command['print']['ams_id'] = ams_index
            command['print']['slot_id'] = tray_index
        else:
            command = SEND_GCODE_TEMPLATE
            gcode = AMS_READ_RFID_GCODE
            gcode = gcode.format(global_tray_index = (ams_index*4) + tray_index)
            command['print']['param'] = gcode
        self.client.publish(command)

    def _service_call_set_filament(self, data: dict):
        ams_device, entity_id = self._get_ams_device_and_tray(data)
        if entity_id is None:
            return False
        
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
            tray_index = 0
        elif not self.get_model().supports_feature(Features.AMS):
            LOGGER.error(f"AMS not available")
            return False
        elif re.search(r"tray_([1-4])$", entity_unique_id):
            ams_index, tray_index = self._get_ams_and_tray_index_from_entity_entry(ams_device, entity_entry)
            if ams_index is None:
                LOGGER.error("Unable to locate AMS.")
                return
            ams_tray = self.get_model().ams.data[ams_index].tray[tray_index]
            if ams_tray.empty:
                LOGGER.error(f"AMS {ams_index + 1} tray {tray_index + 1} is empty")
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
        command['print']['tray_id'] = tray_index
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
        ams_device, entity_id = self._get_ams_device_and_tray(data)
        if entity_id is None:
            return False

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
        #   H2C_<PRINTERSERIAL>_ExternalSpool_external_spool  # Left
        #   H2C_<PRINTERSERIAL>_ExternalSpool2_external_spool # Right

        temperature = int(data.get('temperature', 0))

        if entity_unique_id.endswith('_external_spool'):
            ams_index = 255
            tray = 0
            target = 254
            # search selected external spool by identifier
            suffices = ['']
            if len(self.get_model().external_spool) == 2:
                suffices = ['2', '']
            for i, ext_spool in enumerate(self.get_model().external_spool):
                vtray = self.get_virtual_tray_device(suffices[i])
                if vtray['identifiers'] == ams_device.identifiers:
                    ams_index = 255 - i
                    # Unless a target temperature override is set, try and find the
                    # midway temperature of the filament set in the ext spool
                    if data.get('temperature') is None and not ext_spool.empty:
                        temperature = (int(ext_spool.nozzle_temp_min) + int(ext_spool.nozzle_temp_max)) // 2
                    break
        elif not self.get_model().supports_feature(Features.AMS):
            LOGGER.error(f"AMS not available")
            return False
        elif re.search(r"tray_([1-4])$", entity_unique_id):
            ams_index, tray = self._get_ams_and_tray_index_from_entity_entry(ams_device, entity_entry)
            if ams_index is None:
                LOGGER.error("Unable to locate AMS.")
                return
            # old protocol
            target = ams_index * 4 + tray

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
        command['print']['ams_id'] = ams_index
        command['print']['slot_id'] = tray
        command['print']['target'] = target
        command['print']['tar_temp'] = temperature
        self.client.publish(command)

    def _service_call_unload_filament(self, data: dict):
        device_id = self._get_ams_device_id(data)
        if device_id is None:
            return False

        dev_reg = device_registry.async_get(self._hass)
        ams_device = dev_reg.async_get(device_id)
        ams_index = self._get_ams_index_from_device(ams_device)
        if ams_index is None:
            # External Spool
            ams_index = 255

        # Printers with older firmware require a different method to change
        # filament. For now, only support newer firmware.
        if not self.get_model().supports_feature(Features.AMS_SWITCH_COMMAND):
            LOGGER.error(f"Loading filament is not available for this printer's firmware version, please update it")
            return False

        command = SWITCH_AMS_TEMPLATE
        command['print']['ams_id'] = ams_index
        command['print']['slot_id'] = 255
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
        if use_ams:
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
                dev_reg.async_update_device(hadevice.id, sw_version=new_sw_ver, hw_version=new_hw_ver, serial_number=self.config_entry.data["serial"])
                self._updatedDevice = True

    async def _reinitialize_sensors(self):
        LOGGER.debug("_reinitialize_sensors START")
        LOGGER.debug("async_forward_entry_unload")
        for platform in PLATFORMS:
            await self.hass.config_entries.async_forward_entry_unload(self.config_entry, platform)
        LOGGER.debug("async_forward_entry_setups")
        await self.hass.config_entries.async_forward_entry_setups(self.config_entry, PLATFORMS)
        LOGGER.debug("_reinitialize_sensors DONE")

        # Versions may have changed so update those now that the device and sensors are ready.
        self._update_device_info()

        # Allow HA entity platform to finish adding entities before we try to delete dead ones.
        # Needs to delay two event loop ticks as entity addition is doubly async.
        await asyncio.sleep(0)
        await asyncio.sleep(0)

        # Check for dead entities and clean them up
        LOGGER.debug("Checking for dead entities to remove")
        self._remove_dead_entities()

    def _remove_dead_entities(self):
        """Remove entities no longer created by the integration."""

        entity_registry = er.async_get(self.hass)
        config_entry_id = self.config_entry.entry_id

        entities = [
            entry for entry in entity_registry.entities.values()
            if entry.config_entry_id == config_entry_id
        ]

        for entity in entities:
            state = self.hass.states.get(entity.entity_id)
            if state is not None and state.attributes.get("restored") is True:
                LOGGER.debug(f"{entity.entity_id} is DEAD. Removing it.")
                entity_registry.async_remove(entity.entity_id)
        
    def _printer_ready(self):
        LOGGER.debug(f"_printer_ready: {self.config_entry.data["serial"]}")

        # First clean up orphaned AMS devices such as when an AMS is moved between printers.
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
            LOGGER.debug("Removing stale AMS.")
            dev_reg.async_remove_device(device)

        # And now we can reinitialize the sensors, which will trigger device creation as necessary.
        self.hass.async_create_task(self._reinitialize_sensors())

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

    def get_virtual_tray_device(self, suffix: str):
        printer_serial = self.config_entry.data["serial"]
        device_type = self.config_entry.data["device_type"]
        device_name=f"{device_type}_{printer_serial}_ExternalSpool{suffix}"

        return DeviceInfo(
            identifiers={(DOMAIN, f"{printer_serial}_ExternalSpool{suffix}")},
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

        return options.get(OPTION_NAME[option], default)
        
    async def set_option_enabled(self, option: Options, enable: bool):
        LOGGER.debug(f"Setting {OPTION_NAME[option]} to {enable}")
        options = dict(self.config_entry.options)

        # First make sure we have at least a default value present to compare against.
        if not OPTION_NAME[option] in options:
            options[OPTION_NAME[option]] = self.get_option_enabled(option)

        # Only apply the change if it differs from the current setting.
        if options[OPTION_NAME[option]] != enable:
            options[OPTION_NAME[option]] = enable
            self._hass.config_entries.async_update_entry(
                entry=self.config_entry,
                title=self.get_model().info.serial,
                data=self.config_entry.data,
                options=options)

            # Refresh all entities to handle deleted/added entities.
            self._printer_ready()

            if option == Options.CAMERA:
                # Camera option changed, need to poke bambu client to update its camera state:
                self.client.set_camera_enabled(enable)

    def get_option_value(self, option: Options) -> int:
        options = dict(self.config_entry.options)
        default = 0
        return options.get(OPTION_NAME[option], default)
        
    async def set_option_value(self, option: Options, value: int):
        LOGGER.debug(f"Setting {OPTION_NAME[option]} to {value}")
        options = dict(self.config_entry.options)

        # First make sure we have at least a default value present to compare against.
        if not OPTION_NAME[option] in options:
            options[OPTION_NAME[option]] = self.get_option_enabled(option)

        if options[OPTION_NAME[option]] != value:
            options[OPTION_NAME[option]] = value
            self._hass.config_entries.async_update_entry(
                entry=self.config_entry,
                title=self.get_model().info.serial,
                data=self.config_entry.data,
                options=options)

            # Force reload of integration to effect cache update.
            return await self.hass.config_entries.async_reload(self._entry.entry_id)

    def _report_generic_issue(self, issue: str, force: bool = False):

        issue_id = f"{issue}_{self.get_model().info.serial}"

        # Check if the issue already exists
        registry = issue_registry.async_get(self._hass)
        existing_issue = registry.async_get_issue(domain=DOMAIN, issue_id=issue_id)

        if force:
            # Delete issue so we can re-create it but only ever have one in the list.
            if existing_issue is not None:
                issue_registry.async_delete_issue(hass=self._hass, domain=DOMAIN, issue_id=issue_id)
        else:
            if existing_issue is not None:
                # Issue already exists, no need to create it again
                return

        # Report the issue
        LOGGER.debug(f"Creating issue for {issue}")
        if force:
            severity = issue_registry.IssueSeverity.ERROR
        else:
            severity = issue_registry.IssueSeverity.WARNING
        issue_registry.async_create_issue(
            hass=self._hass,
            domain=DOMAIN,
            issue_id=issue_id,
            is_fixable=False,
            severity=severity,
            translation_key=issue,
            translation_placeholders = {"device": f"'{self.config_entry.options.get('name', '')}'"},
        )

    def _report_authentication_issue(self):
        # issue_id's are permanent - once ignored they will never show again so we need a unique id 
        # per occurrence per integration instance. That does mean we'll fire a new issue every single
        # print attempt since that's when we'll typically encounter the authentication failure as we
        # attempt to get slicer settings.
        self._report_generic_issue("authentication_failed", True)

    def _report_no_external_storage_issue(self):
        self._report_generic_issue("no_external_storage")

    def _report_live_view_disabled_issue(self):
        self._report_generic_issue("live_view_disabled")

    def _report_encryption_enabled_issue(self, force: bool = False):
        self._report_generic_issue("mqtt_encryption_enabled", force)

    def _report_hybrid_mode_blocking_issue(self, force: bool = False):
        self._report_generic_issue("hybrid_mode_blocking", force)

    @functools.lru_cache(maxsize=1)
    def get_file_cache_directory(self, serial: str|None = None) -> str:
        """Get the file cache directory for this printer."""
        if serial is None:
            serial = self.get_model().info.serial
        default_path = Path(self._hass.config.path(f"www/media/ha-bambulab/{serial}"))
        try:
            default_path.mkdir(parents=True, exist_ok=True)
            return str(default_path)
        except (OSError, PermissionError):
            media_dir = self._hass.config.media_dirs.get("local")
            LOGGER.debug(f"Default media directory not writable, falling back to local media directory : '{media_dir}'")
            fallback_path = Path(media_dir) / f"ha-bambulab/{serial}"
            fallback_path.mkdir(parents=True, exist_ok=True)
            return str(fallback_path)

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
