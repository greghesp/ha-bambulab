import unittest
from unittest.mock import MagicMock

from pybambu.models import Device


def _tray(tray_id, **fields):
    return {"id": str(tray_id), **fields}


def _ams(ams_id, trays):
    return {"id": str(ams_id), "humidity": "4", "temp": "25.0", "tray": trays}


def _ams_3h(ams_id=32):
    # Shape from the H3C diagnostics in #2305: 9 trays split over two drying zones.
    zones = [{"zone_id": 0, "zone_slots": [5, 7]},
             {"zone_id": 1, "zone_slots": [0, 1, 2, 3, 4, 6, 8]}]
    trays = [_tray(t, **TestTrayExistBits.TAGGED) for t in range(9)]
    return {**_ams(ams_id, trays), "zone_info": zones}


class TestTrayExistBits(unittest.TestCase):
    """tray_exist_bits reports physical spool presence even on firmware (e.g. P1S) that
    omits the per-tray ``state`` field. A spool without an RFID tag has no filament
    metadata, so ``empty`` alone cannot tell it apart from an empty slot (#2205)."""

    UNTAGGED = {"tray_info_idx": "", "tray_type": "", "tray_color": "00000000"}
    TAGGED = {"tray_info_idx": "GFA00", "tray_type": "PLA", "tray_color": "FFFFFFFF"}

    def setUp(self):
        self.client = MagicMock()
        self.client.slicer_settings.custom_filaments = {}
        self.client.slicer_settings.filaments = {}
        self.device = Device(self.client)
        self.client._device = self.device

    def push(self, ams_list, **ams_fields):
        self.device.print_update({
            "command": "push_status",
            "msg": 0,
            "ams": {"ams": ams_list, "tray_now": "255", "tray_tar": "255", **ams_fields},
        })

    def trays(self, ams_index):
        return self.device.ams.data[ams_index].tray

    def test_exists_is_none_when_not_reported(self):
        self.push([_ams(0, [_tray(i, **self.UNTAGGED) for i in range(4)])])
        self.assertEqual([t.exists for t in self.trays(0)], [None] * 4)

    def test_untagged_spool_is_empty_but_exists(self):
        # P1S pushall: all four slots occupied, slot 2 holds an untagged third-party spool.
        trays = [_tray(0, **self.TAGGED), _tray(1, **self.UNTAGGED),
                 _tray(2, **self.TAGGED), _tray(3, **self.TAGGED)]
        self.push([_ams(0, trays)], tray_exist_bits="f", tray_is_bbl_bits="d")

        tray = self.trays(0)[1]
        self.assertTrue(tray.empty)
        self.assertIs(tray.exists, True)

    def test_empty_slot_does_not_exist(self):
        self.push([_ams(0, [_tray(i, **self.UNTAGGED) for i in range(4)])], tray_exist_bits="5")
        self.assertEqual([t.exists for t in self.trays(0)], [True, False, True, False])

    def test_multiple_ams_units_use_four_bits_each(self):
        # Layout taken from MOCK-X1CMULTIAMS: AMS 2 tray 0 is empty, the AMS HT (id 128)
        # occupies bit 16 and is left untouched.
        units = [_ams(i, [_tray(t, **self.TAGGED) for t in range(4)]) for i in range(3)]
        units.append(_ams(128, [_tray(0, **self.TAGGED)]))
        self.push(units, tray_exist_bits="10eff")

        self.assertEqual([t.exists for t in self.trays(0)], [True] * 4)
        self.assertEqual([t.exists for t in self.trays(1)], [True] * 4)
        self.assertEqual([t.exists for t in self.trays(2)], [False, True, True, True])
        self.assertIsNone(self.trays(128)[0].exists)

    def test_ams_3h_presence_is_left_unknown(self):
        # H3C + AMS 3H (#2305): the 9-slot unit reports id 32 and its trays sit at bit 28
        # of the mask, not at 32 * 4. Without a known layout, presence must stay unknown
        # rather than read every loaded slot as missing.
        self.push([_ams_3h()], tray_exist_bits="17e0000000")

        self.assertEqual(len(self.trays(32)), 9)
        self.assertEqual([t.exists for t in self.trays(32)], [None] * 9)

    def test_four_slot_ams_still_decoded_next_to_ams_3h(self):
        units = [_ams(0, [_tray(t, **self.TAGGED) for t in range(4)]),
                 _ams_3h()]
        self.push(units, tray_exist_bits="17e0000005")

        self.assertEqual([t.exists for t in self.trays(0)], [True, False, True, False])
        self.assertEqual([t.exists for t in self.trays(32)], [None] * 9)

    def test_presence_updates_when_spool_removed(self):
        self.push([_ams(0, [_tray(i, **self.UNTAGGED) for i in range(4)])], tray_exist_bits="f")
        self.assertIs(self.trays(0)[1].exists, True)
        self.push([], tray_exist_bits="d")
        self.assertIs(self.trays(0)[1].exists, False)

    def test_malformed_bits_are_ignored(self):
        self.push([_ams(0, [_tray(i, **self.UNTAGGED) for i in range(4)])], tray_exist_bits="zz")
        self.assertEqual([t.exists for t in self.trays(0)], [None] * 4)


if __name__ == "__main__":
    unittest.main()
