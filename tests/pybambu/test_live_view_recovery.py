"""Issue #2140: the camera stays unavailable after the user turns LAN Only Liveview on.

The printer reports ipcam.rtsp_url == "disable" while LAN Only Liveview is off. The
integration raised a repair issue for that, but never noticed the setting being turned
back on: the repair stayed, and on chamber-image printers (P1/A1) the image thread had
already exhausted its connect attempts, so the camera stayed dead until a reload.
"""
import threading
import unittest
from unittest.mock import MagicMock, patch

from pybambu.bambu_client import BambuClient
from pybambu.models import Camera

DISABLED = {"ipcam": {"rtsp_url": "disable"}}
ENABLED = {"ipcam": {"rtsp_url": "rtsps://192.0.2.10/streaming/live/1"}}


class TestLiveViewEvents(unittest.TestCase):
    def setUp(self):
        self.client = MagicMock()
        self.client._enable_camera = True
        self.camera = Camera(self.client)

    def events(self):
        return [c.args[0] for c in self.client.callback.call_args_list]

    def test_disabled_fires_once(self):
        self.camera.print_update(DISABLED)
        self.camera.print_update(DISABLED)

        self.assertEqual(self.events(), ["event_printer_live_view_disabled"])

    def test_turning_live_view_back_on_fires_enabled(self):
        self.camera.print_update(DISABLED)
        self.camera.print_update(ENABLED)

        self.assertEqual(self.events(), [
            "event_printer_live_view_disabled",
            "event_printer_live_view_enabled",
        ])

    def test_enabled_without_prior_disable_fires_nothing(self):
        self.camera.print_update(ENABLED)

        self.assertEqual(self.events(), [])

    def test_partial_payload_without_ipcam_does_not_fire_enabled(self):
        self.camera.print_update(DISABLED)
        self.camera.print_update({"mc_percent": 10})

        self.assertEqual(self.events(), ["event_printer_live_view_disabled"])

    def test_disabling_again_after_reenable_fires_disabled_again(self):
        self.camera.print_update(DISABLED)
        self.camera.print_update(ENABLED)
        self.camera.print_update(DISABLED)

        self.assertEqual(self.events().count("event_printer_live_view_disabled"), 2)


class _AliveThread(threading.Thread):
    def __init__(self):
        super().__init__(daemon=True)
        self._release = threading.Event()

    def stop(self):
        self._release.set()

    def run(self):
        self._release.wait(30)


class TestStartCameraRestart(unittest.TestCase):
    def setUp(self):
        self.client = BambuClient({
            'host': '192.0.2.10',
            'serial': 'TESTSERIAL123',
            'access_code': '12345678',
            'enable_camera': True,
            'device_type': 'P1S',
        })
        self.client._device.info._ip_address = '192.0.2.10'

    def _start_with_mock_thread(self):
        with patch("pybambu.bambu_client.ChamberImageThread") as thread_cls:
            self.client.start_camera()
        return thread_cls

    def test_restarts_a_chamber_thread_that_has_exited(self):
        dead = MagicMock()
        dead.is_alive.return_value = False
        self.client._camera = dead

        thread_cls = self._start_with_mock_thread()

        thread_cls.assert_called_once()
        thread_cls.return_value.start.assert_called_once()

    def test_does_not_start_a_second_thread_while_one_is_running(self):
        running = _AliveThread()
        running.start()
        self.client._camera = running
        try:
            thread_cls = self._start_with_mock_thread()
            thread_cls.assert_not_called()
            self.assertIs(self.client._camera, running)
        finally:
            running.stop()
            running.join(1)


if __name__ == "__main__":
    unittest.main()
