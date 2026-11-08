"""H3C display regressions: AMS bus IDs and non-SD storage telemetry."""

import json
import unittest
from pathlib import Path
from unittest.mock import MagicMock

from pybambu.const import Home_Flag_Values, Printers, SDCARD_STATUS
from pybambu.models import AMSInstance, HomeFlag


class TestAMSDeviceName(unittest.TestCase):
    def test_ams3h_uses_model_name_without_changing_bus_id(self):
        ams = AMSInstance(MagicMock(), "AMS 3H", 32)
        self.assertEqual(ams.device_name_suffix, "AMS_3H")
        self.assertEqual(ams.index, 32)

    def test_legacy_ams_names_are_preserved(self):
        for model, index, expected in (
            ("AMS", 0, "AMS_1"),
            ("AMS 2 Pro", 3, "AMS_4"),
            ("AMS HT", 128, "AMS_128"),
        ):
            with self.subTest(model=model):
                self.assertEqual(AMSInstance(MagicMock(), model, index).device_name_suffix, expected)


class TestH3CStorageDisplay(unittest.TestCase):
    def setUp(self):
        self.client = MagicMock()
        self.client._device_type = Printers.H3C
        self.home = HomeFlag(self.client)

    def test_h3c_does_not_raise_missing_sdcard_event_before_version(self):
        self.home.print_update({"home_flag": 0, "sdcard": False})
        self.assertEqual(self.home.sdcard_status, "not_applicable")
        self.client.callback.assert_not_called()

    def test_legacy_flags_do_not_claim_usb_or_internal_storage_health(self):
        for flags in (0, Home_Flag_Values.SD_CARD_PRESENT, Home_Flag_Values.SD_CARD_ABNORMAL):
            with self.subTest(flags=flags):
                self.home.print_update({"home_flag": int(flags), "sdcard": True})
                self.assertEqual(self.home.sdcard_status, "not_applicable")
        self.client.callback.assert_not_called()

    def test_usb_telemetry_is_retained_through_partial_updates(self):
        storage = [{"name": "usb", "total": "120111296", "used": "74859904"}]
        self.assertIsNone(self.home.reported_storage)
        self.assertTrue(self.home.print_update({"device": {"storage": storage}}))
        self.assertEqual(self.home.reported_storage, storage)
        self.assertFalse(self.home.print_update({"device": {"cam": {}}}))
        self.assertEqual(self.home.reported_storage, storage)
        self.assertTrue(self.home.print_update({"device": {"storage": []}}))
        self.assertEqual(self.home.reported_storage, [])

    def test_null_storage_does_not_erase_last_report(self):
        self.home.print_update({"device": {"storage": [{"name": "usb"}]}})
        self.home.print_update({"device": {"storage": None}})
        self.assertEqual(self.home.reported_storage, [{"name": "usb"}])

    def test_legacy_printers_keep_sdcard_states_and_events(self):
        self.home._device_type = Printers.H2C
        self.home.print_update({"home_flag": 0})
        self.assertEqual(self.home.sdcard_status, "missing")
        self.client.callback.assert_called_once_with("event_printer_missing_sdcard")
        self.home.print_update({"home_flag": int(Home_Flag_Values.SD_CARD_PRESENT)})
        self.assertEqual(self.home.sdcard_status, "normal")
        self.home.print_update({"home_flag": int(Home_Flag_Values.SD_CARD_ABNORMAL)})
        self.assertEqual(self.home.sdcard_status, "abnormal")

    def test_state_is_valid_and_translated(self):
        self.assertIn("not_applicable", SDCARD_STATUS)
        root = Path(__file__).resolve().parents[2] / "custom_components/bambu_lab/translations"
        for language, text in (("en", "Not applicable"), ("de", "Nicht zutreffend")):
            translations = json.loads((root / f"{language}.json").read_text())
            self.assertEqual(translations["entity"]["sensor"]["sdcard_status"]["state"]["not_applicable"], text)

    def test_usb_presence_is_unknown_until_storage_is_reported(self):
        self.assertIsNone(self.home.usb_connected)
        self.home.print_update({"sdcard": True})
        self.assertIsNone(self.home.usb_connected)
        self.home.print_update({"device": {"storage": [{"name": "usb"}]}})
        self.assertTrue(self.home.usb_connected)
        self.home.print_update({"device": {"storage": [{"name": "internal"}]}})
        self.assertFalse(self.home.usb_connected)

    def test_capacities_use_explicit_camera_kb_counters(self):
        self.home.print_update({"device": {
            "storage": [{"name": "usb", "total": "999", "used": "1"}],
            "cam": {"tl_external_total_kb": 104857600, "tl_external_free_kb": 31457280},
        }})
        self.assertEqual(self.home.usb_capacity_kib("total"), 104857600)
        self.assertEqual(self.home.usb_capacity_kib("free"), 31457280)
        self.assertEqual(self.home.usb_capacity_kib("used"), 73400320)
        self.assertTrue(self.home.print_update({"device": {"cam": {"tl_external_free_kb": 20971520}}}))
        self.assertEqual(self.home.usb_capacity_kib("used"), 83886080)

    def test_detaching_usb_clears_capacity_counters(self):
        self.home.print_update({"device": {"storage": [{"name": "usb"}], "cam": {
            "tl_external_total_kb": 1000, "tl_external_free_kb": 500,
        }}})
        self.home.print_update({"device": {"storage": [], "cam": {
            "tl_external_total_kb": 1000, "tl_external_free_kb": 500,
        }}})
        self.assertIsNone(self.home.usb_capacity_kib("total"))
        self.home.print_update({"device": {"storage": [{"name": "usb"}]}})
        self.assertIsNone(self.home.usb_capacity_kib("total"))

    def test_counters_before_first_storage_report_are_preserved(self):
        self.home.print_update({"device": {"cam": {"tl_external_total_kb": 1000, "tl_external_free_kb": 0}}})
        self.assertIsNone(self.home.usb_capacity_kib("total"))
        self.home.print_update({"device": {"storage": [{"name": "usb"}]}})
        self.assertEqual(self.home.usb_capacity_kib("free"), 0)
        self.assertEqual(self.home.usb_capacity_kib("used"), 1000)

    def test_invalid_counters_do_not_create_misleading_capacities(self):
        self.home.print_update({"device": {"storage": [{"name": "usb"}]}})
        for bad in (-1, True, "NaN", None, 1.5):
            with self.subTest(value=bad):
                self.home.print_update({"device": {"cam": {"tl_external_total_kb": bad}}})
                self.assertIsNone(self.home.usb_capacity_kib("total"))
        self.home.print_update({"device": {"cam": {"tl_external_total_kb": 1000, "tl_external_free_kb": 2000}}})
        self.assertIsNone(self.home.usb_capacity_kib("free"))
        self.assertIsNone(self.home.usb_capacity_kib("used"))

    def test_usb_sensor_translations_exist(self):
        root = Path(__file__).resolve().parents[2] / "custom_components/bambu_lab/translations"
        for language in ("en", "de"):
            sensors = json.loads((root / f"{language}.json").read_text())["entity"]["sensor"]
            for key in ("usb_connection", "usb_storage_total", "usb_storage_used", "usb_storage_free"):
                self.assertIn(key, sensors)
