import datetime
import logging
import os
from typing import Annotated, Union, Tuple

from fastapi import FastAPI, Header, HTTPException
from geopy import distance
from pydantic import BaseModel

from traccar_client import TraccarClient
from transport_client import TransportClient


class JourneyStop(BaseModel):
    latitude: float
    longitude: float


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

api_token = os.environ.get("TRAIN_INFO_API_TOKEN")
traccar_device = os.environ.get("TRAIN_INFO_TRACCAR_DEVICE")
home_latitude, home_longitude = os.environ.get("TRAIN_INFO_HOME_POSITION").split(';')
default_to_latitude, default_to_longitude = os.environ.get("TRAIN_INFO_DEFAULT_TO_POSITION").split(';')

app = FastAPI()

current_journey_stop: JourneyStop
special_journey_stop = False

traccar_client = TraccarClient()
transport_client = TransportClient()


@app.get("/journey/info")
async def get_info(authorization: Annotated[Union[str, None], Header()] = None):
    validate_authorization(authorization)

    current_latitude, current_longitude = get_traccar_position()

    if special_journey_stop:
        logger.info("Using special journey stop")
        to_latitude = current_journey_stop.latitude
        to_longitude = current_journey_stop.longitude
    elif is_in_home_zone((current_latitude, current_longitude)):
        logger.info("Using default to position")
        to_latitude = default_to_latitude
        to_longitude = default_to_longitude
    else:
        logger.info("Using home position")
        to_latitude = home_latitude
        to_longitude = home_longitude

    journeys = transport_client.get_journey(
        current_latitude,
        current_longitude,
        to_latitude,
        to_longitude,
    )

    if 'journeys' in journeys and len(journeys['journeys']) > 0:
        selected_journey = journeys['journeys'][0]['legs']
        part = next((part for part in selected_journey if 'walking' not in part or not part['walking']), None)

        if part is not None:

            parsed_departure = datetime.datetime.fromisoformat(part['departure'])
            formatted_departure = parsed_departure.strftime('%H:%M')

            return {
                'line': part['line']['name'],
                'from': part['origin']['name'],
                'to': part['direction'],
                'delay': part['departureDelay'] / 60,
                'platform': part['departurePlatform'],
                'departure': formatted_departure,
            }

    raise HTTPException(status_code=404, detail="Could not find good journey")


@app.post("/journey/to")
async def set_journey_to(journey_stop: JourneyStop, authorization: Annotated[Union[str, None], Header()] = None):
    global current_journey_stop, special_journey_stop
    validate_authorization(authorization)
    current_journey_stop = journey_stop
    special_journey_stop = True
    return {}


def validate_authorization(token):
    if token != f"Bearer {api_token}":
        raise HTTPException(status_code=401, detail="Unauthorized")


def get_traccar_position():
    device = traccar_client.get_device(traccar_device)[0]
    position = traccar_client.get_position(device['positionId'])[0]
    return position['latitude'], position['longitude']


def is_in_home_zone(position: Tuple[float, float]) -> bool:
    return distance.distance((home_latitude, home_longitude), position).m < 500
