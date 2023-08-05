import datetime
import logging
import os
from threading import Timer
from typing import Annotated, Union, Tuple, Optional

from fastapi import FastAPI, Header, HTTPException, Body
from geopy import distance
from pydantic import BaseModel

from gmaps_resolver import GMapsResolver
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

current_journey_stop: Optional[JourneyStop] = None
reset_destination_timer: Optional[Timer] = None

traccar_client = TraccarClient()
transport_client = TransportClient()


@app.get("/journey/info")
async def get_info(authorization: Annotated[Union[str, None], Header()] = None):
    validate_authorization(authorization)

    journeys = get_journey_list_for_current_destination()

    if 'journeys' in journeys and len(journeys['journeys']) > 0:
        selected_journey = journeys['journeys'][0]['legs']
        part = next((part for part in selected_journey if 'walking' not in part or not part['walking']), None)

        if part is not None:
            parsed_departure = datetime.datetime.fromisoformat(part['plannedDeparture'])
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


def convert_date_to_timestamp(date: str):
    date = datetime.datetime.fromisoformat(date)
    return int(date.timestamp())


@app.get("/journey/details")
async def get_info(authorization: Annotated[Union[str, None], Header()] = None):
    validate_authorization(authorization)

    journeys = get_journey_list_for_current_destination()

    def map_trip(trip):
        from_name = trip['origin']['name'] if 'name' in trip['origin'] else None
        to_name = trip['destination']['name'] if 'name' in trip['destination'] else None

        return {
            'departure': convert_date_to_timestamp(trip['departure']),
            'departureDelay': int(trip['departureDelay'] / 60) if trip['departureDelay'] is not None else None,
            'departurePlatform': trip.get('departurePlatform', None),
            'arrival': convert_date_to_timestamp(trip['arrival']),
            'arrivalDelay': int(trip['arrivalDelay'] / 60) if trip['arrivalDelay'] is not None else None,
            'arrivalPlatform': trip.get('arrivalPlatform', None),
            'direction': trip.get('direction', None),
            'walking': 'walking' in trip and trip['walking'],
            'distance': trip.get('distance', None),
            'line': trip['line']['name'] if 'line' in trip else None,
            'from': from_name,
            'to': to_name
        }

    def map_journey(journey):
        return {
            'refresh_token': journey['refreshToken'],
            'trips': [map_trip(trip) for trip in journey['legs']]
        }

    if 'journeys' in journeys:
        return [map_journey(journey) for journey in journeys['journeys']]

    return []


def get_journey_list_for_current_destination():
    current_latitude, current_longitude = get_traccar_position()
    to_latitude, to_longitude = get_journey_destination(current_latitude, current_longitude)
    journeys = transport_client.get_journey(
        current_latitude,
        current_longitude,
        to_latitude,
        to_longitude,
    )
    return journeys


def get_journey_destination(current_latitude, current_longitude):
    if current_journey_stop is not None:
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
    return to_latitude, to_longitude


@app.post("/journey/destination")
async def set_journey_destination(journey_stop: JourneyStop, authorization: Annotated[Union[str, None], Header()] = None):
    validate_authorization(authorization)
    set_current_destination(journey_stop)
    return {}


@app.post("/journey/destination/gmaps")
async def set_journey_destination(body: Annotated[str, Body(..., media_type="plain/text")], authorization: Annotated[Union[str, None], Header()] = None):
    validate_authorization(authorization)

    if body is None or not body.startswith('https://maps.app.goo.gl'):
        raise HTTPException(status_code=400, detail="Invalid gmaps link")

    resolver = GMapsResolver()
    lat, lng = resolver.resolve_url(body)
    journey_stop = JourneyStop(latitude=lat, longitude=lng)
    set_current_destination(journey_stop)

    return {'lat': lat, 'lng': lng}


def validate_authorization(token):
    if token != f"Bearer {api_token}":
        raise HTTPException(status_code=401, detail="Unauthorized")


def get_traccar_position():
    device = traccar_client.get_device(traccar_device)[0]
    position = traccar_client.get_position(device['positionId'])[0]
    return position['latitude'], position['longitude']


def is_in_home_zone(position: Tuple[float, float]) -> bool:
    return distance.distance((home_latitude, home_longitude), position).m < 500


def reset_destination():
    global current_journey_stop, reset_destination_timer
    logger.info("Special journey stop has been reset")
    current_journey_stop = None
    reset_destination_timer = None


def set_current_destination(journey_stop: JourneyStop):
    global current_journey_stop, reset_destination_timer

    current_journey_stop = journey_stop

    logger.info(f"Special journey stop set to {current_journey_stop.latitude},{current_journey_stop.longitude}")

    if reset_destination_timer is not None:
        reset_destination_timer.cancel()

    reset_destination_timer = Timer(3600.0, reset_destination)
    reset_destination_timer.start()
