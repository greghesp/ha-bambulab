import unittest

from pybambu.utils import fan_percentage


class TestFanPercentage(unittest.TestCase):
    """Regression tests for the fan_percentage round->ceil fix.

    The printer reports an instantaneous raw 0-15 PWM value that
    oscillates between adjacent integers when serving a target whose
    exact 0-15 representation isn't an integer. round() picks
    different buckets either side of the midpoint, so HA fan-speed
    entities flip between adjacent 10% values on every push.
    """

    def test_zero_speed_returns_zero(self):
        self.assertEqual(fan_percentage(0), 0)
        self.assertEqual(fan_percentage("0"), 0)
        self.assertEqual(fan_percentage(None), 0)

    def test_full_speed_returns_one_hundred(self):
        self.assertEqual(fan_percentage(15), 100)
        self.assertEqual(fan_percentage("15"), 100)

    def test_oscillation_between_raw_2_and_3_pins_to_same_bucket(self):
        # Live capture: with user setting at 20% the printer alternates
        # big_fan2_speed between '2' and '3' across consecutive print
        # pushes. Both must round to the same 10% bucket so HA doesn't
        # flip on every message.
        speed_for_raw_2 = fan_percentage(2)
        speed_for_raw_3 = fan_percentage(3)
        self.assertEqual(
            speed_for_raw_2, speed_for_raw_3,
            f"raw 2 -> {speed_for_raw_2} but raw 3 -> {speed_for_raw_3}; "
            "values disagree => HA will flip on every MQTT push"
        )

    def test_low_speeds_round_up_to_nearest_ten(self):
        # raw 1 -> 6.67%, raw 2 -> 13.33%, raw 4 -> 26.67%
        # All should round up so the reported value is never lower
        # than the actual fan output.
        self.assertEqual(fan_percentage(1), 10)
        self.assertEqual(fan_percentage(2), 20)
        self.assertEqual(fan_percentage(4), 30)
        self.assertEqual(fan_percentage(5), 40)


if __name__ == '__main__':
    unittest.main()
