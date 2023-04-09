from __future__ import annotations

from .const import (
    BRAND,
    DOMAIN,
    LOGGER,
    SCAN_INTERVAL,
)
import asyncio
import json
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers import device_registry
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator
from homeassistant.core import CALLBACK_TYPE, Event, HomeAssistant, callback
from homeassistant.const import CONF_HOST, EVENT_HOMEASSISTANT_STOP
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
                                  access_code = entry.data["access_code"])

        self._updatedDevice = False
        self.data = self.client.get_device()
        self._use_mqtt()
        super().__init__(
            hass,
            LOGGER,
            name=DOMAIN,
            update_interval=SCAN_INTERVAL
        )

    @callback
    def _use_mqtt(self) -> None:
        """Use MQTT for updates."""

        def message_handler(message):
            match message:
                case "event_printer_data_update":
                    self._update_device_data()

                case "event_printer_info_update":
                    self._update_device_info()
                    
                case "event_ams_info_update":
                    self._update_ams_info()

        async def listen():
            LOGGER.debug("Use MQTT: Listen")
            await self.client.connect(callback=message_handler)

        asyncio.create_task(listen())

    def shutdown(self) -> None:
        """ Halt the MQTT listener thread """
        self.client.disconnect()

    async def _publish(self, msg):
        return self.client.publish(msg)

    async def _async_update_data(self):
        LOGGER.debug(f"_async_update_data: MQTT connected: {self.client.connected}")
        device = self.client.get_device()
        return device
    
    def _update_device_data(self):
        device = self.client.get_device()
        self.async_set_updated_data(device)

    def _update_device_info(self):
        if not self._updatedDevice:
            device = self.client.get_device()
            new_sw_ver = device.info.sw_ver
            new_hw_ver = device.info.hw_ver
            LOGGER.debug(f"'{new_sw_ver}' '{new_hw_ver}'")
            if (new_sw_ver != "Unknown"):
                dev_reg = device_registry.async_get(self._hass)
                device = dev_reg.async_get_device(identifiers={(DOMAIN, self.data.info.serial)})
                dev_reg.async_update_device(device.id, sw_version=new_sw_ver, hw_version=new_hw_ver)

                # Fix up missing or incorrect device_type now that we know what the printer model is.
                device_type = self.client.get_device().info.device_type
                if self._entry.data.get("device_type", "") != device_type:
                    LOGGER.debug(f"Force updating device type: {device_type}")
                    self._hass.config_entries.async_update_entry(
                        self._entry,
                        title=self._entry.data["serial"],
                        data={
                            "device_type": device_type,
                            "serial": self._entry.data["serial"],
                            "host": self._entry.data["host"],
                            "access_code": self._entry.data["access_code"]
                        }
                    )
                self._updatedDevice = True

    def _update_ams_info(self):
        device = self.client.get_device()
        dev_reg = device_registry.async_get(self._hass)
        for index in range (0, len(device.ams.data)):
            hadevice = dev_reg.async_get_or_create(config_entry_id=self._entry.entry_id,
                                                identifiers={(DOMAIN, device.ams.data[index]["serial"])})
            serial = self._entry.data["serial"]
            device_type = self._entry.data["device_type"]
            dev_reg.async_update_device(hadevice.id,
                                        name=f"{device_type}_{serial}_AMS_{index+1}",
                                        model="AMS",
                                        manufacturer=BRAND,
                                        sw_version=device.ams.data[index]["sw_version"],
                                        hw_version=device.ams.data[index]["hw_version"])
