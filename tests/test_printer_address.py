"""A printer that moved to a new IP address is found again through Bambu Cloud (issue #1954).

Run in a Home Assistant Python environment; skips when Home Assistant is absent.
"""
import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

pytest.importorskip("homeassistant")

from custom_components.bambu_lab import config_flow, printer_address
from custom_components.bambu_lab import coordinator as coordinator_module
from custom_components.bambu_lab.config_flow import BambuOptionsFlowHandler
from custom_components.bambu_lab.coordinator import BambuDataUpdateCoordinator

SERIAL = "TESTSERIAL"
OLD_IP = "192.0.2.196"
NEW_IP = "192.0.2.198"
DATA = {"serial": SERIAL, "device_type": "P1S"}
OPTIONS = {
    "name": "P1S",
    "region": "NorthAmerica",
    "email": "user@example.com",
    "username": "u_1",
    "auth_token": "token",
    "access_code": "11111111",
    "host": OLD_IP,
    "local_mqtt": True,
    "force_ip": False,
}
UNREACHABLE = "event_printer_unreachable"
ACCESS_DENIED = "event_printer_access_denied"


class _Network:
    """The cloud account and the local network, as the integration sees them."""

    def __init__(self):
        self.device = {"dev_id": SERIAL, "dev_access_code": "11111111", "online": True}
        self.devices = [{"dev_id": "OTHER", "dev_access_code": "99999999", "online": True}, self.device]
        self.reported_ip = NEW_IP
        self.cloud_result = 0
        self.printer_at = (NEW_IP, "11111111")
        self.tested = []

    def client(self, config):
        async def try_connection():
            if not config["local_mqtt"]:
                self.tested.append("cloud")
                return self.cloud_result
            target = (config["host"], config["access_code"])
            self.tested.append(target)
            return 0 if target == self.printer_at else -1

        info = SimpleNamespace(ip_address=self.reported_ip)
        return SimpleNamespace(
            try_connection=try_connection,
            get_device=lambda: SimpleNamespace(info=info))


@pytest.fixture
def network(monkeypatch):
    network = _Network()

    def cloud(*args):
        return SimpleNamespace(get_device_list=lambda: network.devices)

    monkeypatch.setattr(printer_address, "BambuClient", network.client)
    monkeypatch.setattr(printer_address, "BambuCloud", cloud)
    monkeypatch.setattr(coordinator_module, "BambuCloud", cloud)
    return network


def _lookup(**options):
    return printer_address.find_moved_printer(DATA, {**OPTIONS, **options})


def test_new_address_is_found(network):
    assert _lookup() == {"host": NEW_IP, "access_code": "11111111"}


def test_access_code_that_changed_along_with_the_address_is_picked_up(network):
    network.device["dev_access_code"] = "22222222"
    network.printer_at = (NEW_IP, "22222222")

    assert _lookup() == {"host": NEW_IP, "access_code": "22222222"}


def test_stored_access_code_is_kept_when_the_cloud_has_none(network):
    network.device["dev_access_code"] = ""

    assert _lookup() == {"host": NEW_IP, "access_code": "11111111"}


def test_address_that_does_not_answer_locally_is_not_used(network):
    network.printer_at = None

    assert _lookup() is None


def test_unchanged_address_is_left_alone(network):
    network.reported_ip = OLD_IP

    assert _lookup() is None
    assert network.tested == ["cloud"]


@pytest.mark.parametrize("ip", ["", "0.0.0.0"])
def test_printer_without_a_reported_address_is_left_alone(network, ip):
    network.reported_ip = ip

    assert _lookup() is None
    assert network.tested == ["cloud"]


def test_switched_off_printer_is_not_contacted(network):
    network.device["online"] = False

    assert _lookup() is None
    assert network.tested == []


def test_failed_cloud_connection_changes_nothing(network):
    network.cloud_result = -1

    assert _lookup() is None
    assert network.tested == ["cloud"]


@pytest.mark.parametrize("devices", [None, [], [{"dev_id": "OTHER", "online": True}]])
def test_printer_missing_from_the_account_changes_nothing(network, devices):
    network.devices = devices

    assert _lookup() is None
    assert network.tested == []


@pytest.mark.parametrize("options", [
    {"auth_token": ""},
    {"force_ip": True},
    {"local_mqtt": False},
    {"host": "printer.example.com"},
])
def test_entries_the_lookup_does_not_apply_to(network, options):
    assert _lookup(**options) is None
    assert network.tested == []


@pytest.fixture
def coordinator():
    coordinator = object.__new__(BambuDataUpdateCoordinator)
    coordinator._shutdown = False
    coordinator._access_denied_handled = False
    coordinator._next_address_lookup = 0.0
    coordinator._address_lookup_running = False
    coordinator.config_entry = SimpleNamespace(entry_id="entry", data=DATA, options=dict(OPTIONS))

    def update_entry(entry, *, data, options):
        entry.options = options

    coordinator._hass = coordinator.hass = MagicMock()
    coordinator._hass.config_entries.async_update_entry.side_effect = update_entry
    coordinator._hass.config_entries.async_reload = AsyncMock()
    coordinator._report_access_code_rejected_issue = MagicMock()
    return coordinator


def _send(coordinator, *events, before_lookup_ends=lambda: None):
    async def run():
        loop = asyncio.get_running_loop()
        tasks = []
        coordinator._hass.async_add_executor_job = (
            lambda func, *args: loop.run_in_executor(None, func, *args))
        coordinator._hass.async_create_task = lambda coro, *args, **kwargs: tasks.append(loop.create_task(coro))
        coordinator._hass.async_create_background_task = coordinator._hass.async_create_task
        for event in events:
            coordinator.event_handler_internal(event)
        before_lookup_ends()
        await asyncio.gather(*tasks)

    asyncio.run(run())


def test_unreachable_printer_is_moved_to_its_new_address(coordinator, network):
    _send(coordinator, UNREACHABLE)

    assert coordinator.config_entry.options == {**OPTIONS, "host": NEW_IP}
    coordinator._hass.config_entries.async_reload.assert_awaited_once_with("entry")


def test_unreachable_printer_at_the_same_address_is_not_reloaded(coordinator, network):
    network.reported_ip = OLD_IP

    _send(coordinator, UNREACHABLE)

    coordinator._hass.config_entries.async_update_entry.assert_not_called()
    coordinator._hass.config_entries.async_reload.assert_not_awaited()


def test_lookups_are_spaced_out(coordinator, network, monkeypatch):
    clock = SimpleNamespace(now=1000.0)
    monkeypatch.setattr(coordinator_module, "time", SimpleNamespace(monotonic=lambda: clock.now))
    network.reported_ip = OLD_IP

    _send(coordinator, UNREACHABLE)
    _send(coordinator, UNREACHABLE)
    assert network.tested == ["cloud"]

    clock.now += coordinator_module.ADDRESS_LOOKUP_INTERVAL
    _send(coordinator, UNREACHABLE)
    assert network.tested == ["cloud", "cloud"]


def test_entry_unloaded_during_the_lookup_is_not_touched(coordinator, network):
    def unload():
        coordinator._shutdown = True

    _send(coordinator, UNREACHABLE, before_lookup_ends=unload)

    coordinator._hass.config_entries.async_update_entry.assert_not_called()


def test_access_denied_by_another_printer_on_the_old_address(coordinator, network):
    _send(coordinator, ACCESS_DENIED)

    assert coordinator.config_entry.options["host"] == NEW_IP
    coordinator._hass.config_entries.async_reload.assert_awaited_once_with("entry")


def test_only_one_lookup_runs_at_a_time(coordinator, network):
    _send(coordinator, UNREACHABLE, ACCESS_DENIED)

    assert network.tested.count("cloud") == 1
    coordinator._hass.config_entries.async_reload.assert_awaited_once_with("entry")


def test_failing_lookup_is_logged_and_can_run_again(coordinator, network, monkeypatch, caplog):
    def fail(data, options):
        raise KeyError("devices")

    with monkeypatch.context() as patch:
        patch.setattr(coordinator_module, "find_moved_printer", fail)
        _send(coordinator, UNREACHABLE)
    assert "devices" in caplog.text
    coordinator._hass.config_entries.async_reload.assert_not_awaited()

    coordinator._next_address_lookup = 0.0
    _send(coordinator, UNREACHABLE)
    assert coordinator.config_entry.options["host"] == NEW_IP


def test_access_denied_at_the_right_address_changes_nothing(coordinator, network):
    network.reported_ip = OLD_IP

    _send(coordinator, ACCESS_DENIED)

    coordinator._hass.config_entries.async_update_entry.assert_not_called()
    coordinator._report_access_code_rejected_issue.assert_not_called()


def _access_code_in_form(monkeypatch, cloud_code, user_input=None):
    """The access code the reconfigure form shows. The printer refuses any code submitted."""
    def client(config):
        info = SimpleNamespace(ip_address=NEW_IP)
        return SimpleNamespace(
            try_connection=AsyncMock(return_value=5 if config["local_mqtt"] else 0),
            get_device=lambda: SimpleNamespace(info=info))

    monkeypatch.setattr(config_flow, "BambuClient", client)
    flow = BambuOptionsFlowHandler(SimpleNamespace(data=DATA, options=dict(OPTIONS)))
    flow.hass = MagicMock()
    flow.hass.async_add_executor_job = AsyncMock(
        return_value=[{"dev_id": SERIAL, "name": "P1S", "dev_access_code": cloud_code}])

    result = asyncio.run(flow.async_step_Bambu_Lan(user_input))

    return next(key.default() for key in result["data_schema"].schema if key == "access_code")


def test_form_shows_the_current_code_from_the_cloud(monkeypatch):
    assert _access_code_in_form(monkeypatch, "22222222") == "22222222"


def test_form_shows_the_stored_code_when_the_cloud_has_none(monkeypatch):
    assert _access_code_in_form(monkeypatch, "") == "11111111"


def test_form_keeps_the_typed_code_after_an_error(monkeypatch):
    user_input = {
        "host": NEW_IP,
        "access_code": "33333333",
        "local_mqtt": True,
        "print_cache_count": "1",
        "timelapse_cache_count": "1",
        "usage_hours": "0",
        "advanced": {"disable_ssl_verify": False, "enable_firmware_update": False},
    }

    assert _access_code_in_form(monkeypatch, "22222222", user_input) == "33333333"
