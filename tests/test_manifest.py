"""Checks on the integration manifest.

The RTSP camera (X1/H2 series) sets CameraEntityFeature.STREAM and
use_stream_for_stills=True, so both live view and still snapshots go through
Home Assistant's `stream` component. If that component isn't loaded (e.g. the
user doesn't use `default_config:`), the camera fails with "does not support
play stream service" and never shows an image. Declaring `stream` as a
dependency makes HA load it before this integration. See issue #221.
"""
import json
import os

MANIFEST_PATH = os.path.join(
    os.path.dirname(__file__), "..", "custom_components", "bambu_lab", "manifest.json"
)


def _load_manifest() -> dict:
    with open(MANIFEST_PATH, encoding="utf-8") as manifest_file:
        return json.load(manifest_file)


def test_manifest_declares_stream_dependency_for_rtsp_camera():
    manifest = _load_manifest()

    assert "stream" in manifest["dependencies"]


def test_manifest_dependencies_are_sorted_and_unique():
    dependencies = _load_manifest()["dependencies"]

    assert dependencies == sorted(set(dependencies))
