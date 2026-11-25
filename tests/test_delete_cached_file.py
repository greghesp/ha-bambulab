"""Tests for deleting individual cached files."""
import asyncio
from pathlib import Path

import pytest

pytest.importorskip("homeassistant")

from custom_components.bambu_lab.coordinator import BambuDataUpdateCoordinator


def _coordinator(cache_dir: Path) -> BambuDataUpdateCoordinator:
    coordinator = object.__new__(BambuDataUpdateCoordinator)
    coordinator.get_file_cache_directory = lambda: str(cache_dir)
    return coordinator


@pytest.mark.parametrize(
    ("relative_path", "sidecars"),
    [
        ("prints/job.3mf", ("job.jpg", "job.gcode", "job.3mf.part")),
        ("timelapse/video.mp4", ("video.jpg", "video.mp4.part")),
    ],
)
def test_delete_cached_file_removes_file_and_sidecars(
    tmp_path, relative_path, sidecars
):
    cache_dir = tmp_path
    file_path = cache_dir / relative_path
    file_path.parent.mkdir(parents=True)
    file_path.write_bytes(b"cached file")
    for sidecar in sidecars:
        (file_path.parent / sidecar).write_bytes(b"sidecar")

    result = asyncio.run(_coordinator(cache_dir).delete_cached_file(relative_path))

    assert result == {"success": True, "deleted_count": len(sidecars) + 1}
    assert not file_path.exists()
    assert all(not (file_path.parent / sidecar).exists() for sidecar in sidecars)


@pytest.mark.parametrize(
    "relative_path",
    ("timelapse/video.txt", "gcode/job.gcode", "../timelapse/video.mp4"),
)
def test_delete_cached_file_rejects_unsupported_paths(tmp_path, relative_path):
    result = asyncio.run(_coordinator(tmp_path).delete_cached_file(relative_path))

    assert result["success"] is False