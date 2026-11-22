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

    def test_flag3_bit4_is_kept_across_incremental_frames(self):
        self.fun.print_update({"fun": "", "flag3": 65552})
        self.fun.print_update({"gcode_state": "IDLE"})
        self.assertTrue(self.fun.mqtt_signature_required)

    # Values from a P1S in issue #2255: developer mode off -> on clears only bit 4.
    def test_flag3_bit4_clearing_turns_signature_requirement_off(self):
        self.fun.print_update({"fun": "", "flag3": 90783})  # 0x1629F, developer mode off
        self.assertTrue(self.fun.mqtt_signature_required)
        self.fun.print_update({"fun": "", "flag3": 90767})  # 0x1628F, developer mode on
        self.assertFalse(self.fun.mqtt_signature_required)

    def test_flag3_bit4_setting_again_turns_signature_requirement_back_on(self):
        self.fun.print_update({"fun": "", "flag3": 90767})
        self.fun.print_update({"fun": "", "flag3": 90783})
        self.assertTrue(self.fun.mqtt_signature_required)

    def test_disabled_event_fired_when_signature_requirement_clears(self):
        self.fun.print_update({"fun": "", "flag3": 90783})
        self.client.callback.reset_mock()
        self.fun.print_update({"fun": "", "flag3": 90767})
        self.client.callback.assert_called_once_with("event_printer_mqtt_encryption_disabled")

    def test_disabled_event_fired_when_fun_bit29_clears(self):
        self.fun.print_update({"fun": "20000000"})
        self.client.callback.reset_mock()
        self.fun.print_update({"fun": "10000000"})
        self.client.callback.assert_called_once_with("event_printer_mqtt_encryption_disabled")

    def test_no_disabled_event_when_never_secured(self):
        self.fun.print_update({"fun": "", "flag3": 90767})
        self.fun.print_update({"fun": "", "flag3": 90767})
        self.client.callback.assert_not_called()

    def test_enabled_event_fires_again_after_requirement_returns(self):
        self.fun.print_update({"fun": "", "flag3": 90783})
        self.fun.print_update({"fun": "", "flag3": 90767})
        self.client.callback.reset_mock()
        self.fun.print_update({"fun": "", "flag3": 90783})
        self.client.callback.assert_called_once_with("event_printer_mqtt_encryption_enabled")

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
