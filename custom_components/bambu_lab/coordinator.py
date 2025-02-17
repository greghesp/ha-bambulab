from __future__ import annotations

from .const import (
    BRAND,
    DOMAIN,
    LOGGER,
    LOGGERFORHA,
    Options,
    OPTION_NAME,
)
import asyncio
from typing import Any

from homeassistant import config_entries
from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers import device_registry
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator
from homeassistant.core import Event, HomeAssistant, callback
from homeassistant.const import (
    EVENT_HOMEASSISTANT_STOP,
    Platform
)

from .pybambu import BambuClient
from .pybambu.const import (
    Features,
    PRINT_PROJECT_FILE_BUS_EVENT,
    SEND_GCODE_BUS_EVENT,
    SKIP_OBJECTS_BUS_EVENT,
    MOVE_AXIS_BUS_EVENT,
    EXTRUDE_RETRACT_BUS_EVENT,
    LOAD_FILAMENT_BUS_EVENT,
    UNLOAD_FILAMENT_BUS_EVENT,
)
from .pybambu.commands import (
    PRINT_PROJECT_FILE_TEMPLATE,
    SEND_GCODE_TEMPLATE,
    SKIP_OBJECTS_TEMPLATE,
    MOVE_AXIS_GCODE,
    HOME_GCODE,
    EXTRUDER_GCODE,
    SWITCH_AMS_TEMPLATE,
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
        self.hass.bus.async_listen(PRINT_PROJECT_FILE_BUS_EVENT, self._service_call_print_project_file)
        self.hass.bus.async_listen(SEND_GCODE_BUS_EVENT, self._service_call_send_gcode)
        self.hass.bus.async_listen(SKIP_OBJECTS_BUS_EVENT, self._service_call_skip_objects)
        self.hass.bus.async_listen(MOVE_AXIS_BUS_EVENT, self._service_call_move_axis)
        self.hass.bus.async_listen(EXTRUDE_RETRACT_BUS_EVENT, self._service_call_extrude_retract)
        self.hass.bus.async_listen(LOAD_FILAMENT_BUS_EVENT, self._service_call_load_filament)
        self.hass.bus.async_listen(UNLOAD_FILAMENT_BUS_EVENT, self._service_call_unload_filament)

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
        self.client.disconnect()

    async def _publish(self, msg):
        return self.client.publish(msg)

    def _service_call_is_for_me(self, data: dict):
        dev_reg = device_registry.async_get(self._hass)
        hadevice = dev_reg.async_get_device(identifiers={(DOMAIN, self.get_model().info.serial)})
        device_id = data.get('device_id', [])
        if len(device_id) != 1:
            LOGGER.error("Invalid skip objects data payload: {data}")
            return False

        return (device_id[0] == hadevice.id)

    def _service_call_skip_objects(self, event: Event):
        data = event.data
        if not self._service_call_is_for_me(data):
            return
        
        LOGGER.debug(f"_service_call_skip_objects: {data}")
        command = SKIP_OBJECTS_TEMPLATE
        object_ids = data.get("objects")
        command["print"]["obj_list"] = [int(x) for x in object_ids.split(',')]
        self.client.publish(command)

    def _service_call_send_gcode(self, event: Event):
        data = event.data
        if not self._service_call_is_for_me(data):
            return
        
        LOGGER.debug(f"_service_call_send_gcode: {data}")
        command = SEND_GCODE_TEMPLATE
        command['print']['param'] = f"{data.get('command')}\n"
        self.client.publish(command)

    def _service_call_move_axis(self, event: Event):
        data = event.data
        if not self._service_call_is_for_me(data):
            return

        LOGGER.debug(f"_service_call_move_axis: {data}")

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

    def _service_call_extrude_retract(self, event: Event):
        data = event.data
        if not self._service_call_is_for_me(data):
            return

        LOGGER.debug(f"_service_call_extrude_retract: {data}")

        move = data.get('type').upper()
        force = data.get('force')

        if move not in ['EXTRUDE', 'RETRACT']:
            LOGGER.error(f"Invalid extrusion move '{move}'")
            return False

        nozzle_temp = self.get_model().temperature.nozzle_temp
        if force is not True and nozzle_temp < 170:
            LOGGER.error(f"Nozzle temperature too low to perform extrusion: {nozzle_temp}ºC")
            return False

        command = SEND_GCODE_TEMPLATE
        gcode = EXTRUDER_GCODE
        distance = (1 if move == 'EXTRUDE' else -1) * 10

        gcode = gcode.format(distance=distance)

        command['print']['param'] = gcode
        self.client.publish(command)

    def _service_call_load_filament(self, event: Event):
        data = event.data
        if not self._service_call_is_for_me(data):
            return

        LOGGER.debug(f"_service_call_load_filament: {data}")

        # Printers with older firmware require a different method to change
        # filament. For now, only support newer firmware.
        if not self.get_model().supports_feature(Features.AMS_SWITCH_COMMAND):
            LOGGER.error(f"Loading filament is not available for this printer's firmware version, please update it")
            return False

        tray = int(data.get('tray', 1))
        temperature = int(data.get('temperature', 0))

        if data.get('external_spool') is True:
            tray = 254
            # Unless a target temperature override is set, try and find the
            # midway temperature of the filament set in the ext spool
            ext_spool = self.get_model().external_spool
            if data.get('temperature') is None and not ext_spool.empty:
                temperature = (int(ext_spool.nozzle_temp_min) + int(ext_spool.nozzle_temp_max)) / 2
        elif not self.get_model().supports_feature(Features.AMS):
            LOGGER.error(f"AMS not available")
            return False
        elif data.get('tray') is not None and tray >= 1 and tray <= 16:
            # Zero-index the tray ID and find the AMS index
            tray = tray -1
            ams_idx = (tray // 4)
            
            # Check the AMS exists and has filament
            if not self.get_model().ams.data[ams_idx] or self.get_model().ams.data[ams_idx].tray[tray].empty:
                LOGGER.error(f"AMS tray '{data.get('tray')}' is empty")
                return False

            # Unless a target temperature override is set, try and find the
            # midway temperature of the filament set in the ext spool
            if data.get('temperature') is None:
                ams_tray = self.get_model().ams.data[ams_idx].tray[tray]
                temperature = (int(ams_tray.nozzle_temp_min) + int(ams_tray.nozzle_temp_max)) / 2
        else:
            LOGGER.error(f"An AMS tray or external spool is required")
            return False

        command = SWITCH_AMS_TEMPLATE
        command['print']['target'] = tray
        command['print']['tar_temp'] = temperature
        self.client.publish(command)

    def _service_call_unload_filament(self, event: Event):
        data = event.data
        if not self._service_call_is_for_me(data):
            return

        LOGGER.debug(f"_service_call_unload_filament: {data}")

        if not self.get_model().supports_feature(Features.AMS_SWITCH_COMMAND):
            LOGGER.error(f"Loading filament is not available for this printer's firmware version, please update it")
            return
        
        command = SWITCH_AMS_TEMPLATE
        command['print']['target'] = 255
        self.client.publish(command)

    def _service_call_print_project_file(self, event: Event):
        data = event.data
        if not self._service_call_is_for_me(data):
            return

        LOGGER.debug(f"_service_call_print_project_file: {data}")
        command = PRINT_PROJECT_FILE_TEMPLATE
        file = data.get("filepath")
        plate = data.get("plate")
        timelapse = data.get("timelapse")
        bed_leveling = data.get("bed_leveling")
        flow_cali = data.get("flow_cali")
        vibration_cali = data.get("vibration_cali")
        layer_inspect = data.get("layer_inspect")
        use_ams = data.get("use_ams")
        ams_mapping = data.get("ams_mapping")

        command["print"]["param"] = f"Metadata/plate_{plate}.gcode"
        command["print"]["url"] = f"ftp://{file}"
        command["print"]["timelapse"] = timelapse
        command["print"]["bed_leveling"] = bed_leveling
        command["print"]["flow_cali"] = flow_cali
        command["print"]["vibration_cali"] = vibration_cali
        command["print"]["layer_inspect"] = layer_inspect
        command["print"]["use_ams"] = use_ams
        command["print"]["ams_mapping"] = [int(x) for x in ams_mapping.split(',')]

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
        LOGGER.debug("async_forward_entry_setups")
        await self.hass.config_entries.async_forward_entry_setups(self.config_entry, [Platform.SENSOR])
        LOGGER.debug("_reinitialize_sensors DONE")

    def _update_ams_info(self):
        LOGGER.debug("_update_ams_info")

        # We don't need to add the AMS devices here as home assistant will ignore devices with no sensors and
        # automatically add devices when we add sensors linked to them with the device we pass when adding the
        # sensors - which is controlled in the single get_ams_device() method.

        # But we can use this to clean up orphaned AMS devices such as when an AMS is moved between printers.
        existing_ams_devices = []
        for index in range (0, len(self.get_model().ams.data)):
            ams_entry = self.get_model().ams.data[index]
            if ams_entry is not None:
                existing_ams_devices.append(ams_entry.serial)

        config_entry_id=self.config_entry.entry_id
        dev_reg = device_registry.async_get(self._hass)
        ams_devices_to_remove = []
        for device in dev_reg.devices.values():
            if config_entry_id in device.config_entries:
                # This device is associated with this printer.
                if device.model == 'AMS':
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
        printer_serial = self.config_entry.data["serial"]
        device_type = self.config_entry.data["device_type"]
        device_name=f"{device_type}_{printer_serial}_AMS_{index+1}"
        ams_serial = self.get_model().ams.data[index].serial

        return DeviceInfo(
            identifiers={(DOMAIN, ams_serial)},
            via_device=(DOMAIN, printer_serial),
            name=device_name,
            model="AMS",
            manufacturer=BRAND,
            hw_version=self.get_model().ams.data[index].hw_version,
            sw_version=self.get_model().ams.data[index].sw_version
        )

    def get_virtual_tray_device(self):
        printer_serial = self.config_entry.data["serial"]
        device_type = self.config_entry.data["device_type"]
        device_name=f"{device_type}_{printer_serial}_ExternalSpool"

        return DeviceInfo(
            identifiers={(DOMAIN, f"{printer_serial}_ExternalSpool")},
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
        
        if option == Options.MANUALREFRESH:
            await self.client.set_manual_refresh_mode(enable)
        
        force_reload = False
        match option:
            case Options.CAMERA:
                force_reload = True
            case Options.IMAGECAMERA:
                force_reload = True
            case Options.FTP:
                force_reload = True
            case Options.TIMELAPSE:
                force_reload = True

        if force_reload:
            # Force reload of sensors.
            return await self.hass.config_entries.async_reload(self._entry.entry_id)
