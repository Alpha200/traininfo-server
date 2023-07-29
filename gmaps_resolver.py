import re
import requests
import os

gmaps_key = os.environ.get("TRAIN_INFO_GMAPS_KEY")


class GMapsResolver:
    def resolve_url(self, url: str):
        result = requests.get(url, allow_redirects=False)
        location_header = result.headers.get('Location')
        ftid = re.search('0x[0-9a-f]+:(0x[0-9a-f]+)', location_header)

        params = {
            'cid': ftid.group(1),
            'key': gmaps_key
        }

        place_result = requests.get('https://maps.googleapis.com/maps/api/place/details/json', params=params)
        place_result.raise_for_status()
        place_data = place_result.json()
        location = place_data['result']['geometry']['location']
        return location['lat'], location['lng']
