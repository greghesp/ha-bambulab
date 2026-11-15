"""E1 air purifier protocol and discovery regressions."""

import unittest
from unittest.mock import MagicMock

from pybambu.air_purifier import AirPurifier, PURIFIER_GEARS
from pybambu.commands import GET_VERSION
from pybambu.models import Device


E1_VERSION = {"command": "get_version", "module": [{
    "name": "aps", "id": 0, "sn": "TEST-E1-SERIAL", "product_name": "E1 Air Purifier",
    "hw_ver": "APS04", "sw_ver": "00.00.25.92",
}]}
E1_STATUS = {"aux": "2002801004", "device": {"aps": {
    "type": 1, "pm": 3, "gear": 15, "rpm": 3509,
    "f_type": 1, "f_use": 0, "f_to": 720,
}}}


class TestAirPurifier(unittest.TestCase):
    def setUp(self):
        self.client = MagicMock()
        self.purifier = AirPurifier(self.client)

    def test_initial_status_and_version_in_either_order(self):
        for status_first in (True, False):
            with self.subTest(status_first=status_first):
                purifier = AirPurifier(self.client)
                if status_first:
                    purifier.print_update(E1_STATUS)
                    self.assertFalse(purifier.ready)
                    purifier.info_update(E1_VERSION)
                else:
                    purifier.info_update(E1_VERSION)
                    self.assertFalse(purifier.ready)
                    purifier.print_update(E1_STATUS)
                self.assertTrue(purifier.ready)
                self.assertEqual(purifier.serial, "TEST-E1-SERIAL")
                self.assertEqual((purifier.model, purifier.hw_version, purifier.sw_version),
                                 ("E1 Air Purifier", "APS04", "00.00.25.92"))
                self.assertEqual((purifier.gear, purifier.pm, purifier.rpm), (15, 3, 3509))
                self.assertEqual((purifier.filter_type, purifier.filter_used_raw, purifier.filter_total_raw),
                                 (1, 0, 720))

    def test_partial_and_invalid_telemetry_preserves_known_values(self):
        self.purifier.info_update(E1_VERSION)
        self.purifier.print_update(E1_STATUS)
        self.purifier.print_update({"device": {"aps": {"pm": 5}}})
        self.assertEqual((self.purifier.pm, self.purifier.rpm, self.purifier.gear), (5, 3509, 15))
        self.purifier.print_update({"aux": "invalid", "device": {"aps": {
            "gear": True, "pm": -1, "rpm": "0", "f_use": None,
        }}})
        self.assertEqual((self.purifier.pm, self.purifier.rpm, self.purifier.gear), (5, 3509, 15))
        self.assertTrue(self.purifier.ready)

    def test_empty_aps_does_not_create_device(self):
        self.purifier.print_update({"device": {"aps": {}}})
        self.assertIsNone(self.purifier.connected)
        self.assertFalse(self.purifier.ready)

    def test_disconnect_clears_state_and_requires_fresh_identity(self):
        self.purifier.info_update(E1_VERSION)
        self.purifier.print_update(E1_STATUS)
        self.purifier.print_update({"aux": "0", "device": {"aps": E1_STATUS["device"]["aps"]}})
        self.assertFalse(self.purifier.ready)
        self.assertIsNone(self.purifier.gear)
        self.purifier.print_update(E1_STATUS)
        self.assertFalse(self.purifier.ready)
        self.purifier.info_update(E1_VERSION)
        self.assertTrue(self.purifier.ready)

    def test_mode_commands_use_bambu_studio_protocol(self):
        self.purifier.info_update(E1_VERSION)
        self.purifier.print_update(E1_STATUS)
        self.client.publish.return_value = True
        for mode, value in PURIFIER_GEARS.items():
            with self.subTest(mode=mode):
                self.assertTrue(self.purifier.set_mode(mode))
                self.client.publish.assert_called_with({"print": {
                    "sequence_id": "0", "command": "part_control", "module": "aps", "action": str(value),
                }})
                self.assertEqual(self.purifier.gear, 15)
        self.assertFalse(self.purifier.set_mode("invalid"))
        self.client.publish.return_value = False
        self.assertFalse(self.purifier.set_mode("silent"))

    def test_late_attach_requests_identity_and_reinitializes_once(self):
        client = MagicMock()
        client._device_type = "H3C"
        client.slicer_settings.custom_filaments = {}
        device = Device(client)
        client._device = device
        device.get_version_data = {"command": "get_version"}
        device.push_all_data = {"command": "push_status"}
        device.air_purifier.connected = False

        device.print_update(E1_STATUS)
        client.publish.assert_called_once_with(GET_VERSION)
        self.assertFalse(device.air_purifier.ready)
        self.assertNotIn(unittest.mock.call("event_printer_ready"), client.callback.call_args_list)
        device.print_update(E1_STATUS)
        client.publish.assert_called_once_with(GET_VERSION)

        device.info_update(E1_VERSION)
        self.assertTrue(device.air_purifier.ready)
        self.assertEqual(client.callback.call_args_list.count(unittest.mock.call("event_printer_ready")), 1)
        device.info_update(E1_VERSION)
        self.assertEqual(client.callback.call_args_list.count(unittest.mock.call("event_printer_ready")), 1)

    def test_initial_accessory_without_version_metadata_requests_identity(self):
        for status_first in (True, False):
            with self.subTest(status_first=status_first):
                client = MagicMock()
                client._device_type = "H3C"
                client.slicer_settings.custom_filaments = {}
                device = Device(client)
                client._device = device
                status = {**E1_STATUS, "command": "push_status", "msg": 0}
                version = {"command": "get_version", "module": []}
                if status_first:
                    device.print_update(status)
                    device.info_update(version)
                else:
                    device.info_update(version)
                    device.print_update(status)
                client.publish.assert_called_once_with(GET_VERSION)
                self.assertFalse(device.air_purifier.ready)
                device.info_update(E1_VERSION)
                self.assertTrue(device.air_purifier.ready)

    def test_attached_replacement_reinitializes_with_new_identity(self):
        client = MagicMock()
        client._device_type = "H3C"
        client.slicer_settings.custom_filaments = {}
        device = Device(client)
        client._device = device
        device.get_version_data = {"command": "get_version"}
        device.push_all_data = {"command": "push_status"}
        device.air_purifier.info_update(E1_VERSION)
        device.air_purifier.print_update(E1_STATUS)
        device.print_update({"aux": "0"})
        device.print_update(E1_STATUS)
        replacement = {"command": "get_version", "module": [{
            "name": "aps", "sn": "REPLACEMENT-E1", "product_name": "E1 Air Purifier",
        }]}
        device.info_update(replacement)
        self.assertEqual(device.air_purifier.identity, "REPLACEMENT-E1")
        self.assertEqual(client.callback.call_args_list.count(unittest.mock.call("event_printer_ready")), 1)
