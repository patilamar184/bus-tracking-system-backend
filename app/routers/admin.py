from datetime import timedelta

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload

from app.auth import (
    create_access_token,
    generate_api_key,
    generate_public_token,
    get_current_admin,
    hash_api_key,
    verify_password,
)
from app.database import get_db
from app.models import ONLINE_WINDOW_SECONDS, Admin, Bus, BusStop, Device, Route, utcnow
from app.schemas import (
    BusCreate,
    BusCreateResponse,
    BusDetail,
    BusListItem,
    BusUpdate,
    DashboardResponse,
    LoginRequest,
    RouteCreate,
    RouteOut,
    RouteUpdate,
    TokenResponse,
)

router = APIRouter(prefix="/api/admin", tags=["Admin"])
secured = [Depends(get_current_admin)]


def _get_bus(db: Session, bus_id: int) -> Bus:
    bus = db.get(Bus, bus_id)
    if bus is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Bus not found")
    return bus


def _get_route(db: Session, route_id: int) -> Route:
    route = db.get(Route, route_id)
    if route is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Route not found")
    return route


# ---------- Authentication ----------
@router.post("/login", response_model=TokenResponse)
def login(data: LoginRequest, db: Session = Depends(get_db)):
    admin = db.scalar(select(Admin).where(Admin.username == data.username))
    if admin is None or not verify_password(data.password, admin.hashed_password):
        raise HTTPException(
            status.HTTP_401_UNAUTHORIZED,
            "Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return TokenResponse(access_token=create_access_token(admin.username))


# ---------- Dashboard ----------
@router.get("/dashboard", response_model=DashboardResponse, dependencies=secured)
def dashboard(db: Session = Depends(get_db)):
    cutoff = utcnow() - timedelta(seconds=ONLINE_WINDOW_SECONDS)
    total_buses = db.scalar(select(func.count(Bus.id))) or 0
    online_buses = (
        db.scalar(
            select(func.count(Bus.id))
            .select_from(Bus)
            .join(Device, Device.device_id == Bus.device_id)
            .where(Device.last_heartbeat >= cutoff)
        )
        or 0
    )
    total_routes = db.scalar(select(func.count(Route.id))) or 0
    return DashboardResponse(
        total_buses=total_buses,
        online_buses=online_buses,
        offline_buses=total_buses - online_buses,
        total_routes=total_routes,
    )


# ---------- Buses ----------
@router.get("/buses", response_model=list[BusListItem], dependencies=secured)
def list_buses(db: Session = Depends(get_db)):
    return db.scalars(select(Bus).options(selectinload(Bus.device)).order_by(Bus.id)).all()


@router.post(
    "/buses",
    response_model=BusCreateResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=secured,
)
def create_bus(data: BusCreate, db: Session = Depends(get_db)):
    if db.scalar(select(Bus.id).where(Bus.bus_number == data.bus_number)):
        raise HTTPException(status.HTTP_409_CONFLICT, "Bus number already exists")
    if db.scalar(select(Device.id).where(Device.device_id == data.device_id)):
        raise HTTPException(status.HTTP_409_CONFLICT, "Device ID already exists")

    api_key = generate_api_key()
    token = generate_public_token()
    while db.scalar(select(Bus.id).where(Bus.public_token == token)):
        token = generate_public_token()

    bus = Bus(
        bus_number=data.bus_number,
        bus_name=data.bus_name,
        public_token=token,
        device=Device(device_id=data.device_id, api_key_hash=hash_api_key(api_key)),
    )
    db.add(bus)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status.HTTP_409_CONFLICT, "Bus number or device ID already exists")

    return BusCreateResponse(
        id=bus.id,
        bus_number=bus.bus_number,
        bus_name=bus.bus_name,
        device_id=bus.device_id,
        public_token=bus.public_token,
        public_tracking_url=bus.public_tracking_url,
        device_api_key=api_key,
    )


@router.get("/buses/{bus_id}", response_model=BusDetail, dependencies=secured)
def get_bus(bus_id: int, db: Session = Depends(get_db)):
    return _get_bus(db, bus_id)


@router.put("/buses/{bus_id}", response_model=BusDetail, dependencies=secured)
def update_bus(bus_id: int, data: BusUpdate, db: Session = Depends(get_db)):
    bus = _get_bus(db, bus_id)
    if data.bus_name is not None:
        bus.bus_name = data.bus_name
    if "route_id" in data.model_fields_set:
        bus.route = None if data.route_id is None else _get_route(db, data.route_id)
    db.commit()
    return bus


@router.delete("/buses/{bus_id}", status_code=status.HTTP_204_NO_CONTENT, dependencies=secured)
def delete_bus(bus_id: int, db: Session = Depends(get_db)):
    bus = _get_bus(db, bus_id)
    device = bus.device
    # Deleting the bus also deletes its latest location (cascade). Its device record
    # exists only for this bus, so it is removed too; the route is left untouched.
    db.delete(bus)
    if device is not None:
        db.delete(device)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# ---------- Routes ----------
@router.get("/routes", response_model=list[RouteOut], dependencies=secured)
def list_routes(db: Session = Depends(get_db)):
    return db.scalars(
        select(Route).options(selectinload(Route.stops), selectinload(Route.buses)).order_by(Route.id)
    ).all()


@router.post(
    "/routes", response_model=RouteOut, status_code=status.HTTP_201_CREATED, dependencies=secured
)
def create_route(data: RouteCreate, db: Session = Depends(get_db)):
    route = Route(
        route_name=data.route_name,
        description=data.description,
        stops=[BusStop(**stop.model_dump()) for stop in data.stops],
    )
    db.add(route)
    db.commit()
    return route


@router.put("/routes/{route_id}", response_model=RouteOut, dependencies=secured)
def update_route(route_id: int, data: RouteUpdate, db: Session = Depends(get_db)):
    route = _get_route(db, route_id)
    if data.route_name is not None:
        route.route_name = data.route_name
    if "description" in data.model_fields_set:
        route.description = data.description
    if data.stops is not None:
        # Replace the whole ordered stops list (old stops are deleted as orphans).
        route.stops = [BusStop(**stop.model_dump()) for stop in data.stops]
    db.commit()
    return route


@router.delete("/routes/{route_id}", status_code=status.HTTP_204_NO_CONTENT, dependencies=secured)
def delete_route(route_id: int, db: Session = Depends(get_db)):
    route = _get_route(db, route_id)
    db.delete(route)  # stops are deleted; assigned buses get route_id = NULL
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
