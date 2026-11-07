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
