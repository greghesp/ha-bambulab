import unittest
from unittest.mock import MagicMock, patch

import requests

from pybambu.bambu_cloud import BambuCloud


COVER_URL = "https://example-bucket.s3.amazonaws.com/plate_1.png"


def _response(status_code, content=b"", chunks=None):
    """Minimal stand-in for a streamed requests response."""
    response = MagicMock()
    response.status_code = status_code
    response.__enter__.return_value = response
    # read1 returns whatever bytes are available, then b"" at end of body.
    response.raw.read1.side_effect = list(chunks if chunks is not None else [content]) + [b""]
    return response


class TestCoverImageDownload(unittest.TestCase):
    """Regression tests for #2171.

    The cover image download runs on the MQTT thread while the first full
    status push is being processed, before event_printer_ready fires. Without a
    timeout, a stalled connection to the image host blocked that thread
    forever, so the printer's entities were never created.
    """

    def setUp(self):
        self.cloud = BambuCloud("", "", "", "")

    @patch("pybambu.bambu_cloud.requests.get")
    def test_download_passes_a_timeout(self, mock_get):
        mock_get.return_value = _response(200, b"png-bytes")

        self.cloud.download(COVER_URL)

        timeout = mock_get.call_args.kwargs.get("timeout")
        self.assertIsNotNone(timeout, "cover image download must not wait forever")

    @patch("pybambu.bambu_cloud.requests.get")
    def test_download_returns_content_on_success(self, mock_get):
        mock_get.return_value = _response(200, b"png-bytes")

        self.assertEqual(self.cloud.download(COVER_URL), b"png-bytes")

    @patch("pybambu.bambu_cloud.requests.get")
    def test_download_returns_none_on_timeout(self, mock_get):
        mock_get.side_effect = requests.exceptions.ReadTimeout("stalled")

        self.assertIsNone(self.cloud.download(COVER_URL))

    @patch("pybambu.bambu_cloud.requests.get")
    def test_download_returns_none_on_http_error(self, mock_get):
        # An expired presigned URL returns an XML error body, which must not be
        # handed to the cover image entity as if it were a PNG.
        mock_get.return_value = _response(403, b"<Error>AccessDenied</Error>")

        self.assertIsNone(self.cloud.download(COVER_URL))

    @patch("pybambu.bambu_cloud.requests.get")
    def test_download_streams_the_body(self, mock_get):
        # The body is read in chunks so the overall deadline can be checked.
        mock_get.return_value = _response(200, chunks=[b"png-", b"bytes"])

        self.assertEqual(self.cloud.download(COVER_URL), b"png-bytes")
        self.assertTrue(mock_get.call_args.kwargs.get("stream"))

    @patch("pybambu.bambu_cloud.time.monotonic")
    @patch("pybambu.bambu_cloud.requests.get")
    def test_download_gives_up_on_a_trickling_body(self, mock_get, mock_monotonic):
        # requests' timeout only bounds each socket read. A host that keeps
        # sending a few bytes just inside it would hold the MQTT thread with no
        # limit, so the whole download also has a wall-clock deadline.
        mock_get.return_value = _response(200, chunks=[b"a", b"b", b"c", b"d"])
        mock_monotonic.side_effect = [0, 5, 10, 100, 200]

        self.assertIsNone(self.cloud.download(COVER_URL))

    @patch("pybambu.bambu_cloud.requests.get")
    def test_download_falls_back_without_read1(self, mock_get):
        # urllib3 < 2.3 has no read1; the body is still returned.
        response = _response(200)
        response.raw = MagicMock(spec=["read"])
        response.iter_content.return_value = iter([b"png-", b"bytes"])
        mock_get.return_value = response

        self.assertEqual(self.cloud.download(COVER_URL), b"png-bytes")


if __name__ == "__main__":
    unittest.main()
