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
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator
from homeassistant.core import CALLBACK_TYPE, Event, HomeAssistant, callback
from homeassistant.const import CONF_HOST, EVENT_HOMEASSISTANT_STOP
import paho.mqtt.client as mqtt
from .pybambu import BambuClient
from .pybambu.const import Features

class BambuDataUpdateCoordinator(DataUpdateCoordinator):
    config_entry: ConfigEntry

    def __init__(self, hass, *, entry: ConfigEntry) -> None:
        self._entry = entry
        LOGGER.debug(f"{entry.entry_id}")
        LOGGER.debug(f"Entry: {entry.data}")
        self.client = BambuClient(entry.data["host"], entry.data["serial"], entry.data["access_code"],
                                  entry.data["tls"], entry.data["device_type"])

        LOGGER.debug("Setting starting data")
        self.data = self.client.get_device()
        LOGGER.debug(f"Data: {self.data.__dict__}")
        LOGGER.debug("_use_mqtt")
        self._use_mqtt()
        super().__init__(
            hass,
            LOGGER,
            name=DOMAIN,
            update_interval=SCAN_INTERVAL
        )

    @callback
    def _use_mqtt(self) -> None:
        """Use MQTT for updates, instead of polling."""

        def message_handler(message):
            self.async_set_updated_data(message)

        async def listen():
            LOGGER.debug("Use MQTT: Listen")
            self.client = BambuClient(self._entry.data["host"], self._entry.data["serial"],
                                      self._entry.data["access_code"], self._entry.data["tls"],
                                      self._entry.data["device_type"])
            await self.client.connect(callback=message_handler)

        asyncio.create_task(listen())

    async def _publish(self, msg):
        return self.client.publish(msg)

    async def _async_update_data(self):
        LOGGER.debug(f"_async_update_data: MQTT connected: {self.client.connected}")
        return self.client.get_device()

    async def wait_for_data_ready(self):
        """Wait until we have received version data"""
        LOGGER.debug("WAITING FOR DATA READY")
        while (self.data == None) or (self.data.info.device_type) == "Unknown":
            await asyncio.sleep(1)
        return
