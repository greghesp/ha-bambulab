"""Print progress must not carry the previous print's value into a new one."""

import unittest
from unittest.mock import MagicMock

from pybambu.models import PrintJob


class TestPrintProgressStart(unittest.TestCase):
    def setUp(self):
        self.client = MagicMock()
        self.client.ftp_enabled = True
        self.job = PrintJob(self.client)
        self.job._update_task_data = MagicMock()
        self.job._download_timelapse = MagicMock()

    def _last_print(self, state, percent):
        self.job.print_update({"gcode_state": state, "mc_percent": percent})

    def test_finished_print_stays_at_100_until_the_next_one(self):
        self._last_print("FINISH", 100)
        self.job.print_update({"gcode_state": "IDLE"})
        self.assertEqual(self.job.print_percentage, 100)

    def test_prepare_clears_previous_progress(self):
        for state, percent in (("FINISH", 100), ("IDLE", 100), ("FAILED", 79)):
            with self.subTest(state=state):
                self.setUp()
                self._last_print(state, percent)
                self.job.print_update({"gcode_state": "PREPARE"})
                self.assertEqual(self.job.print_percentage, 0)

    def test_progress_is_cleared_before_print_started_event(self):
        self._last_print("FINISH", 100)
        seen = []
        self.client.callback.side_effect = lambda event: seen.append((event, self.job.print_percentage))
        self.job.print_update({"gcode_state": "PREPARE"})
        self.assertIn(("event_print_started", 0), seen)

    def test_slicing_clears_previous_progress(self):
        self._last_print("FINISH", 100)
        self.job.print_update({"gcode_state": "SLICING"})
        self.assertEqual(self.job.print_percentage, 0)

    def test_full_status_during_prepare_keeps_progress_at_0(self):
        # Printers that push their full status repeat the old mc_percent.
        self._last_print("FINISH", 100)
        self.job.print_update({"gcode_state": "PREPARE", "mc_percent": 100})
        self.assertEqual(self.job.print_percentage, 0)
        self.job.print_update({"mc_percent": 100})
        self.assertEqual(self.job.print_percentage, 0)

    def test_progress_is_followed_once_running(self):
        self._last_print("FINISH", 100)
        self.job.print_update({"gcode_state": "PREPARE"})
        self.job.print_update({"gcode_state": "RUNNING"})
        self.assertEqual(self.job.print_percentage, 0)
        self.job.print_update({"mc_percent": 3})
        self.assertEqual(self.job.print_percentage, 3)
        self.job.print_update({"layer_num": 2})
        self.assertEqual(self.job.print_percentage, 3)

    def test_start_without_prepare_clears_finished_progress(self):
        self._last_print("FINISH", 100)
        self.job.print_update({"gcode_state": "RUNNING"})
        self.assertEqual(self.job.print_percentage, 0)

    def test_start_without_prepare_keeps_reported_progress(self):
        self._last_print("FINISH", 100)
        self.job.print_update({"gcode_state": "RUNNING", "mc_percent": 1})
        self.assertEqual(self.job.print_percentage, 1)

    def test_resumed_print_keeps_its_progress(self):
        # Resuming after a power loss goes from idle to running part way through.
        self._last_print("IDLE", 78)
        self.job.print_update({"gcode_state": "RUNNING"})
        self.assertEqual(self.job.print_percentage, 78)

    def test_pause_keeps_progress(self):
        self._last_print("RUNNING", 40)
        self.job.print_update({"gcode_state": "PAUSE"})
        self.job.print_update({"gcode_state": "RUNNING"})
        self.assertEqual(self.job.print_percentage, 40)

    def test_startup_during_print_uses_reported_progress(self):
        self._last_print("RUNNING", 55)
        self.assertEqual(self.job.print_percentage, 55)


if __name__ == "__main__":
    unittest.main()
