from __future__ import annotations

import base64
import json
import requests

from dataclasses import dataclass

from .const import LOGGER

@dataclass
class BambuCloud:
  
    def __init__(self):
        self._email = ""    

    def _get_authentication_token(self) -> dict:
        LOGGER.debug("Getting accessToken from Bambu Cloud")
        url = 'https://api.bambulab.com/v1/user-service/user/login'
        data = {'account': self._email, 'password': self._password}
        LOGGER.debug(f"Data = {data}")
        response = requests.post(url, json=data, timeout=10)
        if not response.ok:
            LOGGER.debug(f"Received error: {response.status_code}")
            raise ValueError(response.status_code)
        LOGGER.debug(f"Success: {response.json()}")
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

    def _test_authentication_token(self) -> dict:
        LOGGER.debug("Getting accessToken from Bambu Cloud")
        url = 'https://api.bambulab.com/v1/user-service/user/login'
        headers = {'Authorization': 'Bearer ' + self._auth_token}
        response = requests.get(url, headers=headers, timeout=10)
        if not response.ok:
            LOGGER.debug(f"Received error: {response.status_code}")
            raise ValueError(response.status_code)
        LOGGER.debug(f"Success: {response.json()}")

    def TestAuthentication(self, email: str, username: str, auth_token: str) -> bool:
        self._email = email
        self._username = username
        self._auth_token = auth_token
        try:
            self.GetDeviceList()
        except:
            return False
        return True

    def Login(self, email: str, password: str):
        self._email = email
        self._password = password

        self._auth_token = self._get_authentication_token()
        self._username = self._get_username_from_authentication_token()

    def GetDeviceList(self) -> dict:
        LOGGER.debug("Getting device list from Bambu Cloud")
        url = 'https://api.bambulab.com/v1/iot-service/api/user/bind'
        headers = {'Authorization': 'Bearer ' + self._auth_token}
        response = requests.get(url, headers=headers, timeout=10)
        if not response.ok:
            LOGGER.debug(f"Received error: {response.status_code}")
            raise ValueError(response.status_code)
        LOGGER.debug(f"Success: {response.json()}")
        return response.json()['devices']

    def GetTaskList(self) -> dict:
        LOGGER.debug("Getting task list from Bambu Cloud")
        url = 'https://api.bambulab.com/v1/user-service/my/tasks'
        headers = {'Authorization': 'Bearer ' + self._auth_token}
        response = requests.get(url, headers=headers, timeout=10)
        if not response.ok:
            LOGGER.debug(f"Received error: {response.status_code}")
            raise ValueError(response.status_code)
        #LOGGER.debug(f"Success: {response.json()}")
        return response.json()
    
    def GetTaskListForPrinter(self, deviceId: str) -> dict:
        LOGGER.debug(f"Getting task list from Bambu Cloud for Printer: {deviceId}")
        data = self.GetTaskList()
        for task in data['hits']:
            if task['deviceId'] == deviceId:
                LOGGER.debug(f"TASK: {task}")
                return task
        return {}

    def GetDeviceTypeFromDeviceProductName(self, device_product_name: str):
        match device_product_name:
            case "X1E":
                return "X1E"
            case "X1 Carbon":
                return "X1C"
            case "X1":
                return "X1"
            case "P1P":
                return "P1P"
            case "P1S":
                return "P1S"
            case "A1":
                return "A1"
            case "A1 Mini":
                return "A1Mini"
            case _:
                return "New"

    @property
    def username(self):
        return self._username
    
    @property
    def auth_token(self):
        return self._auth_token