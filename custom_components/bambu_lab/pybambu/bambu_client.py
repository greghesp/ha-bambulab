from __future__ import annotations

import queue
import json
import math
import re
import socket
import ssl
import struct
import threading
import time

from dataclasses import dataclass
from typing import Any

import paho.mqtt.client as mqtt

from .bambu_cloud import BambuCloud
from .const import (
    LOGGER,
    Features,
)
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
        LOGGER.info("Watchdog thread started.")
        WATCHDOG_TIMER = 30
        while True:
            # Wait out the remainder of the watchdog delay or 1s, whichever is higher.
            interval = time.time() - self._last_received_data
            wait_time = max(1, WATCHDOG_TIMER - interval)
            if self._stop_event.wait(wait_time):
                # Stop event has been set. Exit thread.
                break
            interval = time.time() - self._last_received_data
            if not self._watchdog_fired and (interval > WATCHDOG_TIMER):
                LOGGER.debug(f"Watchdog fired. No data received for {math.floor(interval)} seconds for {self._client._device.info.device_type}/{self._client._serial}.")
                self._watchdog_fired = True
                self._client._on_watchdog_fired()
            elif interval < WATCHDOG_TIMER:
                self._watchdog_fired = False

        LOGGER.info("Watchdog thread exited.")


class ChamberImageThread(threading.Thread):
    def __init__(self, client):
        self._client = client
        self._stop_event = threading.Event()
        super().__init__()

    def stop(self):
        self._stop_event.set()

    def run(self):
        LOGGER.debug("{self._client._device.info.device_type}: Chamber image thread started.")

        auth_data = bytearray()

        username = 'bblp'
        access_code = self._client._access_code
        hostname = self._client.host
        port = 6000
        MAX_CONNECT_ATTEMPTS = 12
        connect_attempts = 0

        auth_data += struct.pack("<I", 0x40)   # '@'\0\0\0
        auth_data += struct.pack("<I", 0x3000) # \0'0'\0\0
        auth_data += struct.pack("<I", 0)      # \0\0\0\0
        auth_data += struct.pack("<I", 0)      # \0\0\0\0
        for i in range(0, len(username)):
            auth_data += struct.pack("<c", username[i].encode('ascii'))
        for i in range(0, 32 - len(username)):
            auth_data += struct.pack("<x")
        for i in range(0, len(access_code)):
            auth_data += struct.pack("<c", access_code[i].encode('ascii'))
        for i in range(0, 32 - len(access_code)):
            auth_data += struct.pack("<x")

        ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE

        jpeg_start = bytearray([0xff, 0xd8, 0xff, 0xe0])
        jpeg_end = bytearray([0xff, 0xd9])

        read_chunk_size = 4096 # 4096 is the max we'll get even if we increase this.

        # Payload format for each image is:
        # 16 byte header:
        #   Bytes 0:3   = little endian payload size for the jpeg image (does not include this header).
        #   Bytes 4:7   = 0x00000000
        #   Bytes 8:11  = 0x00000001
        #   Bytes 12:15 = 0x00000000
        # These first 16 bytes are always delivered by themselves.
        #
        # Bytes 16:19                       = jpeg_start magic bytes
        # Bytes 20:payload_size-2           = jpeg image bytes
        # Bytes payload_size-2:payload_size = jpeg_end magic bytes
        #
        # Further attempts to receive data will get SSLWantReadError until a new image is ready (1-2 seconds later)
        while connect_attempts < MAX_CONNECT_ATTEMPTS and not self._stop_event.is_set():
            connect_attempts += 1
            try:
                with socket.create_connection((hostname, port)) as sock:
                    try:
                        sslSock = ctx.wrap_socket(sock, server_hostname=hostname)
                        sslSock.write(auth_data)
                        img = None
                        payload_size = 0

                        status = sslSock.getsockopt(socket.SOL_SOCKET, socket.SO_ERROR)
                        LOGGER.debug(f"{self._client._device.info.device_type}: SOCKET STATUS: {status}")
                        if status != 0:
                            LOGGER.error(f"{self._client._device.info.device_type}: Socket error: {status}")
                    except socket.error as e:
                        LOGGER.error(f"{self._client._device.info.device_type}: Socket error: {e}")
                        # Sleep to allow printer to stabilize during boot when it may fail these connection attempts repeatedly.
                        time.sleep(1)
                        continue

                    sslSock.setblocking(False)
                    while not self._stop_event.is_set():
                        try:
                            dr = sslSock.recv(read_chunk_size)
                            #LOGGER.debug(f"{self._client._device.info.device_type}: Received {len(dr)} bytes.")

                        except ssl.SSLWantReadError:
                            #LOGGER.debug(f"{self._client._device.info.device_type}: SSLWantReadError")
                            time.sleep(1)
                            continue

                        except Exception as e:
                            LOGGER.error(f"{self._client._device.info.device_type}: A Chamber Image thread inner exception occurred:")
                            LOGGER.error(f"{self._client._device.info.device_type}: Exception. Type: {type(e)} Args: {e}")
                            time.sleep(1)
                            continue

                        if img is not None and len(dr) > 0:
                            img += dr
                            if len(img) > payload_size:
                                # We got more data than we expected.
                                LOGGER.error(f"Unexpected image payload received: {len(img)} > {payload_size}")
                                # Reset buffer
                                img = None
                            elif len(img) == payload_size:
                                # We should have the full image now.
                                if img[:4] != jpeg_start:
                                    LOGGER.error("JPEG start magic bytes missing.")
                                elif img[-2:] != jpeg_end:
                                    LOGGER.error("JPEG end magic bytes missing.")
                                else:
                                    # Content is as expected. Send it.
                                    self._client.on_jpeg_received(img)

                                # Reset buffer
                                img = None
                            # else:     
                            # Otherwise we need to continue looping without reseting the buffer to receive the remaining data
                            # and without delaying.

                        elif len(dr) == 16:
                            # We got the header bytes. Get the expected payload size from it and create the image buffer bytearray.
                            # Reset connect_attempts now we know the connect was successful.
                            connect_attempts = 0
                            img = bytearray()
                            payload_size = int.from_bytes(dr[0:3], byteorder='little')

                        elif len(dr) == 0:
                            # This occurs if the wrong access code was provided.
                            LOGGER.error(f"{self._client._device.info.device_type}: Chamber image connection rejected by the printer. Check provided access code and IP address.")
                            # Sleep for a short while and then re-attempt the connection.
                            time.sleep(5)
                            break

                        else:
                            LOGGER.error(f"{self._client._device.info.device_type}: UNEXPECTED DATA RECEIVED: {len(dr)}")
                            time.sleep(1)

            except OSError as e:
                if e.errno == 113:
                    LOGGER.debug(f"{self._client._device.info.device_type}: Host is unreachable")
                else:
                    LOGGER.error(f"{self._client._device.info.device_type}: A Chamber Image thread outer exception occurred:")
                    LOGGER.error(f"{self._client._device.info.device_type}: Exception. Type: {type(e)} Args: {e}")
                if not self._stop_event.is_set():
                    time.sleep(1)  # Avoid a tight loop if this is a persistent error.

            except Exception as e:
                LOGGER.error(f"{self._client._device.info.device_type}: A Chamber Image thread outer exception occurred:")
                LOGGER.error(f"{self._client._device.info.device_type}: Exception. Type: {type(e)} Args: {e}")
                if not self._stop_event.is_set():
                    time.sleep(1)  # Avoid a tight loop if this is a persistent error.

        LOGGER.info(f"{self._client._device.info.device_type}: Chamber image thread exited.")


def mqtt_listen_thread(self):
    LOGGER.info("MQTT listener thread started.")
    exceptionSeen = ""
    while True:
        try:
            host = self.host if self._local_mqtt else self.bambu_cloud.cloud_mqtt_host
            LOGGER.debug(f"Connect: Attempting Connection to {host}")
            self.client.connect(host, self._port, keepalive=5)

            LOGGER.debug("Starting listen loop")
            self.client.loop_forever()
            LOGGER.debug("Ended listen loop.")
            break
        except TimeoutError as e:
            if exceptionSeen != "TimeoutError":
                LOGGER.debug(f"TimeoutError: {e}.")
            exceptionSeen = "TimeoutError"
            time.sleep(5)
        except ConnectionError as e:
            if exceptionSeen != "ConnectionError":
                LOGGER.debug(f"ConnectionError: {e}.")
            exceptionSeen = "ConnectionError"
            time.sleep(5)
        except OSError as e:
            if e.errno == 113:
                if exceptionSeen != "OSError113":
                    LOGGER.debug(f"OSError: {e}.")
                exceptionSeen = "OSError113"
                time.sleep(5)
            else:
                LOGGER.error("A listener loop thread exception occurred:")
                LOGGER.error(f"Exception. Type: {type(e)} Args: {e}")
                time.sleep(1)  # Avoid a tight loop if this is a persistent error.
        except Exception as e:
            LOGGER.error("A listener loop thread exception occurred:")
            LOGGER.error(f"Exception. Type: {type(e)} Args: {e}")
            time.sleep(1)  # Avoid a tight loop if this is a persistent error.

        if self.client is None:
            break

        self.client.disconnect()

    LOGGER.info("MQTT listener thread exited.")


@dataclass
class BambuClient:
    """Initialize Bambu Client to connect to MQTT Broker"""
    _watchdog = None
    _camera = None
    _usage_hours: float

    def __init__(self, device_type: str, serial: str, host: str, local_mqtt: bool, region: str, email: str,
                 username: str, auth_token: str, access_code: str, usage_hours: float = 0, manual_refresh_mode: bool = False):
        self.callback = None
        self.host = host
        self._local_mqtt = local_mqtt
        self._serial = serial
        self._auth_token = auth_token
        self._access_code = access_code
        self._username = username
        self._connected = False
        self._device_type = device_type
        self._usage_hours = usage_hours
        self._port = 1883
        self._refreshed = False
        self._manual_refresh_mode = manual_refresh_mode
        self._device = Device(self)
        self.bambu_cloud = BambuCloud(region, email, username, auth_token)

    @property
    def connected(self):
        """Return if connected to server"""
        return self._connected

    @property
    def manual_refresh_mode(self):
        """Return if the integration is running in poll mode"""
        return self._manual_refresh_mode

    async def set_manual_refresh_mode(self, on):
        self._manual_refresh_mode = on
        if self._manual_refresh_mode:
            # Disconnect from the server. User must manually hit the refresh button to connect to refresh and then it will immediately disconnect.
            self.disconnect()
        else:
            # Reconnect normally
            self.connect(self.callback)

    def connect(self, callback):
        """Connect to the MQTT Broker"""
        self.client = mqtt.Client()
        self.callback = callback
        self.client.on_connect = self.on_connect
        self.client.on_disconnect = self.on_disconnect
        self.client.on_message = self.on_message
        # Set aggressive reconnect polling.
        self.client.reconnect_delay_set(min_delay=1, max_delay=1)

        self.client.tls_set(tls_version=ssl.PROTOCOL_TLS, cert_reqs=ssl.CERT_NONE)
        self.client.tls_insecure_set(True)
        self._port = 8883
        if self._local_mqtt:
            self.client.username_pw_set("bblp", password=self._access_code)
        else:
            self.client.username_pw_set(self._username, password=self._auth_token)

        LOGGER.debug("Starting MQTT listener thread")
        thread = threading.Thread(target=mqtt_listen_thread, args=(self,))
        thread.start()

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
        self._on_connect()

    def _on_connect(self):
        self._connected = True
        self.subscribe_and_request_info()

        LOGGER.debug("Starting watchdog thread")
        self._watchdog = WatchdogThread(self)
        self._watchdog.start()

        if self._device.supports_feature(Features.CAMERA_IMAGE):
            LOGGER.debug("Starting Chamber Image thread")
            self._camera = ChamberImageThread(self)
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
        LOGGER.debug("On Connect: Getting version info")
        self.publish(GET_VERSION)

    def on_disconnect(self,
                      client_: mqtt.Client,
                      userdata: None,
                      result_code: int):
        """Called when MQTT Disconnects"""
        LOGGER.warn(f"On Disconnect: Disconnected from Broker: {result_code}")
        self._on_disconnect()
    
    def _on_disconnect(self):
        self._connected = False
        self._device.info.set_online(False)
        if self._watchdog is not None:
            self._watchdog.stop()
            self._watchdog.join()
        if self._camera is not None:
            self._camera.stop()
            self._camera.join()

    def _on_watchdog_fired(self):
        LOGGER.info("Watch dog fired")
        self._device.info.set_online(False)
        self.publish(START_PUSH)

    def on_jpeg_received(self, bytes):
        self._device.chamber_image.set_jpeg(bytes)

    def on_message(self, client, userdata, message):
        """Return the payload when received"""
        try:
            # X1 mqtt payload is inconsistent. Adjust it for consistent logging.
            clean_msg = re.sub(r"\\n *", "", str(message.payload))
            if self._refreshed:
                LOGGER.debug(f"Received data from: {self._device.info.device_type}: {clean_msg}")
            else:
                LOGGER.debug(f"Received data from: {self._device.info.device_type}")

            json_data = json.loads(message.payload)
            if json_data.get("event"):
                # These are events from the bambu cloud mqtt feed and allow us to detect when a local
                # device has connected/disconnected (e.g. turned on/off)
                if json_data.get("event").get("event") == "client.connected":
                    LOGGER.debug("Client connected event received.")
                    self._on_disconnect() # We aren't guaranteed to recieve a client.disconnected event.
                    self._on_connect()
                elif json_data.get("event").get("event") == "client.disconnected":
                    LOGGER.debug("Client disconnected event received.")
                    self._on_disconnect()
            else:
                self._device.info.set_online(True)
                self._watchdog.received_data()
                if json_data.get("print"):
                    self._device.print_update(data=json_data.get("print"))
                    # Once we receive data, if in manual refresh mode, we disconnect again.
                    if self._manual_refresh_mode:
                        self.disconnect()
                    if json_data.get("print").get("msg", 0) == 0:
                        self._refreshed= False
                elif json_data.get("info") and json_data.get("info").get("command") == "get_version":
                    LOGGER.debug("Got Version Data")
                    self._device.info_update(data=json_data.get("info"))
        except Exception as e:
            LOGGER.error("An exception occurred processing a message:")
            LOGGER.error(f"Exception type: {type(e)}")
            LOGGER.error(f"Exception data: {e}")

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

    async def refresh(self):
        """Force refresh data"""

        if self._manual_refresh_mode:
            self.connect(self.callback)
        else:
            LOGGER.debug("Force Refresh: Getting Version Info")
            self._refreshed = True
            self.publish(GET_VERSION)
            LOGGER.debug("Force Refresh: Request Push All")
            self._refreshed = True
            self.publish(PUSH_ALL)

    def get_device(self):
        """Return device"""
        return self._device

    def disconnect(self):
        """Disconnect the Bambu Client from server"""
        LOGGER.debug("Disconnect: Client Disconnecting")
        if self.client is not None:
            self.client.disconnect()
            self.client = None

    async def try_connection(self):
        """Test if we can connect to an MQTT broker."""
        LOGGER.debug("Try Connection")

        result: queue.Queue[bool] = queue.Queue(maxsize=1)

        def on_message(client, userdata, message):
            json_data = json.loads(message.payload)
            LOGGER.debug(f"Try Connection: Got '{json_data}'")
            if json_data.get("info") and json_data.get("info").get("command") == "get_version":
                LOGGER.debug("Got Version Command Data")
                self._device.info_update(data=json_data.get("info"))
                result.put(True)

        self.client = mqtt.Client()
        self.client.on_connect = self.try_on_connect
        self.client.on_disconnect = self.on_disconnect
        self.client.on_message = on_message

        self.client.tls_set(tls_version=ssl.PROTOCOL_TLS, cert_reqs=ssl.CERT_NONE)
        self.client.tls_insecure_set(True)
        if self._local_mqtt:
            self.client.username_pw_set("bblp", password=self._access_code)
        else:
            self.client.username_pw_set(self._username, password=self._auth_token)
        self._port = 8883

        LOGGER.debug("Test connection: Connecting to %s", self.host)
        try:
            self.client.connect(self.host, self._port)
            self.client.loop_start()
            if result.get(timeout=10):
                return True
        except OSError as e:
            return False
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
