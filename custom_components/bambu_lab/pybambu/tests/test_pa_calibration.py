"""Tests for Pressure Advance calibration features."""

import os
import sys
import copy
import unittest
from unittest.mock import MagicMock

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from pybambu.models import AMSTray, ExternalSpool, Device, HomeFlag
from pybambu.const import Features, Home_Flag_Values
from pybambu.commands import EXTRUSION_CALI_GET_TEMPLATE, EXTRUSION_CALI_SEL_TEMPLATE


class TestCaliIdxParsing(unittest.TestCase):
    def setUp(self):
        self.client = MagicMock()
        self.client.slicer_settings.custom_filaments = {}
        self.client._device.supports_feature.return_value = True
        self.client._device.home_flag.ams_calibrate_remaining = False
        self.tray = AMSTray(self.client)

    def test_cali_idx_default_is_none(self):
        self.assertIsNone(self.tray.cali_idx)

    def test_cali_idx_parsed_from_tray_data(self):
        self.tray.print_update({
            "id": "0",
            "state": "9",
            "tray_type": "PLA",
            "tray_info_idx": "GFA00",
            "cali_idx": 3,
        })
        self.assertEqual(self.tray.cali_idx, 3)

    def test_cali_idx_preserved_when_absent(self):
        self.tray.print_update({
            "id": "0",
            "state": "9",
            "tray_type": "PLA",
            "tray_info_idx": "GFA00",
            "cali_idx": 5,
        })
        self.tray.print_update({
            "id": "0",
            "state": "9",
            "tray_type": "PLA",
            "tray_info_idx": "GFA00",
        })
        self.assertEqual(self.tray.cali_idx, 5)

    def test_cali_idx_minus_one_for_default(self):
        self.tray.print_update({
            "id": "0",
            "state": "9",
            "tray_type": "PLA",
            "tray_info_idx": "GFA00",
            "cali_idx": -1,
        })
        self.assertEqual(self.tray.cali_idx, -1)

    def test_cali_idx_reset_on_empty_slot(self):
        self.tray.print_update({
            "id": "0",
            "state": "9",
            "tray_type": "PLA",
            "tray_info_idx": "GFA00",
            "cali_idx": 2,
        })
        self.assertEqual(self.tray.cali_idx, 2)
        self.tray._reset_empty_slot()
        self.assertIsNone(self.tray.cali_idx)


class TestCaliIdxExternalSpool(unittest.TestCase):
    def setUp(self):
        self.client = MagicMock()
        self.client.slicer_settings.custom_filaments = {}
        self.client._device.supports_feature.return_value = True
        self.client._device.home_flag.ams_calibrate_remaining = False
        self.client._device.ams.active_ams_index = 255
        self.client._device.ams.active_tray_index = 0
        self.spool = ExternalSpool(self.client, index=0)

    def test_cali_idx_parsed_from_vir_slot(self):
        self.spool.print_update({
            "vir_slot": [
                {
                    "id": "255",
                    "tray_type": "PLA",
                    "tray_info_idx": "GFA00",
                    "cali_idx": 7,
                }
            ]
        })
        self.assertEqual(self.spool.cali_idx, 7)


class TestPACalibrationCapability(unittest.TestCase):
    def test_home_flag_bit_16(self):
        self.assertEqual(Home_Flag_Values.PA_CALIBRATION, 0x00010000)

    def test_features_enum_has_pa_calibration(self):
        self.assertIsNotNone(Features.PA_CALIBRATION)


class TestCommandTemplates(unittest.TestCase):
    def test_extrusion_cali_get_template_structure(self):
        cmd = copy.deepcopy(EXTRUSION_CALI_GET_TEMPLATE)
        self.assertEqual(cmd['print']['command'], 'extrusion_cali_get')
        self.assertIn('filament_id', cmd['print'])
        self.assertIn('nozzle_diameter', cmd['print'])
        self.assertIn('extruder_id', cmd['print'])

    def test_extrusion_cali_sel_template_structure(self):
        cmd = copy.deepcopy(EXTRUSION_CALI_SEL_TEMPLATE)
        self.assertEqual(cmd['print']['command'], 'extrusion_cali_sel')
        self.assertIn('tray_id', cmd['print'])
        self.assertIn('cali_idx', cmd['print'])
        self.assertIn('filament_id', cmd['print'])
        self.assertIn('nozzle_diameter', cmd['print'])

    def test_extrusion_cali_sel_default_is_minus_one(self):
        cmd = copy.deepcopy(EXTRUSION_CALI_SEL_TEMPLATE)
        self.assertEqual(cmd['print']['cali_idx'], -1)


if __name__ == '__main__':
    unittest.main()
