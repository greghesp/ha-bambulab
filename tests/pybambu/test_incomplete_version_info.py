import unittest
from unittest.mock import MagicMock, call, patch

from pybambu.commands import GET_VERSION
from pybambu.models import Device
from pybambu.utils import get_sw_version

OTA = {"name": "ota", "sw_ver": "01.10.00.00", "hw_ver": "OTA", "sn": "01P00A000000000"}
ESP32 = {"name": "esp32", "sw_ver": "01.16.38.70", "hw_ver": "AP04", "sn": "01P00A000000000"}
AMS = {"name": "ams/0", "sw_ver": "01.00.06.83", "hw_ver": "AMS08", "sn": "00600A000000000"}


def version(*modules):
    return {"command": "get_version", "module": list(modules)}


class TestIncompleteVersionInfo(unittest.TestCase):
    """A printer that is still starting up can answer get_version without its firmware version, or
    not at all. Entities depend on the firmware version, so wait for it and ask again (#2033)."""

    def setUp(self):
        self.connect_new_device()
        self.now = 1000.0
        patcher = patch("pybambu.models.time.monotonic", side_effect=lambda: self.now)
        patcher.start()
        self.addCleanup(patcher.stop)

    def connect_new_device(self):
        self.client = MagicMock()
        self.client._device_type = "P1S"
        self.client.slicer_settings.custom_filaments = {}
        self.device = Device(self.client)
        self.client._device = self.device

    @property
    def request_count(self):
        return self.client.publish.call_args_list.count(call(GET_VERSION))

    @property
    def ready_count(self):
        return self.client.callback.call_args_list.count(call("event_printer_ready"))

    def push(self, msg=0):
        self.device.print_update({"command": "push_status", "msg": msg})

    def test_not_ready_until_the_firmware_version_is_known(self):
        for push_first in (True, False):
            for modules in ((), (ESP32,), (ESP32, AMS)):
                with self.subTest(push_first=push_first, modules=[m["name"] for m in modules]):
                    self.connect_new_device()
                    if push_first:
                        self.push()
                        self.device.info_update(version(*modules))
                    else:
                        self.device.info_update(version(*modules))
                        self.push()

                    self.assertFalse(self.device.has_full_printer_data)
                    self.assertEqual(self.ready_count, 0)

    def test_ready_once_when_the_firmware_version_arrives(self):
        self.push()
        self.device.info_update(version(ESP32))

        self.device.info_update(version(OTA, ESP32, AMS))
        self.push()

        self.assertTrue(self.device.has_full_printer_data)
        self.assertEqual(self.ready_count, 1)

    def test_incomplete_reply_does_not_undo_a_known_version(self):
        self.push()
        self.device.info_update(version(OTA, ESP32))

        self.device.info_update(version(ESP32))
        self.push()

        self.assertTrue(self.device.has_full_printer_data)
        self.assertEqual(self.ready_count, 1)
        self.assertEqual(self.request_count, 0)

    def test_requests_version_after_an_incomplete_reply(self):
        self.push()
        self.device.info_update(version(ESP32))
        self.now += 5

        self.push(msg=1)

        self.assertEqual(self.request_count, 1)

    def test_requests_version_when_no_reply_arrives(self):
        self.push()
        self.now += 4
        self.push(msg=1)
        # The request made on connect may still be answered.
        self.assertEqual(self.request_count, 0)

        self.now += 1
        self.push(msg=1)

        self.assertEqual(self.request_count, 1)

    def test_requests_back_off_and_stop_once_the_version_arrives(self):
        self.device.info_update(version())
        times = []
        for _ in range(1200):
            before = self.request_count
            self.push(msg=1)
            if self.request_count > before:
                times.append(self.now)
            self.now += 1
        gaps = [later - earlier for earlier, later in zip(times, times[1:])]
        self.assertEqual(gaps, [5, 10, 20, 40, 80, 160, 300, 300])

        self.device.info_update(version(OTA))
        requested = self.request_count
        for _ in range(600):
            self.now += 1
            self.push(msg=1)

        self.assertEqual(self.request_count, requested)

    def test_warns_once_when_the_version_never_arrives(self):
        self.device.info_update(version())
        with patch("pybambu.models.LOGGER.warning") as warning:
            for _ in range(150):
                self.push(msg=1)
                self.now += 1
            warning.assert_not_called()
            for _ in range(1200):
                self.push(msg=1)
                self.now += 1

        warning.assert_called_once()

    def test_blank_firmware_version_is_not_a_version(self):
        for blank in ({"sw_ver": ""}, {"sw_ver": None}):
            with self.subTest(**blank):
                self.assertEqual(get_sw_version([{**OTA, **blank}], "unknown"), "unknown")
                self.assertEqual(get_sw_version([{**OTA, **blank}], "01.09.00.00"), "01.09.00.00")
