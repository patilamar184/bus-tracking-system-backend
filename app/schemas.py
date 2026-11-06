from datetime import datetime, timezone
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, PlainSerializer, field_validator

Latitude = Annotated[float, Field(ge=-90, le=90)]
Longitude = Annotated[float, Field(ge=-180, le=180)]


def _utc_iso(value: datetime) -> str:
    """Serialize datetimes as UTC ISO strings ending in 'Z' so browsers parse them correctly."""
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


UTCDatetime = Annotated[datetime, PlainSerializer(_utc_iso, return_type=str, when_used="json")]


class InputModel(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)


class OutputModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


# ---------- Auth ----------
class LoginRequest(InputModel):
    username: str = Field(min_length=1, max_length=64)
    password: str = Field(min_length=1, max_length=72)


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class DashboardResponse(BaseModel):
    total_buses: int
    online_buses: int
    offline_buses: int
    total_routes: int


# ---------- Stops & routes ----------
class StopIn(InputModel):
    stop_name: str = Field(min_length=1, max_length=120)
    latitude: Latitude
    longitude: Longitude
    stop_order: int = Field(ge=1)


class StopOut(OutputModel):
    id: int
    stop_name: str
    latitude: float
    longitude: float
    stop_order: int


def _unique_orders(stops: list[StopIn] | None) -> list[StopIn] | None:
    if stops is not None:
        orders = [s.stop_order for s in stops]
        if len(orders) != len(set(orders)):
            raise ValueError("stop_order values must be unique within a route")
    return stops


class RouteCreate(InputModel):
    route_name: str = Field(min_length=1, max_length=120)
    description: str | None = Field(default=None, max_length=500)
    stops: list[StopIn] = []

    _check_orders = field_validator("stops")(_unique_orders)


class RouteUpdate(InputModel):
    route_name: str | None = Field(default=None, min_length=1, max_length=120)
    description: str | None = Field(default=None, max_length=500)
    stops: list[StopIn] | None = None

    _check_orders = field_validator("stops")(_unique_orders)


class RouteOut(OutputModel):
    id: int
    route_name: str
    description: str | None
    bus_count: int
    stops: list[StopOut]


# ---------- Buses ----------
class BusCreate(InputModel):
    bus_number: str = Field(min_length=1, max_length=50)
    bus_name: str = Field(min_length=1, max_length=120)
    device_id: str = Field(min_length=1, max_length=64)


class BusCreateResponse(BaseModel):
    id: int
    bus_number: str
    bus_name: str
    device_id: str
    public_token: str
    public_tracking_url: str
    device_api_key: str  # shown only once, at creation; only its hash is stored


class BusUpdate(InputModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")  # rejects device_id

    bus_name: str | None = Field(default=None, min_length=1, max_length=120)
    route_id: int | None = None  # send null to unassign the route


class BusListItem(OutputModel):
    id: int
    bus_number: str
    bus_name: str
    device_id: str
    route_id: int | None
    device_status: str
    last_heartbeat: UTCDatetime | None
    public_tracking_url: str


class LocationOut(OutputModel):
    latitude: float
    longitude: float
    speed_kmph: float
    altitude_m: float | None
    satellites: int | None
    updated_at: UTCDatetime


class BusDetail(OutputModel):
    id: int
    bus_number: str
    bus_name: str
    device_id: str
    is_active: bool
    device_status: str
    last_heartbeat: UTCDatetime | None
    public_token: str
    public_tracking_url: str
    route: RouteOut | None
    location: LocationOut | None


# ---------- Device ----------
class HeartbeatRequest(InputModel):
    device_id: str = Field(min_length=1, max_length=64)


class HeartbeatResponse(BaseModel):
    message: str
    device_status: str


class LocationRequest(InputModel):
    device_id: str = Field(min_length=1, max_length=64)
    latitude: Latitude
    longitude: Longitude
    speed_kmph: float = Field(ge=0, le=400)
    altitude_m: float | None = Field(default=None, ge=-500, le=100000)
    satellites: int | None = Field(default=None, ge=0, le=100)


class LocationResponse(BaseModel):
    message: str


# ---------- Parent ----------
class ParentLocation(OutputModel):
    latitude: float
    longitude: float
    speed_kmph: float
    updated_at: UTCDatetime


class ParentRoute(OutputModel):
    route_name: str
    stops: list[StopOut]


class ParentTrackResponse(OutputModel):
    bus_number: str
    bus_name: str
    route: ParentRoute | None
    location: ParentLocation | None
    device_status: str


class ETAResponse(BaseModel):
    stop_name: str
    eta_minutes: int | None = None
    distance_km: float | None = None
    message: str | None = None  # explains why the ETA is unavailable
