from __future__ import annotations

import base64
import json
import requests

from dataclasses import dataclass

from .const import LOGGER

@dataclass
class BambuCloud:
  
    def __init__(self, region: str, email: str, username: str, auth_token: str):
        self._region = region
        self._email = email
        self._username = username
        self._auth_token = auth_token

    def _get_authentication_token(self) -> dict:
        LOGGER.debug("Getting accessToken from Bambu Cloud")
        if self._region == "China":
            url = 'https://api.bambulab.cn/v1/user-service/user/login'
        else:
            url = 'https://api.bambulab.com/v1/user-service/user/login'
        data = {'account': self._email, 'password': self._password}
        LOGGER.debug(f"Data = {data}")
        response = requests.post(url, json=data, timeout=10)
        if not response.ok:
            LOGGER.debug(f"Received error: {response.status_code}")
            raise ValueError(response.status_code)
        return response.json()['accessToken']

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

    def login(self, region: str, email: str, password: str):
        self._region = region
        self._email = email
        self._password = password

        self._auth_token = self._get_authentication_token()
        self._username = self._get_username_from_authentication_token()

    def get_device_list(self) -> dict:
        LOGGER.debug("Getting device list from Bambu Cloud")
        if self._region == "China":
            url = 'https://api.bambulab.cn/v1/iot-service/api/user/bind'
        else:
            url = 'https://api.bambulab.com/v1/iot-service/api/user/bind'
        headers = {'Authorization': 'Bearer ' + self._auth_token}
        response = requests.get(url, headers=headers, timeout=10)
        if not response.ok:
            LOGGER.debug(f"Received error: {response.status_code}")
            raise ValueError(response.status_code)
        #LOGGER.debug(f"DEVICE LIST: {response.json()}")
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
        if self._region == "China":
            url = 'https://api.bambulab.cn/v1/iot-service/api/slicer/setting?version=undefined'
        else:
            url = 'https://api.bambulab.com/v1/iot-service/api/slicer/setting?version=undefined'
        headers = {'Authorization': 'Bearer ' + self._auth_token}
        response = requests.get(url, headers=headers, timeout=10)
        if not response.ok:
            LOGGER.debug(f"Received error: {response.status_code}")
            raise ValueError(response.status_code)
        #LOGGER.debug(f"SLICER SETTINGS: {response.json()}")
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
        if self._region == "China":
            url = 'https://api.bambulab.cn/v1/user-service/my/tasks'
        else:
            url = 'https://api.bambulab.com/v1/user-service/my/tasks'
        headers = {'Authorization': 'Bearer ' + self._auth_token}
        response = requests.get(url, headers=headers, timeout=10)
        if not response.ok:
            LOGGER.debug(f"Received error: {response.status_code}")
            raise ValueError(response.status_code)
        return response.json()
    
    def get_latest_task_for_printer(self, deviceId: str) -> dict:
        LOGGER.debug(f"Getting latest task from Bambu Cloud for Printer: {deviceId}")
        data = self.get_tasklist_for_printer(deviceId)
        if len(data) != 0:
            return data[0]
        LOGGER.debug("No tasks found for printer")
        return None

    def get_tasklist_for_printer(self, deviceId: str) -> dict:
        LOGGER.debug(f"Getting task list from Bambu Cloud for Printer: {deviceId}")
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
        response = requests.get(url,  timeout=10)
        if not response.ok:
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
