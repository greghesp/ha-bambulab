"""Tests for remote media source helper behavior."""

import unittest
from datetime import datetime, timezone

from pybambu.media_sources import (
    Ftps990MediaSource,
    RemoteMediaFile,
    Tcp6000MediaSource,
    canonical_storage,
    dedupe_remote_files,
    storage_cache_segment,
)


class FakeClient:
    tcp6000_media_supported = True
    tcp6000_media_storages = []


class TestRemoteMediaSources(unittest.TestCase):
    def test_dedupe_preserves_distinct_storage_volumes(self):
        files = [
            RemoteMediaFile(
                name="video_2026-08-05_09-00-00.mp4",
                path="/timelapse/video_2026-08-05_09-00-00.mp4",
                size=123,
                media_type="timelapse",
                source=Tcp6000MediaSource.name,
                storage="internal",
                modified=datetime(2026, 8, 5, 1, 0, tzinfo=timezone.utc),
            ),
            RemoteMediaFile(
                name="video_2026-08-05_09-00-00.mp4",
                path="/timelapse/video_2026-08-05_09-00-00.mp4",
                size=123,
                media_type="timelapse",
                source=Tcp6000MediaSource.name,
                storage="udisk",
                modified=datetime(2026, 8, 5, 2, 0, tzinfo=timezone.utc),
            ),
        ]

        result = dedupe_remote_files(files)

        self.assertEqual(2, len(result))
        self.assertEqual({"internal", "external"}, {canonical_storage(file.storage) for file in result})

    def test_dedupe_prefers_tcp6000_for_same_external_file_alias(self):
        files = [
            RemoteMediaFile(
                name="model.3mf",
                path="/cache/model.3mf",
                size=456,
                media_type="model",
                source=Tcp6000MediaSource.name,
                storage="udisk",
                modified=datetime(2026, 8, 5, 1, 0, tzinfo=timezone.utc),
            ),
            RemoteMediaFile(
                name="model.3mf",
                path="/cache/model.3mf",
                size=456,
                media_type="model",
                source=Ftps990MediaSource.name,
                storage="external",
                modified=datetime(2026, 8, 5, 2, 0, tzinfo=timezone.utc),
            ),
        ]

        result = dedupe_remote_files(files)

        self.assertEqual(1, len(result))
        self.assertEqual(Tcp6000MediaSource.name, result[0].source)

    def test_tcp6000_storage_candidates_cover_internal_and_external(self):
        source = Tcp6000MediaSource(FakeClient())
        source._ability_storages = ["internal"]

        candidates = source._storage_candidates("timelapse")

        self.assertIn("internal", candidates)
        self.assertIn("emmc", candidates)
        self.assertIn("udisk", candidates)
        self.assertIn("sdcard", candidates)
        self.assertIn("", candidates)

    def test_storage_cache_segment_groups_known_storage_aliases(self):
        self.assertEqual("internal", storage_cache_segment("emmc"))
        self.assertEqual("external", storage_cache_segment("udisk"))

    def test_tcp6000_download_request_uses_relative_path_with_directories(self):
        remote_file = RemoteMediaFile(
            name="video.jpg",
            path="thumbnail/video.jpg",
            size=0,
            media_type="timelapse",
            source=Tcp6000MediaSource.name,
            storage="internal",
        )

        request = Tcp6000MediaSource._download_request(remote_file)

        self.assertEqual({"path": "thumbnail/video.jpg", "offset": 0}, request)


if __name__ == "__main__":
    unittest.main()
