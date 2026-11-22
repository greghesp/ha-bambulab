"""Tests for AMS drying model constants."""

import unittest

from pybambu.const import AMS_DRYING_MODELS, AMS_MODELS, AMS_MODELS_AND_EXTERNAL_SPOOL


class TestAmsDryingModels(unittest.TestCase):
    def test_ams_3h_is_supported_for_drying(self):
        self.assertIn("AMS 3H", AMS_DRYING_MODELS)

    def test_ams_3h_is_in_ams_model_lists(self):
        self.assertIn("AMS 3H", AMS_MODELS)
        self.assertIn("AMS 3H", AMS_MODELS_AND_EXTERNAL_SPOOL)
