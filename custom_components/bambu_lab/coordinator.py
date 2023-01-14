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


class BambuDataUpdateCoordinator(DataUpdateCoordinator):

    config_entry: ConfigEntry

    def __init__(self, hass, *, entry: ConfigEntry) -> None:
        self.client = mqtt.Client()
        self.connected = False
        self._entry = entry
        LOGGER.debug(entry)
        super().__init__(
            hass,
            LOGGER,
            name=DOMAIN,
            update_interval=SCAN_INTERVAL
        )

    @callback
    def _use_mqtt(self) -> None:
        """Use MQTT for updates, instead of polling."""
        async def listen() -> None:
            def on_message(client, userdata, message):
                LOGGER.debug(f"Received message {message}")
                self.async_set_updated_data(json.loads(message.payload))

            def on_connect(
                    client_: mqtt.Client,
                    userdata: None,
                    flags: dict[str, Any],
                    result_code: int,
                    properties: mqtt.Properties | None = None,
            ) -> None:
                """Handle connection result."""
                LOGGER.debug("MQTT Connected")
                self.connected = True

            self.client.on_connect = on_connect
            self.client.on_message = on_message
            LOGGER.debug(f"Connecting to MQTT {self._entry.data[CONF_HOST]}")

            self.client.connect(self._entry.data[CONF_HOST], 1883)
            self.client.loop_start()
            LOGGER.debug(f"Subscribing to device/{self._entry.data['serial']}/report")
            self.client.subscribe(f"device/{self._entry.data['serial']}/report")

        async def close_connection(_: Event) -> None:
            self.client.disconnect()
            self.client.loop_stop()
            self.connected = False

        # Clean disconnect WebSocket on Home Assistant shutdown
        self.hass.bus.async_listen_once(
            EVENT_HOMEASSISTANT_STOP, close_connection
        )

        asyncio.create_task(listen())

    async def _async_update_data(self):
        LOGGER.debug(f"Coordinator update connected? {self.connected}")
        if not self.connected:
            self._use_mqtt()

        # TODO:  Not sure this is the way to handle this.  Could do with some sort of state
        return "not_connected"
