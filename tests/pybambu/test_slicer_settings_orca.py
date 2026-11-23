import unittest
from unittest.mock import MagicMock, patch

from pybambu.bambu_cloud import CloudAuthError
from pybambu.models import SlicerSettings
from pybambu.orca_cloud import OrcaCloud, OrcaCloudAuthError, OrcaCloudError

ORCA_FILAMENT = {
    "name": "Orca PLA",
    "filament_vendor": "Orca",
    "filament_type": "PLA",
    "nozzle_temperature_range_low": 190,
    "nozzle_temperature_range_high": 230,
}

BAMBU_SETTINGS = {"filament": {"private": [{
    "name": "Bambu PETG @Bambu Lab P1S 0.4 nozzle",
    "filament_id": "PBAMBU",
    "filament_vendor": "Bambu",
    "filament_type": "PETG",
    "nozzle_temperature": [220, 260],
}]}}


def _client(bambu_token="", orca_filaments=None, orca_error=None, bambu_settings=None):
    client = MagicMock()
    client._device.info.device_type = "P1S"
    client._serial = "SERIAL"
    client.bambu_cloud.auth_token = bambu_token
    client.bambu_cloud.get_slicer_settings.return_value = bambu_settings
    if orca_filaments is None and orca_error is None:
        client.orca_cloud = None
    else:
        client.orca_cloud = MagicMock()
        if orca_error is not None:
            client.orca_cloud.get_filament_profiles.side_effect = orca_error
        else:
            client.orca_cloud.get_filament_profiles.return_value = orca_filaments
    return client


def _events(client):
    return [call.args[0] for call in client.callback.call_args_list]


class TestSlicerSettingsOrcaCloud(unittest.TestCase):
    def setUp(self):
        # Bambu Cloud loading staggers its first request and backs off between retries.
        patcher = patch("pybambu.models.time.sleep")
        self.sleep = patcher.start()
        self.addCleanup(patcher.stop)

    def test_lan_only_printer_loads_orca_filaments(self):
        client = _client(orca_filaments={"PORCA": ORCA_FILAMENT})
        settings = SlicerSettings(client)

        settings.update()

        info = settings.filaments["PORCA"]
        self.assertEqual(info.name, "Orca PLA")
        self.assertEqual(info.filament_vendor, "Orca")
        self.assertEqual(info.filament_type, "PLA")
        self.assertEqual(info.nozzle_temperature_range_low, 190)
        self.assertEqual(info.nozzle_temperature_range_high, 230)
        client.bambu_cloud.get_slicer_settings.assert_not_called()

    def test_both_clouds_are_combined_and_orca_wins_on_conflict(self):
        newer = dict(ORCA_FILAMENT, name="Renamed in Orca")
        client = _client(bambu_token="tok", bambu_settings=BAMBU_SETTINGS,
                         orca_filaments={"PORCA": ORCA_FILAMENT, "PBAMBU": newer})
        settings = SlicerSettings(client)

        settings.update()

        self.assertEqual(set(settings.filaments), {"PORCA", "PBAMBU"})
        self.assertEqual(settings.filaments["PBAMBU"].name, "Renamed in Orca")

    def test_orca_auth_failure_raises_orca_event_and_keeps_bambu_filaments(self):
        client = _client(bambu_token="tok", bambu_settings=BAMBU_SETTINGS,
                         orca_error=OrcaCloudAuthError("rejected"))
        settings = SlicerSettings(client)

        settings.update()

        self.assertCountEqual(_events(client), [
            "event_orca_cloud_authentication_failed",
            "event_printer_bambu_authentication_succeeded",
        ])
        self.assertIn("PBAMBU", settings.filaments)

    def test_orca_outage_is_not_reported_as_auth_failure(self):
        client = _client(orca_error=OrcaCloudError("503"))
        settings = SlicerSettings(client)

        settings.update()

        client.callback.assert_not_called()
        self.assertEqual(settings.filaments, {})

    def test_orca_filaments_load_when_bambu_rejects_the_token(self):
        client = _client(bambu_token="tok", orca_filaments={"PORCA": ORCA_FILAMENT})
        client.bambu_cloud.get_slicer_settings.side_effect = CloudAuthError(401)
        settings = SlicerSettings(client)

        settings.update()

        self.assertEqual(_events(client), ["event_printer_bambu_authentication_failed"])
        self.assertEqual(set(settings.filaments), {"PORCA"})

    def test_orca_filaments_do_not_wait_for_bambu_retries(self):
        client = _client(bambu_token="tok", orca_filaments={"PORCA": ORCA_FILAMENT})
        settings = SlicerSettings(client)
        seen_while_waiting = []
        self.sleep.side_effect = lambda _: seen_while_waiting.append(set(settings.filaments))

        settings.update()

        self.assertEqual(client.bambu_cloud.get_slicer_settings.call_count, SlicerSettings.MAX_ATTEMPTS)
        self.assertEqual(seen_while_waiting, [{"PORCA"}] * SlicerSettings.MAX_ATTEMPTS)
        self.assertEqual(set(settings.filaments), {"PORCA"})

    def test_unexpected_orca_response_does_not_block_bambu(self):
        # A sign-in response that is JSON but not an object, through the real client.
        session = MagicMock()
        session.post.return_value.status_code = 200
        session.post.return_value.json.return_value = ["unexpected"]
        client = _client(bambu_token="tok", bambu_settings=BAMBU_SETTINGS)
        client.orca_cloud = OrcaCloud("token", session=session)
        settings = SlicerSettings(client)

        settings.update()

        self.assertEqual(_events(client), ["event_printer_bambu_authentication_succeeded"])
        self.assertEqual(set(settings.filaments), {"PBAMBU"})

    def test_bambu_only_behaviour_is_unchanged(self):
        client = _client(bambu_token="tok", bambu_settings=BAMBU_SETTINGS)
        settings = SlicerSettings(client)

        settings.update()

        self.assertEqual(settings.filaments["PBAMBU"].name, "Bambu PETG")
        self.assertEqual(settings.filaments["PBAMBU"].nozzle_temperature_range_high, 260)


if __name__ == "__main__":
    unittest.main()
