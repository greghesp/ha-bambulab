import threading
import time
import unittest
from unittest.mock import MagicMock, patch

from pybambu.bambu_client import BambuClient, ChamberImageThread
from pybambu.const import LOGGER


class TestAccessDeniedDisconnect(unittest.TestCase):
    """CONNACK code 5 means the printer rejected the access code - typically because a
    factory reset regenerated it. The client already stops retrying in that case; these
    pin the event that lets the integration layer react (refresh the code from Bambu
    Cloud, or raise a repair issue)."""

    def setUp(self):
        self.client = BambuClient({
            'host': '192.0.2.10',
            'serial': 'TESTSERIAL123',
            'enable_camera': False,
        })
        self.events = []
        self.client._callback = self.events.append
        self.client.client = MagicMock()

    def test_access_denied_fires_the_event(self):
        self.client.on_disconnect(client_=None, userdata=None, result_code=5)

        self.assertIn("event_printer_access_denied", self.events)

    def test_other_error_codes_do_not_fire_it(self):
        self.client.on_disconnect(client_=None, userdata=None, result_code=16)

        self.assertNotIn("event_printer_access_denied", self.events)

    def test_a_repeated_access_denied_fires_the_event_once(self):
        self.client.on_disconnect(client_=None, userdata=None, result_code=5)
        self.client.on_disconnect(client_=None, userdata=None, result_code=5)

        self.assertEqual(self.events.count("event_printer_access_denied"), 1)


class _StuckThread(threading.Thread):
    """Stands in for a child thread that ignores stop(), e.g. blocked in a socket call."""

    def __init__(self):
        super().__init__(daemon=True)
        self._release = threading.Event()
        self.stop_called = False

    def stop(self):
        self.stop_called = True

    def run(self):
        self._release.wait(30)

    def release(self):
        self._release.set()


class TestDisconnectNeverBlocks(unittest.TestCase):
    """_on_disconnect runs on paho's network thread. If it blocks, paho's own reconnect
    never runs and the printer stays offline with nothing logged (#2129)."""

    def setUp(self):
        self.client = BambuClient({
            'host': '192.0.2.10',
            'serial': 'TESTSERIAL123',
            'enable_camera': False,
        })
        self.client._callback = lambda event: None
        self.client.client = MagicMock()
        self.stuck = _StuckThread()
        self.stuck.start()
        self.addCleanup(self.stuck.release)

    def _assert_returns_promptly(self):
        start = time.monotonic()
        with patch("pybambu.bambu_client.THREAD_STOP_TIMEOUT", 0.05):
            self.client._on_disconnect()
        self.assertLess(time.monotonic() - start, 5)
        self.assertTrue(self.stuck.stop_called)

    def test_stuck_watchdog_does_not_block(self):
        self.client._watchdog = self.stuck
        self._assert_returns_promptly()

    def test_stuck_camera_does_not_block(self):
        self.client._camera = self.stuck
        self._assert_returns_promptly()
        self.assertIsNone(self.client._camera)

    def test_stuck_thread_is_logged(self):
        self.client._camera = self.stuck
        with self.assertLogs(LOGGER, level="WARNING") as logs:
            self._assert_returns_promptly()
        self.assertTrue(any("did not stop" in line for line in logs.output))


class TestChamberConnectTimeout(unittest.TestCase):
    def test_connect_has_a_timeout_and_a_timeout_only_logs_at_debug(self):
        client = MagicMock()
        client._access_code = "12345678"
        client._device.info.ip_address = "192.0.2.10"
        client._device.info.device_type = "P1S"
        thread = ChamberImageThread(client)
        timeouts = []

        def connect(address, timeout=None):
            timeouts.append(timeout)
            thread.stop()
            raise TimeoutError("timed out")

        with patch("pybambu.bambu_client.socket.create_connection", side_effect=connect), \
                self.assertNoLogs(LOGGER, level="ERROR"):
            thread.run()

        self.assertEqual(len(timeouts), 1)
        self.assertIsNotNone(timeouts[0])
