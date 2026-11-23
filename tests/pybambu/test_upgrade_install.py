"""Tests for firmware install failures being reported instead of swallowed (#2251)."""

import unittest
from unittest.mock import MagicMock, patch

import requests

from pybambu.const import Printers
from pybambu.models import FirmwareUpdateError, Upgrade
from pybambu.utils import get_upgrade_url

VALID_URL = (
    "https://public-cdn.bblmw.com/upgrade/device/offline/"
    "C11/01.08.01.00/abcdef0123/offline-01.08.01.00-20250101.zip"
)


class TestUpgradeInstall(unittest.TestCase):
    def setUp(self):
        self.client = MagicMock()
        self.client._device.info.device_type = Printers.A1
        self.upgrade = Upgrade(self.client)

    def test_install_raises_when_firmware_url_unavailable(self):
        with patch("pybambu.models.get_upgrade_url", return_value=None):
            with self.assertRaises(FirmwareUpdateError):
                self.upgrade.install()
        self.client.publish.assert_not_called()

    def test_install_raises_for_unknown_printer_model(self):
        self.client._device.info.device_type = "UNKNOWN_MODEL"
        with self.assertRaises(FirmwareUpdateError):
            self.upgrade.install()
        self.client.publish.assert_not_called()

    def test_install_raises_when_firmware_url_cannot_be_parsed(self):
        with patch("pybambu.models.get_upgrade_url", return_value="https://example.com/not-firmware"):
            with self.assertRaises(FirmwareUpdateError):
                self.upgrade.install()
        self.client.publish.assert_not_called()

    def test_install_works_without_release_url_having_been_read(self):
        # printer_name used to be set only as a side effect of release_url().
        self.assertIsNone(self.upgrade.printer_name)
        with patch("pybambu.models.get_upgrade_url", return_value=VALID_URL) as get_url:
            self.upgrade.install()
        get_url.assert_called_once_with("a1")
        self.client.publish.assert_called_once()


class TestGetUpgradeUrl(unittest.TestCase):
    def test_returns_none_on_http_error(self):
        response = MagicMock(status_code=403, text="blocked")
        with patch("pybambu.utils.requests.get", return_value=response):
            self.assertIsNone(get_upgrade_url("a1"))

    def test_returns_none_on_request_exception(self):
        with patch("pybambu.utils.requests.get", side_effect=requests.ConnectionError("down")):
            self.assertIsNone(get_upgrade_url("a1"))

    def test_uses_a_timeout(self):
        response = MagicMock(status_code=200, text="<html></html>")
        with patch("pybambu.utils.requests.get", return_value=response) as get:
            get_upgrade_url("a1")
        self.assertIn("timeout", get.call_args.kwargs)


if __name__ == "__main__":
    unittest.main()
