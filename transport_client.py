import os

import requests

# Public: https://v6.db.transport.rest
base_url = os.environ.get("TRAIN_INFO_TRANSPORT_BASE_URL")


class TransportClient:
    def get_journey(self, from_latitude: float, from_longitude: float, to_latitude: float, to_longitude: float):
        params = {
            'from.latitude': str(from_latitude),
            'from.longitude': str(from_longitude),
            'to.latitude': str(to_latitude),
            'to.longitude': str(to_longitude),
            'from.address': 'start',
            'to.address': 'stop',
        }

        headers = {
            'Accept': 'application/json',
        }

        result = requests.get(f"{base_url}/journeys", params=params, headers=headers)
        result.raise_for_status()

        return result.json()
