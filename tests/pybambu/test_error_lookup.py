"""
Tests for get_hms_error_text and get_print_error_text.

Correctness may be affected by an update to the error_text.json; if this occurs
simply update the text or select a different locale, printer serial number, etc.
"""
import unittest
from unittest.mock import patch

from pybambu.const import Printers
from pybambu.utils import get_HMS_error_text, get_print_error_text

class TestErrorLookup(unittest.TestCase):
    def test_exact_hms_error_lookup(self):
        """When the specific HMS error code is known, the correct message is returned."""
        self.assertEqual(
            "O Motor-A tem um curto-circuito. Pode ter falhado.",
            get_HMS_error_text("0300_0600_0001_0002", Printers.H2S, "pt-BR"),
            )

        self.assertEqual(
            "Unformatierte SD-Karte. Bitte formatieren.",
            get_HMS_error_text("0500_0100_0003_0006", Printers.A1MINI, "de"),
            )

    def test_exact_print_error_lookup(self):
        """When the specific print error code is known, the correct message is returned."""
        self.assertEqual(
            "Erro detectado no tapete.",
            get_print_error_text("0500_4054", Printers.H2S, "pt-BR"),
            )

        self.assertEqual(
            "Por favor, inserte una tarjeta SD y reinicie la impresión.",
            get_print_error_text("0500400C", Printers.A1, "es"),
            )

    def test_language_fallback(self):
        """The base language (de) is used when the locale (de-CH) is not found"""
        self.assertEqual(
            "Die Empfindlichkeit des Kraftsensors 1 ist zu niedrig. Die elektrische Verbindung ist vielleicht kaputt.",
            get_HMS_error_text("03000A0000010003", Printers.H2S, "de-CH"),
            )
        
    def test_english_fallback(self):
        """English is used when the language is not found"""
        self.assertEqual(
            "The temperature sensor of the Laser Module may have a short circuit.",
            get_HMS_error_text("0300950000010001", Printers.H2S, "he"),
            )

    def test_model_fallback(self):
        """A fallback to another printer type occurs when appropriate, preferring the same language"""

        # dev_id prefix is not in the error_text.json file
        self.assertEqual(
            "Die Empfindlichkeit des Kraftsensors 1 ist zu niedrig. Die elektrische Verbindung ist vielleicht kaputt.",
            get_HMS_error_text("03000A0000010003", "unknown", "de-CH"),
            )

        # error is not known for H2S but known for the fallback model (H2D)
        self.assertEqual(
            "Das rechte Seitenfenster scheint ge\u00f6ffnet zu sein. Die Aufgabe wurde pausiert.",
            get_HMS_error_text("0300990000010001", Printers.H2S, "de")
        )

    def test_unknown(self):
        """The default of 'unknown' is printed when appropriate"""
        self.assertEqual(
            "unknown",
            get_HMS_error_text("1234_1234_1234_1234", Printers.H2S, "xx-YY"),
            )

class TestH3CErrorLookup(unittest.TestCase):
    def test_h3c_ams_3h_messages(self):
        cases = {
            "2A00_2800_0002_0004": "AMS 3H slot 9",
            "2A00_2500_0002_0004": "AMS 3H slot 6",
            "2A00_2000_0002_0004": "AMS 3H slot 1",
            "2A00_2000_0002_0008": "returned filament",
            "2A00_2000_0002_0001": "AMS 3H slot 1",
            "2A00_2000_0003_0001": "AMS 3H slot 1",
            "2A00_2600_0002_0001": "AMS 3H slot 7",
            "2A00_2600_0003_0001": "AMS 3H slot 7",
        }
        for code, expected in cases.items():
            with self.subTest(code=code):
                self.assertIn(expected, get_HMS_error_text(code, Printers.H3C, "en"))
                self.assertEqual(
                    get_HMS_error_text(code, Printers.H3C, "en"),
                    get_HMS_error_text(code, Printers.H3C, "xx-YY"),
                )

    def test_model_override_precedes_alphabetically_earlier_default(self):
        # Generated JSON is sorted; a default must not hide a model override.
        from pybambu.utils import _get_error_text
        data = {"device_hms": {"1234000000020001": {
            "A generic message": [], "Z model-specific message": ["H3C"],
        }}}
        _get_error_text.cache_clear()
        try:
            with patch("pybambu.utils._load_error_data", return_value=data):
                self.assertEqual("Z model-specific message", get_HMS_error_text("1234000000020001", Printers.H3C, "en"))
                self.assertEqual("A generic message", get_HMS_error_text("1234000000020001", Printers.H2C, "en"))
        finally:
            _get_error_text.cache_clear()
