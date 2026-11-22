import os
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import MagicMock

from pybambu.media_sources import RemoteMediaFile
from pybambu.models import PrintJob


def _remote_file(name="video_2025-09-25_10-00-00.mp4"):
    return RemoteMediaFile(
        name=name,
        path=f"/timelapse/{name}",
        size=4,
        media_type="timelapse",
        source="ftps",
        storage="sdcard",
    )


class TestLastTimelapse(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.cache = Path(self.tmp.name)
        self.client = MagicMock()
        self.client.cache_path = str(self.cache)
        self.client._test_mode = False
        self.client._timelapse_cache_count = 1
        self.print_job = PrintJob(self.client)

        source = MagicMock()
        source.name = "ftps"
        self.print_job._remote_media_sources = MagicMock(return_value=[source])
        self.print_job._close_remote_media_sources = MagicMock()
        self.print_job._remote_file_is_stable = MagicMock(return_value=True)
        self.print_job._download_timelapse_thumbnail = MagicMock()
        self.print_job._remote_file_aliases = MagicMock(side_effect=lambda candidates, selected: [selected])
        self.print_job._download_remote_file_atomic = MagicMock(side_effect=self._write_local)

    def tearDown(self):
        self.tmp.cleanup()

    def _write_local(self, source, remote_file, local_path):
        local_path.parent.mkdir(parents=True, exist_ok=True)
        local_path.write_bytes(b"data")

    def _callbacks(self):
        return [c.args[0] for c in self.client.callback.call_args_list]

    def test_last_timelapse_is_none_before_any_download(self):
        self.assertIsNone(self.print_job.last_timelapse_path)

    def test_download_records_path_and_fires_event(self):
        remote = _remote_file()
        self.print_job._collect_remote_files = MagicMock(return_value=[remote])

        self.print_job._async_download_timelapse()

        expected = self.print_job._timelapse_cache_path(remote)
        self.assertEqual(self.print_job.last_timelapse_path, str(expected))
        self.assertTrue(expected.exists())
        self.assertIn("event_timelapse_downloaded", self._callbacks())

    def test_cached_file_still_records_path(self):
        remote = _remote_file()
        local = self.print_job._timelapse_cache_path(remote)
        self._write_local(None, remote, local)
        self.print_job._collect_remote_files = MagicMock(return_value=[remote])

        self.print_job._async_download_timelapse()

        self.print_job._download_remote_file_atomic.assert_not_called()
        self.assertEqual(self.print_job.last_timelapse_path, str(local))
        self.assertIn("event_timelapse_downloaded", self._callbacks())

    def test_no_candidates_leaves_path_unset_and_fires_no_event(self):
        self.print_job._collect_remote_files = MagicMock(return_value=[])

        self.print_job._async_download_timelapse()

        self.assertIsNone(self.print_job.last_timelapse_path)
        self.assertNotIn("event_timelapse_downloaded", self._callbacks())

    def test_failed_download_fires_no_event(self):
        self.print_job._collect_remote_files = MagicMock(return_value=[_remote_file()])
        self.print_job._download_remote_file_atomic = MagicMock(side_effect=OSError("boom"))

        self.print_job._async_download_timelapse()

        self.assertIsNone(self.print_job.last_timelapse_path)
        self.assertNotIn("event_timelapse_downloaded", self._callbacks())

    def test_prune_restores_newest_cached_timelapse(self):
        older = self.cache / "timelapse" / "sdcard" / "old.mp4"
        newer = self.cache / "timelapse" / "sdcard" / "new.mp4"
        for path, age in ((older, 120), (newer, 10)):
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(b"data")
            stamp = time.time() - age
            os.utime(path, (stamp, stamp))
        self.client._timelapse_cache_count = -1

        self.print_job.prune_timelapse_files()

        self.assertEqual(self.print_job.last_timelapse_path, str(newer))

    def test_prune_clears_path_when_file_is_gone(self):
        self.print_job.last_timelapse_path = str(self.cache / "timelapse" / "missing.mp4")

        self.print_job.prune_timelapse_files()

        self.assertIsNone(self.print_job.last_timelapse_path)


if __name__ == "__main__":
    unittest.main()
