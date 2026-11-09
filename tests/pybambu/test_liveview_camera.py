"""Switching the live view between the main and BirdsEye cameras.

Printers with a BirdsEye camera stream one camera at a time. They report the one that is
live in ipcam.current_liveview and the ones they have in ipcam.support_liveview_cams, and
Bambu Studio switches with a change_liveview_cam_idx camera command (camera 4 is the main
camera, 5 the BirdsEye camera).
"""
import unittest
from unittest.mock import MagicMock

from pybambu.commands import SWITCH_LIVEVIEW_CAMERA_TEMPLATE
from pybambu.const import LIVEVIEW_CAMERAS
from pybambu.models import Camera


def _ipcam(**fields):
    return {"ipcam": {"rtsp_url": "rtsps://192.0.2.10:322/streaming/live/1", **fields}}


class TestLiveviewCamera(unittest.TestCase):
    def setUp(self):
        self.client = MagicMock()
        self.client._enable_camera = False
        self.camera = Camera(self.client)

    def test_printer_without_camera_info_has_no_choice(self):
        self.camera.print_update(_ipcam())
        self.assertIsNone(self.camera.liveview_camera)
        self.assertEqual(self.camera.liveview_camera_options, [])
        self.assertFalse(self.camera.supports_liveview_switch)

    def test_reports_the_live_camera_and_the_choices(self):
        changed = self.camera.print_update(_ipcam(current_liveview=5, support_liveview_cams=[4, 5]))
        self.assertTrue(changed)
        self.assertEqual(self.camera.liveview_camera, "birdseye")
        self.assertEqual(self.camera.liveview_camera_options, ["main", "birdseye"])
        self.assertTrue(self.camera.supports_liveview_switch)

    def test_single_camera_printer_has_nothing_to_switch(self):
        self.camera.print_update(_ipcam(current_liveview=4, support_liveview_cams=[4]))
        self.assertEqual(self.camera.liveview_camera, "main")
        self.assertFalse(self.camera.supports_liveview_switch)

    def test_unknown_camera_ids_are_ignored(self):
        self.camera.print_update(_ipcam(current_liveview=9, support_liveview_cams=[4, 9, "x"]))
        self.assertIsNone(self.camera.liveview_camera)
        self.assertEqual(self.camera.liveview_camera_options, ["main"])
        self.assertFalse(self.camera.supports_liveview_switch)

    def test_partial_update_keeps_the_camera_info(self):
        self.camera.print_update(_ipcam(current_liveview=4, support_liveview_cams=[4, 5]))
        self.camera.print_update({"ipcam": {"resolution": "1080p"}})
        self.camera.print_update({"print": {}})
        self.assertEqual(self.camera.liveview_camera, "main")
        self.assertTrue(self.camera.supports_liveview_switch)

    def test_switching_publishes_the_studio_command(self):
        self.camera.print_update(_ipcam(current_liveview=4, support_liveview_cams=[4, 5]))
        self.camera.set_liveview_camera("birdseye")

        command = self.client.publish.call_args.args[0]
        self.assertEqual(command["camera"]["command"], "change_liveview_cam_idx")
        self.assertEqual(command["camera"]["camera_id"], 5)
        self.assertEqual(command["camera"]["version"], 1)
        # The template itself must not change.
        self.assertEqual(SWITCH_LIVEVIEW_CAMERA_TEMPLATE["camera"]["camera_id"], 4)

    def test_switching_to_an_unsupported_camera_does_nothing(self):
        self.camera.print_update(_ipcam(current_liveview=4, support_liveview_cams=[4]))
        self.camera.set_liveview_camera("birdseye")
        self.camera.set_liveview_camera("nonsense")
        self.client.publish.assert_not_called()

    def test_camera_names(self):
        self.assertEqual(LIVEVIEW_CAMERAS, {4: "main", 5: "birdseye"})


if __name__ == "__main__":
    unittest.main()
