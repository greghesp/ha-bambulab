"""Optional frontend registration checks: run in a Home Assistant Python environment.

The lightweight pybambu CI suite does not install Home Assistant. These tests
skip when it is absent.
"""
import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

pytest.importorskip("homeassistant")

import custom_components.bambu_lab as bambu_lab
from custom_components.bambu_lab.const import (
    DOMAIN,
    ENTRY_TYPE,
    ENTRY_TYPE_FILAMENT_INVENTORY,
    ENTRY_TYPE_MAKERWORLD,
)
from custom_components.bambu_lab.frontend import (
    BambuLabCardRegistration,
    find_external_card_resources,
)

FILENAME = "ha-bambulab-cards.js"
HACS_URL = "/hacsfiles/ha-bambulab-cards/ha-bambulab-cards.js?hacstag=123"
CARDS_URL = "/bambu_lab/ha-bambulab-cards.js"
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

    # A subclass, so that the property isn't replaced for the other tests too.
    class Registration(BambuLabCardRegistration):
        lovelace_resources = resources

    return Registration(MagicMock()), resources


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


class FakeLazyResources:
    """Mimics Home Assistant's resource collection, which loads on first use."""

    def __init__(self, items=()):
        self._stored = list(items)
        self._items = []
        self._loading = None
        self.loaded = False

    async def _async_read(self):
        # Like Home Assistant's Store, concurrent reads wait for the first one.
        if self._loading:
            await self._loading
            return
        self._loading = asyncio.get_running_loop().create_future()
        await asyncio.sleep(0.01)
        self._loading.set_result(None)
        self._loading = None

    async def async_get_info(self):
        if not self.loaded:
            await self._async_read()
            self._items = list(self._stored)
            self.loaded = True
        return {"resources": len(self._items)}

    def async_items(self):
        return list(self._items)

    async def async_create_item(self, data):
        self._items = [*self._items, {"id": "new", "url": data["url"]}]

    async def async_update_item(self, item_id, updates):
        self._items = [
            {**item, "url": updates["url"]} if item["id"] == item_id else item
            for item in self._items
        ]

    async def async_delete_item(self, item_id):
        self._items = [item for item in self._items if item["id"] != item_id]


def _lazy_registration(items=(), mode="storage"):
    resources = FakeLazyResources(items)
    hass = MagicMock()
    hass.http.async_register_static_paths = AsyncMock()
    hass.data = {"lovelace": MagicMock(resource_mode=mode, mode=mode, resources=resources)}
    return BambuLabCardRegistration(hass), resources


def _urls(resources):
    return [item["url"] for item in resources.async_items()]


def test_registers_without_waiting_for_a_browser_to_load_the_resources():
    reg, resources = _lazy_registration()
    asyncio.run(reg.async_register())
    assert [url.split("?")[0] for url in _urls(resources)] == [CARDS_URL]


def test_updates_old_version_without_waiting_for_a_browser():
    reg, resources = _lazy_registration(
        [{"id": "1", "url": f"{CARDS_URL}?v=0.0.1"}, {"id": "2", "url": "/hacsfiles/x/x.js"}]
    )
    asyncio.run(reg.async_register())
    assert len(_urls(resources)) == 2
    assert f"{CARDS_URL}?v=0.0.1" not in _urls(resources)
    assert "/hacsfiles/x/x.js" in _urls(resources)


def test_dashboard_loading_the_resources_meanwhile_does_not_undo_the_update():
    reg, resources = _lazy_registration([{"id": "1", "url": f"{CARDS_URL}?v=0.0.1"}])

    async def register_while_a_dashboard_loads():
        await asyncio.gather(reg.async_register(), resources.async_get_info())

    asyncio.run(register_while_a_dashboard_loads())
    assert len(_urls(resources)) == 1
    assert f"{CARDS_URL}?v=0.0.1" not in _urls(resources)


def test_leaves_yaml_mode_resources_alone():
    reg, resources = _lazy_registration(mode="yaml")
    asyncio.run(reg.async_register())
    assert resources.loaded is False
    assert _urls(resources) == []


def test_registration_failure_is_logged_instead_of_raised(caplog):
    reg, resources = _lazy_registration()
    resources.async_create_item = AsyncMock(side_effect=ValueError("rejected"))
    asyncio.run(reg.async_register())
    assert "rejected" in caplog.text


def test_unregister_loads_resources_first():
    reg, resources = _lazy_registration(
        [{"id": "1", "url": BUNDLED_URL}, {"id": "2", "url": "/hacsfiles/x/x.js"}]
    )
    asyncio.run(reg.async_unregister())
    assert _urls(resources) == ["/hacsfiles/x/x.js"]


def _entry(entry_id, disabled=False, entry_type=None, cards=None):
    return SimpleNamespace(
        entry_id=entry_id,
        disabled_by="user" if disabled else None,
        data={ENTRY_TYPE: entry_type} if entry_type else {"serial": entry_id},
        options={} if cards is None else {"register_cards": cards},
    )


def _hass_with(*entries):
    """Only enabled, not ignored, entries are returned, as the integration asks for."""
    hass = MagicMock()

    def async_entries(domain, include_ignore=True, include_disabled=True):
        assert not include_ignore
        return [e for e in entries if include_disabled or not e.disabled_by]

    hass.config_entries.async_entries = async_entries
    hass.config_entries.async_unload_platforms = AsyncMock(return_value=True)
    hass.data = {
        DOMAIN: {
            e.entry_id: MagicMock(async_stop_reinitialize=AsyncMock()) for e in entries
        }
    }
    return hass


@pytest.fixture
def unregister(monkeypatch):
    unregister = AsyncMock()
    monkeypatch.setattr(BambuLabCardRegistration, "async_unregister", unregister)
    return unregister


def test_reload_keeps_the_resource(unregister):
    entry = _entry("a")
    asyncio.run(bambu_lab.async_unload_entry(_hass_with(entry), entry))
    unregister.assert_not_awaited()


def test_disabling_one_of_two_printers_keeps_the_resource(unregister):
    entry = _entry("a", disabled=True)
    asyncio.run(bambu_lab.async_unload_entry(_hass_with(entry, _entry("b")), entry))
    unregister.assert_not_awaited()


def test_disabling_the_last_enabled_printer_removes_the_resource(unregister):
    entry = _entry("a", disabled=True)
    asyncio.run(
        bambu_lab.async_unload_entry(_hass_with(entry, _entry("b", disabled=True)), entry)
    )
    unregister.assert_awaited_once()


def test_removing_one_of_two_printers_keeps_the_resource(unregister):
    asyncio.run(bambu_lab.async_remove_entry(_hass_with(_entry("b")), _entry("a")))
    unregister.assert_not_awaited()


@pytest.mark.parametrize("entry_type", [ENTRY_TYPE_MAKERWORLD, ENTRY_TYPE_FILAMENT_INVENTORY])
def test_removing_the_last_printer_removes_the_resource(unregister, entry_type):
    hass = _hass_with(_entry("cloud", entry_type=entry_type))
    asyncio.run(bambu_lab.async_remove_entry(hass, _entry("a")))
    unregister.assert_awaited_once()


@pytest.mark.parametrize("entry_type", [ENTRY_TYPE_MAKERWORLD, ENTRY_TYPE_FILAMENT_INVENTORY])
def test_removing_a_cloud_entry_keeps_the_resource(unregister, entry_type):
    asyncio.run(
        bambu_lab.async_remove_entry(_hass_with(), _entry("cloud", entry_type=entry_type))
    )
    unregister.assert_not_awaited()


@pytest.fixture
def register(monkeypatch):
    register = AsyncMock()
    monkeypatch.setattr(BambuLabCardRegistration, "async_register", register)
    return register


def _update(*entries):
    asyncio.run(bambu_lab._async_update_card_registration(_hass_with(*entries)))


def test_registers_cards_by_default(register, unregister):
    _update(_entry("a"))
    register.assert_awaited_once()
    unregister.assert_not_awaited()


def test_turning_the_option_off_removes_the_resource(register, unregister):
    _update(_entry("a", cards=False))
    register.assert_not_awaited()
    unregister.assert_awaited_once()


def test_one_printer_with_the_option_on_keeps_the_cards(register, unregister):
    _update(_entry("a", cards=False), _entry("b", cards=True))
    register.assert_awaited_once()
    unregister.assert_not_awaited()


def test_disabled_printer_with_the_option_on_does_not_keep_the_cards(
    register, unregister
):
    _update(_entry("a", cards=False), _entry("b", disabled=True))
    register.assert_not_awaited()
    unregister.assert_awaited_once()


@pytest.mark.parametrize(
    "entry_type", [ENTRY_TYPE_MAKERWORLD, ENTRY_TYPE_FILAMENT_INVENTORY]
)
def test_cloud_entries_do_not_keep_the_cards(register, unregister, entry_type):
    _update(_entry("a", cards=False), _entry("cloud", entry_type=entry_type))
    register.assert_not_awaited()
    unregister.assert_awaited_once()


def test_failing_to_remove_the_cards_does_not_fail_setup(register, unregister, caplog):
    unregister.side_effect = RuntimeError("boom")
    _update(_entry("a", cards=False))
    assert "Failed to remove the Bambu Lab cards" in caplog.text


def test_removing_the_last_printer_that_wants_the_cards_removes_the_resource(
    unregister,
):
    asyncio.run(
        bambu_lab.async_remove_entry(_hass_with(_entry("b", cards=False)), _entry("a"))
    )
    unregister.assert_awaited_once()
