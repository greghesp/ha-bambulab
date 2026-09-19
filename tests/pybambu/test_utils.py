import unittest

from pybambu.utils import (
    fan_percentage,
    get_authenticated_rtsp_url,
    get_display_filament_type,
)


class TestAuthenticatedRTSPUrl(unittest.TestCase):
    def test_disabled_liveview_has_no_stream_url(self):
        self.assertIsNone(
            get_authenticated_rtsp_url("disable", "192.0.2.10", "12345678")
        )

    def test_valid_url_uses_configured_host_and_escaped_access_code(self):
        self.assertEqual(
            get_authenticated_rtsp_url(
                "rtsps://192.0.2.20:322/streaming/live/1",
                "192.0.2.10",
                "code@word",
            ),
            "rtsps://bblp:code%40word@192.0.2.10:322/streaming/live/1",
        )

    def test_invalid_scheme_is_rejected(self):
        self.assertIsNone(
            get_authenticated_rtsp_url(
                "https://192.0.2.20/live", "", "12345678"
            )
        )


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


class TestDisplayFilamentType(unittest.TestCase):
    """Bambu Studio display remapping for support materials."""

    def test_gfs00_or_pla_s_is_sup_pla(self):
        self.assertEqual(get_display_filament_type("GFS00", "PLA"), "Sup.PLA")
        self.assertEqual(get_display_filament_type("", "PLA-S"), "Sup.PLA")
        self.assertEqual(get_display_filament_type("GFS00", "PLA-S"), "Sup.PLA")

    def test_gfs01_or_pa_s_is_sup_pa(self):
        self.assertEqual(get_display_filament_type("GFS01", "PA"), "Sup.PA")
        self.assertEqual(get_display_filament_type("", "PA-S"), "Sup.PA")

    def test_gfs06_or_abs_s_is_sup_abs(self):
        self.assertEqual(get_display_filament_type("GFS06", "ABS"), "Sup.ABS")
        self.assertEqual(get_display_filament_type("", "ABS-S"), "Sup.ABS")

    def test_regular_types_are_unchanged(self):
        self.assertEqual(get_display_filament_type("GFA00", "PLA"), "PLA")
        self.assertEqual(get_display_filament_type("GFS05", "PLA"), "PLA")
        self.assertEqual(get_display_filament_type("", ""), "")


if __name__ == '__main__':
    unittest.main()
