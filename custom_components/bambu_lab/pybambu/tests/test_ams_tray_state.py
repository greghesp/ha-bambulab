"""Tests for AMS tray state interpretation."""

import os
import sys
import unittest
from unittest.mock import MagicMock

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from pybambu.utils import ams_tray_spool_loaded
from pybambu.models import AMSTray


class TestAMSTraySpoolLoaded(unittest.TestCase):
    def test_legacy(self):
        self.assertFalse(ams_tray_spool_loaded(0))
        self.assertFalse(ams_tray_spool_loaded(1))
        self.assertFalse(ams_tray_spool_loaded(2))
        self.assertTrue(ams_tray_spool_loaded(3))
        self.assertFalse(ams_tray_spool_loaded(5))

    def test_new_format_steady(self):
        self.assertFalse(ams_tray_spool_loaded(8))
        self.assertTrue(ams_tray_spool_loaded(9))
        self.assertFalse(ams_tray_spool_loaded(10))
        self.assertTrue(ams_tray_spool_loaded(11))

    def test_new_format_motion(self):
        self.assertFalse(ams_tray_spool_loaded(17))
        self.assertFalse(ams_tray_spool_loaded(21))


class TestAMSTrayState(unittest.TestCase):
    def setUp(self):
        self.client = MagicMock()
        self.client.slicer_settings.custom_filaments = {}
        self.tray = AMSTray(self.client)

    def test_legacy_state_0_empty(self):
        self.tray.print_update({"id": "0", "state": 0})
        self.assertTrue(self.tray.empty)
        self.assertEqual(self.tray.state, 0)

    def test_legacy_state_1_empty(self):
        self.tray.print_update({"id": "0", "state": 1})
        self.assertTrue(self.tray.empty)

    def test_legacy_state_2_loading_empty(self):
        self.tray.print_update({"id": "0", "state": 2})
        self.assertTrue(self.tray.empty)

    def test_legacy_state_3_uses_metadata(self):
        self.tray.print_update({
            "id": "0",
            "state": 3,
            "tray_type": "PLA",
            "tray_info_idx": "GFA00",
        })
        self.assertFalse(self.tray.empty)
        self.assertFalse(self.tray.unknown)
        self.assertNotEqual(self.tray.name, "?")
        self.assertEqual(self.tray.type, "PLA")

    def test_legacy_state_3_bad_metadata_unknown(self):
        self.tray.print_update({
            "id": "0",
            "state": 3,
            "tray_type": "",
            "tray_info_idx": "",
        })
        self.assertFalse(self.tray.empty)
        self.assertTrue(self.tray.unknown)

    def test_legacy_state_3_type_only(self):
        self.tray.print_update({
            "id": "0",
            "state": 3,
            "tray_type": "PLA",
            "tray_info_idx": "",
        })
        self.assertFalse(self.tray.empty)
        self.assertFalse(self.tray.unknown)
        self.assertEqual(self.tray.name, "PLA")

    def test_legacy_state_5_empty(self):
        self.tray.print_update({"id": "0", "state": 5})
        self.assertTrue(self.tray.empty)
        self.assertEqual(self.tray.state, 5)

    def test_state_9_unknown_spool(self):
        self.tray.print_update({"id": "0", "state": 9})
        self.assertFalse(self.tray.empty)
        self.assertTrue(self.tray.unknown)

    def test_state_8_empty(self):
        self.tray.print_update({"id": "0", "state": 8})
        self.assertTrue(self.tray.empty)

    def test_motion_state_21_empty_despite_type(self):
        self.tray.print_update({
            "id": "0",
            "state": 21,
            "tray_type": "PETG",
        })
        self.assertTrue(self.tray.empty)

    def test_state_11_full_payload(self):
        self.tray.print_update({
            "id": "1",
            "state": 11,
            "tray_info_idx": "P3507b3f",
            "tray_type": "PETG",
            "tray_color": "E1E1E1FF",
        })
        self.assertFalse(self.tray.empty)
        self.assertFalse(self.tray.unknown)
        self.assertEqual(self.tray.name, "PETG")

    def test_motion_state_21_metadata_only_clears_tray(self):
        self.tray.name = "PETG"
        self.tray.empty = False
        self.tray.print_update({"id": "0", "state": 21})
        self.assertTrue(self.tray.empty)
        self.assertEqual(self.tray.name, "Empty")

    def test_state_11_clear_profile_keeps_slot_loaded(self):
        self.tray.print_update({
            "id": "1",
            "state": 11,
            "tray_info_idx": "",
            "tray_type": "PETG",
            "tray_color": "E1E1E1FF",
            "tray_sub_brands": "",
        })
        self.assertFalse(self.tray.empty)
        self.assertEqual(self.tray.name, "PETG")

    def test_state_11_clear_all_metadata_unknown(self):
        self.tray.print_update({
            "id": "1",
            "state": 11,
            "tray_info_idx": "",
            "tray_type": "",
            "tray_sub_brands": "",
        })
        self.assertFalse(self.tray.empty)
        self.assertTrue(self.tray.unknown)

    def test_metadata_only_state_11_after_clear_unknown(self):
        self.tray.type = ""
        self.tray.print_update({"id": "1", "state": 11})
        self.assertFalse(self.tray.empty)
        self.assertTrue(self.tray.unknown)

    def test_metadata_only_state_11_with_type(self):
        self.tray.type = "PETG"
        self.tray.print_update({"id": "1", "state": 11})
        self.assertFalse(self.tray.empty)
        self.assertEqual(self.tray.name, "PETG")

    def test_id_only_legacy_empty(self):
        self.tray.print_update({"id": "0"})
        self.assertTrue(self.tray.empty)
        self.assertEqual(self.tray.state, 0)


if __name__ == '__main__':
    unittest.main()
