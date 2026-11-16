"""H3C rack movement and safety checks."""

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from pybambu.const import Printers
from pybambu.models import HotendRack, Info


@pytest.fixture
def rack():
    client = MagicMock()
    client.publish.return_value = True
    client._device = SimpleNamespace(
        info=SimpleNamespace(device_type=Printers.H3C, online=True),
        print_job=SimpleNamespace(gcode_state="IDLE"),
        print_fun=SimpleNamespace(mqtt_signature_required=False),
        has_full_printer_data=True,
        supports_feature=lambda feature: True,
    )
    return HotendRack(client)


def ready(rack):
    rack.print_update({"gcode_state": "IDLE", "device": {"holder": {"stat": 0, "job": 0, "pos": 2}}})


@pytest.mark.parametrize("direction,action", [("up", 1), ("down", 2)])
def test_movement_commands_and_pending_guard(rack, direction, action):
    ready(rack)
    assert rack.can_move
    assert rack.move(direction)
    rack._client.publish.assert_called_once_with({"print": {
        "command": "nozzle_holder_ctrl", "sequence_id": "0", "action": action,
    }})
    assert not rack.can_move
    assert not rack.move("up")
    rack.print_update({"device": {"holder": {"stat": 11, "job": 5}}})
    assert not rack.can_move
    rack.print_update({"device": {"holder": {"stat": 0, "job": 0}}})
    assert rack.can_move


def test_missing_and_invalid_telemetry_never_assumes_idle(rack):
    assert not rack.can_move
    rack.print_update({"gcode_state": "IDLE", "device": {"holder": {"stat": 0}}})
    assert not rack.can_move
    rack.print_update({"device": {"holder": {"job": 0}}})
    assert rack.can_move
    rack.print_update({"device": {"holder": {"stat": True}}})
    assert not rack.can_move
    rack.print_update({"device": {"holder": {"stat": 0, "job": None}}})
    assert not rack.can_move
    rack._client.publish.assert_not_called()


@pytest.mark.parametrize("state", ["RUNNING", "PAUSE", "PREPARE", "unknown"])
def test_print_in_progress_or_unknown_blocks_movement(rack, state):
    ready(rack)
    rack._client._device.print_job.gcode_state = state
    assert not rack.can_move
    assert not rack.move("down")
    rack._client.publish.assert_not_called()


@pytest.mark.parametrize("state", ["IDLE", "FINISH", "FAILED"])
def test_idle_or_completed_print_allows_control(rack, state):
    ready(rack)
    rack._client._device.print_job.gcode_state = state
    assert rack.can_move


def test_busy_offline_signed_and_other_models_are_blocked(rack):
    ready(rack)
    device = rack._client._device
    for obj, attr, value, reset in (
        (device.info, "online", False, True),
        (device.print_fun, "mqtt_signature_required", True, False),
        (device.info, "device_type", Printers.H2C, Printers.H3C),
        (device, "has_full_printer_data", False, True),
    ):
        setattr(obj, attr, value)
        assert not rack.can_move
        assert not rack.move("down")
        setattr(obj, attr, reset)
    rack.print_update({"device": {"holder": {"stat": 1, "job": 5}}})
    assert not rack.can_move
    rack._client.publish.assert_not_called()


def test_disconnect_requires_new_holder_and_print_state(rack):
    ready(rack)
    rack._client._device.hotend_rack = rack
    rack._client._device.info._client = rack._client
    Info.set_online(rack._client._device.info, False)
    Info.set_online(rack._client._device.info, True)
    assert not rack.can_move
    rack.print_update({"device": {"holder": {"stat": 0, "job": 0}}})
    assert not rack.can_move
    rack.print_update({"gcode_state": "IDLE"})
    assert rack.can_move


def test_failed_publish_does_not_leave_pending(rack):
    ready(rack)
    rack._client.publish.return_value = False
    assert not rack.move("down")
    assert rack.can_move


def test_publish_exception_does_not_leave_pending(rack):
    ready(rack)
    rack._client.publish.side_effect = RuntimeError("network error")
    with pytest.raises(RuntimeError, match="network error"):
        rack.move("up")
    assert rack.can_move


def test_pending_timeout_requires_fresh_idle_report(rack):
    ready(rack)
    with patch("pybambu.models.time.monotonic", return_value=100):
        assert rack.move("down")
    with patch("pybambu.models.time.monotonic", return_value=131):
        assert not rack.can_move
        rack.print_update({"device": {"holder": {"stat": 0, "job": 0}}})
        assert rack.can_move


@pytest.mark.parametrize("busy_field,idle_field", [("job", "stat"), ("stat", "job")])
def test_partial_reports_cannot_reuse_pre_move_idle(rack, busy_field, idle_field):
    ready(rack)
    assert rack.move("down")
    rack.print_update({"device": {"holder": {busy_field: 1}}})
    rack.print_update({"device": {"holder": {busy_field: 0}}})
    assert not rack.can_move
    rack.print_update({"device": {"holder": {idle_field: 0}}})
    assert not rack.can_move
    rack.print_update({"device": {"holder": {"stat": 0, "job": 0}}})
    assert rack.can_move


def test_pending_timeout_does_not_override_observed_busy(rack):
    ready(rack)
    with patch("pybambu.models.time.monotonic", return_value=100):
        assert rack.move("down")
    rack.print_update({"device": {"holder": {"stat": 1, "job": 0}}})
    with patch("pybambu.models.time.monotonic", return_value=131):
        rack.print_update({"device": {"holder": {"stat": 0}}})
        assert not rack.can_move
        rack.print_update({"device": {"holder": {"job": 0}}})
        assert not rack.can_move
        rack.print_update({"device": {"holder": {"stat": 0, "job": 0}}})
        assert rack.can_move


def test_unknown_direction_never_publishes(rack):
    ready(rack)
    assert not rack.move("home")
    rack._client.publish.assert_not_called()
