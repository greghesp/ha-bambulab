"""Usage-hours accounting on print completion.

The printer's own usage counter does not include canceled prints (see
greghesp/ha-bambulab#475), so the integration must not add their duration
either or the two drift apart.
"""
import unittest
from datetime import timedelta
from unittest.mock import MagicMock

from pybambu.models import PrintJob

CANCELED_PRINT_ERROR = 50348044


class TestUsageHours(unittest.TestCase):
    def setUp(self):
        self.client = MagicMock()
        self.client._device.info.usage_hours = 100.0
        self.print_job = PrintJob(self.client)
        # Keep the test off the network / FTP paths.
        self.print_job._download_timelapse = MagicMock()
        self.print_job._update_task_data = MagicMock()
        self.print_job._clear_model_data = MagicMock()
        self.print_job.print_update({"gcode_state": "IDLE"})

    def _start_print(self, hours_ago: float):
        self.print_job.print_update({"gcode_state": "RUNNING"})
        self.print_job.start_time = self.print_job.start_time - timedelta(hours=hours_ago)

    def test_finished_print_adds_usage_hours(self):
        self._start_print(hours_ago=2)

        self.print_job.print_update({"gcode_state": "FINISH"})

        self.assertAlmostEqual(self.client._device.info.usage_hours, 102.0, places=2)

    def test_non_canceled_failure_adds_usage_hours(self):
        self._start_print(hours_ago=1.5)

        self.print_job.print_update({"gcode_state": "FAILED", "print_error": 117473286})

        self.assertAlmostEqual(self.client._device.info.usage_hours, 101.5, places=2)

    def test_canceled_print_does_not_add_usage_hours(self):
        self._start_print(hours_ago=2.35)

        self.print_job.print_update({"print_error": CANCELED_PRINT_ERROR})
        self.print_job.print_update({"gcode_state": "FAILED"})

        self.assertAlmostEqual(self.client._device.info.usage_hours, 100.0, places=2)

    def test_canceled_print_in_same_payload_does_not_add_usage_hours(self):
        self._start_print(hours_ago=2.35)

        self.print_job.print_update({"gcode_state": "FAILED", "print_error": CANCELED_PRINT_ERROR})

        self.assertAlmostEqual(self.client._device.info.usage_hours, 100.0, places=2)

    def test_cancel_still_skips_hours_when_print_error_clears_before_idle(self):
        self._start_print(hours_ago=1)

        self.print_job.print_update({"print_error": CANCELED_PRINT_ERROR})
        self.print_job.print_update({"print_error": 0})
        self.print_job.print_update({"gcode_state": "FAILED"})

        self.assertAlmostEqual(self.client._device.info.usage_hours, 100.0, places=2)

    def test_print_after_canceled_print_adds_usage_hours(self):
        self._start_print(hours_ago=1)
        self.print_job.print_update({"print_error": CANCELED_PRINT_ERROR})
        self.print_job.print_update({"gcode_state": "FAILED"})
        self.print_job.print_update({"print_error": 0})

        self._start_print(hours_ago=3)
        self.print_job.print_update({"gcode_state": "FINISH"})

        self.assertAlmostEqual(self.client._device.info.usage_hours, 103.0, places=2)


if __name__ == "__main__":
    unittest.main()
