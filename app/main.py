import os
from contextlib import asynccontextmanager

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import select

from app import models  # noqa: F401
from app.auth import hash_password
from app.database import Base, SessionLocal, engine
from app.routers import admin, device, parent

load_dotenv()

def get_cors_origins():
    # Render var CORS_ORIGINS nasel tar "*" mhanje saglyanna allow
    # Asel tar comma ne split karun list banav
    raw = os.getenv("CORS_ORIGINS", "").strip()
    if not raw or raw == "*":
        return ["*"]
    return [o.strip() for o in raw.split(",") if o.strip()]

def create_default_admin() -> None:
    username = os.getenv("ADMIN_USERNAME", "").strip()
    password = os.getenv("ADMIN_PASSWORD", "")
    if not username or not password:
        print("WARNING: ADMIN_USERNAME / ADMIN_PASSWORD not set")
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

app.add_middleware(
    CORSMiddleware,
    allow_origins=get_cors_origins(),
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(admin.router)
app.include_router(device.router)
app.include_router(parent.router)