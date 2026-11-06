from fastapi import APIRouter, Depends, Header, HTTPException, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.auth import authenticate_device
from app.database import get_db
from app.models import BusLocation, utcnow
from app.schemas import HeartbeatRequest, HeartbeatResponse, LocationRequest, LocationResponse

router = APIRouter(prefix="/api/device", tags=["Device"])


@router.post("/heartbeat", response_model=HeartbeatResponse)
def heartbeat(
    data: HeartbeatRequest,
    x_api_key: str | None = Header(default=None),
    db: Session = Depends(get_db),
):
    device = authenticate_device(db, data.device_id, x_api_key)
    device.last_heartbeat = utcnow()
    db.commit()
    return HeartbeatResponse(message="Heartbeat received", device_status="online")


@router.post("/location", response_model=LocationResponse)
def update_location(
    data: LocationRequest,
    x_api_key: str | None = Header(default=None),
    db: Session = Depends(get_db),
):
    device = authenticate_device(db, data.device_id, x_api_key)
    bus = device.bus
    if bus is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No bus is linked to this device")

    location = bus.location
    if location is None:
        location = BusLocation(bus=bus)
        db.add(location)
    location.latitude = data.latitude
    location.longitude = data.longitude
    location.speed_kmph = data.speed_kmph
    location.altitude_m = data.altitude_m
    location.satellites = data.satellites
    location.updated_at = utcnow()

    try:
        db.commit()
    except IntegrityError:  # two first-ever location posts raced; the device can simply retry
        db.rollback()
        raise HTTPException(status.HTTP_409_CONFLICT, "Concurrent update, please retry")
    return LocationResponse(message="Location updated successfully")
