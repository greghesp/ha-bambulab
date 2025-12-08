from __future__ import annotations

import asyncio
import ftplib
import functools
import json
import math
import os
import queue
import re
import socket
import ssl
import struct
import threading
import time
import uuid

from dataclasses import dataclass
from typing import Any

import paho.mqtt.client as mqtt

from .bambu_cloud import BambuCloud
from .const import (
    LOGGER,
    Features,
)
from .models import Device, SlicerSettings
from .commands import (
    GET_VERSION,
    PUSH_ALL,
    START_PUSH,
)
from .tests import MockMQTTClient
from .utils import safe_json_loads

class WatchdogThread(threading.Thread):

    def __init__(self, client):
        self._client = client
        self._watchdog_fired = False
        self._stop_event = threading.Event()
        self._last_received_data = time.time()
        super().__init__()
        self.daemon = True

    def stop(self):
        self._stop_event.set()

    def received_data(self):
        self._last_received_data = time.time()

    def run(self):
        self.setName(f"{self._client._device.info.device_type}-Watchdog-{threading.get_native_id()}")
        LOGGER.debug("Watchdog thread started.")

        WATCHDOG_TIMER = 60
        while not self._stop_event.is_set():
            # Wait out the remainder of the watchdog delay or 1s, whichever is higher.
            interval = time.time() - self._last_received_data
            wait_time = max(1, WATCHDOG_TIMER - interval)
            if self._stop_event.wait(wait_time):
                # Stop event has been set. Exit thread.
                break
            interval = time.time() - self._last_received_data
            if not self._watchdog_fired and (interval > WATCHDOG_TIMER):
                LOGGER.debug(f"Watchdog fired. No data received for {math.floor(interval)} seconds for {self._client._serial}.")
                self._watchdog_fired = True
                self._client._on_watchdog_fired()
            elif interval < WATCHDOG_TIMER:
                self._watchdog_fired = False

        LOGGER.debug("Watchdog thread exited.")


class ChamberImageThread(threading.Thread):
    def __init__(self, client: BambuClient):
        self._client = client
        self._stop_event = threading.Event()
        super().__init__()
        self.daemon = True

    def stop(self):
        self._stop_event.set()

    def run(self):
        self.setName(f"{self._client._device.info.device_type}-Chamber-{threading.get_native_id()}")
        LOGGER.debug("Chamber image thread started.")

        auth_data = bytearray()

        username = 'bblp'
        access_code = self._client._access_code
        hostname = self._client._device.info.ip_address
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

        ctx = self._client.local_tls_context

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
                        LOGGER.debug(f"SOCKET STATUS: {status}")
                        if status != 0:
                            LOGGER.error(f"Socket error: {status}")
                    except socket.error as e:
                        LOGGER.error(f"Socket error: {e}")
                        # Sleep to allow printer to stabilize during boot when it may fail these connection attempts repeatedly.
                        if self._stop_event.wait(1):
                            break
                        continue

                    sslSock.setblocking(False)
                    while not self._stop_event.is_set():
                        try:
                            dr = sslSock.recv(read_chunk_size)
                        except ssl.SSLWantReadError:
                            if self._stop_event.wait(1):
                                break
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
                            LOGGER.error("Chamber image connection rejected by the printer. Check provided access code and IP address.")
                            raise RuntimeError("Received no data unexpectedly.")

                        else:
                            LOGGER.error(f"UNEXPECTED DATA RECEIVED: {len(dr)}")
                            raise RuntimeError(f"Unexpected data chunk size received: {len(dr)}")

            except OSError as e:
                if e.errno == 113:
                    LOGGER.debug("Host is unreachable")
                else:
                    LOGGER.error("Chamber Image thread outer exception occurred:")
                    LOGGER.error(f"Exception. Type: {type(e)} Args: {e}")
                if not self._stop_event.is_set():
                    time.sleep(2)  # Avoid a tight loop if this is a persistent error.

            except Exception as e:
                LOGGER.error(f"Chamber Image thread exception occurred:")
                LOGGER.error(f"Exception. Type: {type(e)} Args: {e}")
                if not self._stop_event.is_set():
                    time.sleep(2)  # Avoid a tight loop if this is a persistent error.

        LOGGER.debug("Chamber image thread exited.")


class MqttThread(threading.Thread):
    def __init__(self, client):
        self._client = client
        self._stop_event = threading.Event()
        super().__init__()
        self.daemon = True

    def stop(self):
        self._stop_event.set()

    def run(self):
        self.setName(f"{self._client._device.info.device_type}-Mqtt-{threading.get_native_id()}")
        LOGGER.debug("MQTT listener thread started.")

        exceptionSeen = ""
        while not self._stop_event.is_set():
            try:
                host = self._client.host if self._client._local_mqtt else self._client.bambu_cloud.cloud_mqtt_host
                LOGGER.debug(f"Connect: Attempting Connection to {host}")
                self._client.client.connect(host, self._client._port, keepalive=5)

                LOGGER.debug("Starting listen loop")
                self._client.client.loop_forever()
                LOGGER.debug("Ended listen loop.")
                break
            except TimeoutError as e:
                if exceptionSeen != "TimeoutError":
                    LOGGER.debug(f"TimeoutError: {e}.")
                exceptionSeen = "TimeoutError"
                if self._stop_event.wait(5):
                    break
            except ConnectionError as e:
                if exceptionSeen != "ConnectionError":
                    LOGGER.debug(f"ConnectionError: {e}.")
                exceptionSeen = "ConnectionError"
                if self._stop_event.wait(5):
                    break
            except OSError as e:
                if e.errno == 113:
                    if exceptionSeen != "OSError113":
                        LOGGER.debug(f"OSError: {e}.")
                    exceptionSeen = "OSError113"
                    if self._stop_event.wait(5):
                        break
                else:
                    LOGGER.error("A listener loop thread exception occurred:")
                    LOGGER.error(f"Exception. Type: {type(e)} Args: {e}")
                    if self._stop_event.wait(1):  # Avoid a tight loop if this is a persistent error.
                        break
            except Exception as e:
                LOGGER.error("A listener loop thread exception occurred:")
                LOGGER.error(f"Exception. Type: {type(e)} Args: {e}")
                if self._stop_event.wait(1):  # Avoid a tight loop if this is a persistent error.
                    break

            if self._client.client is None or self._stop_event.is_set():
                break

            try:
                self._client.client.disconnect()
            except Exception:
                pass

        LOGGER.debug("MQTT listener thread exited.")

class ImplicitFTP_TLS(ftplib.FTP_TLS):
    """
    FTP_TLS subclass that automatically wraps sockets in SSL to support implicit FTPS.
    see https://stackoverflow.com/a/36049814
    """
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._sock = None

    @property
    def sock(self):
        """Return the socket."""
        return self._sock

    @sock.setter
    def sock(self, value):
        """When modifying the socket, ensure that it is ssl wrapped."""
        if value is not None and not isinstance(value, ssl.SSLSocket):
            value = self.context.wrap_socket(value)
        self._sock = value

    """
    Increases relability with some printers
    Courtesy @WolfwithSword
    """
    def ntransfercmd(self, cmd, rest=None):
        conn, size = ftplib.FTP.ntransfercmd(self, cmd, rest)
        if self._prot_p:
            session = self.sock.session
            if isinstance(self.sock, ssl.SSLSocket):
                session = self.sock.session
            conn = self.context.wrap_socket(conn,
                                            server_hostname=self.host,
                                            session=session)
        return conn, size
    
    def storbinary_no_unwrap(self, cmd, fp, blocksize=8192, callback=None, rest=None):
        """Version of storbinary that skips conn.unwrap() to avoid SSL timeout."""
        self.voidcmd('TYPE I')
        with self.transfercmd(cmd, rest) as conn:
            while True:
                buf = fp.read(blocksize)
                if not buf:
                    break
                conn.sendall(buf)
                if callback:
                    callback(buf)
            # SKIP conn.unwrap() which causes timeout
            conn.close()
        return self.voidresp()    

@dataclass
class BambuClient:
    """Initialize Bambu Client to connect to MQTT Broker"""
    _watchdog = None
    _camera = None
    _mqtt = None
    _usage_hours: float = 0
    _test_mode: bool = False
    _mock: bool = False
    client = None

    def __init__(self, config):
        self._config = config
        self.host = config['host']
        self._callback = None
        self._test_mode = False

        self._access_code = config.get('access_code', '')
        self._auth_token = config.get('auth_token', '')
        self._device_type = config.get('device_type', 'unknown').upper()
        self._local_mqtt = config.get('local_mqtt', False)
        self._serial = config.get('serial', '')
        self._enable_camera = config.get('enable_camera', True) and (self.host != "")
        self._enable_ftp = (self.host != "")
        if self._serial.startswith('MOCK-'):
            self._enable_ftp = False
            self._enable_camera = False
            self._mock = True
        self._usage_hours = config.get('usage_hours', 0)
        self._username = config.get('username', '')
        self._print_cache_count = max(-1, int(config.get('print_cache_count', 1)))
        if self._print_cache_count == 0:
            # We always cache at least one model as we use that to avoid redownloading from ftp on startup.
            self._print_cache_count = 1
        self._timelapse_cache_count = max(-1, int(config.get('timelapse_cache_count', 0)))
        self._disable_ssl_verify = config.get('disable_ssl_verify', False)
        self._cache_path = config.get('file_cache_path', f'/config/www/media/ha-bambulab/{self._serial}')

        self._connected = False
        self._port = 8883
        self._refreshed = False

        self._device = Device(self)
        self.bambu_cloud = BambuCloud(
            region = config.get('region', ''),
            email = config.get('email', ''),
            username = config.get('username', ''),
            auth_token = config.get('auth_token', '')
        )
        self._loaded_slicer_settings = False
        self.slicer_settings = SlicerSettings(self)
        language = config.get('user_language', 'pt')
        if 'zh' in language:
            language = 'zh-CN'
        else:
            language = language[:2]
        self._user_language = language

    @property
    def settings(self):
        return self._config
    
    @property
    def cache_path(self):
        return self._cache_path

    @property
    def user_language(self):
        return self._user_language

    @property
    def connected(self):
        """Return if connected to server"""
        return self._connected

    @property
    def camera_enabled(self):
        return self._enable_camera

    def callback(self, event: str):
        if self._callback is not None:
            self._callback(event)

    def set_camera_enabled(self, enable):
        self._enable_camera = enable and (self.host != "")
        if self._enable_camera:
            self.start_camera()
        else:
            self.stop_camera()

    @property
    def ftp_enabled(self):
        return self._enable_ftp

    @property
    def local_tls_context(self):
        if self._disable_ssl_verify:
            return create_insecure_ssl_context()
        else:
            return create_local_ssl_context()

    def setup_tls(self):
        if self._local_mqtt:
            self.client.tls_set_context(self.local_tls_context)
            if self._disable_ssl_verify:
                self.client.tls_insecure_set(True) 
        else:
            self.client.tls_set()

    async def connect(self, callback):
        """Connect to the MQTT Broker"""
        if self._mock:
            self.client = MockMQTTClient(self._serial)
        else:
            self.client = mqtt.Client(client_id=f"ha-bambulab-{uuid.uuid4()}",
                                      protocol=mqtt.MQTTv311,
                                      clean_session=True)
            self.client.enable_logger()
        self._callback = callback
        self.client.on_connect = self.on_connect
        self.client.on_disconnect = self.on_disconnect
        self.client.on_message = self.on_message
        # Set aggressive reconnect polling.
        self.client.reconnect_delay_set(min_delay=1, max_delay=1)

        # Run the blocking tls_set method in a separate thread
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, self.setup_tls)

        if self._local_mqtt:
            self.client.username_pw_set("bblp", password=self._access_code)
        else:
            self.client.username_pw_set(self._username, password=self._auth_token)

        LOGGER.debug("Starting MQTT listener thread")
        self._mqtt = MqttThread(self)
        self._mqtt.start()

        self._device.print_job.prune_print_history_files()
        self._device.print_job.prune_timelapse_files()

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
        LOGGER.debug("On Connect: Connected to printer")
        self._on_connect()

    def start_camera(self):
        if not self._device.supports_feature(Features.CAMERA_RTSP):
            if self._device.supports_feature(Features.CAMERA_IMAGE):
                if self._enable_camera and not self._test_mode:
                    if self._device.info.ip_address != "" and self._device.info.ip_address != "0.0.0.0" and self._access_code != "":
                        LOGGER.debug("Starting Chamber Image thread")
                        self._camera = ChamberImageThread(self)
                        self._camera.start()
                    else:
                        LOGGER.debug("Skipping camera setup as local access details not provided.")

    def stop_camera(self):
        if self._camera is not None:
            LOGGER.debug("Stopping camera thread")
            self._camera.stop()
            self._camera.join()
            self._camera = None

    def _on_connect(self):
        self._connected = True

        if self._device.info.ip_address != "" and self._device.info.ip_address != "0.0.0.0":
            LOGGER.debug("Starting watchdog thread")
            self._watchdog = WatchdogThread(self)
            self._watchdog.start()

        self.subscribe_and_request_info()

        # Start camera if enabled
        self.start_camera()

    def on_disconnect(self,
                      client_: mqtt.Client,
                      userdata: None,
                      result_code: int):
        """Called when MQTT Disconnects"""
        if (result_code == 0):
            LOGGER.debug(f"On Disconnect: Printer disconnected cleanly")
        else:
            LOGGER.warning(f"On Disconnect: Printer disconnected with error code: {result_code}")
        self._on_disconnect()

    def _on_disconnect(self):
        LOGGER.debug("_on_disconnect: Lost connection to the printer")
        self._loaded_slicer_settings = False
        self._connected = False
        self._device.info.set_online(False)
        if self._watchdog is not None:
            LOGGER.debug("Stopping watchdog thread")
            self._watchdog.stop()
            self._watchdog.join()
        self.stop_camera()

    def _on_watchdog_fired(self):
        LOGGER.info("Watch dog fired")
        self._device.info.set_online(False)
        self.publish(START_PUSH)

    def on_jpeg_received(self, bytes):
        self._device.chamber_image.set_image(bytes)

    def on_message(self, client, userdata, message):
        """Return the payload when received"""
        try:
            if self.client is None:
                # We have been shut down. Drop any messages we receive late.
                return

            if not self._loaded_slicer_settings:
                # Only update slicer settings once per successful connection to the printer.
                self._loaded_slicer_settings = True
                self.slicer_settings.update()

            if self._refreshed:
                # X1 mqtt payload is inconsistent. Adjust it for consistent logging.
                clean_msg = re.sub(r"\\n *", "", str(message.payload))
                # And adjust all payload to be meet proper json syntax instead of being pythonized so I can feed it directly into an online json prettifier
                clean_msg = re.sub(r"\'", "\"", str(clean_msg))
                clean_msg = re.sub(r"True", "true", str(clean_msg))
                clean_msg = re.sub(r"False", "false", str(clean_msg))
                LOGGER.debug(f"Received data: {clean_msg}")

            json_data = safe_json_loads(message.payload)
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
                if self._watchdog is not None:
                    self._watchdog.received_data()
                if json_data.get("print"):
                    self._device.print_update(data=json_data.get("print"))
                    if json_data.get("print").get("msg", 0) == 0:
                        self._refreshed= False
                elif json_data.get("info") and json_data.get("info").get("command") == "get_version":
                    self._device.info_update(data=json_data.get("info"))
                elif json_data.get("system") and json_data.get("system").get("command"):
                    self._device.observe_system_command(data=json_data.get("system"))


        except Exception as e:
            LOGGER.error("An exception occurred processing a message:", exc_info=e)
            LOGGER.debug(message.payload)

    def subscribe(self):
        """Subscribe to report topic"""
        LOGGER.debug(f"Subscribing: device/{self._serial}/report")
        self.client.subscribe(f"device/{self._serial}/report")

    def publish(self, msg):
        """Publish a custom message"""
        result = self.client.publish(f"device/{self._serial}/request", json.dumps(msg))
        status = result.rc
        if status == 0:
            LOGGER.debug(f"Sent {msg} to topic device/{self._serial}/request")
            return True

        LOGGER.error(f"Failed to send message to topic device/{self._serial}/request")
        return False

    async def refresh(self):
        """Force refresh data"""
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
        
        # Stop and wait for background threads
        if self._mqtt is not None:
            LOGGER.debug("Stopping MQTT thread")
            self._mqtt.stop()
            self._mqtt.join(timeout=5)
            self._mqtt = None
            
        if self._watchdog is not None:
            LOGGER.debug("Stopping watchdog thread")
            self._watchdog.stop()
            self._watchdog.join(timeout=5)
            self._watchdog = None
            
        if self._camera is not None:
            LOGGER.debug("Stopping camera thread")
            self._camera.stop()
            self._camera.join(timeout=5)
            self._camera = None
        
        # Disconnect MQTT client
        if self.client is not None:
            try:
                self.client.loop_stop()
                self.client.disconnect()
            except Exception as e:
                LOGGER.debug(f"Error during MQTT disconnect: {e}")
            finally:
                self.client = None


    def ftp_connection(self) -> ImplicitFTP_TLS:
        ftp = ImplicitFTP_TLS(context=self.local_tls_context)
        ftp.connect(host=self._device.info.ip_address, port=990, timeout=15)
        ftp.login(user='bblp', passwd=self._access_code)
        ftp.prot_p()
        return ftp

    async def try_connection(self):
        """Test if we can connect to an MQTT broker."""
        LOGGER.debug("Try Connection")

        result: queue.Queue[int] = queue.Queue(maxsize=1)

        self.received_info = False
        self.received_push = False

        def try_on_connect(client_: mqtt.Client,
                           userdata: None,
                           flags: dict[str, Any],
                           result_code: int,
                           properties: mqtt.Properties | None = None, ):

            LOGGER.debug(f"try_on_connect: Connected to printer: {result_code}")
            self.subscribe_and_request_info()

        def try_on_disconnect(client_: mqtt.Client,
                              userdata: None,
                              result_code: int):
            """Called when MQTT Disconnects"""
            LOGGER.debug("try_on_disconnect: Lost connection to the printer")
            if (result_code == 0):
                LOGGER.debug(f"Printer disconnected cleanly")
            else:
                LOGGER.warning(f"Printer disconnected with error code: {result_code}")
                result.put(result_code)

            try_disconnect()

        def try_disconnect():
            if self.client is not None:
                try:
                    self.client.loop_stop()
                    self.client.disconnect()
                except Exception as e:
                    LOGGER.debug(f"Error during MQTT disconnect: {e}")
                finally:
                    self.client = None

        def try_on_message(client, userdata, message):
            json_data = safe_json_loads(message.payload)

            # X1 mqtt payload is inconsistent. Adjust it for consistent logging.
            clean_msg = re.sub(r"\\n *", "", str(message.payload))
            # And adjust all payload to be meet proper json syntax instead of being pythonized so I can feed it directly into an online json prettifier
            clean_msg = re.sub(r"\'", "\"", str(clean_msg))
            clean_msg = re.sub(r"True", "true", str(clean_msg))
            clean_msg = re.sub(r"False", "false", str(clean_msg))

            LOGGER.debug(f"try_on_message: Got '{clean_msg}'")
            if json_data.get("info") and json_data.get("info").get("command") == "get_version":
                LOGGER.debug("Got Version Command Data")
                self._device.info_update(data=json_data.get("info"))
                self.received_info = True
            if (json_data.get('print', {}).get('command', '') == 'push_status') and (json_data.get('print', {}).get('msg', 0) == 0):
                self._device.print_update(data=json_data.get("print"))
                self.received_push = True
            # Observe system command is not needed here because it is not an initial message.

            if self.received_info and self.received_push:
                result.put(0)

        self._test_mode = True
        if self._mock:
            self.client = MockMQTTClient(self._serial)
        else:
            self.client = mqtt.Client()
        self.client.on_connect = try_on_connect
        self.client.on_disconnect = try_on_disconnect
        self.client.on_message = try_on_message

        # Run the blocking tls_set method in a separate thread
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, self.setup_tls)

        host = self.host if self._local_mqtt else self.bambu_cloud.cloud_mqtt_host
        if self._local_mqtt:
            self.client.username_pw_set("bblp", password=self._access_code)
        else:
            self.client.username_pw_set(self._username, password=self._auth_token)

        LOGGER.debug(f"Test connection: Connecting to {host}")
        try:
            self.client.connect(host, self._port)
            self.client.loop_start()
            LOGGER.debug("Waiting for reponse.")
            return_result = result.get(timeout=10)
            if return_result == 0:
                LOGGER.debug("Connection test was successful")
            else:
                LOGGER.debug(f"Connection test failed with result: {return_result}")
            return return_result
        except OSError as e:
            LOGGER.error(f"Connection test to '{host}' failed: {type(e)} Args: {e}")
            return e.errno
        except queue.Empty:
            LOGGER.error(f"Connection test to '{host}' failed with timeout")
            return -1
        finally:
            # Make sure we definitely clean up in all paths.
            try_disconnect()

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

    def download_3mf_and_extract_metadata(self, model_file, thumbnail_cache_path=None):
        return self._device.print_job.extract_3mf_metadata(model_file, thumbnail_cache_path=thumbnail_cache_path)

@functools.lru_cache(maxsize=1)
def create_local_ssl_context():
    """
    This context validates the certificate for TLS connections to local printers.
    """
    script_path = os.path.abspath(__file__)
    directory_path = os.path.dirname(script_path)
    context = ssl.create_default_context()
    for filename in ("bambu.cert", "bambu_p2s_250626.cert", "bambu_h2c_251122.cert"):
        path = os.path.join(directory_path, filename)
        context.load_verify_locations(cafile=path)

    # Ignore "CA cert does not include key usage extension" error since python 3.13
    # See note in https://docs.python.org/3/library/ssl.html#ssl.create_default_context
    context.verify_flags &= ~ssl.VERIFY_X509_STRICT
    # Workaround because some users get this error despite SNI: "certificate verify failed: IP address mismatch"
    context.check_hostname = False
    return context

@functools.lru_cache(maxsize=1)
def create_insecure_ssl_context():
    context = ssl.SSLContext(ssl.PROTOCOL_TLS)
    context.check_hostname = False
    context.verify_mode = ssl.CERT_NONE
    return context
