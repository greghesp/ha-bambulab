import io
import json
import os
import tempfile
import unittest
from zipfile import ZipFile

from pybambu.learned_filaments import (
    LearnedFilamentStore,
    get_learned_filament_store,
    parse_project_settings,
)
from pybambu.models import SlicerSettings
from pybambu.utils import get_filament_name


def _project_settings(**overrides) -> bytes:
    settings = {
        "filament_ids": ["P9816594", "GFA00"],
        "filament_settings_id": [
            "ELEGOO PLA Black @Bambu Lab P1S 0.6 nozzle",
            "Bambu PLA Basic @BBL P1S",
        ],
        "filament_type": ["PLA", "PLA"],
        "filament_vendor": ["ELEGOO", "Bambu Lab"],
        "filament_density": ["1.24", "1.26"],
        "nozzle_temperature_range_high": ["240", "230"],
        "nozzle_temperature_range_low": ["190", "190"],
    }
    settings.update(overrides)
    return json.dumps(settings).encode("utf-8")


class TestParseProjectSettings(unittest.TestCase):
    def test_extracts_only_custom_filaments(self):
        result = parse_project_settings(_project_settings())

        self.assertEqual(list(result), ["P9816594"])
        info = result["P9816594"]
        self.assertEqual(info.name, "ELEGOO PLA Black")
        self.assertEqual(info.filament_vendor, "ELEGOO")
        self.assertEqual(info.filament_type, "PLA")
        self.assertAlmostEqual(info.filament_density, 1.24)
        self.assertEqual(info.nozzle_temperature_range_high, 240)
        self.assertEqual(info.nozzle_temperature_range_low, 190)

    def test_short_or_missing_arrays_do_not_raise(self):
        result = parse_project_settings(
            _project_settings(
                filament_ids=["P1", "P2"],
                filament_settings_id=["Only One @X"],
                filament_vendor=None,
                filament_density=["not-a-number"],
            )
        )
        self.assertEqual(result["P1"].name, "Only One")
        self.assertEqual(result["P1"].filament_vendor, "")
        self.assertEqual(result["P1"].filament_density, 0)
        # No settings name means nothing useful to show: skip it.
        self.assertNotIn("P2", result)

    def test_invalid_payload_returns_empty(self):
        self.assertEqual(parse_project_settings(b"not json"), {})
        self.assertEqual(parse_project_settings(b"[1, 2]"), {})
        self.assertEqual(parse_project_settings(b""), {})


class TestLearnedFilamentStore(unittest.TestCase):
    def setUp(self):
        self._dir = tempfile.TemporaryDirectory()
        self.path = os.path.join(self._dir.name, "sub", "filaments.json")

    def tearDown(self):
        self._dir.cleanup()

    def test_learn_persists_and_reloads(self):
        store = LearnedFilamentStore(self.path)
        self.assertTrue(store.learn_from_project_settings(_project_settings()))

        reloaded = LearnedFilamentStore(self.path)
        self.assertEqual(reloaded.filaments["P9816594"].name, "ELEGOO PLA Black")

    def test_relearning_same_data_does_not_rewrite(self):
        store = LearnedFilamentStore(self.path)
        store.learn_from_project_settings(_project_settings())
        mtime = os.stat(self.path).st_mtime_ns
        self.assertFalse(store.learn_from_project_settings(_project_settings()))
        self.assertEqual(os.stat(self.path).st_mtime_ns, mtime)

    def test_rename_updates_entry(self):
        store = LearnedFilamentStore(self.path)
        store.learn_from_project_settings(_project_settings())
        renamed = _project_settings(
            filament_settings_id=["ELEGOO PLA Matte Black @P1S", "x"]
        )
        self.assertTrue(store.learn_from_project_settings(renamed))
        self.assertEqual(store.filaments["P9816594"].name, "ELEGOO PLA Matte Black")

    def test_merges_entries_written_by_another_store(self):
        first = LearnedFilamentStore(self.path)
        second = LearnedFilamentStore(self.path)
        first.learn_from_project_settings(_project_settings())
        second.learn_from_project_settings(
            _project_settings(filament_ids=["P1111111"], filament_settings_id=["Other @X"])
        )

        reloaded = LearnedFilamentStore(self.path)
        self.assertEqual(set(reloaded.filaments), {"P9816594", "P1111111"})

    def test_corrupt_file_is_ignored(self):
        os.makedirs(os.path.dirname(self.path))
        with open(self.path, "w") as f:
            f.write("{broken")
        store = LearnedFilamentStore(self.path)
        self.assertEqual(store.filaments, {})
        self.assertTrue(store.learn_from_project_settings(_project_settings()))

    def test_memory_only_store_without_path(self):
        store = LearnedFilamentStore(None)
        self.assertTrue(store.learn_from_project_settings(_project_settings()))
        self.assertIn("P9816594", store.filaments)

    def test_shared_store_per_path(self):
        self.assertIs(get_learned_filament_store(self.path), get_learned_filament_store(self.path))
        self.assertIsNot(get_learned_filament_store(None), get_learned_filament_store(None))

    def test_learn_from_3mf(self):
        buf = io.BytesIO()
        with ZipFile(buf, "w") as archive:
            archive.writestr("Metadata/project_settings.config", _project_settings())
        buf.seek(0)
        store = LearnedFilamentStore(None)
        with ZipFile(buf) as archive:
            self.assertTrue(store.learn_from_3mf(archive))
        self.assertIn("P9816594", store.filaments)

    def test_learn_from_3mf_without_settings(self):
        buf = io.BytesIO()
        with ZipFile(buf, "w") as archive:
            archive.writestr("Metadata/slice_info.config", "<config/>")
        buf.seek(0)
        with ZipFile(buf) as archive:
            self.assertFalse(LearnedFilamentStore(None).learn_from_3mf(archive))


class _FakeCloud:
    auth_token = ""


class _FakeClient:
    def __init__(self, path):
        self.bambu_cloud = _FakeCloud()
        self.custom_filament_store_path = path


class TestSlicerSettingsUsesLearnedFilaments(unittest.TestCase):
    def test_learned_filament_names_resolve_in_lan_mode(self):
        settings = SlicerSettings(_FakeClient(None))
        settings.learned.learn_from_project_settings(_project_settings())
        settings.update()  # LAN mode: no cloud token, must not drop learned entries

        self.assertEqual(get_filament_name("P9816594", settings.filaments), "ELEGOO PLA Black")

    def test_cloud_entries_take_precedence(self):
        settings = SlicerSettings(_FakeClient(None))
        settings.learned.learn_from_project_settings(_project_settings())
        settings._load_custom_filaments({
            "filament": {"private": [{
                "name": "Cloud Name @X",
                "filament_id": "P9816594",
                "filament_vendor": "ELEGOO",
                "filament_type": "PLA",
                "nozzle_temperature": [190, 240],
            }]}
        })
        self.assertEqual(settings.filaments["P9816594"].name, "Cloud Name")


if __name__ == "__main__":
    unittest.main()
