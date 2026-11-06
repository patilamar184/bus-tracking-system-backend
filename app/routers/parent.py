from math import asin, cos, radians, sin, sqrt

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Bus, BusStop
from app.schemas import ETAResponse, ParentTrackResponse

router = APIRouter(prefix="/api/parent", tags=["Parent"])

EARTH_RADIUS_KM = 6371.0088


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Straight-line (great-circle) distance between two coordinates in kilometres."""
    dlat = radians(lat2 - lat1)
    dlon = radians(lon2 - lon1)
    a = sin(dlat / 2) ** 2 + cos(radians(lat1)) * cos(radians(lat2)) * sin(dlon / 2) ** 2
    return 2 * EARTH_RADIUS_KM * asin(sqrt(a))


def _get_public_bus(db: Session, public_token: str) -> Bus:
    bus = db.scalar(select(Bus).where(Bus.public_token == public_token))
    if bus is None or not bus.is_active:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Bus not found")
    return bus


@router.get("/track/{public_token}", response_model=ParentTrackResponse)
def track_bus(public_token: str, db: Session = Depends(get_db)):
    return _get_public_bus(db, public_token)


@router.get("/track/{public_token}/eta/{stop_id}", response_model=ETAResponse)
def bus_eta(public_token: str, stop_id: int, db: Session = Depends(get_db)):
    bus = _get_public_bus(db, public_token)

    stop = None
    if bus.route_id is not None:
        stop = db.scalar(
            select(BusStop).where(BusStop.id == stop_id, BusStop.route_id == bus.route_id)
        )
    if stop is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Stop not found on this bus's route")

    location = bus.location
    if location is None:
        return ETAResponse(
            stop_name=stop.stop_name, message="ETA unavailable: no location received yet"
        )

    distance = haversine_km(location.latitude, location.longitude, stop.latitude, stop.longitude)
    distance_km = round(distance, 2)

    if bus.device_status != "online":
        return ETAResponse(
            stop_name=stop.stop_name,
            distance_km=distance_km,
            message="ETA unavailable: bus is offline, last known location may be outdated",
        )
    if not location.speed_kmph or location.speed_kmph <= 0:
        return ETAResponse(
            stop_name=stop.stop_name,
            distance_km=distance_km,
            message="ETA unavailable: bus is not moving",
        )

    return ETAResponse(
        stop_name=stop.stop_name,
        eta_minutes=round(distance / location.speed_kmph * 60),
        distance_km=distance_km,
    )
