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

    def __init__(self, host: str, serial = None):
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
        LOGGER.debug("Connect: Attempting Connection")
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
        self.subscribe(self._serial)

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
          template = "An exception of type {0} occurred. Arguments:\n{1!r}"
          message = template.format(type(e).__name__, e.args)
          LOGGER.debug(message)

        # TODO: This should return, however it appears to cause blocking issues in HA
        # return self._callback(self._device)

    def subscribe(self, serial):
        """Subscribe to report topic"""
        if (serial == None):
          LOGGER.debug(f"Subscribing: Device/#/report")
          self.client.subscribe("device/#/report")
        else:
          LOGGER.debug(f"Subscribing: Device/{serial}/report")
          self.client.subscribe(f"device/{serial}/report")

    def get_device(self):
        """Return device"""
        LOGGER.debug(f"Get Device: Returning device: {self._device}")
        return self._device
 
    def disconnect(self):
        """Disconnect the Bambu Client from server"""
        LOGGER.debug("Disconnect: Client Disconnecting")
        self.client.disconnect()

    async def try_connection(self, serial):
        """Test if we can connect to an MQTT broker."""
        LOGGER.debug("Try Connection")

        result: queue.Queue[bool] = queue.Queue(maxsize=1)

        def on_message(client, userdata, message):
            """Wait for a message and grab the serial number from topic"""
            self._serial = message.topic.split('/')[1]
            LOGGER.debug(f"Try Connection: Got '{message}'")
            LOGGER.debug(f"Try Connection: Got topic and serial {self._serial}")
            result.put(True)

        self._serial = serial
        self.client.on_connect = self.on_connect
        self.client.on_disconnect = self.on_disconnect
        self.client.on_message = on_message
        LOGGER.debug("Try Connection: Connecting to %s for connection test", self.host)
        self.client.connect(self.host, 1883)
        self.client.loop_start()

        try:
            if result.get(timeout=5):
                return self._serial
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
