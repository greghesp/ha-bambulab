from __future__ import annotations

from .const import (
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
    _hass: HomeAssistant
    _updatedDevice: bool

    def __init__(self, hass, *, entry: ConfigEntry) -> None:
        self._entry = entry
        self._hass = hass
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
            self.async_set_updated_data(message)
            if not self._updatedDevice:
                new_sw_ver = message.info.sw_ver
                new_hw_ver = message.info.hw_ver
                LOGGER.debug(f"'{new_sw_ver}' '{new_hw_ver}'")
                if (new_sw_ver != "Unknown"):
                    dev_reg = device_registry.async_get(self._hass)
                    device = dev_reg.async_get_device(identifiers={(DOMAIN, self.data.info.serial)})
                    dev_reg.async_update_device(device.id, sw_version=new_sw_ver, hw_version=new_hw_ver)
                    self._updatedDevice = True

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
        return device;

