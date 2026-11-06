"""Tests for the planned pre-print stages (stg) on StageAction."""

import unittest

from pybambu.models import StageAction

# Plan reported by a P2S before a print: cooling chamber, heatbed preheating,
# homing, plate detection, filament change, extrusion calibration, nozzle
# cleaning, vibration compensation, waiting for bed temp, bed leveling,
# calibration lines.
P2S_PLAN = [29, 2, 13, 11, 4, 8, 14, 3, 54, 1, 51]


class TestStageActionPlan(unittest.TestCase):
    def setUp(self):
        self.stage = StageAction()

    def test_no_plan_has_no_attributes(self):
        self.stage.print_update({"print_type": "cloud", "stg_cur": 13})
        self.assertEqual(self.stage.attributes, {})

    def test_step_follows_plan(self):
        self.stage.print_update({"print_type": "cloud", "stg": P2S_PLAN, "stg_cur": 29})
        self.assertEqual(self.stage.attributes["step"], 1)
        self.assertEqual(self.stage.attributes["total_steps"], 11)
        self.assertEqual(self.stage.attributes["planned_stages"][0], "cooling_chamber")
        self.assertEqual(self.stage.attributes["planned_stages"][-1], "print_calibration_lines")

        self.stage.print_update({"stg_cur": 4})
        self.assertEqual(self.stage.step, 5)

        self.stage.print_update({"stg_cur": 51})
        self.assertEqual(self.stage.step, 11)

    def test_printing_has_no_step(self):
        self.stage.print_update({"print_type": "cloud", "stg": P2S_PLAN, "stg_cur": 51})
        self.stage.print_update({"stg_cur": 0})
        self.assertIsNone(self.stage.attributes["step"])
        self.assertEqual(self.stage.attributes["total_steps"], 11)

    def test_repeated_stage_counts_forward(self):
        self.stage.print_update({"print_type": "cloud", "stg": [2, 1, 2], "stg_cur": 2})
        self.assertEqual(self.stage.step, 1)
        self.stage.print_update({"stg_cur": 1})
        self.assertEqual(self.stage.step, 2)
        self.stage.print_update({"stg_cur": 2})
        self.assertEqual(self.stage.step, 3)
        # Repeated reports of the same stage don't move the step.
        self.stage.print_update({"stg_cur": 2})
        self.assertEqual(self.stage.step, 3)

    def test_new_plan_resets_step(self):
        self.stage.print_update({"print_type": "cloud", "stg": [2, 1, 2], "stg_cur": 2})
        self.stage.print_update({"stg_cur": 1})
        self.stage.print_update({"stg_cur": 2})
        self.assertEqual(self.stage.step, 3)

        self.stage.print_update({"stg": [2, 13], "stg_cur": 2})
        self.assertEqual(self.stage.step, 1)
        self.assertEqual(self.stage.attributes["total_steps"], 2)

    def test_plan_change_is_reported_as_update(self):
        self.stage.print_update({"print_type": "cloud", "stg_cur": 255})
        self.assertTrue(self.stage.print_update({"stg": P2S_PLAN}))
        self.assertFalse(self.stage.print_update({"stg": P2S_PLAN}))


if __name__ == "__main__":
    unittest.main()
