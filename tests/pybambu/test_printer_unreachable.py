"""The integration layer is told when the printer can't be reached on its stored
address, so it can look up a new one (issue #1954).

These use a real paho client against real sockets: paho handles a failed first
connection and a failed reconnect differently, and only the first one raises.
"""
import asyncio
import socket
import tempfile
import threading
import time
import unittest
from unittest.mock import patch

from pybambu.bambu_client import BambuClient

CONNACK_ACCEPTED = b"\x20\x02\x00\x00"
EVENT = "event_printer_unreachable"


class _OneShotBroker:
    """Accepts a single MQTT connection and then goes away, like a printer that moves."""

    def __init__(self):
        self._listener = socket.create_server(("127.0.0.1", 0))
        self.port = self._listener.getsockname()[1]
        threading.Thread(target=self._serve, daemon=True).start()

    def _serve(self):
        connection, _ = self._listener.accept()
        self._listener.close()
        with connection:
            connection.recv(1024)
            connection.sendall(CONNACK_ACCEPTED)
            time.sleep(0.2)


def _closed_port():
    with socket.create_server(("127.0.0.1", 0)) as listener:
        return listener.getsockname()[1]


class TestPrinterUnreachable(unittest.TestCase):

    def _connect(self, port, local_mqtt=True):
        events = []
        client = BambuClient({
            'host': '127.0.0.1',
            'local_mqtt': local_mqtt,
            'serial': 'TESTSERIAL123',
            'enable_camera': False,
            'file_cache_path': tempfile.mkdtemp(),
        })
        client._port = port
        client.setup_tls = lambda: None
        client.probe_remote_media_sources = lambda: False
        asyncio.run(client.connect(callback=events.append))
        self.addCleanup(client.disconnect)
        return events

    def _wait_for_event(self, events, timeout=15):
        deadline = time.monotonic() + timeout
        while EVENT not in events and time.monotonic() < deadline:
            time.sleep(0.05)
        self.assertIn(EVENT, events)

    def test_reported_when_the_first_connection_fails(self):
        self._wait_for_event(self._connect(_closed_port()))

    def test_reported_when_a_working_connection_cannot_be_restored(self):
        self._wait_for_event(self._connect(_OneShotBroker().port))

    def test_not_reported_for_the_cloud_connection(self):
        with patch("pybambu.bambu_cloud.BambuCloud.cloud_mqtt_host", "127.0.0.1"):
            events = self._connect(_closed_port(), local_mqtt=False)
            time.sleep(4)

        self.assertNotIn(EVENT, events)


class TestConnectionTestTimeout(unittest.TestCase):

    def test_a_silent_address_is_a_timeout(self):
        # socket.timeout carries no errno, so it used to come back as an unknown error.
        client = BambuClient({'host': '192.0.2.10', 'local_mqtt': True, 'serial': 'TESTSERIAL123'})
        client.setup_tls = lambda: None
        with patch("paho.mqtt.client.Client.connect", side_effect=TimeoutError("timed out")):
            result = asyncio.run(client.try_connection())

        self.assertEqual(result, -1)


if __name__ == '__main__':
    unittest.main()
