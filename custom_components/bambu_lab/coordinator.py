from __future__ import annotations

from .const import (
    BRAND,
    DOMAIN,
    LOGGER,
    PLATFORMS,
    SCAN_INTERVAL,
)
import asyncio
import json
import time
import threading
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers import device_registry
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator
from homeassistant.core import CALLBACK_TYPE, Event, HomeAssistant, callback
from homeassistant.const import CONF_HOST, EVENT_HOMEASSISTANT_STOP, Platform

import paho.mqtt.client as mqtt

from .pybambu import BambuClient
from .pybambu.const import Features

class BambuDataUpdateCoordinator(DataUpdateCoordinator):
    hass: HomeAssistant
    _updatedDevice: bool
    _entry: ConfigEntry

    def __init__(self, hass, *, entry: ConfigEntry) -> None:
        self._hass = hass
        self._entry = entry
        LOGGER.debug(f"ConfigEntry.Id: {entry.entry_id}")
        self.client = BambuClient(device_type = entry.data.get("device_type", "X1C"),
                                  serial = entry.data["serial"],
                                  host = entry.data["host"],
                                  username = entry.data.get("username", "bblp"),
                                  access_code = entry.data["access_code"])

        self._updatedDevice = False
        self.data = self.get_model()
        self._lock = threading.Lock()
        super().__init__(
            hass,
            LOGGER,
            name=DOMAIN,
            update_interval=SCAN_INTERVAL
        )

    @callback
    async def start_mqtt(self) -> None:
        """Use MQTT for updates."""
        LOGGER.debug("Starting MQTT")

        def event_handler(event):
            match event:
                case "event_printer_info_update":
                    self._update_device_info()
                    if self.get_model().supports_feature(Features.EXTERNAL_SPOOL):
                        self._update_external_spool_info()

                case "event_ams_info_update":
                    self._update_ams_info()

                case "event_light_update":
                    self._update_data()

                case "event_speed_update":
                    self._update_data()

                case "event_printer_data_update":
                    self._update_data()

                case "event_ams_data_update":
                    self._update_data()

                case "event_virtual_tray_data_update":
                    self._update_data()

                case "event_hms_errors":
                    self._update_hms()

                case "event_print_canceled":
                    self.PublishDeviceTriggerEvent(event)

                case "event_print_failed":
                    self.PublishDeviceTriggerEvent(event)

                case "event_print_finished":
                    self.PublishDeviceTriggerEvent(event)

                case "event_print_started":
                    self.PublishDeviceTriggerEvent(event)


        async def listen():
            await self.client.connect(callback=event_handler)

        asyncio.create_task(listen())

    def shutdown(self) -> None:
        """ Halt the MQTT listener thread """
        self.client.disconnect()

    async def _publish(self, msg):
        return self.client.publish(msg)

    async def _async_update_data(self):
        LOGGER.debug(f"HA POLL: MQTT connected: {self.client.connected}")
        device = self.get_model()
        return device
    
    def _update_data(self):
        self._lock.acquire()
        device = self.get_model()
        self.async_set_updated_data(device)
        self._lock.release()

    def _update_hms(self):
        dev_reg = device_registry.async_get(self._hass)
        hadevice = dev_reg.async_get_device(identifiers={(DOMAIN, self.get_model().info.serial)})

        device = self.get_model()
        if device.hms.count == 0:
            event_data = {
                "device_id": hadevice.id,
                "type": "event_printer_error_cleared",
            }
            LOGGER.debug(f"EVENT: HMS errors cleared: {event_data}")
            self._hass.bus.async_fire(f"{DOMAIN}_event", event_data)
        else:
            for index in range (device.hms.count):
                event_data = {
                    "device_id": hadevice.id,
                    "type": "event_printer_error",
                }
                event_data["hms_code"] = device.hms.errors[f"{index+1}-Error"][:device.hms.errors[f"{index+1}-Error"].index(':')]
                event_data["description"] = device.hms.errors[f"{index+1}-Error"][device.hms.errors[f"{index+1}-Error"].index(':')+2:]
                event_data["url"] = device.hms.errors[f"{index+1}-Wiki"]
                LOGGER.debug(f"EVENT: HMS errors: {event_data}")
                self._hass.bus.async_fire(f"{DOMAIN}_event", event_data)

    def _update_device_info(self):
        if not self._updatedDevice:
            device = self.get_model()
            new_sw_ver = device.info.sw_ver
            new_hw_ver = device.info.hw_ver
            LOGGER.debug(f"'{new_sw_ver}' '{new_hw_ver}'")
            if (new_sw_ver != "unknown"):
                self._lock.acquire()
                dev_reg = device_registry.async_get(self._hass)
                hadevice = dev_reg.async_get_device(identifiers={(DOMAIN, self.get_model().info.serial)})
                dev_reg.async_update_device(hadevice.id, sw_version=new_sw_ver, hw_version=new_hw_ver)

                # Fix up missing or incorrect device_type now that we know what the printer model is.
                device_type = self.get_model().info.device_type
                if self._entry.data.get("device_type", "") != device_type:
                    LOGGER.debug(f"Force updating device type: {device_type}")
                    self._hass.config_entries.async_update_entry(
                        self._entry,
                        title=self._entry.data["serial"],
                        data={
                            "device_type": device_type,
                            "serial": self._entry.data["serial"],
                            "host": self._entry.data["host"],
                            "username": self._entry.data.get("username", "bblp"),
                            "access_code": self._entry.data["access_code"]
                        }
                    )
                self._updatedDevice = True
                self._lock.release()

    async def _reinitialize_sensors(self):
        LOGGER.debug("_reinitialize_sensors START")
        if self._lock.acquire(False):
            LOGGER.debug("async_forward_entry_unload")
            await self.hass.config_entries.async_forward_entry_unload(self.config_entry, Platform.SENSOR)
            LOGGER.debug("async_forward_entry_setup")
            await self.hass.config_entries.async_forward_entry_setup(self.config_entry, Platform.SENSOR)
            self._lock.release()
        LOGGER.debug("_reinitialize_sensors DONE")

    def _update_ams_info(self):
        self._lock.acquire()
        device = self.get_model()
        dev_reg = device_registry.async_get(self._hass)
        for index in range (0, len(device.ams.data)):
            LOGGER.debug(f"Initialize AMS {index+1}")
            hadevice = dev_reg.async_get_or_create(config_entry_id=self._entry.entry_id,
                                                   identifiers={(DOMAIN, device.ams.data[index].serial)})
            serial = self._entry.data["serial"]
            device_type = self._entry.data["device_type"]
            dev_reg.async_update_device(hadevice.id,
                                        name=f"{device_type}_{serial}_AMS_{index+1}",
                                        model="AMS",
                                        manufacturer=BRAND,
                                        sw_version=device.ams.data[index].sw_version,
                                        hw_version=device.ams.data[index].hw_version)

        self._lock.release()
        self.hass.async_create_task(self._reinitialize_sensors())

    def _update_external_spool_info(self):
        self._lock.acquire()
        dev_reg = device_registry.async_get(self._hass)
        hadevice = dev_reg.async_get_or_create(config_entry_id=self._entry.entry_id,
                                               identifiers={(DOMAIN, f"{self.get_model().info.serial}_ExternalSpool")})
        serial = self._entry.data["serial"]
        device_type = self._entry.data["device_type"]
        dev_reg.async_update_device(hadevice.id,
                                    name=f"{device_type}_{serial}_ExternalSpool",
                                    model="External Spool",
                                    manufacturer=BRAND,
                                    sw_version="",
                                    hw_version="")
        
        self._lock.release()
        # self.hass.async_create_task(self._reinitialize_sensors())

    def PublishDeviceTriggerEvent(self, event: str):
        dev_reg = device_registry.async_get(self._hass)
        hadevice = dev_reg.async_get_device(identifiers={(DOMAIN, self.get_model().info.serial)})

        event_data = {
            "device_id": hadevice.id,
            "type": event,
        }
        LOGGER.debug(f"EVENT: {event}: {event_data}")
        self._hass.bus.async_fire(f"{DOMAIN}_event", event_data)
        

    def get_model(self):
        return self.client.get_device()

    def get_printer_device(self):
        printer_serial = self._entry.data["serial"]
        device_type = self._entry.data["device_type"]

        return DeviceInfo(
            identifiers={(DOMAIN, printer_serial)},
            name=f"{device_type}_{printer_serial}",
            manufacturer=BRAND,
            model=device_type,
            hw_version=self.get_model().info.hw_ver,
            sw_version=self.get_model().info.sw_ver,
        )

    def get_ams_device(self, index):
        printer_serial = self._entry.data["serial"]
        device_type = self._entry.data["device_type"]
        device_name=f"{device_type}_{printer_serial}_AMS_{index+1}"

        return DeviceInfo(
            identifiers={(DOMAIN, self.get_model().ams.data[index].serial)},
            via_device=(DOMAIN, printer_serial),
            name=device_name,
            model="AMS",
            manufacturer=BRAND,
            hw_version=self.get_model().ams.data[index].hw_version,
            sw_version=self.get_model().ams.data[index].sw_version
        )

    def get_virtual_tray_device(self):
        printer_serial = self._entry.data["serial"]
        device_type = self._entry.data["device_type"]
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
