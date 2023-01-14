from __future__ import annotations
import logging

from dataclasses import dataclass
from typing import Any

import paho.mqtt.client as mqtt
import queue

LOGGER = logging.getLogger(__package__)


@dataclass
class BambuClient:
    def __init__(self, host: str):
        self.host = host
        self.client = mqtt.Client()
        self._serial = None
        self._connected = False

    @property
    def connected(self):
        return self._connected

    def disconnect(self):
        self.client.disconnect()
        self._connected = False
        self.client.loop_stop()

    async def try_connection(self):
        """Test if we can connect to an MQTT broker."""
        result: queue.Queue[bool] = queue.Queue(maxsize=1)

        def on_connect(
                client_: mqtt.Client,
                userdata: None,
                flags: dict[str, Any],
                result_code: int,
                properties: mqtt.Properties | None = None,
        ) -> None:
            """Handle connection result."""
            self._connected = True

        def on_message(client, userdata, message):
            """Wait for a message and grab the serial number from topic"""
            self._serial = message.topic.split('/')[1]
            result.put(True)

        self.client.on_connect = on_connect
        self.client.on_message = on_message
        LOGGER.debug(f"Connecting to {self.host}")
        self.client.connect(self.host, 1883)
        self.client.loop_start()
        self.client.subscribe("device/+/report")

        try:
            if result.get(timeout=5):
                return self._serial
        except queue.Empty:
            return False
        finally:
            self.disconnect()
