import os

import requests
from requests.auth import HTTPBasicAuth

base_url = os.environ.get("TRAIN_INFO_TRACCAR_URL")
traccar_username = os.environ.get("TRAIN_INFO_TRACCAR_USERNAME")
traccar_password = os.environ.get("TRAIN_INFO_TRACCAR_PASSWORD")


class TraccarClient:
    def get_device(self, device_id: str):
        params = {
            'id': device_id
        }

        result = requests.get(f"{base_url}/api/devices", params=params, auth=self.get_authentication())
        result.raise_for_status()

        return result.json()

    def get_position(self, position_id: str):
        params = {
            'id': position_id
        }

        result = requests.get(f"{base_url}/api/positions", params=params, auth=self.get_authentication())
        result.raise_for_status()

        return result.json()

    def get_authentication(self):
        return HTTPBasicAuth(username=traccar_username, password=traccar_password)
