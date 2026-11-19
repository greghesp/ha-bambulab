"""Stored-model fallback regressions using synthetic archives and media replies."""
import ast
import hashlib
import io
import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch
from zipfile import ZipFile

import pytest

from pybambu import model_metadata as metadata
from pybambu.media_sources import RemoteMediaError, RemoteMediaFile, Tcp6000MediaSource
from pybambu.models import PrintJob


def archive(title="Sample project", plate=2, program=b"G1 X1\n", grams="12.3", checksum=True):
    output = io.BytesIO()
    with ZipFile(output, "w") as zipped:
        zipped.writestr("3D/3dmodel.model", f'<model><metadata name="Title">{title}</metadata></model>')
        zipped.writestr("Metadata/slice_info.config", f'<config><plate><metadata key="index" value="{plate}"/><metadata key="weight" value="{grams}"/></plate></config>')
        zipped.writestr(f"Metadata/plate_{plate}.gcode", program)
        if checksum:
            zipped.writestr(f"Metadata/plate_{plate}.gcode.md5", hashlib.md5(program).hexdigest())
    return output.getvalue()


def file(name="different-file.gcode.3mf", modified=None):
    return RemoteMediaFile(name, "/"+name, 1000, "model", "tcp6000", "emmc", modified)


def job():
    return SimpleNamespace(task_id="synthetic-task", _subtask_name="Sample project", plate_idx=2,
                           gcode_file="/data/Metadata/plate_2.gcode")


class Source:
    name = "tcp6000"

    def __init__(self, files=None, values=None):
        self.files = files or [file()]
        self.values = values or {entry.name: archive() for entry in self.files}
        self.calls = []

    def list_files(self, *args, **kwargs):
        assert kwargs["require_complete"] is True
        return self.files

    def model_metadata(self, entry, plate=None, **kwargs):
        self.calls.append((entry.name, plate))
        return self.values[entry.name]


def test_title_fallback_and_actual_archive_validation(tmp_path):
    source = Source()
    selected = metadata.StoredModelLookup().select(job(), source)
    assert selected.file == source.files[0]
    local = tmp_path/"model.3mf"
    local.write_bytes(archive())
    selected.validate_archive(local)


@pytest.mark.parametrize("change", ["title", "plate", "program", "weights"])
def test_downloaded_changed_content_is_refused(tmp_path, change):
    selected = metadata.StoredModelLookup().select(job(), Source())
    args = {"title": {"title": "Other"}, "plate": {"plate": 3},
            "program": {"program": b"G1 X2\n"}, "weights": {"grams": "99"}}[change]
    local = tmp_path/"model.3mf"
    local.write_bytes(archive(**args))
    with pytest.raises(ValueError):
        selected.validate_archive(local)


@pytest.mark.parametrize("alter", ["same", "program", "weights", "checksum"])
def test_copies_require_same_selected_program_and_accounting(alter):
    files = [file("first.3mf"), file("second.3mf")]
    args = {"same": {}, "program": {"program": b"G1 X2\n"},
            "weights": {"grams": "99"}, "checksum": {"checksum": False}}[alter]
    source = Source(files, {files[0].name: archive(), files[1].name: archive(**args)})
    selected = metadata.StoredModelLookup().select(job(), source)
    assert (selected is not None) == (alter == "same")


def test_declared_plate_without_program_checksum_is_not_selected():
    source = Source(values={file().name: archive(checksum=False)})
    assert metadata.StoredModelLookup().select(job(), source) is None


def test_explicit_filename_cannot_be_replaced_by_same_title():
    current = job()
    current.gcode_file = "missing-current-file.3mf"
    source = Source()
    assert metadata.StoredModelLookup().select(current, source) is None
    assert not source.calls


def test_unknown_candidate_or_incomplete_storage_listing_prevents_selection():
    source = Source()
    source.list_files = MagicMock(side_effect=RemoteMediaError("unavailable storage"))
    assert metadata.StoredModelLookup().select(job(), source) is None
    source = Source([file("valid.3mf"), file("bad.3mf")], {"valid.3mf": archive(), "bad.3mf": b"corrupt"})
    assert metadata.StoredModelLookup().select(job(), source) is None


def test_listing_change_during_scan_prevents_selection():
    source = Source()
    source.list_files = MagicMock(side_effect=[source.files, source.files+[file("new.3mf")]])
    assert metadata.StoredModelLookup().select(job(), source) is None


def test_job_change_during_lookup_prevents_selection():
    source, current = Source(), job()
    read = source.model_metadata
    def changing(*args, **kwargs):
        current.task_id = "different-task"
        return read(*args, **kwargs)
    source.model_metadata = changing
    assert metadata.StoredModelLookup().select(current, source) is None


def test_cache_is_not_reused_by_next_job_with_identical_title_and_size():
    source, current, lookup = Source(), job(), metadata.StoredModelLookup()
    assert lookup.select(current, source)
    first_calls = len(source.calls)
    current.task_id = "second-task"
    source.values[file().name] = archive(title="Other title")
    assert lookup.select(current, source) is None
    assert len(source.calls) > first_calls


def test_expired_lookup_cache_is_refreshed():
    source, current, lookup = Source(), job(), metadata.StoredModelLookup()
    assert lookup.select(current, source)
    source.values[file().name] = archive(title="Other title")
    lookup.started -= 61
    assert lookup.select(current, source) is None


def test_fingerprint_requests_share_lookup_budget():
    source, current = Source(), job()
    with patch.object(metadata.time, "monotonic", side_effect=[0, 0, 0, 0, 0, 21]):
        assert metadata.StoredModelLookup().select(current, source) is None
    assert len(source.calls) <= 1


@pytest.mark.parametrize("encoding", ["utf-8", "utf-16", "utf-16-le", "utf-16-be"])
def test_dtd_is_refused_for_all_xml_encodings(encoding):
    output = io.BytesIO()
    with ZipFile(output, "w") as zipped:
        data = '<!DOCTYPE model [<!ENTITY x "expanded">]><model><metadata name="Title">&x;</metadata></model>'
        zipped.writestr("3D/3dmodel.model", data.encode(encoding))
        zipped.writestr("Metadata/slice_info.config", '<config/>')
    with pytest.raises(ValueError):
        metadata.read_identity(output.getvalue())


def test_duplicate_members_and_oversized_metadata_refused():
    output = io.BytesIO(archive())
    with ZipFile(output, "a") as zipped:
        zipped.writestr("3D/3dmodel.model", '<model/>')
    with pytest.raises(ValueError):
        metadata.read_identity(output.getvalue())
    with patch.object(metadata, "MAX_METADATA_BYTES", 1):
        with pytest.raises(ValueError):
            metadata.read_identity(archive())


def test_downloaded_program_is_checked_not_just_its_checksum_member(tmp_path):
    selected = metadata.StoredModelLookup().select(job(), Source())
    output = io.BytesIO(archive())
    with ZipFile(output) as zipped:
        members = {name: zipped.read(name) for name in zipped.namelist()}
    members["Metadata/plate_2.gcode"] = b"different actual program"
    local = tmp_path/"model.3mf"
    with ZipFile(local, "w") as zipped:
        for name, data in members.items():
            zipped.writestr(name, data)
    with pytest.raises(ValueError):
        selected.validate_archive(local)


def protocol(replies):
    source = object.__new__(Tcp6000MediaSource)
    source._send_ctrl_request = MagicMock(return_value=42)
    source._read_matching_reply = MagicMock(side_effect=replies)
    return source


def test_sub_file_protocol_handles_chunking_and_only_requested_members():
    entry = file()
    source = protocol([({"result": 1, "reply": {"path": entry.path, "size": 3, "continue": True}}, b"abc"),
                       ({"result": 0, "reply": {"path": entry.path, "size": 3}}, b"def")])
    assert source.model_metadata(entry, 2) == b"abcdef"
    cmd, request = source._send_ctrl_request.call_args.args
    assert cmd == 2
    assert request == {"paths": [entry.path+"#"+name for name in metadata.METADATA_MEMBERS]
                      +[entry.path+"#Metadata/plate_2.gcode.md5"], "zip": True, "storage": "emmc"}
    assert source._read_matching_reply.call_args.kwargs['max_payload'] < 9*1024*1024


@pytest.mark.parametrize("reply, data", [({"result": 2}, b""),
    ({"result": 0, "reply": {"path": "wrong", "size": 1}}, b"x"),
    ({"result": 0, "reply": {"path": file().path, "size": 2}}, b"x"),
    ({"result": 0, "reply": {"path": file().path, "size": 0}}, b"")])
def test_sub_file_invalid_replies_are_refused(reply, data):
    with pytest.raises(RemoteMediaError):
        protocol([(reply, data)]).model_metadata(file())


def test_metadata_frame_bound_is_opt_in_for_existing_protocol():
    source = object.__new__(Tcp6000MediaSource)
    source._read_exact = MagicMock(side_effect=[(20).to_bytes(4, 'little')+bytes(12), b"x"*20])
    assert source._read_frame()[2] == b"x"*20
    source._read_exact = MagicMock(return_value=(20).to_bytes(4, 'little')+bytes(12))
    with pytest.raises(RemoteMediaError):
        source._read_frame(max_payload=10)
    assert source._read_exact.call_count == 1


def test_advertised_storage_failure_cannot_be_a_complete_title_search():
    source = protocol([({"result": 0, "reply": {"file_lists": []}}, b""),
                       ({"result": 2}, b"")])
    source.media_ability = MagicMock(return_value=["emmc", "udisk"])
    with pytest.raises(RemoteMediaError):
        source.list_files("model", [".3mf"], require_complete=True)


def configured_job():
    current = PrintJob(MagicMock())
    current.task_id = "synthetic-task"
    current._subtask_name = "Sample project"
    current.plate_idx = 2
    current.gcode_file = "/data/Metadata/plate_2.gcode"
    current._collect_remote_files = MagicMock(return_value=[file()])
    current._remote_file_is_stable = MagicMock(return_value=True)
    return current


def test_fallback_forces_fresh_download_and_validates_archive(tmp_path):
    current, source = configured_job(), Source()
    path = tmp_path/"model.3mf"
    path.write_bytes(archive())
    current._download_model_file_from_remote = MagicMock(return_value=str(path))
    assert current._attempt_remote_model_download([source]) == str(path)
    assert current._download_model_file_from_remote.call_args.kwargs['force_download'] is True


def test_job_change_during_full_download_does_not_return_old_archive(tmp_path):
    current, source = configured_job(), Source()
    path = tmp_path/"model.3mf"
    path.write_bytes(archive())
    def download(*args, **kwargs):
        current.task_id = "next-task"
        return str(path)
    current._download_model_file_from_remote = download
    assert current._attempt_remote_model_download([source]) is None


def test_normal_filename_match_never_invokes_metadata_fallback(tmp_path):
    current, source = configured_job(), Source()
    current._subtask_name = "different-file"
    current._download_model_file_from_remote = MagicMock(return_value="normal.3mf")
    assert current._attempt_remote_model_download([source]) == "normal.3mf"
    assert not source.calls
    assert not current._download_model_file_from_remote.call_args.kwargs


def test_metadata_cache_is_excluded_from_diagnostics():
    # Exercise the actual serializer without importing Home Assistant in library tests.
    path = Path(__file__).parents[2]/"custom_components/bambu_lab/diagnostics.py"
    module = ast.parse(path.read_text(encoding="utf-8"))
    method = next(node for node in module.body if isinstance(node, ast.FunctionDef) and node.name == "serialize_pybambu_object")
    from datetime import datetime
    namespace = {"Any": object, "datetime": datetime}
    exec(compile(ast.Module(body=[method], type_ignores=[]), str(path), "exec"), namespace)
    instance = SimpleNamespace(_stored_model_lookup={"private filename": "private title"}, print_weight=1)
    assert json.dumps(namespace[method.name](instance)) == '{"print_weight": 1}'


def test_failed_metadata_with_successful_thumbnail_is_retried():
    current = configured_job()
    current._loaded_model_data = True
    current._async_download_task_data_from_printer_worker = MagicMock(return_value=False)
    current._async_download_task_data_from_printer()
    assert current._loaded_model_data is False
    assert current._next_model_retry_at > 0


def test_partial_lookup_makes_progress_for_more_than_sixty_seconds():
    clock = SimpleNamespace(now=0.0)
    files = [file(f"sample-{index}.3mf") for index in range(20)]
    values = {entry.name: archive(title="Other project") for entry in files}
    values[files[-1].name] = archive()
    source, current, lookup = Source(files, values), job(), metadata.StoredModelLookup()
    read = source.model_metadata
    def slow_read(*args, timeout, **kwargs):
        clock.now += min(timeout, 6)
        if timeout < 6:
            raise TimeoutError()
        return read(*args, **kwargs)
    source.model_metadata = slow_read
    with patch.object(metadata.time, "monotonic", side_effect=lambda: clock.now):
        selected = None
        for _ in range(15):
            selected = lookup.select(current, source)
            if selected:
                break
            clock.now += 5
    assert selected is not None
    assert clock.now > 60
    assert source.calls.count((files[0].name, None)) == 1


def test_strict_listing_rejects_reply_without_file_list():
    source = protocol([({"result": 0, "reply": {}}, b"")])
    source.media_ability = MagicMock(return_value=["emmc"])
    with pytest.raises(RemoteMediaError):
        source.list_files("model", [".3mf"], require_complete=True)


def test_metadata_frame_deadline_covers_all_partial_receives():
    source = object.__new__(Tcp6000MediaSource)
    clock = SimpleNamespace(now=0.0)
    source._ssl = MagicMock()
    source._ssl.gettimeout.return_value = 10
    def trickle(_):
        clock.now += 0.6
        return b"x"
    source._ssl.recv.side_effect = trickle
    with patch("pybambu.media_sources.time.monotonic", side_effect=lambda: clock.now):
        with pytest.raises(RemoteMediaError):
            source._read_exact(3, deadline=1)
    assert source._ssl.recv.call_count == 2
    assert source._ssl.settimeout.call_args.args == (10,)


def test_job_change_in_image_callback_does_not_apply_previous_job_values():
    current = configured_job()
    expected = metadata.job_identity(current)
    with ZipFile(io.BytesIO(archive())) as zipped:
        xml = zipped.read("Metadata/slice_info.config")
    def change_job(_):
        current.task_id = "next-job"
        current.print_weight = 99
        current.gcode_file_downloaded = "next-job.gcode"
        current._ams_print_weights = [99]
    current._client._device.cover_image.set_image.side_effect = change_job
    assert current._parse_and_apply_model_metadata(
        xml, b"synthetic cover", expected_job=expected,
        downloaded_gcode_filename="previous-job.gcode") is False
    assert current.print_weight == 99
    assert current._ams_print_weights == [99]
    assert current.gcode_file_downloaded == "next-job.gcode"


def test_mapping_change_in_image_callback_does_not_apply_old_allocation():
    current = configured_job()
    current.ams_mapping = [0]
    expected = metadata.job_identity(current)
    with ZipFile(io.BytesIO(archive())) as zipped:
        xml = zipped.read("Metadata/slice_info.config")
    def change_mapping(_):
        current.ams_mapping = [1]
        current.print_weight = 99
        current._ams_print_weights = [0, 99]
    current._client._device.cover_image.set_image.side_effect = change_mapping
    assert current._parse_and_apply_model_metadata(xml, b"cover", expected_job=expected) is False
    assert current.print_weight == 99
    assert current._ams_print_weights == [0, 99]
