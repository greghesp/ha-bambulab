"""Home Assistant H3C rack button tests."""

import asyncio
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

pytest.importorskip("homeassistant")

from homeassistant.exceptions import HomeAssistantError

from custom_components.bambu_lab.button import (
    BambuLabHotendRackButton,
    RACK_LOWER_BUTTON_DESCRIPTION,
    RACK_RAISE_BUTTON_DESCRIPTION,
    async_setup_entry,
)
from custom_components.bambu_lab.const import DOMAIN
from custom_components.bambu_lab.pybambu.const import Features, Printers


@pytest.fixture
def context():
    coordinator = MagicMock()
    coordinator.last_update_success = True
    model = coordinator.get_model()
    model.has_full_printer_data = True
    model.info.device_type = Printers.H3C
    model.print_fun.mqtt_signature_required = False
    model.hotend_rack.can_move = True
    model.hotend_rack.move.return_value = True
    model.supports_feature.side_effect = lambda feature: feature == Features.HOTEND_RACK
    coordinator.get_hotend_rack_device.return_value = {"identifiers": {(DOMAIN, "PRINTER_rack")}}
    entry = SimpleNamespace(entry_id="entry", data={"serial": "PRINTER"})
    hass = SimpleNamespace(data={DOMAIN: {"entry": coordinator}})
    return coordinator, entry, hass


def test_platform_registers_two_h3c_buttons_on_rack(context):
    coordinator, entry, hass = context
    entities = []
    asyncio.run(async_setup_entry(hass, entry, entities.extend))
    buttons = [entity for entity in entities if isinstance(entity, BambuLabHotendRackButton)]
    assert {button.unique_id for button in buttons} == {"PRINTER_hotend_rack_raise", "PRINTER_hotend_rack_lower"}
    assert all(button.device_info == {"identifiers": {(DOMAIN, "PRINTER_rack")}} for button in buttons)


@pytest.mark.parametrize("model,signed,rack_exists", [
    (Printers.H2C, False, True), (Printers.H3C, True, True), (Printers.H3C, False, False),
])
def test_no_buttons_for_other_models_signed_commands_or_missing_rack(context, model, signed, rack_exists):
    coordinator, entry, hass = context
    printer = coordinator.get_model()
    printer.info.device_type = model
    printer.print_fun.mqtt_signature_required = signed
    printer.supports_feature.side_effect = lambda feature: feature == Features.HOTEND_RACK and rack_exists
    entities = []
    asyncio.run(async_setup_entry(hass, entry, entities.extend))
    assert not any(isinstance(entity, BambuLabHotendRackButton) for entity in entities)


@pytest.mark.parametrize("description,direction", [
    (RACK_RAISE_BUTTON_DESCRIPTION, "up"), (RACK_LOWER_BUTTON_DESCRIPTION, "down"),
])
def test_press_requests_direction(context, description, direction):
    coordinator, entry, _ = context
    button = BambuLabHotendRackButton(coordinator, entry, description, direction)
    assert button.available
    asyncio.run(button.async_press())
    coordinator.get_model().hotend_rack.move.assert_called_once_with(direction)
    coordinator.async_update_listeners.assert_called_once()


def test_buttons_unavailable_when_control_is_not_ready(context):
    coordinator, entry, _ = context
    button = BambuLabHotendRackButton(coordinator, entry, RACK_LOWER_BUTTON_DESCRIPTION, "down")
    rack = coordinator.get_model().hotend_rack
    rack.can_move = False
    assert not button.available
    with pytest.raises(HomeAssistantError):
        asyncio.run(button.async_press())
    rack.move.assert_not_called()
    rack.can_move = True
    rack.move.return_value = False
    with pytest.raises(HomeAssistantError):
        asyncio.run(button.async_press())


def test_buttons_unavailable_when_coordinator_fails(context):
    coordinator, entry, _ = context
    button = BambuLabHotendRackButton(coordinator, entry, RACK_LOWER_BUTTON_DESCRIPTION, "down")
    rack = coordinator.get_model().hotend_rack
    coordinator.last_update_success = False
    assert not button.available
    with pytest.raises(HomeAssistantError):
        asyncio.run(button.async_press())
    rack.move.assert_not_called()
