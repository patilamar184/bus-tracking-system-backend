from datetime import datetime, timedelta, timezone

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

ONLINE_WINDOW_SECONDS = 60


def utcnow() -> datetime:
    """Current UTC time as a naive datetime (SQLite does not store time zones)."""
    return datetime.now(timezone.utc).replace(tzinfo=None)


class Admin(Base):
    __tablename__ = "admins"

    id: Mapped[int] = mapped_column(primary_key=True)
    username: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    hashed_password: Mapped[str] = mapped_column(String(128))


class Device(Base):
    __tablename__ = "devices"

    id: Mapped[int] = mapped_column(primary_key=True)
    device_id: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    api_key_hash: Mapped[str] = mapped_column(String(64))
    last_heartbeat: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    bus: Mapped["Bus | None"] = relationship(back_populates="device", uselist=False)

    @property
    def is_online(self) -> bool:
        if self.last_heartbeat is None:
            return False
        return utcnow() - self.last_heartbeat <= timedelta(seconds=ONLINE_WINDOW_SECONDS)

    @property
    def status(self) -> str:
        return "online" if self.is_online else "offline"


class Route(Base):
    __tablename__ = "routes"

    id: Mapped[int] = mapped_column(primary_key=True)
    route_name: Mapped[str] = mapped_column(String(120))
    description: Mapped[str | None] = mapped_column(String(500), nullable=True)

    stops: Mapped[list["BusStop"]] = relationship(
        back_populates="route",
        cascade="all, delete-orphan",
        order_by="BusStop.stop_order",
    )
    # No delete cascade: deleting a route sets its buses' route_id to NULL.
    buses: Mapped[list["Bus"]] = relationship(back_populates="route")

    @property
    def bus_count(self) -> int:
        return len(self.buses)


class BusStop(Base):
    __tablename__ = "bus_stops"

    id: Mapped[int] = mapped_column(primary_key=True)
    route_id: Mapped[int] = mapped_column(ForeignKey("routes.id", ondelete="CASCADE"), index=True)
    stop_name: Mapped[str] = mapped_column(String(120))
    latitude: Mapped[float] = mapped_column(Float)
    longitude: Mapped[float] = mapped_column(Float)
    stop_order: Mapped[int] = mapped_column(Integer)

    route: Mapped["Route"] = relationship(back_populates="stops")


class Bus(Base):
    __tablename__ = "buses"

    id: Mapped[int] = mapped_column(primary_key=True)
    bus_number: Mapped[str] = mapped_column(String(50), unique=True, index=True)
    bus_name: Mapped[str] = mapped_column(String(120))
    device_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("devices.device_id"), unique=True
    )
    route_id: Mapped[int | None] = mapped_column(
        ForeignKey("routes.id", ondelete="SET NULL"), nullable=True, index=True
    )
    public_token: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    device: Mapped["Device"] = relationship(back_populates="bus")
    route: Mapped["Route | None"] = relationship(back_populates="buses")
    location: Mapped["BusLocation | None"] = relationship(
        back_populates="bus", uselist=False, cascade="all, delete-orphan"
    )

    @property
    def device_status(self) -> str:
        return self.device.status if self.device else "offline"

    @property
    def last_heartbeat(self) -> datetime | None:
        return self.device.last_heartbeat if self.device else None

    @property
    def public_tracking_url(self) -> str:
        return f"/track/{self.public_token}"


class BusLocation(Base):
    __tablename__ = "bus_locations"

    id: Mapped[int] = mapped_column(primary_key=True)
    bus_id: Mapped[int] = mapped_column(ForeignKey("buses.id", ondelete="CASCADE"), unique=True)
    latitude: Mapped[float] = mapped_column(Float)
    longitude: Mapped[float] = mapped_column(Float)
    speed_kmph: Mapped[float] = mapped_column(Float, default=0.0)
    altitude_m: Mapped[float | None] = mapped_column(Float, nullable=True)
    satellites: Mapped[int | None] = mapped_column(Integer, nullable=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)

    bus: Mapped["Bus"] = relationship(back_populates="location")
