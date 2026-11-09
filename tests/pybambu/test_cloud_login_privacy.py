"""Authentication failures must not log token-bearing server responses."""
import logging
from unittest.mock import MagicMock
import pytest
from pybambu.bambu_cloud import BambuCloud, CodeIncorrectError

SECRET = 'synthetic-secret-not-a-real-token'

@pytest.mark.parametrize('status', [400, 401, 500])
def test_response_and_exception_do_not_include_body(status, caplog):
    cloud = BambuCloud('', '', '', '')
    response = MagicMock(status_code=status, text=SECRET)
    with caplog.at_level(logging.DEBUG), pytest.raises(PermissionError) as error:
        cloud._test_response(response)
    assert SECRET not in caplog.text
    assert SECRET not in str(error.value)


def test_code_rejection_does_not_log_response(caplog):
    cloud = BambuCloud('', '', '', '')
    response = MagicMock(status_code=400)
    response.json.return_value = {'code': 2, 'accessToken': SECRET}
    cloud._post = MagicMock(return_value=response)
    with caplog.at_level(logging.DEBUG), pytest.raises(CodeIncorrectError):
        cloud._get_authentication_token_with_verification_code('123456')
    assert SECRET not in caplog.text
