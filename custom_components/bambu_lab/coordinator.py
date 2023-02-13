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


class BambuDataUpdateCoordinator(DataUpdateCoordinator):
    config_entry: ConfigEntry

    def __init__(self, hass, *, entry: ConfigEntry) -> None:
        self._entry = entry
        self.client = BambuClient(entry.data["host"], entry.data["serial"], entry.data["access_code"],
                                  entry.data["tls"])
        super().__init__(
            hass,
            LOGGER,
            name=DOMAIN,
            update_interval=SCAN_INTERVAL
        )

    @callback
    def _use_mqtt(self) -> None:
        """Use MQTT for updates, instead of polling."""

        LOGGER.debug("Forcing to use MQTT")

        def message_handler(message):
            LOGGER.debug("Received Message")
            self.async_set_updated_data(message)

        async def listen():
            LOGGER.debug("Use MQTT: Listen")
            self.client = BambuClient(self._entry.data["host"], self._entry.data["serial"],
                                      self._entry.data["access_code"], self._entry.data["tls"])
            self.client.connect(callback=message_handler)

        asyncio.create_task(listen())

    async def _publish(self, msg):
        return self.client.publish(msg)

    async def _async_update_data(self):
        LOGGER.debug(f"Coordinator update connected? {self.client.connected}")
        if not self.client.connected:
            self._use_mqtt()

        # TODO:  Not sure this is the way to handle this.  Could do with some sort of state
        device = self.client.get_device()
        LOGGER.debug(f"update data device: {device}")
        return device
