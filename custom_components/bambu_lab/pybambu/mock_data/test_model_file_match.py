"""Tests for matching a remote 3MF to the name the slicer actually stored."""

import unittest
from unittest.mock import MagicMock

from pybambu.media_sources import RemoteMediaFile
from pybambu.models import (
    PrintJob,
    dialog_print_name,
    makerworld_print_name,
    print_filename_candidates,
    truncate_utf8,
)


STRESS_BALL = "Brain Stress Ball (TPU 85/95A)"


def _remote(name: str, path: str | None = None, source: str = "tcp6000") -> RemoteMediaFile:
    return RemoteMediaFile(
        name=name,
        path=path or f"/media/usb0/cache/{name}",
        size=100,
        media_type="model",
        source=source,
        storage="external",
    )


class PrintNameNormalizationTests(unittest.TestCase):
    def test_dialog_name_deletes_illegal_characters(self):
        self.assertEqual(dialog_print_name(STRESS_BALL), "Brain Stress Ball (TPU 8595A)")

    def test_makerworld_name_replaces_spaces_and_illegal_characters(self):
        self.assertEqual(
            makerworld_print_name(STRESS_BALL),
            "Brain_Stress_Ball_(TPU_85_95A)",
        )

    def test_makerworld_name_collapses_underscore_runs(self):
        self.assertEqual(makerworld_print_name("a / b"), "a_b")

    def test_truncate_utf8_keeps_a_character_boundary(self):
        self.assertEqual(truncate_utf8("é" * 60, 100), "é" * 50)
        self.assertEqual(truncate_utf8("abc", 100), "abc")

    def test_candidates_prefer_dialog_then_makerworld_then_raw(self):
        self.assertEqual(
            print_filename_candidates(STRESS_BALL),
            [
                "Brain Stress Ball (TPU 8595A).3mf",
                "Brain Stress Ball (TPU 8595A).gcode.3mf",
                "Brain_Stress_Ball_(TPU_85_95A).3mf",
                "Brain_Stress_Ball_(TPU_85_95A).gcode.3mf",
                f"{STRESS_BALL}.3mf",
                f"{STRESS_BALL}.gcode.3mf",
            ],
        )

    def test_gcode_path_uses_the_basename(self):
        self.assertEqual(
            print_filename_candidates("/data/Metadata/plate_1.gcode"),
            [
                "plate_1.gcode.3mf",
                "plate_1.gcode.gcode.3mf",
            ],
        )

    def test_plain_name_does_not_repeat_the_dialog_form(self):
        self.assertEqual(
            print_filename_candidates("Bambu Cube"),
            [
                "Bambu Cube.3mf",
                "Bambu Cube.gcode.3mf",
                "Bambu_Cube.3mf",
                "Bambu_Cube.gcode.3mf",
            ],
        )


class ModelFileMatchTests(unittest.TestCase):
    def setUp(self):
        self.job = PrintJob.__new__(PrintJob)
        self.job._subtask_name = STRESS_BALL
        self.job.gcode_file = ""
        self.job._client = MagicMock()
        self.job._client.cache_path = "/tmp/bambu-cache"

    def test_filenames_to_try_follow_the_slicer(self):
        self.assertEqual(
            self.job._model_filenames_to_try()[:2],
            [
                "Brain Stress Ball (TPU 8595A).3mf",
                "Brain Stress Ball (TPU 8595A).gcode.3mf",
            ],
        )

    def test_selects_dialog_file_ahead_of_the_raw_mqtt_name(self):
        files = [
            _remote(f"{STRESS_BALL}.gcode.3mf"),
            _remote("Brain Stress Ball (TPU 8595A).gcode.3mf"),
        ]
        selected = self.job._select_model_files(files, self.job._model_filenames_to_try())
        self.assertEqual(selected[0].basename, "Brain Stress Ball (TPU 8595A).gcode.3mf")

    def test_slash_in_print_name_matches_full_basename(self):
        remote = _remote(f"{STRESS_BALL}.gcode.3mf")
        self.assertTrue(
            self.job._remote_model_matches(remote, f"{STRESS_BALL}.gcode.3mf")
        )

    def test_path_candidate_still_matches_final_component(self):
        remote = _remote("plate_1.gcode.3mf", "/cache/plate_1.gcode.3mf")
        self.assertTrue(
            self.job._remote_model_matches(remote, "/data/Metadata/plate_1.gcode.3mf")
        )

    def test_selects_full_name_not_the_segment_after_the_slash(self):
        files = [
            _remote("95A).gcode.3mf"),
            _remote(f"{STRESS_BALL}.gcode.3mf"),
        ]
        selected = self.job._select_model_files(
            files,
            [
                f"{STRESS_BALL}.3mf",
                f"{STRESS_BALL}.gcode.3mf",
            ],
        )
        self.assertEqual(selected[0].basename, f"{STRESS_BALL}.gcode.3mf")

    def test_cache_path_does_not_split_on_slash_in_the_name(self):
        remote = _remote(f"{STRESS_BALL}.gcode.3mf")
        cache_path, _legacy = self.job._model_cache_paths(remote)
        self.assertNotIn("/", cache_path.name)
        self.assertTrue(cache_path.name.endswith("Brain Stress Ball (TPU 85_95A).gcode.3mf"))
