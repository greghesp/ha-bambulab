import unittest

from pybambu.commands import PRINT_PROJECT_FILE_TEMPLATE
from pybambu.const import LEGACY_SDCARD_PRINTERS, Printers
from pybambu.utils import build_print_project_file_command


class TestPrintProjectFileUrl(unittest.TestCase):
    def test_p2s_uses_ftp_url(self):
        """The P2S rejects file:///sdcard with 0500_4002 (#2207)."""
        command = build_print_project_file_command(Printers.P2S, {"filepath": "cache/a.3mf"})
        self.assertEqual(command["print"]["url"], "ftp:///cache/a.3mf")

    def test_h2d_uses_ftp_url(self):
        command = build_print_project_file_command(Printers.H2D, {"filepath": "cache/a.3mf"})
        self.assertEqual(command["print"]["url"], "ftp:///cache/a.3mf")

    def test_legacy_printers_use_sdcard_url(self):
        for printer in LEGACY_SDCARD_PRINTERS:
            with self.subTest(printer=printer):
                command = build_print_project_file_command(printer, {"filepath": "cache/a.3mf"})
                self.assertEqual(command["print"]["url"], "file:///sdcard/cache/a.3mf")

    def test_full_url_is_passed_through(self):
        command = build_print_project_file_command(
            Printers.X1C, {"filepath": "ftp:///cache/a.3mf"}
        )
        self.assertEqual(command["print"]["url"], "ftp:///cache/a.3mf")


class TestPrintProjectFileOptions(unittest.TestCase):
    def test_disabled_calibrations_send_integer_flags(self):
        """The P2S decides from auto_bed_leveling / extrude_cali_flag, not the booleans (#2207)."""
        command = build_print_project_file_command(
            Printers.P2S,
            {"filepath": "cache/a.3mf", "bed_leveling": False, "flow_cali": False},
        )
        self.assertIs(command["print"]["bed_leveling"], False)
        self.assertEqual(command["print"]["auto_bed_leveling"], 0)
        self.assertIs(command["print"]["flow_cali"], False)
        self.assertEqual(command["print"]["extrude_cali_flag"], 0)

    def test_enabled_calibrations_send_integer_flags(self):
        command = build_print_project_file_command(
            Printers.P2S,
            {"filepath": "cache/a.3mf", "bed_leveling": True, "flow_cali": True},
        )
        self.assertEqual(command["print"]["auto_bed_leveling"], 1)
        self.assertEqual(command["print"]["extrude_cali_flag"], 1)

    def test_plate_ams_mapping_and_subtask_name(self):
        command = build_print_project_file_command(
            Printers.X1C,
            {
                "filepath": "cache/model.gcode.3mf",
                "plate": 3,
                "use_ams": True,
                "ams_mapping": "0,2,-1",
            },
        )
        self.assertEqual(command["print"]["param"], "Metadata/plate_3.gcode")
        self.assertEqual(command["print"]["ams_mapping"], [0, 2, -1])
        self.assertEqual(command["print"]["subtask_name"], "model.gcode.3mf")

    def test_template_is_not_mutated(self):
        build_print_project_file_command(
            Printers.P2S, {"filepath": "cache/a.3mf", "timelapse": True}
        )
        self.assertEqual(PRINT_PROJECT_FILE_TEMPLATE["print"]["url"], "")
        self.assertIs(PRINT_PROJECT_FILE_TEMPLATE["print"]["timelapse"], False)
        self.assertNotIn("auto_bed_leveling", PRINT_PROJECT_FILE_TEMPLATE["print"])


if __name__ == "__main__":
    unittest.main()
