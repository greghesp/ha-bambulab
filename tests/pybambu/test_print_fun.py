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

    def test_empty_fun_with_flag3_bit16_means_secured(self):
        # Reported on A1 mini fw 01.08.01.00 in #2135: fun == "" and flag3 == 221855 (0x3629F)
        self.fun.print_update({"fun": "", "flag3": 221855})
        self.assertTrue(self.fun.mqtt_signature_required)

    def test_flag3_bit16_is_latched_across_incremental_frames(self):
        self.fun.print_update({"fun": "", "flag3": 221855})
        self.fun.print_update({"gcode_state": "IDLE"})
        self.assertTrue(self.fun.mqtt_signature_required)

    def test_flag3_bit16_clear_stays_unsecured(self):
        self.fun.print_update({"fun": "", "flag3": 671})  # P1P mock value
        self.assertFalse(self.fun.mqtt_signature_required)

    def test_fun_stays_authoritative_over_flag3(self):
        self.fun.print_update({"fun": "10000000", "flag3": 221855})
        self.assertFalse(self.fun.mqtt_signature_required)

    def test_fun_secured_without_flag3(self):
        self.fun.print_update({"fun": "20000000"})
        self.assertTrue(self.fun.mqtt_signature_required)

    def test_encryption_event_fired_once_for_flag3_fallback(self):
        self.fun.print_update({"fun": "", "flag3": 221855})
        self.fun.print_update({"fun": "", "flag3": 221855})
        self.client.callback.assert_called_once_with("event_printer_mqtt_encryption_enabled")

    def test_no_data_means_not_secured(self):
        self.fun.print_update({})
        self.assertFalse(self.fun.mqtt_signature_required)
