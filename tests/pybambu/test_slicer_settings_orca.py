import unittest
from unittest.mock import MagicMock

from pybambu.models import SlicerSettings
from pybambu.orca_cloud import OrcaCloudAuthError, OrcaCloudError

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


class TestSlicerSettingsOrcaCloud(unittest.TestCase):
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

        client.callback.assert_called_once_with("event_orca_cloud_authentication_failed")
        self.assertIn("PBAMBU", settings.filaments)

    def test_orca_outage_is_not_reported_as_auth_failure(self):
        client = _client(orca_error=OrcaCloudError("503"))
        settings = SlicerSettings(client)

        settings.update()

        client.callback.assert_not_called()
        self.assertEqual(settings.filaments, {})

    def test_bambu_only_behaviour_is_unchanged(self):
        client = _client(bambu_token="tok", bambu_settings=BAMBU_SETTINGS)
        settings = SlicerSettings(client)

        settings.update()

        self.assertEqual(settings.filaments["PBAMBU"].name, "Bambu PETG")
        self.assertEqual(settings.filaments["PBAMBU"].nozzle_temperature_range_high, 260)


if __name__ == "__main__":
    unittest.main()
