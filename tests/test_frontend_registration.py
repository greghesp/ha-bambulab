"""Optional frontend registration checks: run in a Home Assistant Python environment.

The lightweight pybambu CI suite does not install Home Assistant. These tests
skip when it is absent.
"""
import asyncio
from unittest.mock import AsyncMock, MagicMock

import pytest

pytest.importorskip("homeassistant")

from custom_components.bambu_lab.frontend import (
    BambuLabCardRegistration,
    find_external_card_resources,
)

FILENAME = "ha-bambulab-cards.js"
HACS_URL = "/hacsfiles/ha-bambulab-cards/ha-bambulab-cards.js?hacstag=123"
BUNDLED_URL = "/bambu_lab/ha-bambulab-cards.js?v=0.8.5"


def test_finds_hacs_copy_of_cards():
    resources = [{"id": "1", "url": HACS_URL}, {"id": "2", "url": BUNDLED_URL}]
    assert find_external_card_resources(resources, FILENAME) == [resources[0]]


def test_ignores_bundled_and_unrelated_resources():
    resources = [
        {"id": "2", "url": BUNDLED_URL},
        {"id": "3", "url": "/hacsfiles/other-card/other-card.js"},
        {"id": "4", "url": "/local/not-ha-bambulab-cards.js"},
    ]
    assert find_external_card_resources(resources, FILENAME) == []


def _registration(items):
    resources = MagicMock()
    resources.async_items.return_value = items
    resources.async_create_item = AsyncMock()
    resources.async_update_item = AsyncMock()
    resources.async_delete_item = AsyncMock()
    reg = BambuLabCardRegistration(MagicMock())
    type(reg).lovelace_resources = property(lambda self: resources)
    return reg, resources


def test_skips_and_removes_bundled_when_hacs_copy_present():
    reg, resources = _registration([{"id": "1", "url": HACS_URL}, {"id": "2", "url": BUNDLED_URL}])
    asyncio.run(reg.async_register_bambu_cards())
    resources.async_create_item.assert_not_called()
    resources.async_update_item.assert_not_called()
    resources.async_delete_item.assert_awaited_once_with("2")


def test_registers_bundled_when_no_external_copy():
    reg, resources = _registration([])
    asyncio.run(reg.async_register_bambu_cards())
    resources.async_create_item.assert_awaited_once()
    resources.async_delete_item.assert_not_called()
