from __future__ import annotations

import json
import queue
import ssl
import time
import threading
import struct
import sys
import socket


from dataclasses import dataclass
from typing import Any

import paho.mqtt.client as mqtt

from .const import LOGGER, Features
from .models import Device
from .commands import (
    GET_VERSION,
    PUSH_ALL,
    START_PUSH,
)


class WatchdogThread(threading.Thread):

    def __init__(self, client):
        self._client = client
        self._watchdog_fired = False
        self._stop_event = threading.Event()
        self._last_received_data = time.time()
        super().__init__()

    def stop(self):
        self._stop_event.set()

    def received_data(self):
        self._last_received_data = time.time()

    def run(self):
        LOGGER.debug("Watchdog thread started.")
        WATCHDOG_TIMER = 20
        while True:
            # Wait out the remainder of the watchdog delay or 1s, whichever is higher.
            interval = time.time() - self._last_received_data
            wait_time = max(1, WATCHDOG_TIMER - interval)
            if self._stop_event.wait(wait_time):
                # Stop event has been set. Exit thread.
                break
            interval = time.time() - self._last_received_data
            if not self._watchdog_fired and (interval > WATCHDOG_TIMER):
                LOGGER.debug(f"Watchdog fired. No data received for {interval} seconds.")
                self._watchdog_fired = True
                self._client.on_watchdog_fired()
            elif interval < WATCHDOG_TIMER:
                self._watchdog_fired = False

        LOGGER.debug("Watchdog thread exited.")


class P1PCameraThread(threading.Thread):
    def __init__(self, client):
        self._client = client
        self._stop_event = threading.Event()
        super().__init__()

    def stop(self):
        self._stop_event.set()

    def run(self):
        LOGGER.debug("P1P Camera thread started.")

        d = bytearray()

        username = 'bblp'
        access_code = self._client._access_code
        hostname = self._client.host
        port = 6000

        d += struct.pack("IIL", 0x40, 0x3000, 0x0)
        for i in range(0, len(username)):
            d += struct.pack("<c", username[i].encode('ascii'))
        for i in range(0, 32-len(username)):
            d += struct.pack("<x")
        for i in range(0, len(access_code)):
            d += struct.pack("<c", access_code[i].encode('ascii'))
        for i in range(0, 32-len(access_code)):
            d += struct.pack("<x")

        ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE

        jpeg_start = "ff d8 ff e0"
        jpeg_end = "ff d9"

        read_chunk_size = 1024

        with socket.create_connection((hostname, port)) as sock:
            sslSock = ctx.wrap_socket(sock, server_hostname=hostname)
            sslSock.write(d)
            buf = bytearray()
            start = False

            sslSock.setblocking(False)
            while not self._stop_event.is_set():
                try:
                    dr = sslSock.recv(read_chunk_size)
                except ssl.SSLWantReadError:
                    time.sleep(1)
                    continue

                buf += dr

                if not start:
                    i = buf.find(bytearray.fromhex(jpeg_start))
                    if i >= 0:
                        start = True
                        buf = buf[i:]
                    continue

                i = buf.find(bytearray.fromhex(jpeg_end))
                if i >= 0:
                    img = buf[:i+len(jpeg_end)]
                    buf = buf[i+len(jpeg_end):]
                    start = False

                    self._client.on_jpeg_received(img)

        LOGGER.debug("P1P Camera thread exited.")


def mqtt_listen_thread(self):
    LOGGER.debug("MQTT listener thread started.")
    exceptionSeen = ""
    while True:
        try:
            LOGGER.debug(f"Connect: Attempting Connection to {self.host}")
            self.client.connect(self.host, self._port, keepalive=5)

            LOGGER.debug("Starting listen loop")
            self.client.loop_forever()
            LOGGER.debug("MQTT listener thread exited.")
            break
        except TimeoutError as e:
            if exceptionSeen != "TimeoutError":
                LOGGER.debug(f"TimeoutError: {e.args}.")
            exceptionSeen = "TimeoutError"
            time.sleep(5)
        except ConnectionError as e:
            if exceptionSeen != "ConnectionError":
                LOGGER.debug(f"ConnectionError: {e.args}.")
            exceptionSeen = "ConnectionError"
            time.sleep(5)
        except OSError as e:
            if e.errno == 113:
                if exceptionSeen != "OSError113":
                    LOGGER.debug(f"OSError: {e.args}.")
                exceptionSeen = "OSError113"
                time.sleep(5)
            else:
                LOGGER.error("A listener loop thread exception occurred:")
                LOGGER.error(f"Exception. Type: {type(e)} Args: {e.args}")
                time.sleep(1)  # Avoid a tight loop if this is a persistent error.
        except Exception as e:
            LOGGER.error("A listener loop thread exception occurred:")
            LOGGER.error(f"Exception. Type: {type(e)} Args: {e.args}")
            time.sleep(1)  # Avoid a tight loop if this is a persistent error.
        self.client.disconnect()


@dataclass
class BambuClient:
    """Initialize Bambu Client to connect to MQTT Broker"""
    _watchdog = None
    _camera = None

    def __init__(self, device_type: str, serial: str, host: str, username: str, access_code: str):
        self.host = host
        self.client = mqtt.Client()
        self._serial = serial
        self._access_code = access_code
        self._username = username
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
        self.client.username_pw_set(self._username, password=self._access_code)

        LOGGER.debug("Starting MQTT listener thread")
        thread = threading.Thread(target=mqtt_listen_thread, args=(self,))
        thread.start()

        return

    def subscribe_and_request_info(self):
        LOGGER.debug("Now subscribing...")
        self.subscribe()
        LOGGER.debug("On Connect: Getting version info")
        self.publish(GET_VERSION)
        LOGGER.debug("On Connect: Request push all")
        self.publish(PUSH_ALL)

    def on_connect(self,
                   client_: mqtt.Client,
                   userdata: None,
                   flags: dict[str, Any],
                   result_code: int,
                   properties: mqtt.Properties | None = None, ):
        """Handle connection"""
        LOGGER.info("On Connect: Connected to Broker")
        self._connected = True
        self.subscribe_and_request_info()

        LOGGER.debug("Starting watchdog thread")
        self._watchdog = WatchdogThread(self)
        self._watchdog.start()

        if self._device.supports_feature(Features.CAMERA_IMAGE):
            LOGGER.debug("Starting P1P camera thread")
            self._camera = P1PCameraThread(self)
            self._camera.start()


    def try_on_connect(self,
                   client_: mqtt.Client,
                   userdata: None,
                   flags: dict[str, Any],
                   result_code: int,
                   properties: mqtt.Properties | None = None, ):
        """Handle connection"""
        LOGGER.info("On Connect: Connected to Broker")
        self._connected = True
        LOGGER.debug("Now test subscribing...")
        self.subscribe()
        # For the initial configuration connection attempt, we just need version info.
        LOGGER.debug("On Connect: Getting version ynfo")
        self.publish(GET_VERSION)

    def on_disconnect(self,
                      client_: mqtt.Client,
                      userdata: None,
                      result_code: int):
        """Called when MQTT Disconnects"""
        LOGGER.warn(f"On Disconnect: Disconnected from Broker: {result_code}")
        self._connected = False
        self._device.info.set_online(False)
        if self._watchdog is not None:
            self._watchdog.stop()
            self._watchdog.join()
        if self._camera is not None:
            self._camera.stop()
            self._camera.join()

    def on_watchdog_fired(self):
        LOGGER.debug("Watch dog fired")
        self._device.info.set_online(False)
        self.publish(START_PUSH)

    def on_jpeg_received(self, bytes):
        LOGGER.debug("JPEG received")
        self._device.p1p_camera.on_jpeg_received(bytes)

    def on_message(self, client, userdata, message):
        """Return the payload when received"""
        try:
            LOGGER.debug(f"On Message: Received Message: {message.payload}")
            json_data = json.loads(message.payload)
            if json_data.get("event"):
                if json_data.get("event").get("event") == "client.connected":
                    LOGGER.debug("Client connected event received.")
                    self._device.info.set_online(True)
                    self.subscribe_and_request_info()
                    self._watchdog.received_data()
                elif json_data.get("event").get("event") == "client.disconnected":
                    LOGGER.debug("Client disconnected event received.")
                    self._device.info.set_online(False)
            else:
                self._device.info.set_online(True)
                self._watchdog.received_data()
                if json_data.get("print"):
                    self._device.print_update(data=json_data.get("print"))
                elif json_data.get("info") and json_data.get("info").get("command") == "get_version":
                    LOGGER.debug("Got Version Command Data")
                    self._device.info_update(data=json_data.get("info"))
        except Exception as e:
            LOGGER.error("An exception occurred processing a message:")
            LOGGER.error(f"Exception type: {type(e)}")
            LOGGER.error(f"Exception args: {e.args}")

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

        LOGGER.error(f"Failed to send message to topic device/{self._serial}/request")
        return False

    def refresh(self):
        """Force refresh data"""
        LOGGER.debug("Force Refresh: Getting Version Info")
        self.publish(GET_VERSION)
        LOGGER.debug("Force Refresh: Request Push All")
        self.publish(PUSH_ALL)
        return

    def get_device(self):
        """Return device"""
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
                self._device.info_update(data=json_data.get("info"))
                result.put(True)

        self.client.on_connect = self.try_on_connect
        self.client.on_disconnect = self.on_disconnect
        self.client.on_message = on_message

        self.client.tls_set(tls_version=ssl.PROTOCOL_TLS, cert_reqs=ssl.CERT_NONE)
        self.client.tls_insecure_set(True)
        self.client.username_pw_set(self._username, password=self._access_code)
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
