"""Optional checks that entity reinitialization passes never overlap (#2337).

Run in a Home Assistant Python environment; they skip when it is absent. No MQTT
connection is made.

A reconnecting printer can fire event_printer_ready several times in quick succession.
Adding or removing an RTSP camera awaits go2rtc, so overlapping passes used to tear an
entity down while another pass was still adding it. That left a camera state nobody
owned, and the next pass registered the camera again under a numbered entity ID.
"""
import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

pytest.importorskip("homeassistant")

import custom_components.bambu_lab as integration
from custom_components.bambu_lab import coordinator as coordinator_module
from custom_components.bambu_lab.const import DOMAIN, PLATFORMS
from custom_components.bambu_lab.coordinator import BambuDataUpdateCoordinator


class _ConfigEntries:
    """Forwards platforms the way HA does, yielding to the event loop while it works."""

    def __init__(self):
        self.loaded = set(PLATFORMS)
        self.busy = 0
        self.overlaps = []
        self.unloads = 0
        self.setups = 0
        self.fail_next_setup = False

    def _enter(self, operation):
        if self.busy:
            self.overlaps.append(operation)
        self.busy += 1

    async def wait_for_setup(self):
        while not self.setups:
            await asyncio.sleep(0)

    async def async_forward_entry_unload(self, entry, platform):
        self._enter(f"unload {platform}")
        self.unloads += 1
        await asyncio.sleep(0)
        self.loaded.discard(platform)
        self.busy -= 1
        return True

    async def async_unload_platforms(self, entry, platforms):
        self._enter("integration unload")
        await asyncio.sleep(0)
        self.loaded -= set(platforms)
        self.busy -= 1
        return True

    async def async_forward_entry_setups(self, entry, platforms):
        self._enter("setup")
        self.setups += 1
        try:
            await asyncio.sleep(0.01)
            if self.fail_next_setup:
                self.fail_next_setup = False
                raise ValueError("setup failed")
            already_loaded = self.loaded & set(platforms)
            if already_loaded:
                self.overlaps.append(f"setup of loaded platforms {already_loaded}")
            self.loaded |= set(platforms)
        finally:
            self.busy -= 1


@pytest.fixture
def make_coordinator(monkeypatch):
    monkeypatch.setattr(coordinator_module.device_registry, "async_get", lambda hass: MagicMock())
    monkeypatch.setattr(
        coordinator_module.device_registry, "async_entries_for_config_entry", lambda registry, entry_id: []
    )

    def make():
        tasks = []

        def create_task(coro):
            task = asyncio.get_running_loop().create_task(coro)
            tasks.append(task)
            return task

        entries = _ConfigEntries()
        coordinator = object.__new__(BambuDataUpdateCoordinator)
        coordinator.hass = coordinator._hass = SimpleNamespace(
            config_entries=entries, async_create_task=create_task
        )
        coordinator.config_entry = SimpleNamespace(
            entry_id="entry", data={"serial": "SERIAL", "device_type": "H2C"}, disabled_by=None
        )
        coordinator._shutdown = False
        coordinator._reinitialize_requested = False
        coordinator._reinitialize_lock = asyncio.Lock()
        coordinator.get_model = lambda: SimpleNamespace(
            ams=SimpleNamespace(data={}), ams_identities_resolved=True, supports_feature=lambda feature: True
        )
        coordinator._update_device_info = lambda: None
        coordinator.cleanups = []
        coordinator._remove_dead_entities = lambda: coordinator.cleanups.append(
            entries.busy == 0 and entries.loaded == set(PLATFORMS)
        )

        async def settle():
            while any(not task.done() for task in tasks):
                await asyncio.sleep(0.005)
            await asyncio.gather(*tasks, return_exceptions=True)

        return coordinator, entries, settle

    return make


def test_ready_events_during_a_pass_do_not_overlap_it(make_coordinator):
    async def run():
        coordinator, entries, settle = make_coordinator()
        coordinator._printer_ready()
        for _ in range(3):
            await asyncio.sleep(0)
            coordinator._printer_ready()
        await settle()
        return coordinator, entries

    coordinator, entries = asyncio.run(run())

    assert entries.overlaps == []
    assert entries.loaded == set(PLATFORMS)


def test_dead_entity_cleanup_only_runs_with_every_platform_set_up(make_coordinator):
    async def run():
        coordinator, entries, settle = make_coordinator()
        coordinator._printer_ready()
        await entries.wait_for_setup()
        coordinator._printer_ready()
        await settle()
        return coordinator

    coordinator = asyncio.run(run())

    assert coordinator.cleanups and all(coordinator.cleanups)


def test_ready_events_during_a_pass_share_one_follow_up_pass(make_coordinator):
    async def run():
        coordinator, entries, settle = make_coordinator()
        coordinator._printer_ready()
        await asyncio.sleep(0)
        for _ in range(5):
            coordinator._printer_ready()
        await settle()
        return entries

    entries = asyncio.run(run())

    # The follow-up is needed: the model may have changed after the first pass read it.
    assert entries.setups == 2


def test_a_failed_pass_does_not_block_the_next_one(make_coordinator):
    async def run():
        coordinator, entries, settle = make_coordinator()
        entries.fail_next_setup = True
        coordinator._printer_ready()
        await settle()
        coordinator._printer_ready()
        await settle()
        return entries

    entries = asyncio.run(run())

    assert entries.setups == 2
    assert entries.loaded == set(PLATFORMS)


def test_a_failed_pass_still_runs_the_requested_follow_up(make_coordinator):
    async def run():
        coordinator, entries, settle = make_coordinator()
        entries.fail_next_setup = True
        coordinator._printer_ready()
        await asyncio.sleep(0)
        coordinator._printer_ready()
        await settle()
        return entries

    entries = asyncio.run(run())

    assert entries.setups == 2
    assert entries.loaded == set(PLATFORMS)


def test_no_follow_up_pass_starts_after_shutdown(make_coordinator):
    async def run():
        coordinator, entries, settle = make_coordinator()
        coordinator._printer_ready()
        await entries.wait_for_setup()
        coordinator._printer_ready()
        coordinator._shutdown = True
        await settle()
        return entries

    entries = asyncio.run(run())

    assert entries.setups == 1
    assert entries.unloads == len(PLATFORMS)


async def _unload_integration(monkeypatch, coordinator):
    cards = MagicMock()
    cards.async_unregister = AsyncMock()
    monkeypatch.setattr(integration, "BambuLabCardRegistration", lambda hass: cards)
    coordinator.shutdown = lambda: None
    hass = coordinator.hass
    hass.data = {DOMAIN: {"entry": coordinator}}
    assert await integration.async_unload_entry(hass, coordinator.config_entry)


@pytest.mark.parametrize("phase", ["unload", "setup"])
def test_unloading_the_integration_waits_for_the_pass_in_progress(make_coordinator, monkeypatch, phase):
    async def run():
        coordinator, entries, settle = make_coordinator()
        coordinator._printer_ready()
        await asyncio.sleep(0)
        if phase == "setup":
            await entries.wait_for_setup()
        await _unload_integration(monkeypatch, coordinator)
        await settle()
        return coordinator, entries

    coordinator, entries = asyncio.run(run())

    assert entries.overlaps == []
    assert entries.loaded == set()
    assert coordinator.cleanups == []
    # A pass that has not set the platforms up again yet must not start doing so.
    assert entries.setups == (1 if phase == "setup" else 0)


def test_unloading_the_integration_does_not_wait_forever(make_coordinator, monkeypatch):
    async def run():
        coordinator, entries, settle = make_coordinator()
        monkeypatch.setattr(coordinator_module, "REINITIALIZE_STOP_TIMEOUT", 0.01, raising=False)
        await coordinator._reinitialize_lock.acquire()
        await asyncio.wait_for(_unload_integration(monkeypatch, coordinator), 1)
        return entries

    assert asyncio.run(run()).loaded == set()
