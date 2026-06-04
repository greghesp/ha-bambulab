import json
import os
import sys
import unittest

# Add the parent directory to the Python path to find pybambu
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from pybambu.models import FilamentInventory


class TestFilamentInventory(unittest.TestCase):
    def setUp(self):
        # MUST open UTF-8: the fixture contains emoji in a note field, and the
        # default encoding on Windows (cp1252) would raise UnicodeDecodeError.
        with open(os.path.join(os.path.dirname(__file__), 'filament_v2.json'), 'r', encoding='utf-8') as f:
            self.data = json.load(f)
        self.inventory = FilamentInventory()

    def test_empty_payload(self):
        self.inventory.update({})
        self.assertEqual(self.inventory.total_spool_count, 0)
        self.assertEqual(self.inventory.total_remaining_g, 0)
        self.assertEqual(self.inventory.spools, [])
        self.assertEqual(self.inventory.groups, [])

    def test_none_payload(self):
        # A failed cloud fetch returns None; the model must treat it as empty.
        self.inventory.update(None)
        self.assertEqual(self.inventory.total_spool_count, 0)

    def test_spool_count_and_total(self):
        self.inventory.update(self.data)
        self.assertEqual(self.inventory.total_spool_count, 4)
        # 1000 (TPU) + 931 + 86 + 0
        self.assertEqual(self.inventory.total_remaining_g, 2017)

    def test_spool_fields(self):
        self.inventory.update(self.data)
        spool = next(s for s in self.inventory.spools if s["id"] == 1001)
        self.assertEqual(spool["vendor"], "Bambu Lab")
        self.assertEqual(spool["name"], "PLA Basic")
        self.assertEqual(spool["type"], "PLA")
        self.assertEqual(spool["filament_id"], "GFA00")
        self.assertEqual(spool["color"], "#FFFFFFFF")
        self.assertEqual(spool["colors"], ["#FFFFFFFF"])
        self.assertEqual(spool["color_type"], 2)
        self.assertEqual(spool["remaining_g"], 931)
        self.assertEqual(spool["total_g"], 1000)
        self.assertEqual(spool["remaining_pct"], 93)
        self.assertEqual(spool["tray_id_name"], "A00-W01")
        self.assertEqual(spool["rfid"], "AAAA0000000000000000000000000001")
        self.assertEqual(spool["updated_at"], 1780424283)
        self.assertEqual(spool["note"], "")

    def test_missing_optional_field_defaults(self):
        # Spool 1003 has no trayIdName; parser must default it, not crash.
        self.inventory.update(self.data)
        spool = next(s for s in self.inventory.spools if s["id"] == 1003)
        self.assertEqual(spool["tray_id_name"], "")

    def test_zero_weight_pct(self):
        self.inventory.update(self.data)
        spool = next(s for s in self.inventory.spools if s["id"] == 1003)
        self.assertEqual(spool["remaining_g"], 0)
        self.assertEqual(spool["remaining_pct"], 0)

    def test_multicolor(self):
        self.inventory.update(self.data)
        spool = next(s for s in self.inventory.spools if s["id"] == 1003)
        self.assertEqual(spool["color_type"], 0)
        self.assertEqual(spool["colors"], ["#F772A4FF", "#00918BFF"])

    def test_manual_spool_null_colors(self):
        # A manually-added spool sends "colors": null (explicit JSON null, key
        # present). The parser must normalise this to [] and NOT leave None,
        # otherwise the HA attribute would contain a null and templates break.
        self.inventory.update(self.data)
        spool = next(s for s in self.inventory.spools if s["id"] == 1000)
        self.assertEqual(spool["colors"], [])
        self.assertEqual(spool["color"], "#77167E")
        self.assertEqual(spool["rfid"], "")
        self.assertEqual(spool["tray_id_name"], "")

    def test_freeform_note_with_special_chars(self):
        # The note field is freeform user text. Emoji, quotes, braces, commas,
        # and semicolons must round-trip intact (it is just a JSON string value;
        # json.loads decodes it fully - this guards against any future
        # hand-rolled parsing or encoding mistakes).
        self.inventory.update(self.data)
        spool = next(s for s in self.inventory.spools if s["id"] == 1000)
        self.assertEqual(spool["note"], "😂😂😂{ } , ; ' ' \"and\"💀")

    def test_all_fields_null_does_not_crash(self):
        # Defensive: any field could come back as explicit JSON null. The parser
        # must coerce every field to a sane typed default and never raise or
        # leak None into string/int fields. id is allowed to stay None (it is an
        # opaque identifier, not rendered/aggregated).
        payload = {"hits": [{
            "id": None, "RFID": None, "filamentVendor": None,
            "filamentName": None, "filamentType": None, "filamentId": None,
            "color": None, "colors": None, "colorType": None,
            "netWeight": None, "totalNetWeight": None, "trayIdName": None,
            "note": None, "updatedAt": None,
        }]}
        self.inventory.update(payload)
        self.assertEqual(self.inventory.total_spool_count, 1)
        spool = self.inventory.spools[0]
        self.assertEqual(spool["rfid"], "")
        self.assertEqual(spool["vendor"], "")
        self.assertEqual(spool["name"], "")
        self.assertEqual(spool["type"], "")
        self.assertEqual(spool["filament_id"], "")
        self.assertEqual(spool["color"], "")
        self.assertEqual(spool["colors"], [])
        self.assertEqual(spool["color_type"], 0)
        self.assertEqual(spool["remaining_g"], 0)
        self.assertEqual(spool["total_g"], 0)
        self.assertEqual(spool["remaining_pct"], 0)
        self.assertEqual(spool["tray_id_name"], "")
        self.assertEqual(spool["note"], "")
        self.assertEqual(spool["updated_at"], 0)
        # An all-null spool still groups (under the empty vendor/name key).
        self.assertEqual(self.inventory.total_remaining_g, 0)

    def test_hits_with_non_dict_entry_is_skipped_safely(self):
        # Be tolerant of a malformed entry (e.g. null in the hits array)
        # without aborting the whole inventory.
        payload = {"hits": [None, {"id": 5, "filamentName": "PLA", "netWeight": 50, "totalNetWeight": 100}]}
        self.inventory.update(payload)
        self.assertEqual(self.inventory.total_spool_count, 1)
        self.assertEqual(self.inventory.spools[0]["id"], 5)

    def test_unknown_future_fields_are_ignored(self):
        # Forward-compatibility contract: if Bambu adds new fields to the API,
        # the parser must ignore them gracefully (no crash) and the output spool
        # dict must contain exactly our known, fixed set of keys.
        payload = {"hits": [{
            "id": 9, "filamentVendor": "Bambu Lab", "filamentName": "PLA Basic",
            "filamentType": "PLA", "netWeight": 500, "totalNetWeight": 1000,
            # Hypothetical future additions:
            "spoolDiameter": 1.75, "purchaseUrl": "https://example.com",
            "nestedFutureObject": {"a": 1, "b": [2, 3]},
        }]}
        self.inventory.update(payload)
        self.assertEqual(self.inventory.total_spool_count, 1)
        spool = self.inventory.spools[0]
        self.assertEqual(
            set(spool.keys()),
            {"id", "rfid", "vendor", "name", "type", "filament_id", "color",
             "colors", "color_type", "remaining_g", "total_g", "remaining_pct",
             "tray_id_name", "note", "updated_at"},
        )
        self.assertNotIn("spoolDiameter", spool)
        self.assertEqual(spool["remaining_g"], 500)

    def test_grouping(self):
        self.inventory.update(self.data)
        # Groups keyed by vendor + name. "Bambu Lab PLA Basic" has 2 spools.
        basic = next(g for g in self.inventory.groups if g["name"] == "PLA Basic")
        self.assertEqual(basic["vendor"], "Bambu Lab")
        self.assertEqual(basic["count"], 2)
        self.assertEqual(basic["total_remaining_g"], 1017)  # 931 + 86
        self.assertEqual(len(basic["spools"]), 2)

        silk = next(g for g in self.inventory.groups if g["name"] == "PLA Silk")
        self.assertEqual(silk["count"], 1)
        self.assertEqual(silk["total_remaining_g"], 0)

        # The manual TPU spool forms its own Generic group.
        tpu = next(g for g in self.inventory.groups if g["name"] == "TPU")
        self.assertEqual(tpu["vendor"], "Generic")
        self.assertEqual(tpu["count"], 1)
        self.assertEqual(tpu["total_remaining_g"], 1000)


if __name__ == '__main__':
    unittest.main()
