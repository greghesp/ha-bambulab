import unittest
from unittest.mock import MagicMock

from pybambu.const import Features
from pybambu.models import AMSList, ExternalSpool, Extruder


class TestExternalSpoolBlankPayload(unittest.TestCase):
    """The holder has no sensor, so a full payload with blank filament fields is how the
    printer reports that nothing is configured on it (#2097)."""

    BLANK = {
        "id": "254",
        "tag_uid": "",
        "tray_info_idx": "",
        "tray_type": "",
        "tray_sub_brands": "",
        "tray_color": "",
        "tray_weight": "0",
        "state": 8,
    }

    def setUp(self):
        self.client = MagicMock()
        self.client.slicer_settings.custom_filaments = {}
        self.client._device.supports_feature.return_value = False
        self.spool = ExternalSpool(self.client, 0)

    def test_blank_payload_reads_as_empty_not_unknown(self):
        self.spool.print_update({"vt_tray": self.BLANK})

        self.assertTrue(self.spool.empty)
        self.assertFalse(self.spool.unknown)
        self.assertEqual(self.spool.name, "Empty")
        self.assertEqual(self.spool.type, "Empty")

    def test_configured_spool_still_reads_as_loaded(self):
        self.spool.print_update({"vt_tray": {
            **self.BLANK,
            "tray_info_idx": "GFA00",
            "tray_type": "PLA",
        }})

        self.assertFalse(self.spool.empty)
        self.assertEqual(self.spool.type, "PLA")

    def test_type_without_profile_is_still_loaded(self):
        self.spool.print_update({"vt_tray": {**self.BLANK, "tray_type": "PETG"}})

        self.assertFalse(self.spool.empty)
        self.assertEqual(self.spool.name, "PETG")


class TestExternalSpoolInactive(unittest.TestCase):
    """A loaded external spool that isn't feeding is still loaded (#2239)."""

    def setUp(self):
        self.client = MagicMock()
        self.client.slicer_settings.custom_filaments = {}
        self.client._device.supports_feature.return_value = True
        self.spool = ExternalSpool(self.client, 0)
        self.spool.print_update({"vt_tray": {
            "id": "254",
            "tray_info_idx": "GFG00",
            "tray_type": "PETG",
            "tray_color": "001489FF",
        }})

    def test_inactive_spool_is_not_empty(self):
        # An AMS tray is feeding
        self.client._device.ams.active_ams_index = 0
        self.client._device.ams.active_tray_index = 2

        self.assertFalse(self.spool.active)
        self.assertFalse(self.spool.empty)
        self.assertEqual(self.spool.type, "PETG")

    def test_active_spool_is_not_empty(self):
        self.client._device.ams.active_ams_index = 255
        self.client._device.ams.active_tray_index = 0

        self.assertTrue(self.spool.active)
        self.assertFalse(self.spool.empty)


class TestExternalSpoolDualNozzleWithoutAms(unittest.TestCase):
    """An IDEX/dual-nozzle printer (X2D, H2D) with no AMS feeds each nozzle from its own
    external spool. Only the spool feeding the active nozzle is active (#2181)."""

    # Extruder "snow" is unit << 8 | tray. Unit 255 is external spool 0, 254 external spool 1,
    # tray 0xFF means nothing loaded.
    RIGHT_EXT_LOADED = 0xFF00
    LEFT_EXT_LOADED = 0xFE00
    NOTHING_LOADED = 0xFFFF

    def setUp(self):
        self.client = MagicMock()
        self.client.slicer_settings.custom_filaments = {}
        device = self.client._device
        device.extruder = Extruder(self.client)
        device.ams = AMSList(self.client)
        device.external_spool = [ExternalSpool(self.client, 0), ExternalSpool(self.client, 1)]
        device.supports_feature.side_effect = lambda feature: {
            Features.AMS: len(device.ams.data) != 0,
            Features.DUAL_NOZZLES: True,
        }.get(feature, False)

    def _push(self, active_index: int, right_snow: int, left_snow: int):
        data = {"device": {"extruder": {
            "state": (active_index << 4) | 2,
            "info": [
                {"id": 0, "snow": right_snow},
                {"id": 1, "snow": left_snow},
            ],
        }}}
        self.client._device.extruder.print_update(data)
        self.client._device.ams.print_update(data)

    def test_right_nozzle_printing_activates_only_first_spool(self):
        self._push(0, self.RIGHT_EXT_LOADED, self.LEFT_EXT_LOADED)
        spools = self.client._device.external_spool

        self.assertTrue(spools[0].active)
        self.assertFalse(spools[1].active)
        self.assertIs(self.client._device.ams.active_tray, spools[0])

    def test_switching_to_left_nozzle_moves_active_spool(self):
        self._push(0, self.RIGHT_EXT_LOADED, self.LEFT_EXT_LOADED)
        self._push(1, self.RIGHT_EXT_LOADED, self.LEFT_EXT_LOADED)
        spools = self.client._device.external_spool

        self.assertFalse(spools[0].active)
        self.assertTrue(spools[1].active)
        self.assertIs(self.client._device.ams.active_tray, spools[1])

    def test_nothing_loaded_leaves_both_spools_inactive(self):
        self._push(0, self.NOTHING_LOADED, self.NOTHING_LOADED)
        spools = self.client._device.external_spool

        self.assertFalse(spools[0].active)
        self.assertFalse(spools[1].active)
        self.assertIsNone(self.client._device.ams.active_tray)


class TestExternalSpoolSingleNozzleWithoutAms(unittest.TestCase):
    """Single-nozzle printers without an AMS only have the one spool, so it stays active."""

    def test_only_spool_is_active(self):
        client = MagicMock()
        client.slicer_settings.custom_filaments = {}
        client._device.supports_feature.return_value = False

        self.assertTrue(ExternalSpool(client, 0).active)
