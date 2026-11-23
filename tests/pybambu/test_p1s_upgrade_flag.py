"""P1P printers fitted with the P1S upgrade kit report it via home_flag bits."""
from unittest.mock import MagicMock

from pybambu.const import Home_Flag_Values
from pybambu.models import HomeFlag


def _home_flag(value: int) -> HomeFlag:
    flag = HomeFlag(MagicMock())
    flag.print_update({"home_flag": value})
    return flag


def test_upgrade_installed_when_installed_plus_bit_set():
    flag = _home_flag(Home_Flag_Values.SUPPORTED_PLUS | Home_Flag_Values.INSTALLED_PLUS)
    assert flag.p1s_upgrade_supported
    assert flag.p1s_upgrade_installed


def test_upgrade_not_installed_when_only_supported_bit_set():
    flag = _home_flag(Home_Flag_Values.SUPPORTED_PLUS)
    assert flag.p1s_upgrade_supported
    assert not flag.p1s_upgrade_installed


def test_upgrade_installed_handles_negative_home_flag():
    # Printers report home_flag as a signed 32-bit int, e.g. -1066934785.
    flag = _home_flag(-1066934785)
    assert flag.p1s_upgrade_installed == ((-1066934785 & 0x04000000) != 0)
