"""Tests for the filament color name lookup (#2027)."""

import unittest
from unittest.mock import MagicMock

from pybambu.filament_colors import FILAMENT_COLORS, get_filament_color_name
from pybambu.models import AMSTray, ExternalSpool


class TestFilamentColorTable(unittest.TestCase):
    def test_entries_are_well_formed(self):
        self.assertGreater(len(FILAMENT_COLORS), 0)
        for filament_id, entries in FILAMENT_COLORS.items():
            for entry in entries:
                with self.subTest(filament_id=filament_id, entry=entry):
                    self.assertTrue(entry["name"])
                    self.assertTrue(entry["code"])
                    self.assertTrue(entry["colors"])
                    for color in entry["colors"]:
                        self.assertRegex(color, r"^[0-9A-F]{8}$")

    def test_a_color_set_names_one_color_per_filament(self):
        for filament_id, entries in FILAMENT_COLORS.items():
            color_sets = [tuple(sorted(entry["colors"])) for entry in entries]
            self.assertEqual(len(color_sets), len(set(color_sets)), filament_id)


class TestGetFilamentColorName(unittest.TestCase):
    def test_single_color(self):
        self.assertEqual(get_filament_color_name("GFA00", ["FFFFFFFF"]), "Jade White")

    def test_same_color_is_named_per_filament(self):
        self.assertEqual(get_filament_color_name("GFA00", ["000000FF"]), "Black")
        self.assertEqual(get_filament_color_name("GFA01", ["000000FF"]), "Charcoal")
        self.assertEqual(get_filament_color_name("GFA01", ["FFFFFFFF"]), "Ivory White")

    def test_alpha_is_significant(self):
        self.assertEqual(get_filament_color_name("GFC00", ["000000FF"]), "Black")
        self.assertEqual(get_filament_color_name("GFC00", ["00000000"]), "Transparent")

    def test_multi_color_ignores_order(self):
        # Reported by an RFID spool, see #1867.
        expected = get_filament_color_name("GFA05", ["418FDEFF", "70C884FF"])
        self.assertIsNotNone(expected)
        self.assertEqual(get_filament_color_name("GFA05", ["70C884FF", "418FDEFF"]), expected)

    def test_single_color_of_a_multi_color_filament_does_not_match(self):
        self.assertIsNone(get_filament_color_name("GFA05", ["418FDEFF"]))

    def test_lower_case_color(self):
        self.assertEqual(get_filament_color_name("GFA00", ["c12e1fff"]), "Red")

    def test_unknown_filament_or_color(self):
        self.assertIsNone(get_filament_color_name("GFL99", ["FFFFFFFF"]))
        self.assertIsNone(get_filament_color_name("P8874e68", ["FFFFFFFF"]))
        self.assertIsNone(get_filament_color_name("GFA00", ["123456FF"]))
        self.assertIsNone(get_filament_color_name("", ["FFFFFFFF"]))
        self.assertIsNone(get_filament_color_name("GFA00", []))

    def test_tag_code_names_a_color_whose_hex_changed(self):
        # Older RFID spools carry a hex value Bambu Lab has since revised.
        self.assertEqual(get_filament_color_name("GFA00", ["00358EFF"], "A00-B9"), "Blue")
        self.assertEqual(get_filament_color_name("GFG00", ["9EA2A2FF"], "G00-D0"), "Gray")

    def test_tag_code_is_zero_padded_on_newer_firmware(self):
        self.assertEqual(get_filament_color_name("GFA00", ["00358EFF"], "A00-B09"), "Blue")

    def test_color_wins_over_tag_code(self):
        # These tags use a code that isn't in the table (S02-W0 is listed as W1).
        self.assertEqual(get_filament_color_name("GFS02", ["FFFFFFFF"], "S02-W0"), "White")
        self.assertEqual(get_filament_color_name("GFA00", ["C12E1FFF"], "A00-W1"), "Red")

    def test_tag_code_of_another_filament_is_ignored(self):
        self.assertIsNone(get_filament_color_name("GFA01", ["123456FF"], "A00-K0"))

    def test_malformed_tag_code_is_ignored(self):
        for tray_id_name in ("", None, "A00", "A00-", "-K0", "A00-K", 5):
            with self.subTest(tray_id_name=tray_id_name):
                self.assertIsNone(get_filament_color_name("GFA00", ["123456FF"], tray_id_name))


def _tray_data(**overrides):
    return {
        "id": "0",
        "state": 11,
        "tray_info_idx": "GFA00",
        "tray_type": "PLA",
        "tray_id_name": "A00-K0",
        "tray_color": "000000FF",
        "cols": ["000000FF"],
        "ctype": 0,
        **overrides,
    }


class TestTrayColorName(unittest.TestCase):
    def setUp(self):
        client = MagicMock()
        client.slicer_settings.custom_filaments = {}
        self.tray = AMSTray(client)
        self.spool = ExternalSpool(client, 0)

    def test_no_spool(self):
        self.assertIsNone(self.tray.color_name)
        self.assertIsNone(self.spool.color_name)

    def test_rfid_spool(self):
        self.tray.print_update(_tray_data())
        self.assertEqual(self.tray.color_name, "Black")

    def test_multi_color_spool(self):
        self.tray.print_update(_tray_data(
            tray_info_idx="GFA05", tray_id_name="A05-T4", tray_color="418FDEFF",
            cols=["418FDEFF", "70C884FF"], ctype=1))
        self.assertEqual(self.tray.color_name,
                         get_filament_color_name("GFA05", ["418FDEFF", "70C884FF"]))

    def test_firmware_without_cols(self):
        data = {k: v for k, v in _tray_data().items() if k not in ("cols", "ctype")}
        self.tray.print_update(data)
        self.assertEqual(self.tray.color_name, "Black")

    def test_older_spool_is_named_from_the_tag(self):
        self.tray.print_update(_tray_data(
            tray_id_name="A00-B9", tray_color="00358EFF", cols=["00358EFF"]))
        self.assertEqual(self.tray.color_name, "Blue")

    def test_third_party_spool(self):
        self.tray.print_update(_tray_data(tray_info_idx="GFL99", tray_id_name=""))
        self.assertIsNone(self.tray.color_name)

    def test_cleared_when_spool_is_removed(self):
        self.tray.print_update(_tray_data(
            tray_id_name="A00-B9", tray_color="00358EFF", cols=["00358EFF"]))
        self.tray.print_update({"id": "0", "state": 10})
        self.assertIsNone(self.tray.color_name)
        # The tag of the removed spool must not name an untagged one.
        self.tray.print_update({
            "id": "0", "state": 11, "tray_info_idx": "GFA00", "tray_type": "PLA",
            "tray_color": "123456FF", "cols": ["123456FF"]})
        self.assertIsNone(self.tray.color_name)

    def test_color_changed_without_cols(self):
        self.tray.print_update(_tray_data())
        self.tray.print_update({"id": "0", "state": 11, "tray_color": "C12E1FFF"})
        self.assertEqual(self.tray.color_name, "Red")

    def test_color_changed_without_tag_code(self):
        self.tray.print_update(_tray_data())
        self.tray.print_update({"id": "0", "state": 11, "tray_color": "123456FF", "cols": ["123456FF"]})
        self.assertIsNone(self.tray.color_name)

    def test_partial_update_keeps_the_tag_code(self):
        self.tray.print_update(_tray_data(
            tray_id_name="A00-B9", tray_color="00358EFF", cols=["00358EFF"]))
        self.tray.print_update({"id": "0", "state": 11, "remain": 50})
        self.assertEqual(self.tray.color_name, "Blue")

    def test_external_spool(self):
        # No RFID reader on the holder: the color is whatever was set for it.
        self.spool.print_update({"vt_tray": _tray_data(id="254", tray_id_name="")})
        self.assertEqual(self.spool.color_name, "Black")
        self.spool.print_update({"vt_tray": _tray_data(
            id="254", tray_info_idx="", tray_type="", tray_id_name="",
            tray_color="00000000", cols=["00000000"])})
        self.assertIsNone(self.spool.color_name)


if __name__ == "__main__":
    unittest.main()
