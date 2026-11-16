"""AMS 3H slots that the H3C reports as virtual slots (#2253).

The H3C reports a 2.85 mm spool in AMS 3H slot k (zero-based) as `vir_slot`
entry `255 - k`, while the regular AMS tray k stays empty.
"""

import copy
import json
import unittest
from pathlib import Path
from unittest.mock import MagicMock

from pybambu.const import Printers
from pybambu.models import Device

AMS_3H_INDEX = 32
TPU_SLOT = 7
TPU_VIR_SLOT_ID = 255 - TPU_SLOT  # 248

TPU_VIR_SLOT = {
    "id": str(TPU_VIR_SLOT_ID),
    "state": 267,
    "tag_uid": "7E611ABD00000100",
    "tray_type": "TPU",
    "tray_sub_brands": "TPU 75A (2.85mm)",
    "tray_info_idx": "GFU06",
    "tray_color": "E4002BFF",
    "tray_diameter": "2.85",
    "remain": 91,
    "remain_g": 914,
    "tray_weight": "1000",
}


def empty_vir_slot(slot_id: int) -> dict:
    return {"id": str(slot_id), "state": 1}


def vir_slots(*loaded: dict) -> list[dict]:
    """All nine H3C virtual slots (247-255), with the given entries loaded."""
    by_id = {int(entry["id"]): entry for entry in loaded}
    return [by_id.get(slot_id, empty_vir_slot(slot_id)) for slot_id in range(247, 256)]


class TestAms3hVirtualSlot(unittest.TestCase):
    def setUp(self):
        payload = json.loads(Path(__file__).with_name("H3C_AMS3H.json").read_text())
        self.push_status = payload["push_status"]
        self.client = MagicMock()
        self.client._device_type = Printers.H3C
        self.client.slicer_settings.custom_filaments = {}
        self.device = Device(self.client)
        self.client._device = self.device
        self.device.info_update(payload["get_version"])

    def push(self, vir_slot=None, **overrides) -> None:
        status = copy.deepcopy(self.push_status)
        if vir_slot is not None:
            status["vir_slot"] = vir_slot
        status.update(overrides)
        self.device.print_update(status)

    @property
    def tpu_tray(self):
        return self.device.ams.data[AMS_3H_INDEX].tray[TPU_SLOT]

    def test_virtual_slot_filament_is_shown_on_its_ams_3h_slot(self):
        self.push(vir_slot=vir_slots(TPU_VIR_SLOT))

        tray = self.tpu_tray
        self.assertFalse(tray.empty)
        self.assertEqual(tray.type, "TPU")
        self.assertEqual(tray.sub_brands, "TPU 75A (2.85mm)")
        self.assertEqual(tray.idx, "GFU06")
        self.assertEqual(tray.color, "E4002BFF")
        self.assertEqual(tray.tag_uid, "7E611ABD00000100")
        self.assertEqual(tray.filament_diameter, 2.85)
        self.assertEqual(tray.remaining_weight_g, 914)
        self.assertEqual(tray.remain, 91)

    def test_virtual_slot_filament_is_not_reported_as_external_spool(self):
        self.push(vir_slot=vir_slots(TPU_VIR_SLOT))

        self.assertTrue(self.device.external_spool[0].empty)
        self.assertTrue(self.device.external_spool[1].empty)

    def test_regular_tray_delta_does_not_hide_virtual_slot_filament(self):
        self.push(vir_slot=vir_slots(TPU_VIR_SLOT))

        # Incremental AMS update for the regular (empty) tray, without vir_slot.
        self.device.print_update({
            "ams": {"ams": [{"id": str(AMS_3H_INDEX), "tray": [{"id": str(TPU_SLOT), "state": 160}]}]},
        })

        self.assertFalse(self.tpu_tray.empty)
        self.assertEqual(self.tpu_tray.type, "TPU")

    def test_unloading_virtual_slot_empties_the_ams_3h_slot(self):
        self.push(vir_slot=vir_slots(TPU_VIR_SLOT))
        self.push(vir_slot=vir_slots())

        self.assertTrue(self.tpu_tray.empty)
        self.assertEqual(self.tpu_tray.name, "Empty")
        self.assertIsNone(self.tpu_tray.filament_diameter)

    def test_regular_tray_filament_is_unchanged_without_virtual_data(self):
        self.push(vir_slot=vir_slots())

        tray = self.device.ams.data[AMS_3H_INDEX].tray[0]
        self.assertFalse(tray.empty)
        self.assertEqual(tray.type, "PLA")
        self.assertTrue(self.tpu_tray.empty)

    def test_spool_reported_by_the_ams_takes_precedence(self):
        status = copy.deepcopy(self.push_status)
        status["ams"]["ams"][0]["tray"][TPU_SLOT] = dict(
            status["ams"]["ams"][0]["tray"][0], id=str(TPU_SLOT))
        status["vir_slot"] = vir_slots(TPU_VIR_SLOT)
        self.device.print_update(status)

        self.assertFalse(self.tpu_tray.empty)
        self.assertEqual(self.tpu_tray.type, "PLA")

    def test_external_spool_ids_keep_feeding_the_external_spools(self):
        external = dict(TPU_VIR_SLOT, id="255")
        self.push(vir_slot=vir_slots(external))

        self.assertFalse(self.device.external_spool[0].empty)
        self.assertEqual(self.device.external_spool[0].type, "TPU")
        self.assertEqual(self.device.ams.data[AMS_3H_INDEX].tray[0].type, "PLA")

    def test_feeding_from_virtual_slot_resolves_to_ams_3h_slot(self):
        extruder = copy.deepcopy(self.push_status["device"]["extruder"])
        extruder["info"][0]["snow"] = TPU_VIR_SLOT_ID << 8
        extruder["info"][0]["star"] = TPU_VIR_SLOT_ID << 8
        device_info = dict(self.push_status["device"], extruder=extruder)

        self.push(vir_slot=vir_slots(TPU_VIR_SLOT), device=device_info)

        ams = self.device.ams
        self.assertIs(ams.active_tray, self.tpu_tray)
        self.assertEqual(ams.active_ams_index, AMS_3H_INDEX)
        self.assertEqual(ams.active_tray_index, TPU_SLOT)
        self.assertEqual(ams.target_ams_index, AMS_3H_INDEX)
        self.assertTrue(self.tpu_tray.active)
        self.assertTrue(ams.data[AMS_3H_INDEX].active)
        self.assertFalse(self.device.external_spool[0].active)

    def test_unknown_virtual_slot_without_ams_3h_does_not_crash(self):
        device = Device(self.client)
        self.client._device = device
        device.print_update({
            "device": {"extruder": {"info": [{"id": 0, "snow": TPU_VIR_SLOT_ID << 8}]}},
            "vir_slot": vir_slots(TPU_VIR_SLOT),
        })

        self.assertIsNone(device.ams.active_tray)


if __name__ == "__main__":
    unittest.main()
