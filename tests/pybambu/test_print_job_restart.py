"""Per-tray print weight/length survive an integration restart mid-print (issue #1048).

print.ams_mapping is only sent once, when a print starts. If the integration wasn't running then,
the 3MF's per-filament usage couldn't be assigned to trays. These tests cover the two ways it is
now recovered: the print.mapping sent in every full status on newer firmware, and a small record
of the last observed ams_mapping kept in the integration's file cache for older firmware.
"""
import json
import os
import tempfile
import unittest
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

from pybambu.models import PrintJob, tray_mapping_slot_index

SLICE_INFO = (
    '<config><plate>'
    '<metadata key="index" value="1" />'
    '<metadata key="weight" value="30.0" />'
    '<filament id="1" type="PLA" color="#2850E0" used_m="8.0" used_g="24.0" />'
    '<filament id="2" type="PLA" color="#161616" used_m="2.0" used_g="6.0" />'
    '</plate></config>'
).encode()


def _running_status(**overrides):
    status = {
        "gcode_state": "RUNNING",
        "subtask_name": "Benchy",
        "gcode_file": "/data/Metadata/plate_1.gcode",
        "task_id": "12345",
        "plate_idx": 1,
    }
    status.update(overrides)
    return status


class TrayMappingSlotIndexTest(unittest.TestCase):
    def test_regular_ams_tray(self):
        self.assertEqual(tray_mapping_slot_index(0x0000), 0)
        self.assertEqual(tray_mapping_slot_index(0x0103), 7)
        self.assertEqual(tray_mapping_slot_index(0x0303), 15)

    def test_ams_ht_unit(self):
        self.assertEqual(tray_mapping_slot_index(0x8000), 16)
        self.assertEqual(tray_mapping_slot_index(0x8100), 17)

    def test_not_an_ams_slot(self):
        self.assertIsNone(tray_mapping_slot_index(0xFFFF))  # unused project filament
        self.assertIsNone(tray_mapping_slot_index(0xFF00))  # external spool
        self.assertIsNone(tray_mapping_slot_index(0xFE00))  # external spool 2
        self.assertIsNone(tray_mapping_slot_index(0x0004))  # tray out of range


class _PrintJobTestCase(unittest.TestCase):
    def setUp(self):
        self._cache = tempfile.TemporaryDirectory()
        self.addCleanup(self._cache.cleanup)
        self.client = self._make_client()

    def _make_client(self):
        client = MagicMock()
        client.cache_path = self._cache.name
        client.ftp_enabled = True
        client._device.supports_feature.return_value = False
        client._device.external_spool[0].active = False
        client._device.external_spool[1].active = False
        return client

    def _new_print_job(self, client=None):
        job = PrintJob(client or self.client)
        job._update_task_data = MagicMock()
        job._download_timelapse = MagicMock()
        return job


class TrayMappingFallbackTest(_PrintJobTestCase):
    def test_weights_use_tray_mapping_when_ams_mapping_was_missed(self):
        job = self._new_print_job()
        # A restart mid-print: the full status carries print.mapping but never ams_mapping.
        job.print_update(_running_status(mapping=[0x0103, 0x8100]))

        self.assertTrue(job._parse_and_apply_model_metadata(SLICE_INFO))

        self.assertEqual(job.get_print_weights, {"AMS 2 Tray 4": 24.0, "AMS HT 2": 6.0})
        self.assertEqual(job.get_print_lengths, {"AMS 2 Tray 4": 8.0, "AMS HT 2": 2.0})

    def test_ams_mapping_still_wins_when_both_are_known(self):
        job = self._new_print_job()
        job.print_update(_running_status(ams_mapping=[0, 1], mapping=[0x0103, 0x8100]))

        job._parse_and_apply_model_metadata(SLICE_INFO)

        self.assertEqual(job.get_print_weights, {"AMS 1 Tray 1": 24.0, "AMS 1 Tray 2": 6.0})

    def test_unused_and_external_entries_are_skipped(self):
        job = self._new_print_job()
        job.print_update(_running_status(mapping=[0xFFFF, 0x0002]))

        job._parse_and_apply_model_metadata(SLICE_INFO)

        self.assertEqual(job.get_print_weights, {"AMS 1 Tray 3": 6.0})


class PersistedAmsMappingTest(_PrintJobTestCase):
    def _start_print(self, job, ams_mapping=(4, 2), **status):
        job.print_update({"gcode_state": "IDLE"})
        job.print_update({"ams_mapping": list(ams_mapping)})
        job.print_update(_running_status(gcode_state="PREPARE", **status))
        job.print_update(_running_status(**status))

    def _restart(self):
        """A fresh client and PrintJob sharing the same file cache, as after an HA restart."""
        return self._new_print_job(self._make_client())

    def test_ams_mapping_is_restored_after_restart_for_the_same_print(self):
        self._start_print(self._new_print_job())

        job = self._restart()
        job.print_update(_running_status())

        self.assertEqual(job.ams_mapping, [4, 2])
        job._parse_and_apply_model_metadata(SLICE_INFO)
        self.assertEqual(job.get_print_weights, {"AMS 2 Tray 1": 24.0, "AMS 1 Tray 3": 6.0})

    def test_start_time_is_restored_after_restart(self):
        first = self._new_print_job()
        self._start_print(first)
        self.assertIsNotNone(first.start_time)

        job = self._restart()
        job.print_update(_running_status())

        self.assertEqual(job.start_time, first.start_time)

    def test_mapping_from_another_print_is_not_restored(self):
        self._start_print(self._new_print_job())

        for changed in ({"subtask_name": "Other"}, {"task_id": "99999"}, {"plate_idx": 2}):
            with self.subTest(changed=changed):
                job = self._restart()
                job.print_update(_running_status(**changed))
                self.assertEqual(job.ams_mapping, [])
                self.assertIsNone(job.start_time)

    def test_reprint_of_the_same_file_is_told_apart_by_gcode_start_time(self):
        self._start_print(self._new_print_job(), gcode_start_time="1700000000")

        job = self._restart()
        job.print_update(_running_status(gcode_start_time="1700009999"))

        self.assertEqual(job.ams_mapping, [])

    def test_nothing_is_restored_when_the_printer_is_idle(self):
        self._start_print(self._new_print_job())

        job = self._restart()
        job.print_update(_running_status(gcode_state="FINISH"))

        self.assertEqual(job.ams_mapping, [])

    def test_live_mapping_is_not_overwritten_by_the_record(self):
        self._start_print(self._new_print_job())

        job = self._restart()
        job.print_update(_running_status(ams_mapping=[1, 1]))

        self.assertEqual(job.ams_mapping, [1, 1])

    def test_mapping_is_not_recorded_against_a_later_print(self):
        """A touchscreen print sends no ams_mapping. The previous print's must not be saved for it."""
        first = self._new_print_job()
        self._start_print(first)
        first.print_update({"gcode_state": "FINISH"})
        first.print_update(_running_status(gcode_state="PREPARE", subtask_name="Touchscreen", task_id="0"))
        first.print_update(_running_status(subtask_name="Touchscreen", task_id="0"))

        job = self._restart()
        job.print_update(_running_status(subtask_name="Touchscreen", task_id="0"))

        self.assertEqual(job.ams_mapping, [])

    def test_record_is_deleted_when_the_print_ends(self):
        """A touchscreen reprint of the same file has the same identity, so the record must not outlive its print."""
        first = self._new_print_job()
        self._start_print(first)
        first.print_update({"gcode_state": "FINISH"})
        first.print_update(_running_status(gcode_state="PREPARE"))
        first.print_update(_running_status())

        self.assertFalse(os.path.exists(self._record_path()))
        job = self._restart()
        job.print_update(_running_status())
        self.assertEqual(job.ams_mapping, [])

    def test_record_left_from_a_print_that_ended_while_ha_was_down_is_deleted(self):
        self._start_print(self._new_print_job())

        self._restart().print_update({"gcode_state": "IDLE"})

        self.assertFalse(os.path.exists(self._record_path()))

    def test_mapping_for_a_print_that_never_started_is_dropped(self):
        job = self._new_print_job()
        with patch("pybambu.models.time.monotonic", return_value=1000):
            job.print_update({"gcode_state": "IDLE"})
            job.print_update({"ams_mapping": [4, 2]})
        with patch("pybambu.models.time.monotonic", return_value=1000 + 601):
            job.print_update({"gcode_state": "IDLE"})
            job.print_update(_running_status(subtask_name="Touchscreen", task_id="0"))

        self.assertFalse(os.path.exists(self._record_path()))

    def test_restore_waits_for_the_print_name(self):
        self._start_print(self._new_print_job())

        job = self._restart()
        job.print_update(_running_status(subtask_name=""))
        self.assertEqual(job.ams_mapping, [])
        job.print_update({"subtask_name": "Benchy"})

        self.assertEqual(job.ams_mapping, [4, 2])

    def test_record_follows_a_late_task_id(self):
        job = self._new_print_job()
        self._start_print(job, task_id="0")
        job.print_update({"task_id": "12345"})

        with open(self._record_path()) as f:
            record = json.load(f)
        self.assertEqual(record["task_id"], "12345")
        self.assertEqual(record["ams_mapping"], [4, 2])

    def test_malformed_mapping_in_record_is_ignored(self):
        os.makedirs(os.path.dirname(self._record_path()), exist_ok=True)
        with open(self._record_path(), "w") as f:
            json.dump({"subtask_name": "Benchy", "task_id": "12345", "plate_idx": "1",
                       "ams_mapping": ["x"], "start_time": "not a date"}, f)

        job = self._restart()
        job.print_update(_running_status())

        self.assertEqual(job.ams_mapping, [])

    def test_save_failure_does_not_break_status_updates(self):
        job = self._new_print_job()
        with patch("pybambu.models.Path.write_text", side_effect=OSError("disk full")):
            self._start_print(job)

        self.assertEqual(job.gcode_state, "RUNNING")
        self.assertEqual(job.ams_mapping, [4, 2])

    def _record_path(self):
        return os.path.join(self._cache.name, "prints", "active_print_job.json")

    def test_unreadable_record_is_ignored(self):
        path = os.path.join(self._cache.name, "prints", "active_print_job.json")
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w") as f:
            f.write("{not json")

        job = self._restart()
        job.print_update(_running_status())

        self.assertEqual(job.ams_mapping, [])

    def test_record_contents(self):
        self._start_print(self._new_print_job())

        with open(os.path.join(self._cache.name, "prints", "active_print_job.json")) as f:
            record = json.load(f)

        self.assertEqual(record["ams_mapping"], [4, 2])
        self.assertEqual(record["subtask_name"], "Benchy")
        self.assertEqual(record["task_id"], "12345")
        self.assertEqual(record["plate_idx"], "1")
        self.assertTrue(datetime.fromisoformat(record["start_time"]).tzinfo is not None)


if __name__ == "__main__":
    unittest.main()
