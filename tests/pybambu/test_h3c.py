"""H3C/AMS 3H regressions using a reduced, anonymized device payload (#2209)."""

import copy
import json
import unittest
from pathlib import Path
from unittest.mock import MagicMock

from pybambu.const import Features, Printers
from pybambu.models import AMSInstance, Device
from pybambu.utils import get_printer_type


class TestH3C(unittest.TestCase):
    def setUp(self):
        self.payload = json.loads(Path(__file__).with_name("H3C_AMS3H.json").read_text())
        self.client = MagicMock()
        self.client._device_type = Printers.H3C
        self.client.slicer_settings.custom_filaments = {}
        self.device = Device(self.client)
        self.client._device = self.device

    def load(self, status_first=False):
        if status_first:
            self.device.print_update(self.payload["push_status"])
            self.device.info_update(self.payload["get_version"])
        else:
            self.device.info_update(self.payload["get_version"])
            self.device.print_update(self.payload["push_status"])

    def test_product_name_takes_priority_over_reused_ap05_board(self):
        modules = self.payload["get_version"]["module"]
        self.assertEqual(get_printer_type(modules, Printers.X1C), Printers.H3C)
        self.assertEqual(get_printer_type(list(reversed(modules)), Printers.X1C), Printers.H3C)
        self.assertEqual(get_printer_type([{"name": "ap2", "hw_ver": "AP05"}], Printers.H3C), Printers.H3C)

    def test_partial_product_metadata_preserves_identity(self):
        self.load()
        self.device.info_update({"module": [{"name": "ap2", "hw_ver": "AP05"}]})
        self.assertEqual(self.device.info.device_type, Printers.H3C)
        self.assertEqual(self.device.home_flag._device_type, Printers.H3C)

    def test_door_sensor_uses_stat_and_preserves_partial_updates(self):
        self.load()
        self.assertTrue(self.device.supports_feature(Features.DOOR_SENSOR))

        # H3C firmware 01.01.03.00 reports door state in bit 23 of stat.
        self.device.info.print_update({"stat": "104621A0F0"})
        self.assertFalse(self.device.info.door_open)
        self.device.info.print_update({"stat": "1046A1A0F0"})
        self.assertTrue(self.device.info.door_open)
        self.device.info.print_update({"home_flag": -1067100737})
        self.assertTrue(self.device.info.door_open)
        self.device.info.print_update({"stat": "104621A0F0"})
        self.assertFalse(self.device.info.door_open)
        self.device.info.print_update({"home_flag": -1067100737})
        self.assertFalse(self.device.info.door_open)

    def test_prompt_sound_requires_unsigned_commands(self):
        self.load()
        self.device.print_fun.print_update({"fun": "0"})
        self.assertTrue(self.device.supports_feature(Features.PROMPT_SOUND))
        self.device.print_fun.print_update({"fun": "20000000"})
        self.assertFalse(self.device.supports_feature(Features.PROMPT_SOUND))

    def test_heatbed_light_tracks_commands_despite_error_response(self):
        self.load()
        self.assertTrue(self.device.supports_feature(Features.HEATBED_LIGHT))
        self.assertIsNone(self.device.lights.is_heatbed_light_on)

        # H3C firmware reports failure even though these commands change the light.
        for mode, expected in (("off", False), ("on", True)):
            self.device.observe_system_command({
                "command": "ledctrl",
                "led_node": "heatbed_light",
                "led_mode": mode,
                "result": "fail",
                "reason": "did not find the valid led: heatbed_light",
            })
            self.assertEqual(self.device.lights.is_heatbed_light_on, expected)

    def test_zone_only_ams_telemetry_does_not_crash_in_either_order(self):
        for status_first in (True, False):
            with self.subTest(status_first=status_first):
                self.setUp()
                self.load(status_first)
                ams = self.device.ams.data[32]
                self.assertEqual(ams.model, "AMS 3H")
                self.assertEqual(len(ams.tray), 9)
                self.assertEqual(ams.zones[0]["zone_slots"], [5, 7])
                self.assertEqual(ams.zones[1]["humidity_raw"], "33")
                # Do not replace cabinet measurements with an arbitrary zone.
                self.assertEqual(ams.humidity, 0)
                self.assertEqual(ams.temperature, 0)

    def test_zone_delta_preserves_other_measurements(self):
        self.load()
        self.assertTrue(self.device.ams.print_update({"ams": {"ams": [{"id": "32", "zone_info": [{"zone_id": 1, "temp": "29.5"}]}]}}))
        ams = self.device.ams.data[32]
        self.assertEqual(ams.zones[1]["temp"], "29.5")
        self.assertEqual(ams.zones[1]["humidity_raw"], "33")
        self.assertEqual(ams.zones[0]["zone_slots"], [5, 7])

    def test_ams_drying_follows_heated_zone_timer(self):
        self.load()
        ams = self.device.ams.data[32]
        self.assertFalse(ams.is_drying)
        self.assertEqual(ams.drying_time, 0)

        def update_zones(zone_info):
            self.device.ams.print_update({"ams": {"ams": [{"id": "32", "zone_info": zone_info}]}})

        update_zones([
            {"zone_id": 0, "dry_time": 719, "dry_setting": {
                "dry_duration": 12, "dry_filament": "PLA", "dry_temperature": 55,
            }},
            {"zone_id": 1, "dry_time": 719},
        ])
        self.assertTrue(ams.is_drying)
        self.assertEqual(ams.drying_time, 719)
        update_zones([{"zone_id": 0, "temp": "45.0"}])
        self.assertTrue(ams.is_drying)
        # The duplicate in zone 1 may lag behind a partial update.
        update_zones([{"zone_id": 0, "dry_time": 0}])
        self.assertFalse(ams.is_drying)

    def test_ams_drying_is_unknown_without_a_valid_heated_zone_timer(self):
        ams = AMSInstance(self.client, "AMS 3H", 32)
        self.assertIsNone(ams.is_drying)
        ams.zones = {1: {"dry_time": 1}}
        self.assertIsNone(ams.is_drying)
        ams.zones[0] = {"dry_time": 0}
        self.assertFalse(ams.is_drying)
        ams.zones[0]["dry_time"] = 1
        self.assertTrue(ams.is_drying)
        for value in (None, True, False, -1, "1", "invalid", float("inf")):
            with self.subTest(value=value):
                ams.zones[0]["dry_time"] = value
                self.assertIsNone(ams.drying_time)
                self.assertIsNone(ams.is_drying)

        legacy = AMSInstance(self.client, "AMS HT", 128)
        self.assertFalse(legacy.is_drying)
        legacy.remaining_drying_time = 1
        self.assertEqual(legacy.drying_time, 1)
        self.assertTrue(legacy.is_drying)

    def test_weight_only_delta_signals_an_update(self):
        self.load()
        delta = {"ams": {"ams": [{"id": "32", "tray": [{"id": "0", "remain_g": 611}]}]}}
        self.assertTrue(self.device.ams.print_update(delta))
        self.assertEqual(self.device.ams.data[32].tray[0].remaining_weight_g, 611)
        self.assertFalse(self.device.ams.print_update(delta))

    def test_nine_tools_and_mounted_tool_metadata(self):
        self.load()
        rack = self.device.hotend_rack
        self.assertEqual(list(rack.hotends), list(range(16, 25)))
        self.assertEqual(rack.mounted_slot_id, 16)
        self.assertEqual([sid for sid, tool in rack.hotends.items() if tool.active], [16])
        self.assertEqual(rack.hotends[16].temperature, 220)
        self.assertEqual(rack.hotends[16].target_temperature, 220)
        self.assertEqual(rack.hotends[17].temperature, 31)
        self.assertEqual(rack.hotends[23].type_code, "HT01")
        self.assertEqual(rack.hotends[24].diameter, 0.4)
        self.assertTrue(self.device.supports_feature(Features.HOTEND_RACK))
        self.assertFalse(self.device.supports_feature(Features.DUAL_NOZZLES))
        self.assertFalse(self.device.supports_feature(Features.AMS_SWITCH_COMMAND))
        self.assertFalse(self.device.supports_feature(Features.AMS_READ_RFID_COMMAND))

    def test_filament_link_uses_encoded_ams_and_slot(self):
        self.load()
        attrs = self.device.hotend_rack.filament_attributes(16)
        self.assertEqual(attrs["ams_id"], 32)
        self.assertEqual(attrs["ams_slot"], 1)
        self.assertEqual(attrs["filament_diameter"], 1.75)
        self.assertEqual(attrs["remaining_weight_g"], 612)
        attrs = self.device.hotend_rack.filament_attributes(17)
        self.assertEqual(attrs["ams_slot"], 2)
        self.assertEqual(attrs["remaining_weight_g"], 670)
        self.assertIsNone(self.device.hotend_rack.linked_filament(18))

    def test_tool_return_and_pickup_in_delta_messages(self):
        self.load()
        rack = self.device.hotend_rack
        self.assertTrue(rack.print_update({"device": {"nozzle": {"info": [{"id": 16, "addr_id": 0}]}}}))
        self.assertIsNone(rack.mounted_slot_id)
        self.assertFalse(any(tool.active for tool in rack.hotends.values()))
        self.assertTrue(rack.print_update({"device": {"nozzle": {"info": [{"id": 0, "addr_id": 8}]}}}))
        self.assertEqual(rack.mounted_slot_id, 24)
        self.assertEqual([sid for sid, tool in rack.hotends.items() if tool.active], [24])
        self.assertFalse(rack.print_update({"device": {"nozzle": {"state": rack.state}}}))
        self.assertEqual(rack.mounted_slot_id, 24)

    def test_repeated_payload_does_not_signal_rack_change(self):
        self.load()
        self.assertFalse(self.device.hotend_rack.print_update(self.payload["push_status"]))

    def test_h2c_keeps_six_slot_rack(self):
        self.device.info.device_type = Printers.H2C
        self.device.hotend_rack.print_update(self.payload["push_status"])
        self.assertEqual(list(self.device.hotend_rack.hotends), list(range(16, 22)))

    def test_legacy_ams_and_ht_slot_counts(self):
        self.assertEqual(len(AMSInstance(self.client, "AMS", 0).tray), 4)
        self.assertEqual(len(AMSInstance(self.client, "AMS HT", 128).tray), 1)

    def test_missing_or_invalid_legacy_measurements_keep_previous_values(self):
        self.device.ams.print_update({"ams": {"ams": [{"id": "0", "humidity": "4", "humidity_raw": "42", "temp": "25.5", "tray": []}]}})
        for fields in ({}, {"humidity": None, "humidity_raw": "invalid", "temp": "nan"}):
            self.device.ams.print_update({"ams": {"ams": [dict(fields, id="0")]}})
            ams = self.device.ams.data[0]
            self.assertEqual((ams.humidity_index, ams.humidity, ams.temperature), (4, 42, 25.5))

    def test_late_version_expands_placeholder_without_losing_filament(self):
        status = copy.deepcopy(self.payload["push_status"])
        # A delta before get_version need not include zone metadata.
        del status["ams"]["ams"][0]["zone_info"]
        self.device.ams.print_update(status)
        first = self.device.ams.data[32].tray[0]
        self.device.ams.info_update(self.payload["get_version"])
        self.assertEqual(len(self.device.ams.data[32].tray), 9)
        self.assertIs(self.device.ams.data[32].tray[0], first)
        self.assertEqual(first.remaining_weight_g, 612)
