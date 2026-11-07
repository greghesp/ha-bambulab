import unittest
from unittest.mock import MagicMock

from pybambu.models import PrintFun


class TestPrintFunSignatureDetection(unittest.TestCase):
    def setUp(self):
        self.client = MagicMock()
        self.fun = PrintFun(client=self.client)

    def test_fun_bit29_set_means_secured(self):
        self.fun.print_update({"fun": "20000000"})
        self.assertTrue(self.fun.mqtt_signature_required)

    def test_fun_bit29_clear_means_developer_mode(self):
        self.fun.print_update({"fun": "10000000"})
        self.assertFalse(self.fun.mqtt_signature_required)

    # 0x00010000 = 65536 - bit 16 means encryption supported, bit 4 off means encryption not required
    # 0x00010010 = 65552 - bit 16 means encryption supported, bit 4 on means encryption is required
    def test_empty_fun_with_flag3_bit4_means_secured(self):
        self.fun.print_update({"fun": "", "flag3": 65552})
        self.assertTrue(self.fun.mqtt_signature_required)

    def test_flag3_bit4_is_latched_across_incremental_frames(self):
        self.fun.print_update({"fun": "", "flag3": 65552})
        self.fun.print_update({"gcode_state": "IDLE"})
        self.assertTrue(self.fun.mqtt_signature_required)

    def test_flag3_bit4_clear_stays_unsecured(self):
        self.fun.print_update({"fun": "", "flag3": 65536})  # P1P mock value
        self.assertFalse(self.fun.mqtt_signature_required)

    def test_fun_stays_authoritative_over_flag3(self):
        self.fun.print_update({"fun": "10000000", "flag3": 65536})
        self.assertFalse(self.fun.mqtt_signature_required)

    def test_fun_secured_without_flag3(self):
        self.fun.print_update({"fun": "20000000"})
        self.assertTrue(self.fun.mqtt_signature_required)

    def test_encryption_event_fired_once_for_flag3_fallback(self):
        self.fun.print_update({"fun": "", "flag3": 65552})
        self.fun.print_update({"fun": "", "flag3": 65552})
        self.client.callback.assert_called_once_with("event_printer_mqtt_encryption_enabled")

    def test_no_data_means_not_secured(self):
        self.fun.print_update({})
        self.assertFalse(self.fun.mqtt_signature_required)
