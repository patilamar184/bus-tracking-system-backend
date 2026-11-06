import os
from contextlib import asynccontextmanager

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import select

from app import models  # noqa: F401  (registers tables with SQLAlchemy)
from app.auth import hash_password
from app.database import Base, SessionLocal, engine
from app.routers import admin, device, parent

load_dotenv()


def create_default_admin() -> None:
    """Create the admin from .env on first start. An existing admin is never overwritten."""
    username = os.getenv("ADMIN_USERNAME", "").strip()
    password = os.getenv("ADMIN_PASSWORD", "")
    if not username or not password:
        print("WARNING: ADMIN_USERNAME / ADMIN_PASSWORD not set; no default admin created.")
        return
    with SessionLocal() as db:
        if db.scalar(select(models.Admin).where(models.Admin.username == username)) is None:
            db.add(models.Admin(username=username, hashed_password=hash_password(password)))
            db.commit()


@asynccontextmanager
async def lifespan(_app: FastAPI):
    Base.metadata.create_all(bind=engine)
    create_default_admin()
    yield


app = FastAPI(title="School Bus Tracking API", version="1.0.0", lifespan=lifespan)

origins = [
    o.strip()
    for o in os.getenv("CORS_ORIGINS", "http://localhost:5173,http://localhost:3000").split(",")
    if o.strip()
]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(admin.router)
app.include_router(device.router)
app.include_router(parent.router)
