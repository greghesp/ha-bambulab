"""P3C and AMS 3P support, on synthetic payloads (see p3c_payload)."""

from unittest.mock import MagicMock

import pytest

from p3c_payload import AMS_3P_INFO, AMS_INDEX, TOOL_COUNT, p3c_payload
from pybambu.const import AMS_DRYING_MODELS, AMS_MODELS, Features, Printers
from pybambu.models import AMSInstance, AMSTray, Device
from pybambu.utils import get_HMS_error_text, get_printer_type


def make_device(model=Printers.P3C):
    client = MagicMock()
    client._device_type = model
    client.slicer_settings.custom_filaments = {}
    device = Device(client)
    client._device = device
    device.info.device_type = model
    return device


def load(device, status_first=False, payload=None):
    version, status = payload or p3c_payload()
    if not status_first:
        device.info_update(version)
    device.print_update(status)
    # A bare "n11a" can only be matched to a unit once the status reports one, so Device asks
    # for the version info again and gets the same reply.
    device.info_update(version)


@pytest.fixture
def device():
    result = make_device()
    load(result)
    return result


def test_detected_by_product_name_and_kept_through_partial_replies():
    modules = p3c_payload()[0]["module"]
    board = [{"name": "ap2", "hw_ver": "AP05"}]
    assert get_printer_type(modules, Printers.X1C) == Printers.P3C
    assert get_printer_type(board, Printers.P3C) == Printers.P3C
    assert get_printer_type(board, "unknown") == Printers.X1C


def test_hms_text_names_the_ams_3p():
    assert "AMS 3P" in get_HMS_error_text("2A00_2000_0002_0001", Printers.P3C, "en")
    assert "AMS 3P" not in get_HMS_error_text("0300_A100_0001_0001", Printers.X1C, "en")
    assert "AMS 3P" in get_HMS_error_text("0300_A100_0001_0001", Printers.P3C, "en")


@pytest.mark.parametrize("feature", [
    Features.AUX_FAN, Features.SECONDARY_AUX_FAN, Features.CHAMBER_FAN, Features.AIRDUCT_MODE,
    Features.CHAMBER_TEMPERATURE, Features.CAMERA_RTSP, Features.DOOR_SENSOR, Features.HOTEND_RACK,
    Features.AMS, Features.PROMPT_SOUND, Features.AMS_DRYING_SETTINGS,
])
def test_supported_features(device, feature):
    device.print_fun.print_update({"fun": "0"})
    assert device.supports_feature(feature)


@pytest.mark.parametrize("feature", [
    Features.ACTIVE_CHAMBER_HEATER, Features.HEATBED_LIGHT, Features.CHAMBER_LIGHT_2,
    Features.TOP_COVER_SENSOR, Features.DUAL_NOZZLES, Features.CAMERA_IMAGE, Features.EXTRUDER_TOOL,
    Features.FIRE_ALARM_BUZZER, Features.AMS_READ_RFID_COMMAND, Features.AMS_SWITCH_COMMAND,
    Features.K_VALUE,
])
def test_unsupported_features(device, feature):
    assert not device.supports_feature(feature)


def test_rtsp_camera_is_known_before_the_version_arrives():
    assert make_device().supports_feature(Features.CAMERA_RTSP)


def test_legacy_sdcard_flag_is_not_used(device):
    assert device.home_flag.sdcard_status == "not_applicable"
    assert device.home_flag.usb_connected is True


def test_has_seven_printtools(device):
    rack = device.hotend_rack
    assert rack.is_swaptek
    assert sorted(rack.hotends) == list(range(16, 16 + TOOL_COUNT))
    assert rack.hotends[22].tm == 300


def test_printtool_addresses_past_the_seventh_are_ignored(device):
    device.hotend_rack.print_update({"device": {"nozzle": {
        "exist": 0x1FF0000, "info": [{"addr_id": 7, "id": 23, "temp": 99}]}}})
    assert sorted(device.hotend_rack.hotends) == list(range(16, 16 + TOOL_COUNT))


def test_mounted_printtool_is_found_by_address(device):
    device.hotend_rack.print_update({"device": {"nozzle": {
        "exist": 0x7F0000, "info": [{"addr_id": 6, "id": 0, "temp": 220}]}}})
    assert device.hotend_rack.mounted_slot_id == 22


def test_printtool_is_linked_to_its_ams_3p_slot(device):
    assert device.hotend_rack.linked_filament(16) is device.ams.data[AMS_INDEX].tray[0]


def test_h3c_still_has_nine_printtools():
    h3c = make_device(Printers.H3C)
    h3c.hotend_rack.print_update({"device": {"nozzle": {"exist": 0x1FF0000, "info": []}}})
    assert sorted(h3c.hotend_rack.hotends) == list(range(16, 25))


@pytest.mark.parametrize("status_first", [True, False])
def test_ams_3p_is_identified_from_a_module_without_an_id(status_first):
    device = make_device()
    load(device, status_first)
    assert list(device.ams.data) == [AMS_INDEX]
    ams = device.ams.data[AMS_INDEX]
    assert (ams.model, ams.serial) == ("AMS 3P", "TEST-AMS3P")
    assert len(ams.tray) == TOOL_COUNT
    assert not ams.tray[0].empty
    assert ams.tray[6].empty
    assert ams.device_name_suffix == "AMS_3P"
    assert ams.zones[0]["zone_slots"] == list(range(TOOL_COUNT))


def test_missing_ams_3p_identity_is_requested_again():
    device = make_device()
    version, status = p3c_payload()
    device.info_update(version)
    assert device.ams.data == {}
    device._client.publish.reset_mock()
    device.print_update({**status, "command": "push_status"})
    assert any("get_version" in str(call) for call in device._client.publish.call_args_list)


def test_ams_3p_with_an_explicit_id():
    device = make_device()
    version, _ = p3c_payload()
    modules = [{**m, "id": AMS_INDEX} if m["name"] == "n11a" else m for m in version["module"]]
    device.info_update({**version, "module": modules})
    assert device.ams.data[AMS_INDEX].model == "AMS 3P"
    assert len(device.ams.data[AMS_INDEX].tray) == TOOL_COUNT


@pytest.mark.parametrize("bad_id", ["", "x", None])
def test_an_unusable_explicit_id_falls_back_to_the_status(bad_id):
    device = make_device()
    version, status = p3c_payload()
    modules = [{**m, "id": bad_id} if m["name"] == "n11a" else m for m in version["module"]]
    load(device, payload=({**version, "module": modules}, status))
    assert device.ams.data[AMS_INDEX].serial == "TEST-AMS3P"


def test_ams_3p_beside_an_external_ams():
    """The optional buffer connects up to four other AMS units to PrintTool 1."""
    device = make_device()
    version, status = p3c_payload()
    modules = [*version["module"],
               {"name": "n3f/0", "sn": "TEST-AMS2", "sw_ver": "1", "hw_ver": "N3F05"}]
    units = [{"id": "0", "info": "2003",
              "tray": [{"id": str(tray), "tray_type": "PLA", "state": 11} for tray in range(4)]},
             *status["ams"]["ams"]]
    load(device, payload=({**version, "module": modules},
                          {**status, "ams": {**status["ams"], "ams": units}}))
    assert {index: (ams.model, len(ams.tray)) for index, ams in device.ams.data.items()} == {
        0: ("AMS 2 Pro", 4), AMS_INDEX: ("AMS 3P", TOOL_COUNT)}


def test_external_spool_is_shown_on_its_slot(device):
    """vir_slot 255 - k is PrintTool k's external spool, as on the H3C."""
    device.ams.print_update({"vir_slot": [
        {"id": "249", "state": 267, "tray_type": "TPU", "tray_info_idx": "GFU00", "tray_color": "FF0000FF"}]})
    assert device.ams.data[AMS_INDEX].tray[6].type == "TPU"


def test_ams_3p_has_no_dryer_of_its_own():
    """The drying module is a separate accessory with its own command target."""
    assert "AMS 3P" in AMS_MODELS
    assert "AMS 3P" not in AMS_DRYING_MODELS


@pytest.mark.parametrize("info,count", [(AMS_3P_INFO, 7), ("240002006", 9)])
def test_unidentified_unit_has_the_slots_of_its_type(info, count):
    device = make_device()
    device.ams.print_update({"ams": {"ams": [{"id": "36", "info": info, "zone_info": [{"zone_id": 0}],
                                              "tray": [{"id": "0", "state": 0}]}]}})
    assert len(device.ams.data[36].tray) == count


def test_unit_grown_to_nine_slots_before_its_type_was_known_is_trimmed():
    device = make_device()
    device.ams.print_update({"ams": {"ams": [
        {"id": "36", "zone_info": [{"zone_id": 0}], "tray": [{"id": "6", "state": 0}]}]}})
    device.ams.info_update({"module": [
        {"name": "n11a", "id": 36, "sn": "TEST-AMS3P", "sw_ver": "1", "hw_ver": "N11A05"}]})
    assert len(device.ams.data[36].tray) == TOOL_COUNT


@pytest.mark.parametrize("model,index,count", [
    ("AMS 3P", 36, 7), ("AMS 3H", 32, 9), ("AMS", 0, 4), ("AMS HT", 128, 1), ("Unknown", 1, 4),
])
def test_instance_slot_counts(model, index, count):
    trays = AMSInstance(MagicMock(), model, index).tray
    assert len(trays) == count
    assert all(isinstance(tray, AMSTray) for tray in trays)


def test_ams_3h_module_without_an_id_is_identified_from_the_status():
    """H3C firmware 01.00.02.00 reports a bare "n10a" (#2305)."""
    h3c = make_device(Printers.H3C)
    h3c.ams.print_update({"ams": {"ams": [
        {"id": "32", "info": "240002006", "zone_info": [{"zone_id": 0, "zone_slots": [5, 7]}]}]}})
    h3c.ams.info_update({"module": [
        {"name": "n10a", "sn": "TEST-AMS3H", "sw_ver": "1", "hw_ver": "N10A05"}]})
    assert h3c.ams.data[32].model == "AMS 3H"
    assert h3c.ams.data[32].serial == "TEST-AMS3H"
    assert len(h3c.ams.data[32].tray) == 9
