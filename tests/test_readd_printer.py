"""Optional re-add printer checks: run in a Home Assistant Python environment.

The lightweight pybambu CI suite does not install Home Assistant, so these
tests skip when it is absent.

Re-adding a registered printer replaces its config entry. Before HA 2026.9 a
device can also belong to other integrations' entries, which must be kept.
"""
import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

pytest.importorskip("homeassistant")

from custom_components.bambu_lab import config_flow
from custom_components.bambu_lab.config_flow import BambuLabFlowHandler
from custom_components.bambu_lab.const import DOMAIN, ENTRY_TYPE, ENTRY_TYPE_MAKERWORLD

PRINTER = {
    "dev_id": "SERIAL1",
    "name": "X1C",
    "dev_product_name": "X1 Carbon",
    "dev_access_code": "12345678",
}
USER_INPUT = {
    "skip_local_mqtt": True,
    "access_code": "12345678",
    "print_cache_count": "100",
    "timelapse_cache_count": "1",
    "usage_hours": "0",
    "advanced": {"disable_ssl_verify": False, "enable_firmware_update": False},
}


def _entry(entry_id, domain=DOMAIN, **data):
    return SimpleNamespace(entry_id=entry_id, domain=domain, data=data)


PRINTER_ENTRY = _entry("printer", serial="SERIAL1")
DUPLICATE_ENTRY = _entry("duplicate", serial="SERIAL1")
SECOND_PRINTER_ENTRY = _entry("second_printer", serial="SERIAL2")
MAKERWORLD_ENTRY = _entry("makerworld", **{ENTRY_TYPE: ENTRY_TYPE_MAKERWORLD})
OTHER_INTEGRATION_ENTRY = _entry("other", domain="battery_notes", serial="SERIAL1")
ALL_ENTRIES = [
    PRINTER_ENTRY,
    SECOND_PRINTER_ENTRY,
    MAKERWORLD_ENTRY,
    OTHER_INTEGRATION_ENTRY,
]


def _readd(monkeypatch, entries, show_existing=True, remove_error=None):
    """Re-add PRINTER; returns (removed entry ids, created entry)."""
    # The shape of a pre-2026.9 device shared with another integration.
    device = SimpleNamespace(
        identifiers={(DOMAIN, "SERIAL1")}, config_entries={"printer", "other"}
    )
    monkeypatch.setattr(
        config_flow, "_async_get_printer_device", lambda hass, serial: device
    )
    client = MagicMock(try_connection=AsyncMock(return_value=0))
    monkeypatch.setattr(config_flow, "BambuClient", lambda config: client)

    async def run_in_executor(func, *args):
        return func(*args)

    flow = BambuLabFlowHandler()
    flow.hass = MagicMock()
    flow.hass.async_add_executor_job = run_in_executor
    flow.hass.config_entries.async_entries = lambda domain: [
        entry for entry in entries if entry.domain == domain
    ]
    flow.hass.config_entries.async_remove = AsyncMock(side_effect=remove_error)
    flow._bambu_cloud = MagicMock(username="u_1", auth_token="token")
    flow._bambu_cloud.get_device_list.return_value = [PRINTER]
    flow.serial = "SERIAL1"
    flow._show_existing = show_existing
    flow.async_create_entry = lambda **kwargs: kwargs

    created = asyncio.run(flow.async_step_Bambu_Lan(dict(USER_INPUT)))
    removed = [call.args[0] for call in flow.hass.config_entries.async_remove.await_args_list]
    return removed, created


def test_readding_removes_only_the_printers_own_entry(monkeypatch):
    removed, created = _readd(monkeypatch, ALL_ENTRIES)

    assert removed == ["printer"]
    assert created["data"]["serial"] == "SERIAL1"


def test_readding_removes_duplicate_entries_for_the_printer(monkeypatch):
    removed, _ = _readd(monkeypatch, [*ALL_ENTRIES, DUPLICATE_ENTRY])

    assert sorted(removed) == ["duplicate", "printer"]


def test_adding_a_new_printer_removes_nothing(monkeypatch):
    removed, _ = _readd(monkeypatch, ALL_ENTRIES, show_existing=False)

    assert removed == []


def test_failed_removal_still_creates_the_entry(monkeypatch):
    removed, created = _readd(monkeypatch, ALL_ENTRIES, remove_error=RuntimeError("boom"))

    assert removed == ["printer"]
    assert created["title"] == "SERIAL1"
