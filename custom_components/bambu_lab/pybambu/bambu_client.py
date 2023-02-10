from __future__ import annotations
import queue
import json

from dataclasses import dataclass
from typing import Any

import paho.mqtt.client as mqtt
from .const import LOGGER
from .models import Device


@dataclass
class BambuClient:
    """Initialize Bambu Client to connect to MQTT Broker"""

    def __init__(self, host: str, serial: str):
        self.host = host
        self.client = mqtt.Client()
        self._serial = serial
        self._connected = False
        self._callback = None
        self._device = Device()

    @property
    def connected(self):
        """Return if connected to server"""
        LOGGER.debug(f"Connected: {self._connected}")
        return self._connected

    def connect(self, callback):
        """Connect to the MQTT Broker"""
        self._callback = callback
        self.client.on_connect = self.on_connect
        self.client.on_disconnect = self.on_disconnect
        self.client.on_message = self.on_message
        LOGGER.debug("Connect: Attempting Connection to {self.host}")
        self.client.connect(self.host, 1883)
        self.client.loop_start()

    def on_connect(self,
                   client_: mqtt.Client,
                   userdata: None,
                   flags: dict[str, Any],
                   result_code: int,
                   properties: mqtt.Properties | None = None, ):
        """Handle connection"""
        LOGGER.debug("On Connect: Connected to Broker")
        self._connected = True
        LOGGER.debug("Now Subscribing...")
        self.subscribe()

    def on_disconnect(self,
                      client_: mqtt.Client,
                      userdata: None,
                      result_code: int ):
        LOGGER.debug(f"On Disconnect: Disconnected from Broker: {result_code}")
        self._connected = False
        self.client.loop_stop()

    def on_message(self, client, userdata, message):
        """Return the payload when received"""
        try:
          LOGGER.debug(f"On Message: Received Message: {message.payload}")
          json_data = json.loads(message.payload)
          if json_data.get("print"):
            self._device.update(data=json_data.get("print"))
        except Exception as e:
          LOGGER.debug("An exception occurred:")
          LOGGER.debug(f"Type: {type(e)}")
          LOGGER.debug(f"Args: {e.args}")

        # TODO: This should return, however it appears to cause blocking issues in HA
        # return self._callback(self._device)

    def subscribe(self):
        """Subscribe to report topic"""
        LOGGER.debug(f"Subscribing: Device/{self._serial}/report")
        self.client.subscribe(f"device/{self._serial}/report")

    def get_device(self):
        """Return device"""
        LOGGER.debug(f"Get Device: Returning device: {self._device}")
        return self._device
 
    def disconnect(self):
        """Disconnect the Bambu Client from server"""
        LOGGER.debug("Disconnect: Client Disconnecting")
        self.client.disconnect()

    async def try_connection(self):
        """Test if we can connect to an MQTT broker."""
        LOGGER.debug("Try Connection")

        result: queue.Queue[bool] = queue.Queue(maxsize=1)

        def on_message(client, userdata, message):
            LOGGER.debug(f"Try Connection: Got '{message}'")
            result.put(True)

        self.client.on_connect = self.on_connect
        self.client.on_disconnect = self.on_disconnect
        self.client.on_message = on_message
        LOGGER.debug("Try Connection: Connecting to %s for connection test", self.host)
        self.client.connect(self.host, 1883)
        self.client.loop_start()

        try:
            if result.get(timeout=10):
                return True
        except queue.Empty:
            return False
        finally:
            self.disconnect()

    async def __aenter__(self):
        """Async enter.
        Returns:
            The BambuLab object.
        """
        return self

    async def __aexit__(self, *_exc_info):
        """Async exit.
        Args:
            _exc_info: Exec type.
        """
        self.disconnect()
