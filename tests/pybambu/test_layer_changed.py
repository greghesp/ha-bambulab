import unittest
from unittest.mock import MagicMock

from pybambu.models import PrintJob

EVENT = "event_print_layer_changed"


class TestLayerChanged(unittest.TestCase):
    def setUp(self):
        self.client = MagicMock()
        self.print_job = PrintJob(self.client)
        self.print_job._update_task_data = MagicMock()
        self.print_job._download_timelapse = MagicMock()

    def _events(self):
        return [c.args[0] for c in self.client.callback.call_args_list]

    def _start_printing(self, layer):
        """Put the job mid-print on the given layer, discarding setup events."""
        self.print_job.print_update({"gcode_state": "RUNNING", "layer_num": layer, "total_layer_num": 70})
        self.client.callback.reset_mock()

    def test_fires_once_per_new_layer(self):
        self._start_printing(4)
        self.print_job.print_update({"layer_num": 5})
        self.print_job.print_update({"layer_num": 6})
        self.assertEqual(self._events().count(EVENT), 2)

    def test_layer_is_updated_before_event_fires(self):
        self._start_printing(4)
        seen = []
        self.client.callback.side_effect = lambda event: seen.append((event, self.print_job.current_layer))
        self.print_job.print_update({"layer_num": 5})
        self.assertIn((EVENT, 5), seen)

    def test_fires_for_first_layer(self):
        self._start_printing(0)
        self.print_job.print_update({"layer_num": 1})
        self.assertIn(EVENT, self._events())

    def test_does_not_fire_when_layer_is_unchanged(self):
        self._start_printing(5)
        self.print_job.print_update({"layer_num": 5})
        self.assertNotIn(EVENT, self._events())

    def test_does_not_fire_when_payload_has_no_layer(self):
        self._start_printing(5)
        self.print_job.print_update({"mc_percent": 20})
        self.assertNotIn(EVENT, self._events())

    def test_does_not_fire_when_layer_resets_for_a_new_print(self):
        self._start_printing(70)
        self.print_job.print_update({"layer_num": 0})
        self.assertNotIn(EVENT, self._events())

    def test_fires_when_new_print_skips_the_reset_to_zero(self):
        self._start_printing(70)
        self.print_job.print_update({"layer_num": 1})
        self.assertIn(EVENT, self._events())

    def test_does_not_fire_for_first_data_after_restart_mid_print(self):
        self.print_job.print_update({"gcode_state": "RUNNING", "layer_num": 57, "total_layer_num": 70})
        self.assertNotIn(EVENT, self._events())

    def test_fires_after_print_started(self):
        self.print_job.print_update({"gcode_state": "FINISH", "layer_num": 70})
        self.client.callback.reset_mock()
        self.print_job.print_update({"gcode_state": "RUNNING", "layer_num": 1})
        events = self._events()
        self.assertLess(events.index("event_print_started"), events.index(EVENT))


if __name__ == "__main__":
    unittest.main()
