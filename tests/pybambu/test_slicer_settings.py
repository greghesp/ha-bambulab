import unittest
from unittest.mock import MagicMock, patch

from pybambu.bambu_cloud import BambuCloud, CloudAuthError, CloudflareError
from pybambu.models import SlicerSettings


class TestGetSlicerSettings(unittest.TestCase):
    """Only a genuine auth rejection may surface as an auth failure (#2304).

    A rate limit, server error or network failure used to be indistinguishable
    from a bad token, which raised a false "Authentication failed" repair."""

    def setUp(self):
        self.cloud = BambuCloud("", "", "", "token")

    def test_success_returns_json(self):
        response = MagicMock()
        response.json.return_value = {"filament": {}}
        with patch.object(self.cloud, "_get", return_value=response):
            self.assertEqual(self.cloud.get_slicer_settings(), {"filament": {}})

    def test_401_raises_cloud_auth_error(self):
        with patch.object(self.cloud, "_get", side_effect=PermissionError(401, "unauthorized")):
            with self.assertRaises(CloudAuthError):
                self.cloud.get_slicer_settings()

    def test_403_raises_cloud_auth_error(self):
        with patch.object(self.cloud, "_get", side_effect=PermissionError(403, "forbidden")):
            with self.assertRaises(CloudAuthError):
                self.cloud.get_slicer_settings()

    def test_429_returns_none(self):
        with patch.object(self.cloud, "_get", side_effect=PermissionError(429, "too many requests")):
            self.assertIsNone(self.cloud.get_slicer_settings())

    def test_500_returns_none(self):
        with patch.object(self.cloud, "_get", side_effect=PermissionError(500, "server error")):
            self.assertIsNone(self.cloud.get_slicer_settings())

    def test_cloudflare_block_returns_none(self):
        with patch.object(self.cloud, "_get", side_effect=CloudflareError()):
            self.assertIsNone(self.cloud.get_slicer_settings())

    def test_network_error_returns_none(self):
        with patch.object(self.cloud, "_get", side_effect=TimeoutError("timed out")):
            self.assertIsNone(self.cloud.get_slicer_settings())


def _client(get_slicer_settings):
    client = MagicMock()
    client.bambu_cloud.auth_token = "token"
    client.bambu_cloud.get_slicer_settings.side_effect = get_slicer_settings
    return client


def _events(client):
    return [call.args[0] for call in client.callback.call_args_list]


SETTINGS = {
    "filament": {
        "private": [{
            "filament_id": "P1",
            "name": "My PLA @BBL X1C",
            "filament_vendor": "Acme",
            "filament_type": "PLA",
            "nozzle_temperature": [190, 230],
        }]
    }
}


@patch("pybambu.models.time.sleep")
class TestSlicerSettingsUpdate(unittest.TestCase):

    def test_success_loads_filaments_and_reports_auth_ok(self, sleep):
        client = _client([SETTINGS])
        settings = SlicerSettings(client)
        settings.update()
        self.assertIn("P1", settings.filaments)
        self.assertEqual(settings.filaments["P1"].name, "My PLA")
        self.assertEqual(_events(client), ["event_printer_bambu_authentication_succeeded"])

    def test_auth_rejection_reports_failure_without_retry(self, sleep):
        client = _client(CloudAuthError(401))
        SlicerSettings(client).update()
        self.assertEqual(client.bambu_cloud.get_slicer_settings.call_count, 1)
        self.assertEqual(_events(client), ["event_printer_bambu_authentication_failed"])

    def test_transient_error_is_retried_then_succeeds(self, sleep):
        client = _client([None, None, SETTINGS])
        settings = SlicerSettings(client)
        settings.update()
        self.assertEqual(client.bambu_cloud.get_slicer_settings.call_count, 3)
        self.assertIn("P1", settings.filaments)
        self.assertEqual(_events(client), ["event_printer_bambu_authentication_succeeded"])

    def test_persistent_transient_error_never_reports_auth_failure(self, sleep):
        client = _client(lambda: None)
        SlicerSettings(client).update()
        self.assertEqual(client.bambu_cloud.get_slicer_settings.call_count, SlicerSettings.MAX_ATTEMPTS)
        self.assertNotIn("event_printer_bambu_authentication_failed", _events(client))

    def test_no_token_skips_cloud(self, sleep):
        client = _client([SETTINGS])
        client.bambu_cloud.auth_token = ""
        SlicerSettings(client).update()
        client.bambu_cloud.get_slicer_settings.assert_not_called()
        self.assertEqual(_events(client), [])


@patch("pybambu.models.time.sleep")
class TestCustomFilamentsSurviveRefresh(unittest.TestCase):
    """Every printer reconnect refetches the slicer settings. The filaments already
    loaded must stay usable until a fetch succeeds, or a reconnect during a cloud
    outage loses every custom filament name (#2338)."""

    def setUp(self):
        self.client = _client([SETTINGS])
        self.settings = SlicerSettings(self.client)
        with patch("pybambu.models.time.sleep"):
            self.settings.update()

    def _refresh(self, get_slicer_settings):
        self.client.bambu_cloud.get_slicer_settings.side_effect = get_slicer_settings
        self.settings.update()

    def test_kept_when_refresh_fails(self, sleep):
        self._refresh(lambda: None)
        self.assertIn("P1", self.settings.filaments)

    def test_kept_when_token_is_rejected(self, sleep):
        self._refresh(CloudAuthError(401))
        self.assertIn("P1", self.settings.filaments)

    def test_available_while_refresh_is_retrying(self, sleep):
        seen = []
        sleep.side_effect = lambda _: seen.append("P1" in self.settings.filaments)
        self._refresh([None, SETTINGS])
        self.assertEqual(seen, [True, True])

    def test_kept_when_response_has_no_filament_section(self, sleep):
        self._refresh([{"message": "success"}])
        self.assertIn("P1", self.settings.filaments)

    def test_filament_removed_from_account_is_dropped(self, sleep):
        self._refresh([{"filament": {"private": []}}])
        self.assertEqual(self.settings.filaments, {})

    def test_cleared_when_there_is_no_token(self, sleep):
        self.client.bambu_cloud.auth_token = ""
        self.settings.update()
        self.assertEqual(self.settings.filaments, {})

    def test_refresh_replaces_the_dict_a_reader_is_iterating(self, sleep):
        # Home Assistant iterates filaments on its event loop while this runs on a thread.
        held = self.settings.filaments
        self._refresh([{"filament": {"private": [{**SETTINGS["filament"]["private"][0], "filament_id": "P2"}]}}])
        self.assertEqual(list(held), ["P1"])
        self.assertEqual(list(self.settings.filaments), ["P2"])


if __name__ == "__main__":
    unittest.main()
