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


if __name__ == '__main__':
    unittest.main() 