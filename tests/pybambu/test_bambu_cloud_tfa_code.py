import unittest
from unittest.mock import MagicMock

from pybambu.bambu_cloud import BambuCloud, CodeIncorrectError


def _response(status_code, text):
    response = MagicMock()
    response.status_code = status_code
    response.text = text
    response.cookies.get_dict.return_value = {"token": "token-from-tfa"}
    return response


class TestTfaCodeResponse(unittest.TestCase):
    """The 2FA endpoint answers a wrong code with a 400 that must not read as a connection failure."""

    def _cloud(self, response):
        cloud = BambuCloud("Europe", "user@example.com", "", "")
        cloud._tfaKey = "key"

        csrf = MagicMock()
        csrf.status_code = 204
        csrf.cookies.get.return_value = "csrf"
        cloud._get = MagicMock(return_value=csrf)

        def post(_url, json=None, headers=None, return400=False):
            cloud._test_response(response, return400)
            return response

        cloud._post = MagicMock(side_effect=post)
        cloud._get_username_from_authentication_token = MagicMock(return_value="user")
        return cloud

    def test_wrong_code_raises_code_incorrect(self):
        cloud = self._cloud(_response(400, '{"code":1,"error":"Incorrect code"}'))
        with self.assertRaises(CodeIncorrectError):
            cloud.login_with_2fa_code("000000")

    def test_other_400_stays_a_permission_error(self):
        cloud = self._cloud(_response(400, '{"code":7,"error":"Something else"}'))
        with self.assertRaises(PermissionError):
            cloud.login_with_2fa_code("000000")

    def test_correct_code_logs_in(self):
        cloud = self._cloud(_response(200, "{}"))
        cloud.login_with_2fa_code("123456")
        self.assertEqual(cloud.auth_token, "token-from-tfa")
