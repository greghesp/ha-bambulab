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
        self.client = BambuClient(entry.data["host"], entry.data["serial"], entry.data["access_code"],
                                  entry.data["tls"])
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
                                      self._entry.data["access_code"], self._entry.data["tls"])
            await self.client.connect(callback=message_handler)

        asyncio.create_task(listen())

    async def _publish(self, msg):
        return self.client.publish(msg)

    async def _async_update_data(self):
        LOGGER.debug(f"_async_update_data: MQTT connected: {self.client.connected}")

        # TODO:  Not sure this is the way to handle this.  Could do with some sort of state
        device = self.client.get_device()
        LOGGER.debug(f"update data device: {device}")
        return device

    async def wait_for_data_ready(self):
        """Wait until we have received version data"""
        counter = 0
        while self.data.info.device_type == "Unknown":
            counter = counter + 1
            if counter == 30:
                raise Exception('Failed to receive version response from printer in 30 seconds') 
            await asyncio.sleep(1)

        return

    def supports_feature(self, feature):
        if feature == Features.AUX_FAN:
            return self.data.info.device_type == "X1C" or self.data.info.device_type == "P1P"
        if feature == Features.CHAMBER_LIGHT:
            return self.data.info.device_type == "X1C" or self.data.info.device_type == "P1P"
        return False
