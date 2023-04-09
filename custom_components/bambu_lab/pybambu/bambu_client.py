from __future__ import annotations
import queue
import json
import ssl
import time

from dataclasses import dataclass
from typing import Any
from threading import Thread

import paho.mqtt.client as mqtt
import asyncio

from .const import LOGGER
from .models import Device
from .commands import (
    CHAMBER_LIGHT_ON,
    CHAMBER_LIGHT_OFF,
    SPEED_PROFILE_TEMPLATE,
    GET_VERSION,
    PAUSE,
    RESUME,
    STOP,
    PUSH_ALL
)


def listen_thread(self):
    LOGGER.debug("MQTT listener thread started.")
    while True:
        try:
            LOGGER.debug(f"Connect: Attempting Connection to {self.host}")
            self.client.connect(self.host, self._port, keepalive=5)
            
            LOGGER.debug("Starting listen loop")
            self.client.loop_forever()
            break
        except Exception as e:
            LOGGER.debug(f"Exception {e.args.__str__}")
            if (e.args.__str__ == 'Host is unreachable'):
                LOGGER.debug("Host is unreachable. Sleeping.")
                time.sleep(5)
            else:
                LOGGER.debug("A listener loop thread exception occurred:")
                LOGGER.debug(f"Exception type: {type(e)}")
                LOGGER.debug(f"Exception args: {e.args}")
                # Avoid a tight loop if this is a persistent error.
                time.sleep(1)
            self.client.disconnect()

@dataclass
class BambuClient:
    """Initialize Bambu Client to connect to MQTT Broker"""

    def __init__(self, device_type: str, serial: str, host: str, access_code: str):
        self.host = host
        self.client = mqtt.Client()
        self._serial = serial
        self._access_code = access_code
        self._connected = False
        self.callback = None
        self._device = Device(self, device_type, serial)
        self._port = 1883

    @property
    def connected(self):
        """Return if connected to server"""
        return self._connected

    async def connect(self, callback):
        """Connect to the MQTT Broker"""
        self.callback = callback
        self.client.on_connect = self.on_connect
        self.client.on_disconnect = self.on_disconnect
        self.client.on_message = self.on_message
        # Set aggressive reconnect polling.
        self.client.reconnect_delay_set(min_delay=1, max_delay=1)

        self.client.tls_set(tls_version=ssl.PROTOCOL_TLS, cert_reqs=ssl.CERT_NONE)
        self.client.tls_insecure_set(True)
        self._port = 8883
        self.client.username_pw_set("bblp", password=self._access_code)

        LOGGER.debug("Starting MQTT listener thread")
        thread = Thread(target=listen_thread, args=(self,))
        thread.start()
        return

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
        LOGGER.debug("On Connect: Getting Version Info")
        self.publish(GET_VERSION)
        LOGGER.debug("On Connect: Request Push All")
        self.publish(PUSH_ALL)

    def on_disconnect(self,
                      client_: mqtt.Client,
                      userdata: None,
                      result_code: int):
        """Called when MQTT Disconnects"""
        LOGGER.debug(f"On Disconnect: Disconnected from Broker: {result_code}")
        self._connected = False

    def on_message(self, client, userdata, message):
        """Return the payload when received"""
        try:
            #LOGGER.debug(f"On Message: Received Message: {message.payload}")
            json_data = json.loads(message.payload)
            if json_data.get("print"):
                self._device.update(data=json_data.get("print"))
                self.callback("event_printer_data_update")
            elif json_data.get("info") and json_data.get("info").get("command") == "get_version":
                LOGGER.debug("Got Version Command Data")
                self._device.update(data=json_data.get("info"))
                self.callback("event_printer_info_update")
        except Exception as e:
            LOGGER.debug("An exception occurred:")
            LOGGER.debug(f"Exception type: {type(e)}")
            LOGGER.debug(f"Exception args: {e.args}")

    def subscribe(self):
        """Subscribe to report topic"""
        LOGGER.debug(f"Subscribing: device/{self._serial}/report")
        self.client.subscribe(f"device/{self._serial}/report")

    def publish(self, msg):
        """Publish a custom message"""
        result = self.client.publish(f"device/{self._serial}/request", json.dumps(msg))
        status = result[0]
        if status == 0:
            LOGGER.debug(f"Sent {msg} to topic device/{self._serial}/request")
            return True

        LOGGER.debug(f"Failed to send message to topic device/{self._serial}/request")
        return False

    def command(self, cmd):
        """Publish a command"""
        if cmd == "CHAMBER_LIGHT_ON":
            return self.publish(CHAMBER_LIGHT_ON)
        if cmd == "CHAMBER_LIGHT_OFF":
            return self.publish(CHAMBER_LIGHT_OFF)

    def get_device(self):
        """Return device"""
        #LOGGER.debug(f"Get Device: Returning device: {self._device}")
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
            json_data = json.loads(message.payload)
            if json_data.get("info") and json_data.get("info").get("command") == "get_version":
                LOGGER.debug("Got Version Command Data")
                self._device.update(data=json_data.get("info"))
                result.put(True)

        self.client.on_connect = self.on_connect
        self.client.on_disconnect = self.on_disconnect
        self.client.on_message = on_message

        self.client.tls_set(tls_version=ssl.PROTOCOL_TLS, cert_reqs=ssl.CERT_NONE)
        self.client.tls_insecure_set(True)
        self.client.username_pw_set("bblp", password=self._access_code)
        self._port = 8883

        LOGGER.debug("Try Connection: Connecting to %s for connection test", self.host)
        self.client.connect(self.host, self._port)
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

