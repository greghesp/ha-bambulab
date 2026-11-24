import json
import unittest
from unittest.mock import MagicMock

from pybambu.bambu_cloud import (
    BambuCloud,
    BambuUrl,
    CodeRequiredError,
    IncorrectPasswordError,
)

EMAIL = "user@example.com"
PHONE = "13800000000"


def _response(status_code, body):
    response = MagicMock()
    response.status_code = status_code
    response.text = json.dumps(body)
    response.json.return_value = body
    return response


class FakeBambuCloud(BambuCloud):
    """Answers POST requests from a table and records them."""

    def __init__(self, answers):
        super().__init__("", "", "", "")
        self.answers = answers
        self.requests = []

    def _post(self, urlenum, json, headers={}, return400=False):
        self.requests.append((urlenum, json))
        response = self.answers[urlenum]
        self._test_response(response, return400)
        return response

    def _get_username_from_authentication_token(self):
        return "u_1"


class TestLoginWithoutPassword(unittest.TestCase):
    """Accounts made with Google, Apple or Facebook have no Bambu password (#1877)."""

    def test_blank_password_emails_a_code_without_trying_a_password(self):
        cloud = FakeBambuCloud({BambuUrl.EMAIL_CODE: _response(200, {})})

        with self.assertRaises(CodeRequiredError):
            cloud.login("Europe", EMAIL, "")

        self.assertEqual(
            cloud.requests,
            [(BambuUrl.EMAIL_CODE, {"email": EMAIL, "type": "codeLogin"})],
        )

    def test_blank_password_texts_a_code_to_a_phone_account(self):
        cloud = FakeBambuCloud({BambuUrl.SMS_CODE: _response(200, {})})

        with self.assertRaises(CodeRequiredError):
            cloud.login("China", PHONE, "")

        self.assertEqual(
            cloud.requests,
            [(BambuUrl.SMS_CODE, {"phone": PHONE, "type": "codeLogin"})],
        )

    def test_code_completes_the_login(self):
        cloud = FakeBambuCloud({
            BambuUrl.EMAIL_CODE: _response(200, {}),
            BambuUrl.LOGIN: _response(200, {"accessToken": "token"}),
        })
        with self.assertRaises(CodeRequiredError):
            cloud.login("Europe", EMAIL, "")

        cloud.login_with_verification_code("123456")

        self.assertEqual(
            cloud.requests[-1],
            (BambuUrl.LOGIN, {"account": EMAIL, "code": "123456"}),
        )
        self.assertEqual(cloud.auth_token, "token")

    def test_failed_code_request_is_not_reported_as_a_sent_code(self):
        cloud = FakeBambuCloud({BambuUrl.EMAIL_CODE: _response(500, {})})

        with self.assertRaises(PermissionError):
            cloud.login("Europe", EMAIL, "")


class TestIncorrectPassword(unittest.TestCase):

    def test_both_observed_error_codes_raise_incorrect_password(self):
        # Code 2 was reported on #1877, code 1 on #1496.
        for code in (1, 2):
            with self.subTest(code=code):
                cloud = FakeBambuCloud({
                    BambuUrl.LOGIN: _response(400, {"code": code, "error": "Incorrect password"}),
                })
                with self.assertRaises(IncorrectPasswordError):
                    cloud.login("Europe", EMAIL, "wrong")

    def test_other_400_stays_a_permission_error(self):
        cloud = FakeBambuCloud({
            BambuUrl.LOGIN: _response(400, {"code": 7, "error": "Something else"}),
        })
        with self.assertRaises(PermissionError):
            cloud.login("Europe", EMAIL, "password")

    def test_correct_password_still_logs_in(self):
        cloud = FakeBambuCloud({
            BambuUrl.LOGIN: _response(200, {"accessToken": "token"}),
        })

        cloud.login("Europe", EMAIL, "password")

        self.assertEqual(cloud.auth_token, "token")
        self.assertEqual(cloud.requests[0][1]["password"], "password")


if __name__ == "__main__":
    unittest.main()
