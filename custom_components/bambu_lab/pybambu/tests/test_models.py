import unittest
from unittest.mock import MagicMock
from datetime import datetime
import sys
import os
import json

# Add the pybambu directory to the Python path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from pybambu.models import PrintJob, Info, AMSList, HMSList, PrintError
from pybambu.const import Printers

class TestPrintJob(unittest.TestCase):
    def setUp(self):
        self.client = MagicMock()
        self.print_job = PrintJob(self.client)
        # Load test data from P1P.json
        with open(os.path.join(os.path.dirname(__file__), 'P1P.json'), 'r') as f:
            self.test_data = json.load(f)

    def test_print_update_basic(self):
        # Test basic print update with minimal data
        data = self.test_data['push_all']
        
        result = self.print_job.print_update(data)
        self.assertTrue(result)
        self.assertEqual(self.print_job.print_percentage, 0)
        self.assertEqual(self.print_job.gcode_state, "FAILED")
        self.assertEqual(self.print_job.remaining_time, 759)
        self.assertEqual(self.print_job.current_layer, 1)
        self.assertEqual(self.print_job.total_layers, 70)

class TestInfo(unittest.TestCase):
    def setUp(self):
        self.client = MagicMock()
        self.info = Info(self.client)
        # Load test data from P1P.json
        with open(os.path.join(os.path.dirname(__file__), 'P1P.json'), 'r') as f:
            self.test_data = json.load(f)

    def test_info_update_basic(self):
        # Test basic info update
        data = self.test_data['get_version']
        
        self.info.info_update(data)
        self.assertEqual(self.info.sw_ver, "01.07.00.00")

class TestAMSList(unittest.TestCase):
    def setUp(self):
        self.client = MagicMock()
        self.ams_list = AMSList(self.client)
        # Load test data from P1P.json
        with open(os.path.join(os.path.dirname(__file__), 'P1P.json'), 'r') as f:
            self.test_data = json.load(f)
        # Load H2D test data
        with open(os.path.join(os.path.dirname(__file__), 'H2D.json'), 'r') as f:
            self.h2d_data = json.load(f)

    def test_ams_info_update(self):
        # Test AMS info update
        data = self.test_data['get_version']
        
        self.ams_list.info_update(data)
        self.assertIn(0, self.ams_list.data)
        self.assertEqual(self.ams_list.data[0].sw_version, "00.00.06.49")

    def test_ams_print_update(self):
        # Test AMS print update
        data = self.test_data['push_all']
        
        result = self.ams_list.print_update(data)
        self.assertTrue(result)
        self.assertEqual(self.ams_list.tray_now, 0)
        self.assertIn(0, self.ams_list.data)

    def test_h2d_ams_detection(self):
        # Test that two AMS files are properly detected from H2D.json
        data = self.h2d_data['push_all']
        
        result = self.ams_list.print_update(data)
        self.assertTrue(result)
        
        # Verify that both AMS files are detected
        self.assertIn(0, self.ams_list.data)
        self.assertIn(128, self.ams_list.data)
        
        # Verify AMS 0 details
        ams0 = self.ams_list.data[0]
        self.assertEqual(ams0.humidity, 24)
        self.assertEqual(ams0.temperature, 26.2)
        self.assertEqual(len(ams0.tray), 4)  # Should have 4 trays
        
        # Verify AMS 1 details
        ams_ht = self.ams_list.data[128]
        self.assertEqual(ams_ht.humidity, 6)
        self.assertEqual(ams_ht.temperature, 27.9)
        self.assertEqual(len(ams_ht.tray), 1)  # Should have 4 trays
        
        # Verify tray details for AMS 0
        tray0 = ams0.tray[0]
        self.assertEqual(tray0.remain, 47)
        self.assertEqual(tray0.type, "PLA")
        self.assertEqual(tray0.color, "FFFFFFFF")
        self.assertEqual(tray0.tray_weight, "1000")

if __name__ == '__main__':
    unittest.main() 