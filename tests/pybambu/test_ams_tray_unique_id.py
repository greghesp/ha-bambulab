import unittest

from pybambu.utils import ams_tray_number_from_unique_id


class TestAmsTrayNumberFromUniqueId(unittest.TestCase):
    """AMS tray sensors end in tray_<n>. The AMS 3H has nine slots, so set_filament
    must accept tray_5 to tray_9 as well as the four slots of other AMS units (#2305)."""

    def test_four_slot_ams_trays(self):
        for number in range(1, 5):
            with self.subTest(number=number):
                self.assertEqual(
                    ams_tray_number_from_unique_id(f"X1C_SERIAL_AMS_AMSSERIAL_tray_{number}"),
                    number,
                )

    def test_ams_3h_trays_five_to_nine(self):
        for number in range(5, 10):
            with self.subTest(number=number):
                self.assertEqual(
                    ams_tray_number_from_unique_id(f"H3C_SERIAL_AMS_AMSSERIAL_tray_{number}"),
                    number,
                )

    def test_non_tray_entities_are_rejected(self):
        for unique_id in (
            "X1C_SERIAL_ExternalSpool_external_spool",
            "X1C_SERIAL_AMS_AMSSERIAL_tray_0",
            "X1C_SERIAL_AMS_AMSSERIAL_tray_10",
            "X1C_SERIAL_AMS_AMSSERIAL_humidity",
            "",
            None,
        ):
            with self.subTest(unique_id=unique_id):
                self.assertIsNone(ams_tray_number_from_unique_id(unique_id))


if __name__ == "__main__":
    unittest.main()
