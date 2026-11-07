import unittest
from unittest.mock import MagicMock

from pybambu.bambu_cloud import (
    BambuCloud,
    CloudflareError,
    CsrfError,
    CsrfObtainError,
)


def _response(status_code, text):
    """Minimal stand-in for a requests/cloudscraper response."""
    response = MagicMock()
    response.status_code = status_code
    response.text = text
    return response


class TestCsrfDetection(unittest.TestCase):
    """Regression tests for the 2FA CSRF failure (#2056).

    The 2FA leg of the cloud login posts to bambulab.com, which now requires
    a CSRF cookie that api.bambulab.com never issues. That rejection is a
    structured JSON 403 rather than a Cloudflare challenge page, so it has to
    be told apart from both the Cloudflare block and a generic permission
    failure - the config flow recovers from it specifically, by falling back
    to code login.
    """

    def setUp(self):
        self.cloud = BambuCloud("", "", "", "")

    def test_csrf_403_raises_csrf_error(self):
        body = '{"error":"CSRF error: missing_cookie","reason":"missing_cookie"}'
        with self.assertRaises(CsrfError):
            self.cloud._test_response(_response(403, body))

    def test_cloudflare_403_still_raises_cloudflare_error(self):
        # The pre-existing Cloudflare branch must keep winning for challenge
        # pages, which are HTML and mention cloudflare rather than a cookie.
        body = '<!DOCTYPE html><title>Just a moment...</title>cloudflare'
        with self.assertRaises(CloudflareError):
            self.cloud._test_response(_response(403, body))

    def test_unrelated_403_still_raises_permission_error(self):
        with self.assertRaises(PermissionError):
            self.cloud._test_response(_response(403, '{"error":"forbidden"}'))

    def test_success_response_does_not_raise(self):
        self.cloud._test_response(_response(200, '{"accessToken":"token"}'))


class TestCsrfTokenFetch(unittest.TestCase):
    """The config flow falls back to code login when the CSRF cookie can't be obtained, so
    every way that fetch can fail must surface as CsrfObtainError (#2187)."""

    def setUp(self):
        self.cloud = BambuCloud("", "", "", "")
        self.cloud._tfaKey = "key"
        self.cloud._post = MagicMock()

    def test_csrf_endpoint_404_raises_csrf_obtain_error(self):
        self.cloud._get = MagicMock(side_effect=PermissionError(404, "<title>404 | Bambu Lab</title>"))

        with self.assertRaises(CsrfObtainError):
            self.cloud._get_authentication_token_with_2fa_code("123456")
        self.cloud._post.assert_not_called()

    def test_response_without_cookie_raises_csrf_obtain_error(self):
        response = MagicMock(status_code=204)
        response.cookies.get.return_value = None
        self.cloud._get = MagicMock(return_value=response)

        with self.assertRaises(CsrfObtainError):
            self.cloud._get_authentication_token_with_2fa_code("123456")

    def test_cloudflare_block_is_not_masked(self):
        self.cloud._get = MagicMock(side_effect=CloudflareError())

        with self.assertRaises(CloudflareError):
            self.cloud._get_authentication_token_with_2fa_code("123456")


if __name__ == '__main__':
    unittest.main()
