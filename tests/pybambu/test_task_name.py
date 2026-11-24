"""The task name of a MakerWorld print is the model's name, not its print profile's (issue #1799).

The printer reports the print profile's title as the subtask_name of a MakerWorld print. The job's
Bambu Cloud task has that same title as instanceTitle and the model's name as designTitle.
"""
import unittest
from unittest.mock import MagicMock

from pybambu.models import PrintJob

TASK_ID = "749794604"
OTHER_TASK_ID = "749794000"
PROFILE = "0.2mm layer, 2 walls, 15% infill"
MODEL = "Shelf Elf Minecraft Sword"


def _task(**overrides):
    task = {
        "id": int(TASK_ID),
        "designTitle": MODEL,
        "instanceTitle": PROFILE,
        "cover": "",
        "status": 4,
        "weight": 10.0,
        "length": 300,
    }
    task.update(overrides)
    return task


def _status(**overrides):
    status = {
        "gcode_state": "RUNNING",
        "print_type": "cloud",
        "subtask_name": PROFILE,
        "gcode_file": "/data/Metadata/plate_1.gcode",
        "task_id": TASK_ID,
        "subtask_id": TASK_ID,
        "plate_idx": 1,
    }
    status.update(overrides)
    return status


class TaskNameTest(unittest.TestCase):
    def setUp(self):
        self.client = MagicMock()
        self.client._test_mode = False
        self.client.ftp_enabled = False
        self.client._device.supports_feature.return_value = False
        self.client._device.info.usage_hours = 0
        self.job = PrintJob(self.client)
        self.job._download_timelapse = MagicMock()
        self.job._restore_active_print_record = MagicMock()
        self.job._update_active_print_record = MagicMock()
        self._set_cloud_task(_task())

    def _set_cloud_task(self, task):
        self.client.bambu_cloud.get_latest_task_for_printer.return_value = task

    def _print(self, **overrides):
        self.job.print_update({"gcode_state": "IDLE"})
        self.job.print_update(_status(**overrides))

    def test_model_name_replaces_the_profile_title(self):
        self._print()

        self.assertEqual(MODEL, self.job.task_name)

    def test_reported_name_is_left_alone_for_file_lookup(self):
        self._print()

        self.assertEqual(PROFILE, self.job.subtask_name)
        self.assertIn(f"{PROFILE}.3mf", self.job._model_filenames_to_try())

    def test_name_that_is_not_the_profile_title_is_kept(self):
        # e.g. a MakerWorld project renamed in Bambu Studio's send dialog.
        self._print(subtask_name="Elf sword, take 2")

        self.assertEqual("Elf sword, take 2", self.job.task_name)

    def test_profile_title_with_a_replaced_slash_is_recognized(self):
        # P1 and A1 printers report a "/" in the title as "_".
        self._set_cloud_task(_task(instanceTitle="X1C / P1S / A1"))

        self._print(subtask_name="X1C _ P1S _ A1")

        self.assertEqual(MODEL, self.job.task_name)

    def test_another_jobs_model_name_is_not_used(self):
        # Many profiles share the same default title, so it doesn't identify the job.
        self._set_cloud_task(_task(id=int(OTHER_TASK_ID)))

        self._print()

        self.assertEqual(PROFILE, self.job.task_name)

    def test_subtask_id_identifies_the_job_on_older_firmware(self):
        self._print(task_id=OTHER_TASK_ID)

        self.assertEqual(MODEL, self.job.task_name)

    def test_print_without_cloud_ids_is_not_matched(self):
        self._set_cloud_task(_task(id=0))

        self._print(print_type="local", task_id="0", subtask_id="0")

        self.assertEqual(PROFILE, self.job.task_name)

    def test_task_without_a_model_name_keeps_the_reported_name(self):
        self._set_cloud_task(_task(designTitle=""))

        self._print()

        self.assertEqual(PROFILE, self.job.task_name)

    def test_task_without_a_profile_title_keeps_the_reported_name(self):
        task = _task()
        del task["instanceTitle"]
        self._set_cloud_task(task)

        self._print()

        self.assertEqual(PROFILE, self.job.task_name)

    def test_null_titles_keep_the_reported_name(self):
        self._set_cloud_task(_task(designTitle=None, instanceTitle=None))

        self._print()

        self.assertEqual(PROFILE, self.job.task_name)

    def test_no_cloud_task_keeps_the_reported_name(self):
        self._set_cloud_task(None)

        self._print()

        self.assertEqual(PROFILE, self.job.task_name)

    def test_no_cloud_login_keeps_the_reported_name(self):
        self.client.bambu_cloud.auth_token = ""

        self._print()

        self.assertEqual(PROFILE, self.job.task_name)

    def test_no_name_is_reported_as_none(self):
        self._print(subtask_name="")

        self.assertIsNone(self.job.task_name)

    def test_previous_prints_model_name_is_dropped_when_a_print_starts(self):
        self._print()
        self.job.print_update({"gcode_state": "FINISH"})
        self.client.ftp_enabled = True
        self.job._download_task_data_from_printer = MagicMock()

        # The new print has a profile with the same title, and its ids haven't arrived yet.
        self.job.print_update({"gcode_state": "PREPARE", "subtask_name": PROFILE})

        self.assertEqual(PROFILE, self.job.task_name)

    def test_task_cleared_while_the_name_is_read(self):
        # The sensor reads the name on another thread than the one handling printer messages.
        self._print()

        class ClearedWhileRead(dict):
            def get(_self, *args):
                self.job._task_data = None
                return super().get(*args)

        self.job._task_data = ClearedWhileRead(_task())

        self.assertEqual(MODEL, self.job.task_name)

    def test_model_name_is_kept_after_the_print_finishes(self):
        self._print()

        self.job.print_update({"gcode_state": "FINISH", "print_type": "idle"})

        self.assertEqual(MODEL, self.job.task_name)


if __name__ == "__main__":
    unittest.main()
