from __future__ import annotations

import base64
import json

from curl_cffi import requests

from dataclasses import dataclass

from .const import (
     LOGGER,
     BambuUrl
)

from .utils import get_Url

IMPERSONATE_BROWSER='chrome'

@dataclass
class BambuCloud:
  
    def __init__(self, region: str, email: str, username: str, auth_token: str):
        self._region = region
        self._email = email
        self._username = username
        self._auth_token = auth_token
        self._tfaKey = None

    def _get_headers_with_auth_token(self) -> dict:
        headers = {}
        headers['Authorization'] = f"Bearer {self._auth_token}"
        return headers
    
    def _get_authentication_token(self) -> dict:
        LOGGER.debug("Getting accessToken from Bambu Cloud")

        # First we need to find out how Bambu wants us to login.
        data = {
            "account": self._email,
            "password": self._password,
            "apiError": ""
        }

        response = requests.post(get_Url(BambuUrl.LOGIN, self._region), json=data, impersonate=IMPERSONATE_BROWSER)
        if response.status_code >= 400:
            LOGGER.error(f"Login attempt failed with error code: {response.status_code}")
            LOGGER.debug(f"Response: '{response.text}'")
            raise ValueError(response.status_code)

        LOGGER.debug(f"Response: {response.status_code}")

        auth_json = response.json()
        accessToken = auth_json.get('accessToken', '')
        if accessToken != '':
            # We were provided the accessToken directly.
            return accessToken
        
        loginType = auth_json.get("loginType", None)
        if loginType is None:
            LOGGER.error(f"loginType not present")
            LOGGER.error(f"Response not understood: '{response.text}'")
            return None
        elif loginType == 'verifyCode':
            LOGGER.debug(f"Received verifyCode response")
        elif loginType == 'tfa':
            # Store the tfaKey for later use
            LOGGER.debug(f"Received tfa response")
            self._tfaKey = auth_json.get("tfaKey")
        else:
            LOGGER.debug(f"Did not understand json. loginType = '{loginType}'")
            LOGGER.error(f"Response not understood: '{response.text}'")

        return loginType
    
    def _get_email_verification_code(self):
        # Send the verification code request
        data = {
            "email": self._email,
            "type": "codeLogin"
        }

        LOGGER.debug("Requesting verification code")
        response = requests.post(get_Url(BambuUrl.EMAIL_CODE, self._region), json=data, impersonate=IMPERSONATE_BROWSER)
        
        if response.status_code == 200:
            LOGGER.debug("Verification code requested successfully.")
        else:
            LOGGER.error(f"Received error trying to send verification code: {response.status_code}")
            LOGGER.debug(f"Response: '{response.text}'")
            raise ValueError(response.status_code)

    def _get_authentication_token_with_verification_code(self, code) -> dict:
        LOGGER.debug("Attempting to connect with provided verification code.")
        data = {
            "account": self._email,
            "code": code
        }

        response = requests.post(get_Url(BambuUrl.LOGIN, self._region), json=data, impersonate=IMPERSONATE_BROWSER)

        LOGGER.debug(f"Response: {response.status_code}")
        if response.status_code == 200:
            LOGGER.debug("Authentication successful.")
        elif response.status_code == 400:
            LOGGER.debug(f"Response: '{response.json()}'")
            if response.json()['code'] == 1:
                # Code has expired. Request a new one.
                self._get_email_verification_code()
                return 'codeExpired'
            elif response.json()['code'] == 2:
                # Code was incorrect. Let the user try again.
                return 'codeIncorrect'
            else:
                LOGGER.error(f"Response not understood: '{response.json()}'")
                raise ValueError(response.json()['code'])
        else:
            LOGGER.error(f"Received error trying to authenticate with verification code: {response.status_code}")
            LOGGER.debug(f"Response: '{response.text}'")
            raise ValueError(response.status_code)

        return response.json()['accessToken']
    
    def _get_authentication_token_with_2fa_code(self, code: str) -> dict:
        LOGGER.debug("Attempting to connect with provided 2FA code.")

        data = {
            "tfaKey": self._tfaKey,
            "tfaCode": code
        }

        response = requests.post(get_Url(BambuUrl.TFA_LOGIN, self._region), json=data, impersonate=IMPERSONATE_BROWSER)

        LOGGER.debug(f"Response: {response.status_code}")
        if response.status_code == 200:
            LOGGER.debug("Authentication successful.")
        else:
            LOGGER.error(f"Received error trying to authenticate with verification code: {response.status_code}")
            LOGGER.debug(f"Response: '{response.text}'")
            raise ValueError(response.status_code)

        cookies = response.cookies.get_dict()
        token_from_tfa = cookies.get("token")
        LOGGER.debug(f"token_from_tfa: {token_from_tfa}")

        return token_from_tfa
    
    def _get_username_from_authentication_token(self) -> str:
        # User name is in 2nd portion of the auth token (delimited with periods)
        b64_string = self._auth_token.split(".")[1]
        # String must be multiples of 4 chars in length. For decode pad with = character
        b64_string += "=" * ((4 - len(b64_string) % 4) % 4)
        jsonAuthToken = json.loads(base64.b64decode(b64_string))
        # Gives json payload with "username":"u_<digits>" within it
        return jsonAuthToken['username']
    
    # Retrieves json description of devices in the form:
    # {
    #     'message': 'success',
    #     'code': None,
    #     'error': None,
    #     'devices': [
    #         {
    #             'dev_id': 'REDACTED',
    #             'name': 'Bambu P1S',
    #             'online': True,
    #             'print_status': 'SUCCESS',
    #             'dev_model_name': 'C12',
    #             'dev_product_name': 'P1S',
    #             'dev_access_code': 'REDACTED',
    #             'nozzle_diameter': 0.4
    #             },
    #         {
    #             'dev_id': 'REDACTED',
    #             'name': 'Bambu P1P',
    #             'online': True,
    #             'print_status': 'RUNNING',
    #             'dev_model_name': 'C11',
    #             'dev_product_name': 'P1P',
    #             'dev_access_code': 'REDACTED',
    #             'nozzle_diameter': 0.4
    #             },
    #         {
    #             'dev_id': 'REDACTED',
    #             'name': 'Bambu X1C',
    #             'online': True,
    #             'print_status': 'RUNNING',
    #             'dev_model_name': 'BL-P001',
    #             'dev_product_name': 'X1 Carbon',
    #             'dev_access_code': 'REDACTED',
    #             'nozzle_diameter': 0.4
    #             }
    #     ]
    # }
    
    def test_authentication(self, region: str, email: str, username: str, auth_token: str) -> bool:
        self._region = region
        self._email = email
        self._username = username
        self._auth_token = auth_token
        try:
            self.get_device_list()
        except:
            return False
        return True

    def login(self, region: str, email: str, password: str) -> str:
        self._region = region
        self._email = email
        self._password = password

        result = self._get_authentication_token()
        if result == 'verifyCode':
            return result
        elif result == 'tfa':
            return result
        elif result is None:
            LOGGER.error("Unable to authenticate.")
            return None
        else:
            self._auth_token = result
            self._username = self._get_username_from_authentication_token()
            return 'success'
        
    def login_with_verification_code(self, code: str):
        result = self._get_authentication_token_with_verification_code(code)
        if result == 'codeExpired' or result == 'codeIncorrect':
            return result
        self._auth_token = result
        self._username = self._get_username_from_authentication_token()
        return 'success'

    def login_with_2fa_code(self, code: str):
        result = self._get_authentication_token_with_2fa_code(code)
        self._auth_token = result
        self._username = self._get_username_from_authentication_token()
        return 'success'

    def get_device_list(self) -> dict:
        LOGGER.debug("Getting device list from Bambu Cloud")
        response = requests.get(get_Url(BambuUrl.BIND, self._region), headers=self._get_headers_with_auth_token(), timeout=10, impersonate=IMPERSONATE_BROWSER)
        if response.status_code >= 400:
            LOGGER.debug(f"Received error: {response.status_code}")
            raise ValueError(response.status_code)
        return response.json()['devices']

    # The slicer settings are of the following form:
    #
    # {
    #     "message": "success",
    #     "code": null,
    #     "error": null,
    #     "print": {
    #         "public": [
    #             {
    #                 "setting_id": "GP004",
    #                 "version": "01.09.00.15",
    #                 "name": "0.20mm Standard @BBL X1C",
    #                 "update_time": "2024-07-04 11:27:08",
    #                 "nickname": null
    #             },
    #             ...
    #         }
    #         "private": []
    #     },
    #     "printer": {
    #         "public": [
    #             {
    #                 "setting_id": "GM001",
    #                 "version": "01.09.00.15",
    #                 "name": "Bambu Lab X1 Carbon 0.4 nozzle",
    #                 "update_time": "2024-07-04 11:25:07",
    #                 "nickname": null
    #             },
    #             ...
    #         ],
    #         "private": []
    #     },
    #     "filament": {
    #         "public": [
    #             {
    #                 "setting_id": "GFSA01",
    #                 "version": "01.09.00.15",
    #                 "name": "Bambu PLA Matte @BBL X1C",
    #                 "update_time": "2024-07-04 11:29:21",
    #                 "nickname": null,
    #                 "filament_id": "GFA01"
    #             },
    #             ...
    #         ],
    #         "private": [
    #             {
    #                 "setting_id": "PFUS46ea5c221cabe5",
    #                 "version": "1.9.0.14",
    #                 "name": "Fillamentum PLA Extrafill @Bambu Lab X1 Carbon 0.4 nozzle",
    #                 "update_time": "2024-07-10 06:48:17",
    #                 "base_id": null,
    #                 "filament_id": "Pc628b24",
    #                 "filament_type": "PLA",
    #                 "filament_is_support": "0",
    #                 "nozzle_temperature": [
    #                     190,
    #                     240
    #                 ],
    #                 "nozzle_hrc": "3",
    #                 "filament_vendor": "Fillamentum"
    #             },
    #             ...
    #         ]
    #     },
    #     "settings": {}
    # }

    def get_slicer_settings(self) -> dict:
        LOGGER.debug("Getting slicer settings from Bambu Cloud")
        response = requests.get(get_Url(BambuUrl.SLICER_SETTINGS, self._region), headers=self._get_headers_with_auth_token(), timeout=10, impersonate=IMPERSONATE_BROWSER)
        if response.status_code >= 400:
            LOGGER.error(f"Slicer settings load failed: {response.status_code}")
            LOGGER.error(f"Slicer settings load failed: '{response.text}'")
            return None
        return response.json()
        
    # The task list is of the following form with a 'hits' array with typical 20 entries.
    #
    # "total": 531,
    # "hits": [
    #     {
    #     "id": 35237965,
    #     "designId": 0,
    #     "designTitle": "",
    #     "instanceId": 0,
    #     "modelId": "REDACTED",
    #     "title": "REDACTED",
    #     "cover": "REDACTED",
    #     "status": 4,
    #     "feedbackStatus": 0,
    #     "startTime": "2023-12-21T19:02:16Z",
    #     "endTime": "2023-12-21T19:02:35Z",
    #     "weight": 34.62,
    #     "length": 1161,
    #     "costTime": 10346,
    #     "profileId": 35276233,
    #     "plateIndex": 1,
    #     "plateName": "",
    #     "deviceId": "REDACTED",
    #     "amsDetailMapping": [
    #         {
    #         "ams": 4,
    #         "sourceColor": "F4D976FF",
    #         "targetColor": "F4D976FF",
    #         "filamentId": "GFL99",
    #         "filamentType": "PLA",
    #         "targetFilamentType": "",
    #         "weight": 34.62
    #         }
    #     ],
    #     "mode": "cloud_file",
    #     "isPublicProfile": false,
    #     "isPrintable": true,
    #     "deviceModel": "P1P",
    #     "deviceName": "Bambu P1P",
    #     "bedType": "textured_plate"
    #     },

    def get_tasklist(self) -> dict:
        url = get_Url(BambuUrl.TASKS, self._region)
        response = requests.get(url, headers=self._get_headers_with_auth_token(), timeout=10, impersonate=IMPERSONATE_BROWSER)
        if response.status_code >= 400:
            LOGGER.debug(f"Received error: {response.status_code}")
            LOGGER.debug(f"Received error: '{response.text}'")
            raise ValueError(response.status_code)
        return response.json()
    
    def get_latest_task_for_printer(self, deviceId: str) -> dict:
        LOGGER.debug(f"Getting latest task from Bambu Cloud")
        data = self.get_tasklist_for_printer(deviceId)
        if len(data) != 0:
            return data[0]
        LOGGER.debug("No tasks found for printer")
        return None

    def get_tasklist_for_printer(self, deviceId: str) -> dict:
        LOGGER.debug(f"Getting task list from Bambu Cloud")
        tasks = []
        data = self.get_tasklist()
        for task in data['hits']:
            if task['deviceId'] == deviceId:
                tasks.append(task)
        return tasks

    def get_device_type_from_device_product_name(self, device_product_name: str):
        if device_product_name == "X1 Carbon":
            return "X1C"
        return device_product_name.replace(" ", "")

    def download(self, url: str) -> bytearray:
        LOGGER.debug(f"Downloading cover image: {url}")
        response = requests.get(url, timeout=10, impersonate=IMPERSONATE_BROWSER)
        if response.status_code >= 400:
            LOGGER.debug(f"Received error: {response.status_code}")
            raise ValueError(response.status_code)
        return response.content

    @property
    def username(self):
        return self._username
    
    @property
    def auth_token(self):
        return self._auth_token
    
    @property
    def cloud_mqtt_host(self):
        return "cn.mqtt.bambulab.com" if self._region == "China" else "us.mqtt.bambulab.com"
