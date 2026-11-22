import unittest
from unittest.mock import MagicMock

from pybambu.models import Device


class TestAmsReadingSpikes(unittest.TestCase):
    """The AMS occasionally reports a single wildly wrong temperature or humidity
    sample (e.g. 28 C -> 88 C -> 28 C) that shows up as spikes in HA history (#2134).
    A large jump is only accepted once a second reading confirms it."""

    def setUp(self):
        self.client = MagicMock()
        self.client.slicer_settings.custom_filaments = {}
        self.device = Device(self.client)
        self.client._device = self.device

    def push(self, **fields):
        return self.device.ams.print_update(
            {"ams": {"ams": [{"id": "0", "tray": [], **fields}]}}
        )

    @property
    def ams(self):
        return self.device.ams.data[0]

    def test_first_reading_is_accepted(self):
        self.push(temp="27.9", humidity_raw="14")
        self.assertEqual(self.ams.temperature, 27.9)
        self.assertEqual(self.ams.humidity, 14)

    def test_small_changes_are_accepted_immediately(self):
        self.push(temp="27.9", humidity_raw="15")
        self.push(temp="28.3", humidity_raw="14")
        self.assertEqual(self.ams.temperature, 28.3)
        self.assertEqual(self.ams.humidity, 14)

    def test_single_temperature_spike_is_ignored(self):
        self.push(temp="28.0")
        self.assertFalse(self.push(temp="88.0"))
        self.assertEqual(self.ams.temperature, 28.0)
        self.push(temp="28.1")
        self.assertEqual(self.ams.temperature, 28.1)

    def test_single_temperature_dip_is_ignored(self):
        self.push(temp="27.0")
        self.push(temp="2.0")
        self.assertEqual(self.ams.temperature, 27.0)

    def test_single_humidity_dip_is_ignored(self):
        self.push(humidity_raw="15")
        self.assertFalse(self.push(humidity_raw="3"))
        self.assertEqual(self.ams.humidity, 15)
        self.push(humidity_raw="15")
        self.assertEqual(self.ams.humidity, 15)

    def test_confirmed_jump_is_accepted_on_second_reading(self):
        self.push(temp="25.0", humidity_raw="40")
        self.push(temp="45.0", humidity_raw="20")
        self.assertEqual(self.ams.temperature, 25.0)
        self.assertEqual(self.ams.humidity, 40)
        self.assertTrue(self.push(temp="45.5", humidity_raw="19"))
        self.assertEqual(self.ams.temperature, 45.5)
        self.assertEqual(self.ams.humidity, 19)

    def test_two_different_spikes_in_a_row_are_both_ignored(self):
        self.push(temp="28.0")
        self.push(temp="88.0")
        self.push(temp="2.0")
        self.assertEqual(self.ams.temperature, 28.0)

    def test_filter_is_per_ams_unit(self):
        self.device.ams.print_update({"ams": {"ams": [
            {"id": "0", "temp": "25.0", "tray": []},
            {"id": "1", "temp": "50.0", "tray": []},
        ]}})
        self.assertEqual(self.device.ams.data[0].temperature, 25.0)
        self.assertEqual(self.device.ams.data[1].temperature, 50.0)


if __name__ == "__main__":
    unittest.main()
