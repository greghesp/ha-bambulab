"""Cloud print figures must come from the running job's own cloud task (issue #1801).

When a cloud print's 3mf can't be found on the printer (Bambu Handy/MakerWorld prints report the
profile name instead of the file name), the cloud task is the only source for the print weight. The
newest task can still be the previous job, or have no weight yet, at the moment the print starts.
"""
import unittest
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

from pybambu.bambu_cloud import BambuCloud
from pybambu.models import CLOUD_TASK_RETRY_DELAYS, PrintJob

SERIAL = "SERIAL"
CURRENT_ID = "1440266903"
PREVIOUS_ID = "1440266800"
NEWER_ID = "1440267000"
STATUS_FINISHED = 2
STATUS_RUNNING = 4


def _task(task_id, weight, status, **overrides):
    task = {
        "id": int(task_id),
        "deviceId": SERIAL,
        "weight": weight,
        "length": 1000,
        "bedType": "textured_plate",
        "cover": f"https://example.invalid/{task_id}.png",
        "status": status,
        "startTime": "2026-11-23T10:00:00Z",
        "endTime": "2026-11-23T11:00:00Z",
        "amsDetailMapping": [{"ams": 1, "weight": weight}],
    }
    task.update(overrides)
    return task


PREVIOUS = _task(PREVIOUS_ID, 4.44, STATUS_FINISHED, startTime="2026-11-22T10:00:00Z")
CURRENT = _task(CURRENT_ID, 24.0, STATUS_RUNNING)


def _running_status(**overrides):
    status = {
        "gcode_state": "RUNNING",
        "print_type": "cloud",
        "subtask_name": "0.2mm layer, 2 walls, 15% infill",
        "gcode_file": "/data/Metadata/plate_1.gcode",
        "task_id": CURRENT_ID,
        "subtask_id": CURRENT_ID,
        "plate_idx": 1,
    }
    status.update(overrides)
    return status


class CloudTaskIdentityTest(unittest.TestCase):
    def setUp(self):
        # Bypass __init__, only the task selection is under test.
        self.cloud = BambuCloud.__new__(BambuCloud)
        self.cloud._auth_token = "token"
        self.cloud.download = MagicMock(return_value=b"image")
        self._set_tasks(PREVIOUS)

        self.client = MagicMock()
        self.client._test_mode = False
        self.client._serial = SERIAL
        self.client.ftp_enabled = False
        self.client.bambu_cloud = self.cloud
        self.client._device.supports_feature.return_value = False
        self.client._device.external_spool[0].active = False
        self.client._device.external_spool[1].active = False
        self.client._device.info.usage_hours = 0

        self.job = PrintJob(self.client)
        self.job._download_timelapse = MagicMock()
        self.job._restore_active_print_record = MagicMock()
        self.job._update_active_print_record = MagicMock()

        self._now = 1000.0
        clock = patch("pybambu.models.time.monotonic", side_effect=lambda: self._now)
        clock.start()
        self.addCleanup(clock.stop)

    def _set_tasks(self, *tasks):
        self.cloud.get_tasklist = MagicMock(return_value={"hits": list(tasks)})

    def _start_print(self, **overrides):
        self.job.print_update({"gcode_state": "IDLE"})
        self.cloud.download.reset_mock()
        self.job.print_update(_running_status(**overrides))

    def _wait(self, seconds, **status):
        self._now += seconds
        self.job.print_update({"mc_percent": 1, **status})

    def test_previous_jobs_task_is_not_applied_to_a_running_cloud_print(self):
        self._start_print()

        self.assertEqual(0, self.job.print_weight)
        self.assertEqual(0, self.job.print_length)
        self.assertEqual({}, self.job.get_print_weights)

    def test_previous_jobs_cover_is_not_applied_to_a_running_cloud_print(self):
        self._start_print()

        self.cloud.download.assert_not_called()

    def test_own_task_is_used_even_when_it_is_not_the_newest(self):
        self._set_tasks(_task(NEWER_ID, 99.0, STATUS_FINISHED), CURRENT)

        self._start_print()

        self.assertEqual(24.0, self.job.print_weight)
        self.assertEqual({"AMS 1 Tray 2": 24.0}, self.job.get_print_weights)

    def test_subtask_id_also_identifies_the_task(self):
        # Older firmware reported different task and subtask ids.
        self._set_tasks(_task(NEWER_ID, 99.0, STATUS_FINISHED), CURRENT)

        self._start_print(task_id="1440266902", subtask_id=CURRENT_ID)

        self.assertEqual(24.0, self.job.print_weight)

    def test_weight_is_filled_in_once_the_jobs_task_appears(self):
        self._start_print()
        self._set_tasks(CURRENT, PREVIOUS)

        self._wait(CLOUD_TASK_RETRY_DELAYS[0])

        self.assertEqual(24.0, self.job.print_weight)
        self.assertEqual({"AMS 1 Tray 2": 24.0}, self.job.get_print_weights)
        self.assertEqual(datetime(2026, 11, 23, 10, 0, tzinfo=timezone.utc), self.job.start_time)

    def test_entities_are_refreshed_when_a_retry_fills_in_the_weight(self):
        self._start_print()
        self._set_tasks(CURRENT, PREVIOUS)
        self._now += CLOUD_TASK_RETRY_DELAYS[0]

        self.assertTrue(self.job.print_update({}))

    def test_weight_is_filled_in_once_the_task_has_one(self):
        self._set_tasks(_task(CURRENT_ID, 0, STATUS_RUNNING), PREVIOUS)
        self._start_print()
        self.assertEqual(0, self.job.print_weight)
        self._set_tasks(CURRENT, PREVIOUS)

        self._wait(CLOUD_TASK_RETRY_DELAYS[0])

        self.assertEqual(24.0, self.job.print_weight)

    def test_cover_is_not_downloaded_again_while_the_task_has_no_weight(self):
        self._set_tasks(_task(CURRENT_ID, 0, STATUS_RUNNING))
        self._start_print()
        self.cloud.download.reset_mock()

        self._wait(CLOUD_TASK_RETRY_DELAYS[0])

        self.cloud.download.assert_not_called()

    def test_weight_is_corrected_when_the_job_id_arrives_after_the_print_starts(self):
        self._start_print(task_id=PREVIOUS_ID, subtask_id=PREVIOUS_ID)
        self._set_tasks(CURRENT, PREVIOUS)

        self._wait(CLOUD_TASK_RETRY_DELAYS[0], task_id=CURRENT_ID, subtask_id=CURRENT_ID)

        self.assertEqual(24.0, self.job.print_weight)

    def test_cloud_is_not_asked_again_before_the_retry_delay(self):
        self._start_print()
        calls = self.cloud.get_tasklist.call_count

        self._wait(CLOUD_TASK_RETRY_DELAYS[0] - 1)

        self.assertEqual(calls, self.cloud.get_tasklist.call_count)

    def test_retries_are_bounded_for_one_print(self):
        self._start_print()
        calls = self.cloud.get_tasklist.call_count

        for _ in range(len(CLOUD_TASK_RETRY_DELAYS) + 5):
            self._wait(max(CLOUD_TASK_RETRY_DELAYS))

        self.assertEqual(calls + len(CLOUD_TASK_RETRY_DELAYS), self.cloud.get_tasklist.call_count)

    def test_the_next_print_gets_its_own_retries(self):
        self._start_print()
        for _ in range(len(CLOUD_TASK_RETRY_DELAYS) + 1):
            self._wait(max(CLOUD_TASK_RETRY_DELAYS))
        self.job.print_update({"gcode_state": "FINISH"})
        self.job.print_update(_running_status(task_id=NEWER_ID, subtask_id=NEWER_ID))
        self._set_tasks(_task(NEWER_ID, 7.5, STATUS_RUNNING))

        self._wait(CLOUD_TASK_RETRY_DELAYS[0])

        self.assertEqual(7.5, self.job.print_weight)

    def test_cloud_is_not_asked_again_once_the_jobs_task_is_known(self):
        self._set_tasks(CURRENT)
        self._start_print()
        calls = self.cloud.get_tasklist.call_count

        self._wait(max(CLOUD_TASK_RETRY_DELAYS))

        self.assertEqual(calls, self.cloud.get_tasklist.call_count)

    def test_cloud_outage_during_a_retry_keeps_the_start_time(self):
        self._start_print()
        started = self.job.start_time
        self.cloud.get_tasklist = MagicMock(return_value=None)

        self._wait(CLOUD_TASK_RETRY_DELAYS[0])

        self.cloud.get_tasklist.assert_called_once_with()
        self.assertIsNotNone(started)
        self.assertEqual(started, self.job.start_time)

    def test_local_prints_are_not_retried(self):
        self._start_print(print_type="local", task_id="8291", subtask_id="")
        calls = self.cloud.get_tasklist.call_count

        self._wait(max(CLOUD_TASK_RETRY_DELAYS))

        self.assertEqual(calls, self.cloud.get_tasklist.call_count)

    def test_retry_does_not_replace_figures_read_from_the_3mf(self):
        self._start_print()
        self.assertTrue(self.job._parse_and_apply_model_metadata(
            b'<config><plate><metadata key="index" value="1" />'
            b'<metadata key="weight" value="30.0" /></plate></config>'
        ))
        calls = self.cloud.get_tasklist.call_count

        self._wait(max(CLOUD_TASK_RETRY_DELAYS))

        self.assertEqual(calls, self.cloud.get_tasklist.call_count)
        self.assertEqual(30.0, self.job.print_weight)

    def test_retry_waits_for_a_running_printer_download(self):
        self._start_print()
        self.job._ftpThread = MagicMock()
        calls = self.cloud.get_tasklist.call_count

        self._wait(max(CLOUD_TASK_RETRY_DELAYS))

        self.assertEqual(calls, self.cloud.get_tasklist.call_count)

    def test_task_stuck_as_running_is_replaced_by_the_jobs_own(self):
        self._set_tasks(_task(PREVIOUS_ID, 4.44, STATUS_RUNNING))
        self._start_print()
        self._set_tasks(CURRENT, PREVIOUS)

        self._wait(CLOUD_TASK_RETRY_DELAYS[0])

        self.assertEqual(24.0, self.job.print_weight)

    def test_weight_is_filled_in_when_the_printer_has_the_cover_but_no_matching_3mf(self):
        """The P2S case: the active cover loads over TCP 6000, so model loading isn't retried."""
        self.client.ftp_enabled = True
        self.client._device.supports_feature.return_value = True
        self.job._remote_media_sources = MagicMock(return_value=[])
        self.job._try_active_cover_from_printer = MagicMock(return_value=True)
        self.job._attempt_remote_model_download = MagicMock(return_value=None)
        self.job._attempt_direct_metadata_download = MagicMock(return_value=False)
        self.job._try_active_metadata_from_printer = MagicMock(return_value=False)
        self.job.prune_print_history_files = MagicMock()
        self._start_print()
        while (thread := self.job._ftpThread) is not None:
            thread.join()
        self._set_tasks(CURRENT, PREVIOUS)

        self._wait(CLOUD_TASK_RETRY_DELAYS[0])

        self.job._attempt_remote_model_download.assert_called()
        self.assertEqual(24.0, self.job.print_weight)

    def test_unfinished_newest_task_is_still_used_when_the_job_has_no_cloud_id(self):
        self._set_tasks(_task(NEWER_ID, 12.0, STATUS_RUNNING))

        self._start_print(task_id="0", subtask_id="0")

        self.assertEqual(12.0, self.job.print_weight)

    def test_last_task_is_still_shown_while_the_printer_is_idle(self):
        self.job.print_update({"gcode_state": "FINISH", "print_type": "idle"})

        self.assertEqual(4.44, self.job.print_weight)


if __name__ == "__main__":
    unittest.main()
