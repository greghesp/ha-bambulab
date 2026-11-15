"""Tests for Upgrade progress handling once an upgrade has finished."""

import unittest
from unittest.mock import MagicMock

from pybambu.models import Upgrade


def _upgrade_state(status, progress="100", message="RK1126 start write flash success"):
    return {
        "upgrade_state": {
            "dis_state": 3,
            "err_code": 0,
            "ext_new_version_number": "",
            "force_upgrade": False,
            "idx": 4,
            "idx1": 3,
            "message": message,
            "module": "",
            "new_version_state": 1,
            "ota_new_version_number": "01.02.03.04",
            "progress": progress,
            "sequence_id": 0,
            "sn": "**REDACTED**",
            "status": status,
        }
    }


class TestUpgradeProgress(unittest.TestCase):
    def setUp(self):
        self.client = MagicMock()
        self.client._device.info.sw_ver = "01.02.03.00"
        self.upgrade = Upgrade(self.client)

    def test_in_progress_status_keeps_progress(self):
        self.upgrade.print_update(_upgrade_state("UPGRADE_IN_PROGRESS", progress="42", message="42%"))
        self.assertEqual(self.upgrade.upgrade_progress, 42)

    def test_success_resets_progress(self):
        self.upgrade.upgrade_progress = 100
        self.upgrade.print_update(_upgrade_state("UPGRADE_SUCCESS", progress="100", message="upgrade complete"))
        self.assertEqual(self.upgrade.upgrade_progress, 0)
        # The update entity reports "in progress" when progress > 0.
        self.assertFalse(self.upgrade.upgrade_progress > 0)

    def test_fail_resets_progress(self):
        self.upgrade.upgrade_progress = 57
        self.upgrade.print_update(_upgrade_state("UPGRADE_FAIL", progress="57", message="failed"))
        self.assertEqual(self.upgrade.upgrade_progress, 0)
        self.assertFalse(self.upgrade.upgrade_progress > 0)


if __name__ == "__main__":
    unittest.main()
