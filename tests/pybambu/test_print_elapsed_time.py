import unittest
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch

from pybambu.models import PrintJob

START = datetime(2025, 9, 25, 10, 0, tzinfo=timezone.utc)


class TestPrintElapsedTime(unittest.TestCase):
    def setUp(self):
        self.client = MagicMock()
        self.client.ftp_enabled = True
        self.print_job = PrintJob(self.client)
        self.print_job._update_task_data = MagicMock()
        self.print_job._download_timelapse = MagicMock()
        self.print_job.gcode_state = "FINISH"
        self.now = START

    def _update(self, data, now):
        self.now = now
        with patch("pybambu.models.get_end_time", side_effect=self._fake_end_time):
            self.print_job.print_update(data)

    def _fake_end_time(self, remaining_minutes):
        return self.now + timedelta(minutes=remaining_minutes)

    def _elapsed_at(self, now):
        self.now = now
        with patch("pybambu.models.get_end_time", side_effect=self._fake_end_time):
            return self.print_job.elapsed_time

    def test_elapsed_time_is_none_before_any_print(self):
        self.assertIsNone(PrintJob(self.client).elapsed_time)

    def test_elapsed_time_counts_up_while_printing(self):
        self._update({"gcode_state": "RUNNING"}, START)

        self.assertEqual(self._elapsed_at(START + timedelta(minutes=42)), 42)

    def test_elapsed_time_is_frozen_when_print_finishes(self):
        self._update({"gcode_state": "RUNNING"}, START)
        self._update({"gcode_state": "FINISH"}, START + timedelta(hours=2, minutes=5))

        self.assertEqual(self._elapsed_at(START + timedelta(hours=5)), 125)

    def test_elapsed_time_is_frozen_when_print_fails(self):
        self._update({"gcode_state": "RUNNING"}, START)
        self._update({"gcode_state": "FAILED"}, START + timedelta(minutes=17))

        self.assertEqual(self._elapsed_at(START + timedelta(hours=1)), 17)

    def test_elapsed_time_spans_more_than_a_day(self):
        self._update({"gcode_state": "RUNNING"}, START)
        self._update({"gcode_state": "FINISH"}, START + timedelta(days=1, hours=3))

        self.assertEqual(self._elapsed_at(START + timedelta(days=2)), 27 * 60)

    def test_usage_hours_include_whole_days(self):
        self.client._device.info.usage_hours = 10
        self._update({"gcode_state": "RUNNING"}, START)
        self._update({"gcode_state": "FINISH"}, START + timedelta(days=1, hours=3, minutes=30))

        self.assertAlmostEqual(self.client._device.info.usage_hours, 10 + 27.5)

    def test_elapsed_time_is_final_when_finished_event_fires(self):
        seen = []
        self.client.callback.side_effect = lambda event: seen.append((event, self.print_job.elapsed_time))
        self._update({"gcode_state": "RUNNING"}, START)
        self._update({"gcode_state": "FINISH"}, START + timedelta(minutes=90))

        self.assertIn(("event_print_finished", 90), seen)

    def test_new_print_resets_elapsed_time(self):
        self._update({"gcode_state": "RUNNING"}, START)
        self._update({"gcode_state": "FINISH"}, START + timedelta(minutes=90))
        second_start = START + timedelta(hours=3)
        self._update({"gcode_state": "RUNNING"}, second_start)

        self.assertEqual(self._elapsed_at(second_start + timedelta(minutes=5)), 5)

    def test_idle_after_restart_uses_cloud_start_and_end(self):
        self.print_job.gcode_state = "FINISH"
        self.print_job.start_time = START
        self.print_job.end_time = START + timedelta(minutes=75)

        self.assertEqual(self._elapsed_at(START + timedelta(days=1)), 75)

    def test_idle_without_end_time_is_unknown(self):
        self.print_job.gcode_state = "FINISH"
        self.print_job.start_time = START

        self.assertIsNone(self._elapsed_at(START + timedelta(hours=1)))


if __name__ == "__main__":
    unittest.main()
