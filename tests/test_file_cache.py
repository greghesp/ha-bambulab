"""The file cache must live outside www/, which HA serves unauthenticated at /local/ (#2167).

file_cache.py has no Home Assistant imports, so it is loaded straight from its
file here rather than through the custom_components package (whose __init__
imports homeassistant).
"""
import importlib.util
from pathlib import Path

_MODULE_PATH = Path(__file__).resolve().parents[1] / "custom_components" / "bambu_lab" / "file_cache.py"
_spec = importlib.util.spec_from_file_location("bambu_file_cache", _MODULE_PATH)
file_cache = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(file_cache)

SERIAL = "0948AD000000000"


def _write(path: Path, content: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(content)


def test_cache_root_uses_local_media_dir(tmp_path):
    root = file_cache.cache_root(str(tmp_path / "media"), str(tmp_path / "config"))

    assert root == tmp_path / "media" / "ha-bambulab"


def test_cache_root_falls_back_to_config_media_when_no_local_media_dir(tmp_path):
    root = file_cache.cache_root(None, str(tmp_path / "config"))

    assert root == tmp_path / "config" / "media" / "ha-bambulab"


def test_cache_root_is_never_under_www(tmp_path):
    config = tmp_path / "config"
    for media_dir in (None, str(tmp_path / "media")):
        root = file_cache.cache_root(media_dir, str(config))
        assert "www" not in root.relative_to(tmp_path).parts


def test_legacy_cache_dir_points_at_www(tmp_path):
    legacy = file_cache.legacy_cache_dir(str(tmp_path), SERIAL)

    assert legacy == tmp_path / "www" / "media" / "ha-bambulab" / SERIAL


def test_migrate_moves_files_and_removes_public_copy(tmp_path):
    legacy = file_cache.legacy_cache_dir(str(tmp_path / "config"), SERIAL)
    new = tmp_path / "media" / "ha-bambulab" / SERIAL
    _write(legacy / "prints" / "cache" / "123-model.gcode.3mf", b"model")
    _write(legacy / "timelapse" / "video.mp4", b"video")

    file_cache.migrate_legacy_cache(legacy, new)

    assert (new / "prints" / "cache" / "123-model.gcode.3mf").read_bytes() == b"model"
    assert (new / "timelapse" / "video.mp4").read_bytes() == b"video"
    assert not legacy.exists()
    assert not legacy.parent.exists()  # the now-empty ha-bambulab folder
    assert legacy.parent.parent.exists()  # www/media is left for the user


def test_migrate_keeps_existing_destination_files(tmp_path):
    legacy = tmp_path / "www" / "media" / "ha-bambulab" / SERIAL
    new = tmp_path / "media" / "ha-bambulab" / SERIAL
    _write(legacy / "prints" / "a.3mf", b"old")
    _write(new / "prints" / "a.3mf", b"new")

    file_cache.migrate_legacy_cache(legacy, new)

    assert (new / "prints" / "a.3mf").read_bytes() == b"new"
    assert not legacy.exists()


def test_migrate_leaves_other_printers_legacy_cache(tmp_path):
    root = tmp_path / "www" / "media" / "ha-bambulab"
    _write(root / SERIAL / "prints" / "a.3mf", b"a")
    _write(root / "OTHER" / "prints" / "b.3mf", b"b")

    file_cache.migrate_legacy_cache(root / SERIAL, tmp_path / "media" / "ha-bambulab" / SERIAL)

    assert not (root / SERIAL).exists()
    assert (root / "OTHER" / "prints" / "b.3mf").exists()


def test_migrate_is_a_no_op_without_legacy_cache(tmp_path):
    new = tmp_path / "media" / "ha-bambulab" / SERIAL

    file_cache.migrate_legacy_cache(tmp_path / "www" / "media" / "ha-bambulab" / SERIAL, new)

    assert not new.exists()
