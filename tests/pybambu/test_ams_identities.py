import unittest
from unittest.mock import MagicMock

from pybambu.models import Device


class TestAmsIdentitiesResolved(unittest.TestCase):
    """Registered AMS devices may only be judged stale once the printer has told us the
    serial of every AMS it reports. Otherwise a blank `sn` in the version payload removes a
    device that is still attached (#2089)."""

    AMS_PAYLOAD = {
        "command": "push_status",
        "msg": 0,
        "ams": {
            "ams": [{"id": "0", "humidity": "4", "temp": "25.0", "tray": []}],
            "tray_now": "255",
            "tray_tar": "255",
        },
    }

    def version(self, sn):
        return {
            "command": "get_version",
            "module": [{
                "name": "ams/0",
                "project_name": "",
                "sw_ver": "00.00.05.96",
                "hw_ver": "AMS08",
                "sn": sn,
            }],
        }

    def setUp(self):
        self.client = MagicMock()
        self.client.slicer_settings.custom_filaments = {}
        self.device = Device(self.client)
        self.client._device = self.device

    def test_not_resolved_before_any_data(self):
        self.assertFalse(self.device.ams_identities_resolved)

    def test_not_resolved_when_version_has_a_blank_serial(self):
        self.device.print_update(self.AMS_PAYLOAD)
        self.device.info_update(self.version(""))

        self.assertTrue(self.device.has_full_printer_data)
        self.assertFalse(self.device.ams_identities_resolved)

    def test_not_resolved_when_push_all_has_no_ams_block(self):
        self.device.print_update({"command": "push_status", "msg": 0})
        self.device.info_update({"command": "get_version", "module": []})

        self.assertFalse(self.device.ams_identities_resolved)

    def test_resolved_once_the_serial_arrives(self):
        self.device.print_update(self.AMS_PAYLOAD)
        self.device.info_update(self.version(""))
        self.device.info_update(self.version("00600A000000000"))

        self.assertTrue(self.device.ams_identities_resolved)

    def test_resolved_when_the_printer_reports_no_ams(self):
        self.device.print_update({"command": "push_status", "msg": 0, "ams": {"ams": []}})
        self.device.info_update({"command": "get_version", "module": []})

        self.assertTrue(self.device.ams_identities_resolved)
