"""Laser/cutter (2D) job details reported by the H2D Laser Edition (#1310)."""
from unittest.mock import MagicMock

from pybambu.models import Processing2D


def _two_d(material="3mm Opaque Glossy Acrylic - Mistletoe Green", clock_in=True,
           clock_in_time=85, stage_state=2, idx=0):
    return {
        "2D": {
            "bs": {"bi": [{"idx": 0, "clock_in": clock_in, "est_time": 1479}], "total_time": 1479},
            "cur_stage": {"clock_in_time": clock_in_time, "idx": idx, "left_time": 722,
                          "process": 51, "state": stage_state},
            "material": {"state": 1, "tar_id": "B-YB-A-A-G1", "tar_name": material},
        }
    }


def test_defaults_before_any_2d_data():
    processing = Processing2D(MagicMock())

    assert processing.material is None
    assert processing.check_in_required is False
    assert processing.check_in_remaining is None


def test_flammable_material_exposes_check_in_countdown():
    processing = Processing2D(MagicMock())

    assert processing.print_update(_two_d(clock_in_time=85)) is True

    assert processing.material == "3mm Opaque Glossy Acrylic - Mistletoe Green"
    assert processing.check_in_required is True
    assert processing.check_in_remaining == 85


def test_countdown_updates_report_a_change():
    processing = Processing2D(MagicMock())
    processing.print_update(_two_d(clock_in_time=85))

    assert processing.print_update(_two_d(clock_in_time=1)) is True
    assert processing.check_in_remaining == 1
    assert processing.print_update(_two_d(clock_in_time=1)) is False


def test_non_flammable_material_has_no_check_in():
    processing = Processing2D(MagicMock())

    processing.print_update(_two_d(material="3mm Basswood Plywood", clock_in=False, clock_in_time=0))

    assert processing.material == "3mm Basswood Plywood"
    assert processing.check_in_required is False
    assert processing.check_in_remaining is None


def test_finished_job_clears_check_in_but_keeps_material():
    processing = Processing2D(MagicMock())
    processing.print_update(_two_d(clock_in_time=85))

    processing.print_update(_two_d(clock_in_time=114, stage_state=0))

    assert processing.material == "3mm Opaque Glossy Acrylic - Mistletoe Green"
    assert processing.check_in_required is False
    assert processing.check_in_remaining is None


def test_empty_material_name_is_none():
    processing = Processing2D(MagicMock())

    processing.print_update(_two_d(material="", clock_in=False, clock_in_time=0, stage_state=0))

    assert processing.material is None


def test_stage_index_without_matching_step_is_not_check_in():
    processing = Processing2D(MagicMock())

    processing.print_update(_two_d(idx=3))

    assert processing.check_in_required is False
    assert processing.check_in_remaining is None


def test_partial_update_without_2d_keeps_state():
    processing = Processing2D(MagicMock())
    processing.print_update(_two_d(clock_in_time=85))

    assert processing.print_update({"gcode_state": "RUNNING"}) is False
    assert processing.check_in_remaining == 85


def test_partial_cur_stage_update_keeps_known_steps():
    processing = Processing2D(MagicMock())
    processing.print_update(_two_d(clock_in_time=85))

    processing.print_update({"2D": {"cur_stage": {"clock_in_time": 40, "idx": 0, "state": 2}}})

    assert processing.check_in_required is True
    assert processing.check_in_remaining == 40
