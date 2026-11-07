import unittest

from pybambu.utils import normalize_service_target


class TestNormalizeServiceTarget(unittest.TestCase):
    """Home Assistant validates a script's `target:` with ensure_list, so device_id and
    entity_id can arrive as lists even though the UI sends a plain string (#1969)."""

    def test_single_item_lists_are_unwrapped(self):
        self.assertEqual(
            normalize_service_target({"device_id": ["abc"], "plate": 1}),
            {"device_id": "abc", "plate": 1},
        )
        self.assertEqual(
            normalize_service_target({"entity_id": ["sensor.x"]}),
            {"entity_id": "sensor.x"},
        )

    def test_plain_strings_are_unchanged(self):
        self.assertEqual(normalize_service_target({"device_id": "abc"}), {"device_id": "abc"})

    def test_input_is_not_mutated(self):
        data = {"device_id": ["abc"]}
        normalize_service_target(data)
        self.assertEqual(data, {"device_id": ["abc"]})

    def test_multiple_targets_are_rejected(self):
        with self.assertRaises(ValueError):
            normalize_service_target({"device_id": ["abc", "def"]})

    def test_empty_target_is_treated_as_absent(self):
        self.assertEqual(
            normalize_service_target({"device_id": [], "entity_id": "sensor.x"}),
            {"entity_id": "sensor.x"},
        )

    def test_no_target_at_all_is_rejected(self):
        with self.assertRaises(ValueError):
            normalize_service_target({"device_id": [], "plate": 1})
        with self.assertRaises(ValueError):
            normalize_service_target({"plate": 1})
