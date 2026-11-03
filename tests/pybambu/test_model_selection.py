import unittest
from datetime import datetime, timezone
from unittest.mock import MagicMock

from pybambu.media_sources import Ftps990MediaSource, RemoteMediaFile
from pybambu.models import PrintJob


class TestModelSelectionForRepeatedTaskName(unittest.TestCase):
    """A new print can share its task name with an older job still on the printer (#2176)."""

    def setUp(self):
        self.print_job = PrintJob(MagicMock())

    def remote(self, path, modified, size=1000):
        return RemoteMediaFile(
            name=path.rsplit("/", 1)[-1],
            path=path,
            size=size,
            media_type="model",
            source=Ftps990MediaSource.name,
            storage="external",
            modified=modified,
        )

    def test_the_file_the_printer_reports_is_tried_first(self):
        self.print_job._subtask_name = "Kostka"
        self.print_job.gcode_file = "Kostka.gcode.3mf"

        candidates = self.print_job._model_filenames_to_try()

        self.assertEqual(candidates[0], "Kostka.gcode.3mf")
        self.assertEqual(len(candidates), len(set(candidates)))

    def test_a_non_3mf_gcode_file_stays_a_last_resort(self):
        self.print_job._subtask_name = "dragon"
        self.print_job.gcode_file = "/data/Metadata/plate_1.gcode"

        self.assertEqual(self.print_job._model_filenames_to_try()[0], "dragon.3mf")

    def test_older_cache_file_with_the_task_name_is_not_selected(self):
        self.print_job._subtask_name = "Kostka"
        self.print_job.gcode_file = "Kostka.gcode.3mf"
        older = self.remote("/cache/Kostka.3mf", datetime(2026, 10, 1, tzinfo=timezone.utc))
        current = self.remote("/Kostka.gcode.3mf", datetime(2026, 10, 20, tzinfo=timezone.utc))

        selected = self.print_job._select_model_file(
            [older, current], self.print_job._model_filenames_to_try()
        )

        self.assertEqual(selected.path, "/Kostka.gcode.3mf")

    def test_newest_of_identically_named_files_wins(self):
        older = self.remote("/cache/Kostka.gcode.3mf", datetime(2026, 10, 1, tzinfo=timezone.utc), size=2000)
        newer = self.remote("/Kostka.gcode.3mf", datetime(2026, 10, 20, tzinfo=timezone.utc))

        selected = self.print_job._select_model_file([older, newer], ["Kostka.gcode.3mf"])

        self.assertEqual(selected.path, "/Kostka.gcode.3mf")

    def test_a_file_without_a_timestamp_does_not_lose_on_recency(self):
        dated = self.remote("/Kostka.gcode.3mf", datetime(2026, 10, 20, tzinfo=timezone.utc), size=2000)
        undated = self.remote("/cache/Kostka.gcode.3mf", None)

        selected = self.print_job._select_model_file([dated, undated], ["Kostka.gcode.3mf"])

        self.assertEqual(selected.path, "/cache/Kostka.gcode.3mf")

    def test_cache_copy_still_breaks_a_timestamp_tie(self):
        modified = datetime(2026, 10, 20, tzinfo=timezone.utc)
        root = self.remote("/Kostka.gcode.3mf", modified, size=2000)
        cache = self.remote("/cache/Kostka.gcode.3mf", modified)

        selected = self.print_job._select_model_file([root, cache], ["Kostka.gcode.3mf"])

        self.assertEqual(selected.path, "/cache/Kostka.gcode.3mf")
