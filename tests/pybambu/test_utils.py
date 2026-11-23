import asyncio
import socket
import unittest
from unittest.mock import AsyncMock, patch

from pybambu.utils import (
    async_resolve_ipv4,
    fan_percentage,
    get_authenticated_rtsp_url,
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

    def test_bytes_url_is_decoded(self):
        self.assertEqual(
            get_authenticated_rtsp_url(
                b"rtsps://192.0.2.20:322/streaming/live/1", "192.0.2.10", "12345678"
            ),
            "rtsps://bblp:12345678@192.0.2.10:322/streaming/live/1",
        )

    def test_bytearray_url_is_decoded(self):
        """bytearray must not reach urlparse, which then returns bytes netlocs (#2115)."""
        self.assertEqual(
            get_authenticated_rtsp_url(
                bytearray(b"rtsps://192.0.2.20:322/streaming/live/1"),
                "192.0.2.10",
                "12345678",
            ),
            "rtsps://bblp:12345678@192.0.2.10:322/streaming/live/1",
        )

    def test_undecodable_url_has_no_stream_url(self):
        self.assertIsNone(
            get_authenticated_rtsp_url(bytearray([0xFF, 0xFE]), "192.0.2.10", "12345678")
        )

    def test_invalid_scheme_is_rejected(self):
        self.assertIsNone(
            get_authenticated_rtsp_url(
                "https://192.0.2.20/live", "", "12345678"
            )
        )


class TestResolveIpv4(unittest.IsolatedAsyncioTestCase):
    """The camera URL handed to go2rtc needs an address, not a name (#1798)."""

    def _patch_getaddrinfo(self, **kwargs):
        return patch.object(
            asyncio.get_running_loop(), "getaddrinfo", AsyncMock(**kwargs)
        )

    async def test_hostname_is_resolved(self):
        result = [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("192.0.2.10", 0))]
        with self._patch_getaddrinfo(return_value=result) as getaddrinfo:
            self.assertEqual(await async_resolve_ipv4("x1c.example"), "192.0.2.10")
        # go2rtc can't parse IPv6 hosts, so only IPv4 is any use.
        self.assertEqual(getaddrinfo.call_args.kwargs["family"], socket.AF_INET)

    async def test_addresses_and_empty_host_are_not_looked_up(self):
        with self._patch_getaddrinfo() as getaddrinfo:
            for host in ("192.0.2.10", "2001:db8::1", ""):
                self.assertEqual(await async_resolve_ipv4(host), host)
        getaddrinfo.assert_not_called()

    async def test_unresolvable_name_is_returned_unchanged(self):
        for error in (socket.gaierror(), UnicodeError()):
            with self._patch_getaddrinfo(side_effect=error):
                self.assertEqual(await async_resolve_ipv4("x1c.example"), "x1c.example")

    async def test_no_ipv4_address_returns_name_unchanged(self):
        with self._patch_getaddrinfo(return_value=[]):
            self.assertEqual(await async_resolve_ipv4("x1c.example"), "x1c.example")

    async def test_slow_lookup_returns_name_unchanged(self):
        async def never_answers(*args, **kwargs):
            await asyncio.sleep(60)

        with (
            self._patch_getaddrinfo(side_effect=never_answers),
            patch("pybambu.utils.HOST_LOOKUP_TIMEOUT", 0.01),
        ):
            self.assertEqual(await async_resolve_ipv4("x1c.example"), "x1c.example")


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
