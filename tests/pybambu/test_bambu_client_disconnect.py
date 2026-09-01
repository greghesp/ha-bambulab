import unittest
from unittest.mock import MagicMock

from pybambu.bambu_client import BambuClient


class TestAccessDeniedDisconnect(unittest.TestCase):
    """CONNACK code 5 means the printer rejected the access code - typically because a
    factory reset regenerated it. The client already stops retrying in that case; these
    pin the event that lets the integration layer react (refresh the code from Bambu
    Cloud, or raise a repair issue)."""

    def setUp(self):
        self.client = BambuClient({
            'host': '192.0.2.10',
            'serial': 'TESTSERIAL123',
            'enable_camera': False,
        })
        self.events = []
        self.client._callback = self.events.append
        self.client.client = MagicMock()

    def test_access_denied_fires_the_event(self):
        self.client.on_disconnect(client_=None, userdata=None, result_code=5)

        self.assertIn("event_printer_access_denied", self.events)

    def test_other_error_codes_do_not_fire_it(self):
        self.client.on_disconnect(client_=None, userdata=None, result_code=16)

        self.assertNotIn("event_printer_access_denied", self.events)

    def test_a_repeated_access_denied_fires_the_event_once(self):
        self.client.on_disconnect(client_=None, userdata=None, result_code=5)
        self.client.on_disconnect(client_=None, userdata=None, result_code=5)

        self.assertEqual(self.events.count("event_printer_access_denied"), 1)
