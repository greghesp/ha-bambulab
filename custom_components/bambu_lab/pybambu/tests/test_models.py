import unittest
from unittest.mock import MagicMock
from datetime import datetime
import sys
import os
import json

# Add the parent directory to the Python path to find pybambu
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from pybambu.models import PrintJob, Info, AMSList, Extruder, HMSList, PrintError, Temperature
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

        # Create a _device object on the client
        self.client._device = MagicMock()
        self.client._device.extruder = Extruder(self.client._device)

        # Load test data from P1P.json
        with open(os.path.join(os.path.dirname(__file__), 'P1P.json'), 'r') as f:
            self.test_data = json.load(f)

    def test_info_update_basic(self):
        # Test basic info update
        data = self.test_data['get_version']
        
        self.info.info_update(data)
        self.assertEqual(self.info.sw_ver, "01.07.00.00")

    def test_info_update_nozzle(self):
        # Test basic info update
        data = self.test_data['push_all']

        self.client._device.extruder.print_update(data)
        self.info.print_update(data)

        self.assertEqual(self.info.active_nozzle_diameter, 0.4)
        self.assertEqual(self.info.active_nozzle_type, "hardened_steel")

class TestAMSList(unittest.TestCase):
    def setUp(self):
        self.client = MagicMock()
        # Create a _device object on the client
        self.client._device = MagicMock()
        self.client._device.extruder = Extruder(self.client._device)
        self.info = Info(self.client)
        self.ams_list = AMSList(self.client)
        # Load test data from P1P.json
        with open(os.path.join(os.path.dirname(__file__), 'P1P.json'), 'r') as f:
            self.test_data = json.load(f)
        # Load H2D test data
        with open(os.path.join(os.path.dirname(__file__), 'H2D.json'), 'r') as f:
            self.h2d_data = json.load(f)
        # Load 2AMS1-1AMS2-1AMSHT test data
        with open(os.path.join(os.path.dirname(__file__), '2AMS1-1AMS2-1AMSHT.json'), 'r') as f:
            self.multi_ams_data = json.load(f)

    def test_ams_info_update(self):
        # Test AMS info update
        data = self.test_data['get_version']
        
        self.ams_list.info_update(data)
        self.assertIn(0, self.ams_list.data)
        self.assertEqual(self.ams_list.data[0].sw_version, "00.00.06.49")

    def test_ams_print_update(self):
        # Test AMS print update
        data = self.test_data['push_all']
        
        result = self.client._device.extruder.print_update(data)
        result = self.ams_list.print_update(data)
        self.assertTrue(result)
        self.assertIn(0, self.ams_list.data)

    def test_h2d_ams_detection(self):
        # Test that two AMS files are properly detected from H2D.json
        data = self.h2d_data['push_all']
        
        result = self.client._device.extruder.print_update(data)
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

    def test_multi_ams_detection(self):
        # Test detection of 4 different AMS instances (2 AMS, 1 AMS 2 Pro, 1 AMS HT)

        # First initialize the version data as we get the model names from that.
        data = self.multi_ams_data['get_version']
        result = self.ams_list.info_update(data)

        # Verify all four AMS instances are detected
        self.assertIn(0, self.ams_list.data)  # First AMS
        self.assertIn(1, self.ams_list.data)  # Second AMS
        self.assertIn(2, self.ams_list.data)  # AMS 2 Pro
        self.assertIn(128, self.ams_list.data)  # AMS HT

        ams0 = self.ams_list.data[0]
        ams1 = self.ams_list.data[1]
        ams2 = self.ams_list.data[2]
        ams_ht = self.ams_list.data[128]

        # Verify they have the right model names
        self.assertEqual(ams0.model, "AMS")  # Verify model name
        self.assertEqual(ams1.model, "AMS")  # Verify model name
        self.assertEqual(ams2.model, "AMS 2 Pro")  # Verify model name
        self.assertEqual(ams_ht.model, "AMS HT")  # Verify model name
        

        # Now that we have the models, we can populate the sensor data from the payload.
        data = self.multi_ams_data['push_all']
        
        result = self.client._device.extruder.print_update(data)
        result = self.ams_list.print_update(data)
        self.assertTrue(result)
        
        # Verify all four AMS instances are detected
        self.assertIn(0, self.ams_list.data)  # First AMS
        self.assertIn(1, self.ams_list.data)  # Second AMS
        self.assertIn(2, self.ams_list.data)  # AMS 2 Pro
        self.assertIn(128, self.ams_list.data)  # AMS HT

        # Refresh the variables after the print_update call.
        ams0 = self.ams_list.data[0]
        ams1 = self.ams_list.data[1]
        ams2 = self.ams_list.data[2]
        ams_ht = self.ams_list.data[128]

        # Verify AMS 0 (First AMS)
        self.assertEqual(len(ams0.tray), 4)  # Should have 4 trays
        self.assertEqual(ams0.humidity, 8)
        self.assertEqual(ams0.temperature, 26.2)
        
        # Verify AMS 1 (Second AMS)
        self.assertEqual(len(ams1.tray), 4)  # Should have 4 trays
        self.assertEqual(ams1.humidity, 4)
        self.assertEqual(ams1.temperature, 25.4)
        
        # Verify AMS 2 (AMS 2 Pro)
        self.assertEqual(len(ams2.tray), 4)  # Should have 4 trays
        self.assertEqual(ams2.humidity, 9)
        self.assertEqual(ams2.temperature, 65.0)
        
        # Verify AMS HT
        self.assertEqual(len(ams_ht.tray), 1)  # Should have only 1 tray
        self.assertEqual(ams_ht.humidity, 8)
        self.assertEqual(ams_ht.temperature, 45.2)
        
        # Verify tray details for first tray in AMS 0
        tray0 = ams0.tray[0]
        self.assertEqual(tray0.remain, 93)
        self.assertEqual(tray0.type, "PLA")
        self.assertEqual(tray0.color, "000000FF")
        self.assertEqual(tray0.tray_weight, "1000")

        # Verify tray details for first tray in AMS HT
        tray0 = ams_ht.tray[0]
        self.assertEqual(tray0.remain, 100)
        self.assertEqual(tray0.type, "PA-CF")
        self.assertEqual(tray0.color, "000000FF")
        self.assertEqual(tray0.tray_weight, "1000")

class TestH2D(unittest.TestCase):
    def setUp(self):
        self.client = MagicMock()
        self.info = Info(self.client)
        self.temperature = Temperature(self.client)

        # Create a _device object on the client
        self.client._device = MagicMock()
        self.client._device.extruder = Extruder(self.client._device)

        # Load H2D test data
        with open(os.path.join(os.path.dirname(__file__), 'H2D.json'), 'r') as f:
            self.h2d_data = json.load(f)
        
        # Mock feature support
        self.client._device.supports_feature.return_value = True

    def test_h2d_nozzle_info(self):
        data = self.h2d_data['push_all']
        result = self.client._device.extruder.print_update(data)
        result = self.info.print_update(data)
        self.assertTrue(result)

        self.assertEqual(self.client._device.extruder.active_nozzle_index, 0)  # right is active
        self.assertEqual(self.info.active_nozzle_diameter, 0.4)
        self.assertEqual(self.info.active_nozzle_type, "hardened_steel")
        self.assertEqual(self.info.left_nozzle_diameter, 0.4)
        self.assertEqual(self.info.right_nozzle_diameter, 0.4)
        self.assertEqual(self.info.left_nozzle_type, "high_flow_hardened_steel")
        self.assertEqual(self.info.right_nozzle_type, "hardened_steel")

        data = self.h2d_data['push_alt_nozzle_info']
        result = self.info.print_update(data)
        self.assertEqual(self.info.active_nozzle_diameter, 0.2)
        self.assertEqual(self.info.active_nozzle_type, "stainless_steel")
        self.assertEqual(self.info.left_nozzle_diameter, 0.6)
        self.assertEqual(self.info.left_nozzle_type, "tungsten_carbide")
        self.assertEqual(self.info.right_nozzle_diameter, 0.2)
        self.assertEqual(self.info.right_nozzle_type, "stainless_steel")

        data = self.h2d_data['push_left_extruder']
        result = self.client._device.extruder.print_update(data)
        self.assertEqual(self.client._device.extruder.active_nozzle_index, 1)

        self.assertEqual(self.info.active_nozzle_diameter, 0.6)
        self.assertEqual(self.info.active_nozzle_type, "tungsten_carbide")
        self.assertEqual(self.info.left_nozzle_diameter, 0.6)
        self.assertEqual(self.info.left_nozzle_type, "tungsten_carbide")
        self.assertEqual(self.info.right_nozzle_diameter, 0.2)
        self.assertEqual(self.info.right_nozzle_type, "stainless_steel")

    def test_h2d_door_open(self):
        data = self.h2d_data['push_all']
        result = self.info.print_update(data)
        self.assertTrue(result)

        self.assertTrue(self.info.door_open_available)
        self.assertFalse(self.info.door_open)

        # On the H2D, door status is in the stat field.
        data = self.h2d_data['push_door_opened']
        result = self.info.print_update(data)
        self.assertTrue(result)
        self.assertTrue(self.info.door_open)

        # On the H2D, door status is in the stat field.
        data = self.h2d_data['push_door_closed']
        result = self.info.print_update(data)
        self.assertTrue(result)
        self.assertFalse(self.info.door_open)

    def test_h2d_door_ignores_old_flag(self):
        data = self.h2d_data['push_all']
        result = self.info.print_update(data)
        self.assertTrue(result)

        self.assertTrue(self.info.door_open_available)
        self.assertFalse(self.info.door_open)

        # On the H2D, door status is in the stat field, not home_flag.
        data = self.h2d_data['push_old_door_opened']
        _ = self.info.print_update(data)
        self.assertFalse(self.info.door_open)

        data = self.h2d_data['push_old_door_closed']
        _ = self.info.print_update(data)
        self.assertFalse(self.info.door_open)


    def test_h2d_nozzles(self):
        data = self.h2d_data['push_all']
        result = self.temperature.print_update(data)
        self.assertTrue(result)

        # Test right nozzle (index 0) temperatures
        self.assertEqual(self.temperature.right_nozzle_temperature, 264)
        self.assertEqual(self.temperature.right_nozzle_target_temperature, 225)

        # Test left nozzle (index 1) temperatures
        self.assertEqual(self.temperature.left_nozzle_temperature, 40)
        self.assertEqual(self.temperature.left_nozzle_target_temperature, 0)


    

if __name__ == '__main__':
    unittest.main() 