import unittest
from unittest.mock import MagicMock

from pybambu.models import ExternalSpool


class TestExternalSpoolBlankPayload(unittest.TestCase):
    """The holder has no sensor, so a full payload with blank filament fields is how the
    printer reports that nothing is configured on it (#2097)."""

    BLANK = {
        "id": "254",
        "tag_uid": "",
        "tray_info_idx": "",
        "tray_type": "",
        "tray_sub_brands": "",
        "tray_color": "",
        "tray_weight": "0",
        "state": 8,
    }

    def setUp(self):
        self.client = MagicMock()
        self.client.slicer_settings.custom_filaments = {}
        self.client._device.supports_feature.return_value = False
        self.spool = ExternalSpool(self.client, 0)

    def test_blank_payload_reads_as_empty_not_unknown(self):
        self.spool.print_update({"vt_tray": self.BLANK})

        self.assertTrue(self.spool.empty)
        self.assertFalse(self.spool.unknown)
        self.assertEqual(self.spool.name, "Empty")
        self.assertEqual(self.spool.type, "Empty")

    def test_configured_spool_still_reads_as_loaded(self):
        self.spool.print_update({"vt_tray": {
            **self.BLANK,
            "tray_info_idx": "GFA00",
            "tray_type": "PLA",
        }})

        self.assertFalse(self.spool.empty)
        self.assertEqual(self.spool.type, "PLA")

    def test_type_without_profile_is_still_loaded(self):
        self.spool.print_update({"vt_tray": {**self.BLANK, "tray_type": "PETG"}})

        self.assertFalse(self.spool.empty)
        self.assertEqual(self.spool.name, "PETG")


class TestExternalSpoolInactive(unittest.TestCase):
    """A loaded external spool that isn't feeding is still loaded (#2239)."""

    def setUp(self):
        self.client = MagicMock()
        self.client.slicer_settings.custom_filaments = {}
        self.client._device.supports_feature.return_value = True
        self.spool = ExternalSpool(self.client, 0)
        self.spool.print_update({"vt_tray": {
            "id": "254",
            "tray_info_idx": "GFG00",
            "tray_type": "PETG",
            "tray_color": "001489FF",
        }})

    def test_inactive_spool_is_not_empty(self):
        # An AMS tray is feeding
        self.client._device.ams.active_ams_index = 0
        self.client._device.ams.active_tray_index = 2

        self.assertFalse(self.spool.active)
        self.assertFalse(self.spool.empty)
        self.assertEqual(self.spool.type, "PETG")

    def test_active_spool_is_not_empty(self):
        self.client._device.ams.active_ams_index = 255
        self.client._device.ams.active_tray_index = 0

        self.assertTrue(self.spool.active)
        self.assertFalse(self.spool.empty)
