"""
Tests for get_hms_error_text and get_print_error_text.

Correctness may be affected by an update to the error_text.json; if this occurs
simply update the text or select a different locale, printer serial number, etc.
"""
import unittest
import os
import sys

# Add the parent directory to the Python path to find pybambu
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

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